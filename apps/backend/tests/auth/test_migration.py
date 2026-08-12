from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import AuthSessionModel, UserModel
from super_ai.memory.sqlite import Base, create_sqlite_engine, upgrade_database


def _schema(connection: Connection) -> dict[str, set[str]]:
    inspector = inspect(connection)
    return {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ("users", "auth_sessions")
    }


async def test_auth_migration_creates_normalized_schema(auth_database_url: str) -> None:
    await upgrade_database(auth_database_url)
    engine = create_sqlite_engine(DatabaseSettings(url=auth_database_url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            schema = await connection.run_sync(_schema)
    finally:
        await engine.dispose()

    assert revision == "20260808_0002"
    assert schema == {
        "users": {"id", "email", "password_hash", "created_at", "updated_at"},
        "auth_sessions": {
            "id", "user_id", "token_hash", "created_at", "last_seen_at", "revoked_at"
        },
    }
    assert UserModel.__table__ is Base.metadata.tables["users"]
    assert AuthSessionModel.__table__ is Base.metadata.tables["auth_sessions"]
