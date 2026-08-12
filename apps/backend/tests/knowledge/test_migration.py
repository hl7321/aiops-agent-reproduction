from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import create_sqlite_engine, upgrade_database


def _columns(connection: Connection) -> set[str]:
    return {item["name"] for item in inspect(connection).get_columns("knowledge_documents")}


async def test_knowledge_migration_has_normalized_document_schema(
    knowledge_database_url: str,
) -> None:
    await upgrade_database(knowledge_database_url)
    engine = create_sqlite_engine(DatabaseSettings(url=knowledge_database_url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            columns = await connection.run_sync(_columns)
    finally:
        await engine.dispose()
    assert revision == "20260812_0004"
    assert columns == {
        "id",
        "owner_user_id",
        "knowledge_base_id",
        "filename",
        "size_bytes",
        "mime_type",
        "sha256",
        "uploaded_at",
        "index_status",
        "chunking_strategy",
        "max_characters",
        "overlap",
        "indexable_text",
        "deleted_at",
        "created_at",
        "updated_at",
    }
