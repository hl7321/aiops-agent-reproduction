from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import Base, create_sqlite_engine
from super_ai.memory.sqlite.migrations import upgrade_database


def _names(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names())


async def test_fresh_upgrade_adds_normalized_diagnostic_tables(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'aiops.sqlite3'}"
    await upgrade_database(url)
    engine = create_sqlite_engine(DatabaseSettings(url=url))
    try:
        async with engine.connect() as connection:
            names = await connection.run_sync(_names)
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()

    assert revision == "20260821_0012"
    assert {
        "diagnostic_tasks",
        "diagnostic_steps",
        "diagnostic_evidence",
        "diagnostic_reports",
        "report_evidence_links",
        "graph_checkpoints",
    } <= names
    assert set(Base.metadata.tables) - {"alembic_version"} <= names
