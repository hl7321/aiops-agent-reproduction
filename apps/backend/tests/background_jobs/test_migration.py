from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import create_sqlite_engine, upgrade_database


def _schema(connection: Connection) -> dict[str, set[str]]:
    inspector = inspect(connection)
    return {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ("background_jobs", "background_job_events")
    }


async def test_background_job_migration_has_exact_durable_columns(
    jobs_database_url: str,
) -> None:
    await upgrade_database(jobs_database_url, revision="20260812_0003")
    engine = create_sqlite_engine(DatabaseSettings(url=jobs_database_url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            schema = await connection.run_sync(_schema)
    finally:
        await engine.dispose()

    assert revision == "20260812_0003"
    assert schema["background_jobs"] == {
        "id",
        "owner_user_id",
        "kind",
        "resource_type",
        "resource_id",
        "status",
        "payload",
        "attempt",
        "max_attempts",
        "timeout_seconds",
        "available_at",
        "lease_owner",
        "lease_expires_at",
        "cancel_requested_at",
        "retry_of_job_id",
        "error_message",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
    }
    assert schema["background_job_events"] == {
        "sequence",
        "job_id",
        "owner_user_id",
        "type",
        "data",
        "created_at",
    }
    assert "heartbeat_at" not in schema["background_jobs"]
    assert "result" not in schema["background_jobs"]
