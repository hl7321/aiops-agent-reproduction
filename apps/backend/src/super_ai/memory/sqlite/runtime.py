"""显式创建和释放的 SQLAlchemy async runtime。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite.paths import ensure_sqlite_parent_directory

SessionFactory = async_sessionmaker[AsyncSession]


def create_sqlite_engine(settings: DatabaseSettings) -> AsyncEngine:
    """显式创建 aiosqlite engine，并启用 SQLite 外键约束。"""
    url = make_url(settings.url)
    if url.drivername != "sqlite+aiosqlite":
        raise ValueError("SQLite persistence 要求 sqlite+aiosqlite 数据库 URL")
    ensure_sqlite_parent_directory(settings.url)
    engine = create_async_engine(settings.url, echo=settings.echo, pool_pre_ping=True)
    event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    """为给定 engine 创建不自动过期的 async session factory。"""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def transaction_scope(factory: SessionFactory) -> AsyncGenerator[AsyncSession, None]:
    """每次创建独立 session；正常提交、异常回滚并始终关闭。"""
    async with factory() as session:
        async with session.begin():
            yield session


class PersistenceRuntime:
    """持有 engine/session factory 的显式生命周期对象。"""

    def __init__(self, engine: AsyncEngine, session_factory: SessionFactory) -> None:
        self._engine: AsyncEngine | None = engine
        self._session_factory: SessionFactory | None = session_factory

    @classmethod
    def start(cls, settings: DatabaseSettings) -> PersistenceRuntime:
        engine = create_sqlite_engine(settings)
        return cls(engine, create_session_factory(engine))

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("持久化 runtime 已关闭")
        return self._engine

    @property
    def session_factory(self) -> SessionFactory:
        if self._session_factory is None:
            raise RuntimeError("持久化 runtime 已关闭")
        return self._session_factory

    async def close(self) -> None:
        """幂等释放连接池并使 session provider 失效。"""
        engine = self._engine
        self._engine = None
        self._session_factory = None
        if engine is not None:
            await engine.dispose()


def _enable_sqlite_foreign_keys(
    connection: DBAPIConnection,
    _record: ConnectionPoolEntry,
) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
