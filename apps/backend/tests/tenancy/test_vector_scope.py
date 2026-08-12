import pytest

from super_ai.tenancy.context import CurrentUser, TenantContext
from super_ai.tenancy.vector_scope import (
    VectorScope,
    build_delete_filter,
    build_search_filter,
    build_vector_metadata,
    post_filter_hits,
    scoped_vector_search,
)


def _scope(*knowledge_base_ids: str) -> VectorScope:
    context = TenantContext.from_current_user(CurrentUser(user_id='user-"a'))
    return VectorScope.from_tenant_context(context, knowledge_base_ids)


def test_vector_metadata_preserves_tenant_owner_kb_and_document() -> None:
    metadata = build_vector_metadata(
        _scope("kb-1"),
        knowledge_base_id="kb-1",
        document_id="doc-1",
        extra={"source": "manual"},
    )

    assert metadata == {
        "source": "manual",
        "tenantId": 'user-"a',
        "ownerUserId": 'user-"a',
        "knowledgeBaseId": "kb-1",
        "documentId": "doc-1",
    }


@pytest.mark.parametrize(
    "protected_key",
    ["tenantId", "ownerUserId", "knowledgeBaseId", "documentId"],
)
def test_extra_metadata_cannot_override_protected_scope(protected_key: str) -> None:
    with pytest.raises(ValueError):
        build_vector_metadata(
            _scope("kb-1"),
            knowledge_base_id="kb-1",
            document_id="doc-1",
            extra={protected_key: "attacker"},
        )


def test_search_filter_contains_only_tenant_and_allowed_knowledge_bases() -> None:
    value = build_search_filter(_scope("kb-2", "kb-1"))

    assert value == 'tenantId == "user-\\"a" and knowledgeBaseId in ["kb-1", "kb-2"]'
    assert "documentId" not in value
    assert "ownerUserId" not in value


async def test_empty_kb_scope_returns_without_calling_milvus() -> None:
    calls = 0

    async def forbidden_search(_filter: str) -> list[dict[str, object]]:
        nonlocal calls
        calls += 1
        raise AssertionError("空 KB scope 不得连接 Milvus")

    result = await scoped_vector_search(_scope(), forbidden_search)

    assert result == []
    assert calls == 0


def test_optional_document_and_metadata_filters_run_after_scoped_retrieval() -> None:
    hits = [
        {"documentId": "doc-1", "kind": "runbook", "tenantId": "user-a"},
        {"documentId": "doc-2", "kind": "alert", "tenantId": "user-a"},
    ]

    result = post_filter_hits(
        hits,
        allowed_document_ids=frozenset({"doc-1"}),
        metadata_filter={"kind": "runbook"},
    )

    assert result == [hits[0]]


def test_delete_filter_requires_tenant_kb_and_document() -> None:
    assert build_delete_filter(
        _scope("kb-1"), knowledge_base_id="kb-1", document_id="doc-1"
    ) == (
        'tenantId == "user-\\"a" and knowledgeBaseId == "kb-1" '
        'and documentId == "doc-1"'
    )

    for knowledge_base_id, document_id in (("", "doc-1"), ("kb-1", "")):
        with pytest.raises(ValueError):
            build_delete_filter(
                _scope("kb-1"),
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
            )
