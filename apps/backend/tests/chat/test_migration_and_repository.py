from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.chat.models import ChatSessionRecord
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import create_sqlite_engine, upgrade_database


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

    assert revision == "20260817_0006"
    assert sessions == {"id", "owner_user_id", "title", "created_at", "updated_at"}
    assert messages == {
        "id", "owner_user_id", "session_id", "role", "content", "sequence", "metadata",
        "created_at",
    }
    assert "ix_chat_messages_owner_session_sequence" in indexes


def test_chat_session_record_is_immutable() -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    record = ChatSessionRecord("session-1", "user-1", "新会话", now, now)
    with pytest.raises(FrozenInstanceError):
        record.title = "changed"  # type: ignore[misc]
