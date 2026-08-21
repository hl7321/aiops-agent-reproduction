import inspect
from pathlib import Path

from super_ai.memory.extended_sqlite.diagnosis_case_repositories import (
    SqliteDiagnosisCaseRepository,
)

CASE_SOURCE = Path(__file__).resolve().parents[2] / "src/super_ai/aiops/cases"


def test_case_repository_methods_are_owner_first() -> None:
    for method_name in ("get_by_task", "get", "list", "create"):
        parameters = list(
            inspect.signature(getattr(SqliteDiagnosisCaseRepository, method_name)).parameters
        )
        assert parameters[:2] == ["self", "owner_user_id"]


def test_case_paths_do_not_write_vectors_or_spawn_ephemeral_tasks() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in CASE_SOURCE.rglob("*.py"))
    assert "Milvus" not in source
    assert "insert_chunks" not in source
    assert "asyncio.create_task" not in source
    assert "DocumentIndexTaskService" in source
