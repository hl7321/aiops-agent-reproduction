"""SQLAlchemy async runtime 与事务约定测试。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import (
    Base,
    CanonicalJson,
    PersistenceRuntime,
    UTCDateTime,
    create_sqlite_engine,
    transaction_scope,
)


class _TestBase(DeclarativeBase):
    pass


class _RuntimeRow(_TestBase):
    __tablename__ = "runtime_rows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[object] = mapped_column(CanonicalJson())
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())


@pytest.fixture
async def runtime(sqlite_database_url: str) -> AsyncIterator[PersistenceRuntime]:
    value = PersistenceRuntime.start(DatabaseSettings(url=sqlite_database_url))
    async with value.engine.begin() as connection:
        await connection.run_sync(_TestBase.metadata.create_all)
    try:
        yield value
    finally:
        await value.close()


def test_product_base_registers_only_current_domain_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "auth_sessions",
        "background_jobs",
        "background_job_events",
        "knowledge_documents",
        "document_index_tasks",
        "chat_sessions",
        "chat_messages",
        "agent_tool_call_audits",
        "user_chat_configurations",
        "user_chat_prompts",
        "user_chat_skills",
        "mcp_connections",
        "diagnostic_tasks",
        "diagnostic_steps",
        "diagnostic_evidence",
        "diagnostic_reports",
        "report_evidence_links",
        "graph_checkpoints",
            "aiops_diagnostic_cases",
            "user_feedback",
        }


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///sync.sqlite3",
        "postgresql+asyncpg://localhost/database",
    ],
)
def test_sqlite_engine_rejects_non_aiosqlite_driver(url: str) -> None:
    with pytest.raises(ValueError, match=r"sqlite\+aiosqlite"):
        create_sqlite_engine(DatabaseSettings(url=url))


async def test_transaction_scope_commits_on_success(runtime: PersistenceRuntime) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        session.add(_RuntimeRow(id="commit", payload={"status": "kept"}, occurred_at=utc_now()))

    async with transaction_scope(runtime.session_factory) as session:
        row = await session.get(_RuntimeRow, "commit")

    assert row is not None
    assert row.payload == {"status": "kept"}
    assert row.occurred_at.tzinfo is timezone.utc


async def test_transaction_scope_rolls_back_on_error(runtime: PersistenceRuntime) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with transaction_scope(runtime.session_factory) as session:
            session.add(
                _RuntimeRow(id="rollback", payload={"status": "discard"}, occurred_at=utc_now())
            )
            raise RuntimeError("boom")

    async with transaction_scope(runtime.session_factory) as session:
        row = await session.get(_RuntimeRow, "rollback")

    assert row is None


async def test_concurrent_scopes_use_distinct_sessions(runtime: PersistenceRuntime) -> None:
    async def insert(row_id: str) -> int:
        async with transaction_scope(runtime.session_factory) as session:
            session.add(_RuntimeRow(id=row_id, payload={"id": row_id}, occurred_at=utc_now()))
            return id(session)

    session_ids = await asyncio.gather(insert("first"), insert("second"))

    async with transaction_scope(runtime.session_factory) as session:
        rows = (await session.scalars(select(_RuntimeRow).order_by(_RuntimeRow.id))).all()

    assert session_ids[0] != session_ids[1]
    assert [row.id for row in rows] == ["first", "second"]


async def test_closed_runtime_rejects_session_factory(sqlite_database_url: str) -> None:
    runtime = PersistenceRuntime.start(DatabaseSettings(url=sqlite_database_url))

    await runtime.close()

    with pytest.raises(RuntimeError, match="已关闭"):
        _ = runtime.session_factory


async def test_sessions_are_closed_after_transaction_scope(runtime: PersistenceRuntime) -> None:
    captured: AsyncSession | None = None
    async with transaction_scope(runtime.session_factory) as session:
        captured = session

    assert captured is not None
    assert not captured.in_transaction()
