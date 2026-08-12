import pytest
from fakes import FakeMilvusClient, FakeMilvusClientFactory
from settings_factory import make_vector_store_settings

from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.errors import VectorStoreError


def _scope(user: str, *knowledge_bases: str) -> VectorScope:
    return VectorScope(
        tenant_id=user,
        owner_user_id=user,
        allowed_knowledge_base_ids=knowledge_bases,
    )


async def test_delete_document_uses_complete_scope_and_separates_users() -> None:
    client_a = FakeMilvusClient(collection_exists=True)
    client_b = FakeMilvusClient(collection_exists=True)
    store_a = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client_a)
    )
    store_b = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client_b)
    )
    await store_a.connect()
    await store_b.connect()

    assert await store_a.delete_document(_scope("user-a", "kb-a"), "kb-a", "doc-a") == 1
    assert await store_b.delete_document(_scope("user-b", "kb-a"), "kb-a", "doc-a") == 1

    filter_a = client_a.delete_calls[0]["filter"]
    filter_b = client_b.delete_calls[0]["filter"]
    assert filter_a == (
        'tenantId == "user-a" and knowledgeBaseId == "kb-a" and documentId == "doc-a"'
    )
    assert 'tenantId == "user-b"' in filter_b
    assert "ownerUserId" not in filter_a
    assert filter_a != filter_b


@pytest.mark.parametrize(
    ("knowledge_base_id", "document_id"),
    [("", "doc-a"), ("kb-a", ""), ("other-kb", "doc-a")],
)
async def test_invalid_delete_scope_never_calls_client(
    knowledge_base_id: str,
    document_id: str,
) -> None:
    client = FakeMilvusClient(collection_exists=True)
    store = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client)
    )
    await store.connect()

    with pytest.raises(ValueError):
        await store.delete_document(
            _scope("user-a", "kb-a"), knowledge_base_id, document_id
        )
    assert client.delete_calls == []


async def test_health_uses_connected_server_version_without_initializing_collection() -> None:
    client = FakeMilvusClient(collection_exists=False)
    client.server_version = "3.0-beta-test"
    store = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client)
    )
    await store.connect()

    health = await store.health()

    assert health.healthy is True
    assert health.server_version == "3.0-beta-test"
    assert client.has_collection_calls == []
    assert client.create_collection_calls == []


async def test_health_redacts_every_token_occurrence_from_client_errors() -> None:
    class FailingHealthClient(FakeMilvusClient):
        def get_server_version(self, **kwargs: object) -> str:
            raise RuntimeError("local-token failed; repeated local-token")

    client = FailingHealthClient(collection_exists=True)
    store = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client)
    )
    await store.connect()

    with pytest.raises(VectorStoreError) as captured:
        await store.health()

    assert "local-token" not in str(captured.value)
    assert str(captured.value).count("[redacted]") == 2
