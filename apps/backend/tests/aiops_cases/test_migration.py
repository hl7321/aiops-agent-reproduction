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
                report_columns,
                step_columns,
                source_columns,
                source_column_details,
                document_columns,
                uniques,
                source_uniques,
                foreign_keys,
                source_foreign_keys,
                indexes,
                revision,
            ) = await connection.run_sync(
                lambda sync: (
                    set(inspect(sync).get_table_names()),
                    {item["name"] for item in inspect(sync).get_columns("aiops_diagnostic_cases")},
                    {item["name"] for item in inspect(sync).get_columns("diagnostic_reports")},
                    {item["name"] for item in inspect(sync).get_columns("diagnostic_steps")},
                    {
                        item["name"]
                        for item in inspect(sync).get_columns("diagnostic_case_sources")
                    },
                    {
                        item["name"]: item
                        for item in inspect(sync).get_columns("diagnostic_case_sources")
                    },
                    {item["name"] for item in inspect(sync).get_columns("knowledge_documents")},
                    inspect(sync).get_unique_constraints("aiops_diagnostic_cases"),
                    inspect(sync).get_unique_constraints("diagnostic_case_sources"),
                    inspect(sync).get_foreign_keys("aiops_diagnostic_cases"),
                    inspect(sync).get_foreign_keys("diagnostic_case_sources"),
                    inspect(sync).get_indexes("aiops_diagnostic_cases"),
                    sync.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one(),
                )
            )
    finally:
        await engine.dispose()
    assert revision == "20260823_0015"
    assert {"aiops_diagnostic_cases", "diagnostic_case_sources"} <= tables
    assert {
        "task_id",
        "report_id",
        "document_id",
        "index_task_id",
        "evidence_ids",
        "incident_fingerprint",
        "knowledge_fingerprint",
        "fingerprint_version",
        "promotion_status",
    } <= case_columns
    assert "trust_state" in report_columns
    assert "error_category" in step_columns
    assert {
        "owner_user_id",
        "case_id",
        "diagnostic_task_id",
        "report_id",
        "approval_feedback_id",
        "evidence_ids",
    } <= source_columns
    assert source_column_details["approval_feedback_id"]["nullable"] is True
    assert "source_metadata" in document_columns
    assert any(item["column_names"] == ["task_id"] for item in uniques)
    assert any(
        item["column_names"] == ["owner_user_id", "incident_fingerprint"]
        for item in uniques
    )
    assert any(
        item["column_names"] == ["owner_user_id", "knowledge_fingerprint"]
        for item in uniques
    )
    assert any(
        item["column_names"] == ["owner_user_id", "report_id"]
        for item in source_uniques
    )
    assert {item["referred_table"] for item in foreign_keys} >= {
        "users",
        "diagnostic_tasks",
        "diagnostic_reports",
        "knowledge_documents",
        "document_index_tasks",
    }
    assert any(item["column_names"] == ["owner_user_id", "created_at", "id"] for item in indexes)
    assert {item["referred_table"] for item in source_foreign_keys} >= {
        "users",
        "aiops_diagnostic_cases",
        "diagnostic_tasks",
        "diagnostic_reports",
        "user_feedback",
    }
    feedback_fk = next(
        item for item in source_foreign_keys if item["referred_table"] == "user_feedback"
    )
    assert (feedback_fk.get("options") or {}).get("ondelete") == "SET NULL"
