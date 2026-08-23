from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.tools import BaseTool

from super_ai.api_responses import AppError
from super_ai.mcp_connections.models import McpConnectionTarget
from super_ai.runtime.logging import log_lifecycle


class McpClient(Protocol):
    async def get_tools(self, *, server_name: str | None = None) -> list[BaseTool]: ...


class McpClientFactory(Protocol):
    def create(self, target: McpConnectionTarget) -> McpClient: ...


class McpToolGateway(Protocol):
    async def discover(
        self,
        targets: Sequence[McpConnectionTarget],
        *,
        builtin_tool_names: frozenset[str],
    ) -> McpToolSet: ...


class LangChainMcpClientFactory:
    """只在显式 create 时构造官方 adapter client。"""

    def create(self, target: McpConnectionTarget) -> McpClient:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        connection: dict[str, Any] = {
            "transport": target.transport,
            "url": target.url,
            "timeout": float(target.timeout_seconds),
            "sse_read_timeout": float(target.timeout_seconds),
        }
        return MultiServerMCPClient(
            {target.name: cast(Any, connection)},
            tool_name_prefix=False,
            handle_tool_errors=False,
        )


@dataclass(frozen=True, slots=True)
class McpToolSet:
    tools: tuple[BaseTool, ...]
    mcp_tool_names: frozenset[str]


Sleep = Callable[[float], Awaitable[None]]


class LangChainMcpToolGateway:
    def __init__(
        self,
        factory: McpClientFactory,
        *,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._factory = factory
        self._sleep = sleep

    async def discover(
        self,
        targets: Sequence[McpConnectionTarget],
        *,
        builtin_tool_names: frozenset[str],
    ) -> McpToolSet:
        if not targets:
            return McpToolSet((), frozenset())
        discovered = await asyncio.gather(*(self._discover_target(target) for target in targets))
        tools: list[BaseTool] = []
        names = set(builtin_tool_names)
        mcp_names: set[str] = set()
        for server_tools in discovered:
            for discovered_tool in server_tools:
                if discovered_tool.name in names:
                    raise AppError(
                        "BUSINESS_MCP_TOOL_NAME_CONFLICT",
                        details={"toolName": discovered_tool.name},
                    )
                names.add(discovered_tool.name)
                mcp_names.add(discovered_tool.name)
                tools.append(discovered_tool)
        return McpToolSet(tuple(tools), frozenset(mcp_names))

    async def _discover_target(self, target: McpConnectionTarget) -> list[BaseTool]:
        log_lifecycle("mcp.discovery", resource_id=target.id, status="running")
        client = self._factory.create(target)
        for attempt in range(target.retries + 1):
            try:
                tools = await asyncio.wait_for(
                    client.get_tools(server_name=target.name),
                    timeout=target.timeout_seconds,
                )
                log_lifecycle("mcp.discovery", resource_id=target.id, status="succeeded")
                return tools
            except Exception as error:
                if attempt >= target.retries:
                    log_lifecycle(
                        "mcp.discovery",
                        resource_id=target.id,
                        status="failed",
                        category=type(error).__name__,
                    )
                    raise AppError("SYSTEM_MCP_CONNECTION_FAILED") from error
                await self._sleep(min(0.1 * (2**attempt), 1.0))
        raise AssertionError("unreachable")
