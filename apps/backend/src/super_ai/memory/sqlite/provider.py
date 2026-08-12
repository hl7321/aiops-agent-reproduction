"""FastAPI lifespan 与每请求事务 session provider。"""

from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite.runtime import PersistenceRuntime, transaction_scope

PersistenceLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_persistence_lifespan(settings: DatabaseSettings) -> PersistenceLifespan:
    """返回进入时创建、退出时释放 runtime 的 FastAPI lifespan。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        runtime = PersistenceRuntime.start(settings)
        app.state.persistence_runtime = runtime
        try:
            yield
        finally:
            delattr(app.state, "persistence_runtime")
            await runtime.close()

    return lifespan


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """从 lifespan runtime 为当前请求提供一个事务 session。"""
    runtime = getattr(request.app.state, "persistence_runtime", None)
    if not isinstance(runtime, PersistenceRuntime):
        raise RuntimeError("FastAPI persistence runtime 尚未启动")
    async with transaction_scope(runtime.session_factory) as session:
        yield session
