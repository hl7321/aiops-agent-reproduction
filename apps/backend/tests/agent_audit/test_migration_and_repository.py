from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from super_ai.agent_audit.models import AgentToolCallAuditRecord, NewAgentToolCallAudit
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.agent_audit_models import AgentToolCallAuditModel
from super_ai.memory.extended_sqlite.agent_audit_repositories import (
    SqliteAgentToolCallAuditRepository,
)
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.chat_models import ChatSessionModel
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import (
    PersistenceRuntime,
    create_sqlite_engine,
    transaction_scope,
    upgrade_database,
)


def _audit_schema(connection: Connection) -> tuple[set[str], set[str], set[str], set[str]]:
    inspector = inspect(connection)
    return (
        {item["name"] for item in inspector.get_columns("agent_tool_call_audits")},
        {
            name
            for item in inspector.get_indexes("agent_tool_call_audits")
            if isinstance((name := item["name"]), str)
        },
        {
            name
            for item in inspector.get_check_constraints("agent_tool_call_audits")
            if isinstance((name := item["name"]), str)
        },
        {
            constrained
            for foreign_key in inspector.get_foreign_keys("agent_tool_call_audits")
            for constrained in foreign_key["constrained_columns"]
        },
    )


async def test_agent_audit_migration_has_normalized_exclusive_parent_schema(
    agent_audit_database_url: str,
) -> None:
    await upgrade_database(agent_audit_database_url)
    engine = create_sqlite_engine(DatabaseSettings(url=agent_audit_database_url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            columns, indexes, checks, foreign_keys = await connection.run_sync(_audit_schema)
    finally:
        await engine.dispose()

    assert revision == "20260821_0012"
    assert columns == {
        "id", "owner_user_id", "tool_call_id", "chat_session_id", "diagnostic_task_id",
        "tool_name", "arguments", "status", "result_summary", "error_message",
        "started_at", "completed_at", "duration_ms",
    }
    assert "parent_call_id" not in columns
    assert indexes == {
        "ix_agent_audits_owner_chat_started_id",
        "ix_agent_audits_owner_diagnostic_started_id",
    }
    assert "ck_agent_audits_exactly_one_parent" in checks
    assert foreign_keys == {"owner_user_id", "chat_session_id"}


async def _seed_parent(runtime: PersistenceRuntime, owner: str, session_id: str) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        now = utc_now()
        session.add(
            UserModel(
                id=owner,
                email=f"{owner}@example.com",
                password_hash="$argon2id$test",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ChatSessionModel(
                id=session_id,
                owner_user_id=owner,
                title="审计测试",
                created_at=now,
                updated_at=now,
            )
        )


async def test_repository_lifecycle_is_owner_scoped_and_stably_sorted(
    agent_audit_database_url: str,
) -> None:
    await upgrade_database(agent_audit_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=agent_audit_database_url))
    try:
        await _seed_parent(runtime, "user-a", "session-a")
        await _seed_parent(runtime, "user-b", "session-b")
        started_at = utc_now()
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteAgentToolCallAuditRepository(session)
            first = await repository.start(
                "user-a",
                NewAgentToolCallAudit(
                    tool_call_id="call-2",
                    chat_session_id="session-a",
                    diagnostic_task_id=None,
                    tool_name="get_current_time",
                    arguments={"timezone": "Asia/Shanghai"},
                    started_at=started_at,
                ),
            )
            second = await repository.start(
                "user-a",
                NewAgentToolCallAudit(
                    tool_call_id="call-1",
                    chat_session_id="session-a",
                    diagnostic_task_id=None,
                    tool_name="knowledge_retrieval",
                    arguments={"query": "SENTINEL_QUERY"},
                    started_at=started_at,
                ),
            )
            await repository.complete(
                "user-a",
                first.id,
                result_summary="当前时间已返回",
                completed_at=started_at + timedelta(milliseconds=12),
            )
            failed = await repository.fail(
                "user-a",
                second.id,
                error_message="apiKey=raw-secret",
                completed_at=started_at + timedelta(milliseconds=20),
                api_key="raw-secret",
            )

        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteAgentToolCallAuditRepository(session)
            assert await repository.list_for_chat("user-b", "session-a") == []
            items = await repository.list_for_chat("user-a", "session-a")

        assert [item.id for item in items] == sorted([first.id, second.id])
        assert items[0].status in {"completed", "failed"}
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error_message is not None and "raw-secret" not in failed.error_message
        assert failed.duration_ms == 20
        assert items[0].arguments
    finally:
        await runtime.close()


async def test_database_rejects_missing_or_double_parent(
    agent_audit_database_url: str,
) -> None:
    await upgrade_database(agent_audit_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=agent_audit_database_url))
    try:
        await _seed_parent(runtime, "user-a", "session-a")
        for chat_session_id, diagnostic_task_id in [(None, None), ("session-a", "task-1")]:
            with pytest.raises(IntegrityError):
                async with transaction_scope(runtime.session_factory) as session:
                    session.add(
                        AgentToolCallAuditModel(
                            id=f"invalid-{diagnostic_task_id or 'none'}",
                            owner_user_id="user-a",
                            tool_call_id="call-invalid",
                            chat_session_id=chat_session_id,
                            diagnostic_task_id=diagnostic_task_id,
                            tool_name="test",
                            arguments_json={},
                            status="started",
                            started_at=utc_now(),
                        )
                    )
    finally:
        await runtime.close()


def test_agent_audit_record_is_immutable() -> None:
    now = utc_now()
    record = AgentToolCallAuditRecord(
        id="audit-1",
        owner_user_id="user-1",
        tool_call_id="call-1",
        chat_session_id="session-1",
        diagnostic_task_id=None,
        tool_name="test",
        arguments={},
        status="started",
        result_summary=None,
        error_message=None,
        started_at=now,
        completed_at=None,
        duration_ms=None,
    )
    with pytest.raises(FrozenInstanceError):
        record.status = "completed"  # type: ignore[misc]
