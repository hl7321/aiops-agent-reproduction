import subprocess
import sys
from pathlib import Path

from super_ai.memory.sqlite import Base

ROOT = Path(__file__).resolve().parents[2]


def test_tenancy_import_has_no_database_network_or_milvus_side_effects(tmp_path: Path) -> None:
    script = """
from unittest.mock import patch

with (
    patch("aiosqlite.connect", side_effect=AssertionError("import connected SQLite")),
    patch("socket.socket.connect", side_effect=AssertionError("import connected network")),
):
    import super_ai.tenancy
    import super_ai.tenancy.dependencies
    import super_ai.tenancy.vector_scope
    import super_ai.memory.sqlite.owner_scope
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_p05_adds_no_tenant_specific_migration_revision() -> None:
    revisions = sorted((ROOT / "migrations/versions").glob("*.py"))

    names = [path.name for path in revisions]
    assert "20260808_0001_persistence_foundation.py" in names
    assert "20260808_0002_add_user_authentication.py" in names
    assert not any("tenant" in name for name in names)
    assert set(Base.metadata.tables) == {
        "users",
        "auth_sessions",
        "background_jobs",
        "background_job_events",
        "knowledge_documents",
        "document_index_tasks",
        "chat_sessions",
        "chat_messages",
        "agent_tool_call_audits",
        "user_chat_configurations",
        "user_chat_prompts",
        "user_chat_skills",
        "mcp_connections",
        "diagnostic_tasks",
        "diagnostic_steps",
        "diagnostic_evidence",
        "diagnostic_reports",
        "report_evidence_links",
        "graph_checkpoints",
        "aiops_diagnostic_cases",
        "diagnostic_case_sources",
        "user_feedback",
    }
