import inspect
import json
from pathlib import Path
from typing import cast

from super_ai.memory.extended_sqlite.knowledge_repositories import (
    SqliteKnowledgeDocumentRepository,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parents[1]
RETRIEVAL_SOURCE = BACKEND_ROOT / "src/super_ai/retrieval"


def test_retrieval_repository_owner_is_first_business_parameter() -> None:
    parameters = list(
        inspect.signature(SqliteKnowledgeDocumentRepository.list_retrieval_corpus).parameters
    )

    assert parameters[:2] == ["self", "owner_user_id"]


def test_retrieval_source_has_no_legacy_algorithm_or_detached_task() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in RETRIEVAL_SOURCE.rglob("*.py")
    )

    assert "BM25Okapi" not in source
    assert "asyncio.create_task" not in source
    assert "fallback" not in source.casefold()


def test_tool_does_not_add_independent_search_http_path() -> None:
    raw: object = json.loads(
        (REPO_ROOT / "packages/api-contracts/contract-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = cast(dict[str, object], raw)
    openapi = cast(dict[str, object], manifest["openapi"])
    paths = cast(dict[str, object], openapi["paths"])

    assert not any("search" in path or "retrieval" in path for path in paths)
