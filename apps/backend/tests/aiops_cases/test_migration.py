from pathlib import Path

from sqlalchemy import inspect

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import create_sqlite_engine, upgrade_database


async def test_case_migration_and_document_metadata(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'cases.sqlite3'}"
    await upgrade_database(url)
    engine = create_sqlite_engine(DatabaseSettings(url=url))
    try:
        async with engine.connect() as connection:
            (
                tables,
                case_columns,
                document_columns,
                uniques,
                foreign_keys,
                indexes,
                revision,
            ) = await connection.run_sync(
                lambda sync: (
                    set(inspect(sync).get_table_names()),
                    {item["name"] for item in inspect(sync).get_columns("aiops_diagnostic_cases")},
                    {item["name"] for item in inspect(sync).get_columns("knowledge_documents")},
                    inspect(sync).get_unique_constraints("aiops_diagnostic_cases"),
                    inspect(sync).get_foreign_keys("aiops_diagnostic_cases"),
                    inspect(sync).get_indexes("aiops_diagnostic_cases"),
                    sync.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one(),
                )
            )
    finally:
        await engine.dispose()
    assert revision == "20260821_0013"
    assert "aiops_diagnostic_cases" in tables
    assert {"task_id", "report_id", "document_id", "index_task_id", "evidence_ids"} <= case_columns
    assert "source_metadata" in document_columns
    assert any(item["column_names"] == ["task_id"] for item in uniques)
    assert {item["referred_table"] for item in foreign_keys} >= {
        "users",
        "diagnostic_tasks",
        "diagnostic_reports",
        "knowledge_documents",
        "document_index_tasks",
    }
    assert any(item["column_names"] == ["owner_user_id", "created_at", "id"] for item in indexes)
