import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.mcp_connections.models import CreateMcpConnection
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.mcp_connection_repositories import (
    SqliteMcpConnectionRepository,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import (
    PersistenceRuntime,
    create_sqlite_engine,
    transaction_scope,
    upgrade_database,
)


def _schema(connection: Connection) -> tuple[set[str], set[str]]:
    inspector = inspect(connection)
    return (
        {column["name"] for column in inspector.get_columns("mcp_connections")},
        {
            name
            for index in inspector.get_indexes("mcp_connections")
            if (name := index["name"]) is not None
        },
    )


async def test_migration_creates_normalized_mcp_connections(mcp_database_url: str) -> None:
    await upgrade_database(mcp_database_url)
    engine = create_sqlite_engine(DatabaseSettings(url=mcp_database_url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            columns, indexes = await connection.run_sync(_schema)
    finally:
        await engine.dispose()

    assert revision == "20260821_0012"
    assert {
        "owner_user_id",
        "name",
        "transport",
        "url",
        "enabled",
        "timeout_seconds",
        "retries",
        "last_check",
        "last_error",
        "discovered_tools",
    }.issubset(columns)
    assert "ix_mcp_connections_owner_updated_id" in indexes


async def test_mcp_migration_downgrade_removes_only_mcp_table(
    mcp_database_url: str,
) -> None:
    await upgrade_database(mcp_database_url)
    configuration = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    configuration.attributes["database_url"] = mcp_database_url
    await asyncio.to_thread(command.downgrade, configuration, "20260818_0009")
    engine = create_sqlite_engine(DatabaseSettings(url=mcp_database_url))
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync: set(inspect(sync).get_table_names())
            )
    finally:
        await engine.dispose()
    assert "mcp_connections" not in tables
    assert "chat_sessions" in tables


async def _seed(runtime: PersistenceRuntime, *owners: str) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        now = utc_now()
        for owner in owners:
            session.add(
                UserModel(
                    id=owner,
                    email=f"{owner}@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )


async def test_repository_scopes_every_operation_to_owner(mcp_database_url: str) -> None:
    await upgrade_database(mcp_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=mcp_database_url))
    try:
        await _seed(runtime, "user-a", "user-b")
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteMcpConnectionRepository(session)
            created = await repository.create(
                "user-a",
                CreateMcpConnection(
                    "CLS",
                    "streamable_http",
                    "https://example.test/mcp?mode=read",
                    True,
                    30,
                    1,
                ),
            )
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteMcpConnectionRepository(session)
            assert await repository.get("user-b", created.id) is None
            assert await repository.delete("user-b", created.id) is False
            assert await repository.list("user-b") == ()
            assert (await repository.get("user-a", created.id)) == created
    finally:
        await runtime.close()


async def test_repository_create_rolls_back_with_transaction(mcp_database_url: str) -> None:
    await upgrade_database(mcp_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=mcp_database_url))
    try:
        await _seed(runtime, "user-a")
        try:
            async with transaction_scope(runtime.session_factory) as session:
                await SqliteMcpConnectionRepository(session).create(
                    "user-a",
                    CreateMcpConnection(
                        "rollback", "sse", "https://example.test/sse", True, 10, 0
                    ),
                )
                raise RuntimeError("rollback")
        except RuntimeError:
            pass
        async with transaction_scope(runtime.session_factory) as session:
            assert await SqliteMcpConnectionRepository(session).list("user-a") == ()
    finally:
        await runtime.close()
