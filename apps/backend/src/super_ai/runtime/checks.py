"""可注入的 SQLite、Milvus、Qwen 与 MCP 真实最小检查。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Protocol

from sqlalchemy import text

from super_ai.llm.config import LlmSettings
from super_ai.llm.provider import QwenOpenAIProvider
from super_ai.mcp_connections.gateway import LangChainMcpClientFactory, LangChainMcpToolGateway
from super_ai.mcp_connections.models import McpConnectionTarget
from super_ai.mcp_connections.settings import ClsMcpServerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite.runtime import create_sqlite_engine
from super_ai.runtime.models import (
    RuntimeDependencies,
    RuntimeDependencyName,
    RuntimeDependencyResult,
)
from super_ai.runtime.security import redact_text
from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.config import VectorStoreSettings


class RuntimeChecks(Protocol):
    async def run(self) -> RuntimeDependencies: ...

    async def run_mcp(self) -> RuntimeDependencyResult: ...


class ConfiguredRuntimeChecks:
    def __init__(
        self,
        database: DatabaseSettings,
        llm: LlmSettings,
        vector_store: VectorStoreSettings,
        mcp: ClsMcpServerSettings,
    ) -> None:
        self._database = database
        self._llm = llm
        self._vector_store = vector_store
        self._mcp = mcp

    async def run(self) -> RuntimeDependencies:
        sqlite, milvus, qwen, mcp = await asyncio.gather(
            self._timed("sqlite", self._check_sqlite),
            self._timed("milvus", self._check_milvus),
            self._timed("qwen", self._check_qwen),
            self.run_mcp(),
        )
        return RuntimeDependencies(sqlite=sqlite, milvus=milvus, qwen=qwen, mcp=mcp)

    async def run_mcp(self) -> RuntimeDependencyResult:
        return await self._timed("mcp", self._check_mcp)

    async def _timed(
        self,
        name: RuntimeDependencyName,
        check: Callable[[], Awaitable[None]],
    ) -> RuntimeDependencyResult:
        started = perf_counter()
        try:
            await check()
        except Exception as error:
            return RuntimeDependencyResult(
                name=name,
                status="unavailable",
                latencyMs=(perf_counter() - started) * 1000,
                error=redact_text(str(error)) or "依赖不可用",
            )
        return RuntimeDependencyResult(
            name=name,
            status="ready",
            latencyMs=(perf_counter() - started) * 1000,
            error=None,
        )

    async def _check_sqlite(self) -> None:
        engine = create_sqlite_engine(self._database)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    async def _check_milvus(self) -> None:
        store = MilvusVectorStore(self._vector_store)
        await store.connect()
        await store.health()

    async def _check_qwen(self) -> None:
        await QwenOpenAIProvider(self._llm).readiness("chat")

    async def _check_mcp(self) -> None:
        if not self._mcp.base_url:
            raise RuntimeError("MCP 回退连接未配置")
        target = McpConnectionTarget(
            "cls-readiness",
            "cls-readiness",
            self._mcp.transport,
            self._mcp.base_url,
            self._mcp.timeout_seconds,
            self._mcp.retries,
        )
        gateway = LangChainMcpToolGateway(LangChainMcpClientFactory())
        await gateway.discover((target,), builtin_tool_names=frozenset())
