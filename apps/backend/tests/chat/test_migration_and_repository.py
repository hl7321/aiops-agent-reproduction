from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.chat.models import ChatSessionRecord
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.sqlite import (
    PersistenceRuntime,
    create_sqlite_engine,
    transaction_scope,
    upgrade_database,
)


def _schema(connection: Connection) -> tuple[set[str], set[str], set[str]]:
    inspector = inspect(connection)
    return (
        {item["name"] for item in inspector.get_columns("chat_sessions")},
        {item["name"] for item in inspector.get_columns("chat_messages")},
        {name for item in inspector.get_indexes("chat_messages") if (name := item["name"])},
    )


async def test_chat_migration_has_normalized_schema(chat_database_url: str) -> None:
    await upgrade_database(chat_database_url)
    engine = create_sqlite_engine(DatabaseSettings(url=chat_database_url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            sessions, messages, indexes = await connection.run_sync(_schema)
    finally:
        await engine.dispose()

    assert revision == "20260821_0012"
    assert sessions == {
        "id", "owner_user_id", "title", "memory_mode", "memory_summary",
        "compacted_message_count", "context_tokens", "last_compacted_at",
        "created_at", "updated_at",
    }
    assert messages == {
        "id", "owner_user_id", "session_id", "role", "content", "sequence", "metadata",
        "created_at",
    }
    assert "ix_chat_messages_owner_session_sequence" in indexes


def test_chat_session_record_is_immutable() -> None:
    now = datetime.now(timezone.utc)
    record = ChatSessionRecord(
        id="session-1", owner_user_id="user-1", title="新会话",
        memory_mode="context_70_percent", memory_summary=None,
        compacted_message_count=0, context_tokens=0, last_compacted_at=None,
        created_at=now, updated_at=now,
    )
    with pytest.raises(FrozenInstanceError):
        record.title = "changed"  # type: ignore[misc]


async def test_repository_memory_updates_are_owner_scoped_and_compare_and_set(
    chat_database_url: str,
) -> None:
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    now = datetime.now(timezone.utc)
    try:
        async with transaction_scope(runtime.session_factory) as session:
            session.add_all([
                UserModel(
                    id="user-a", email="a@example.com", password_hash="hash",
                    created_at=now, updated_at=now,
                ),
                UserModel(
                    id="user-b", email="b@example.com", password_hash="hash",
                    created_at=now, updated_at=now,
                ),
            ])
        async with transaction_scope(runtime.session_factory) as session:
            created = await SqliteChatRepository(session).create("user-a")
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteChatRepository(session)
            assert (
                await repository.update_memory_mode("user-b", created.session.id, "manual")
                is None
            )
            updated = await repository.update_memory_mode("user-a", created.session.id, "manual")
            assert updated is not None and updated.session.memory_mode == "manual"
            assert await repository.update_context_tokens("user-a", created.session.id, 70)
            await repository.append("user-a", created.session.id, "user", "问题", {})
            await repository.append("user-a", created.session.id, "assistant", "回答", {})
            assert not await repository.commit_compaction(
                "user-a", created.session.id, expected_compacted_message_count=1,
                compacted_message_count=2, memory_summary="过期", compacted_at=now,
            )
            assert await repository.commit_compaction(
                "user-a", created.session.id, expected_compacted_message_count=0,
                compacted_message_count=2, memory_summary="摘要", compacted_at=now,
            )
        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", created.session.id)
        assert detail is not None
        assert detail.session.memory_summary == "摘要"
        assert detail.session.compacted_message_count == 2
        assert detail.session.context_tokens == 70
    finally:
        await runtime.close()


async def test_clear_preserves_mode_and_resets_memory_projection(chat_database_url: str) -> None:
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    now = datetime.now(timezone.utc)
    try:
        async with transaction_scope(runtime.session_factory) as session:
            session.add(UserModel(
                id="user-a", email="a@example.com", password_hash="hash",
                created_at=now, updated_at=now,
            ))
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteChatRepository(session)
            created = await repository.create("user-a")
            await repository.update_memory_mode("user-a", created.session.id, "manual")
            await repository.append("user-a", created.session.id, "user", "问题", {})
            await repository.append("user-a", created.session.id, "assistant", "回答", {})
            assert await repository.commit_compaction(
                "user-a", created.session.id, expected_compacted_message_count=0,
                compacted_message_count=2, memory_summary="摘要", compacted_at=now,
            )
            await repository.update_context_tokens("user-a", created.session.id, 80)
            cleared = await repository.clear("user-a", created.session.id)
        assert cleared is not None
        assert cleared.messages == ()
        assert cleared.session.memory_mode == "manual"
        assert cleared.session.memory_summary is None
        assert cleared.session.compacted_message_count == 0
        assert cleared.session.context_tokens == 0
        assert cleared.session.last_compacted_at is None
    finally:
        await runtime.close()


async def test_list_details_batches_messages_and_keeps_owner_scope(chat_database_url: str) -> None:
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    now = datetime.now(timezone.utc)
    try:
        async with transaction_scope(runtime.session_factory) as session:
            session.add_all([
                UserModel(
                    id="user-a", email="a@example.com", password_hash="hash",
                    created_at=now, updated_at=now,
                ),
                UserModel(
                    id="user-b", email="b@example.com", password_hash="hash",
                    created_at=now, updated_at=now,
                ),
            ])
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteChatRepository(session)
            first = await repository.create("user-a")
            second = await repository.create("user-a")
            foreign = await repository.create("user-b")
            await repository.append("user-a", first.session.id, "user", "A1", {})
            await repository.append("user-a", second.session.id, "user", "A2", {})
            await repository.append("user-b", foreign.session.id, "user", "B", {})
        async with transaction_scope(runtime.session_factory) as session:
            details = await SqliteChatRepository(session).list_details("user-a")

        assert {item.session.id for item in details} == {first.session.id, second.session.id}
        assert {item.messages[0].content for item in details} == {"A1", "A2"}
        assert all(item.session.owner_user_id == "user-a" for item in details)
    finally:
        await runtime.close()
