from fakes import FakeMilvusClient, FakeMilvusClientFactory
from settings_factory import make_vector_store_settings

from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.adapter import MilvusVectorStore


def _scope(user: str, *knowledge_bases: str) -> VectorScope:
    return VectorScope(
        tenant_id=user,
        owner_user_id=user,
        allowed_knowledge_base_ids=knowledge_bases,
    )


async def test_search_uses_cosine_ef64_and_only_tenant_kb_filter() -> None:
    client = FakeMilvusClient(collection_exists=True)
    client.search_result = [[{"id": "chunk-a", "distance": 0.91, "entity": {"content": "a"}}]]
    store = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client)
    )
    await store.connect()

    hits = await store.search(_scope("user-a", "kb-a", "kb-b"), [0.1] * 1024, limit=5)

    call = client.search_calls[0]
    assert call["collection_name"] == "super_ai_chunks"
    assert call["anns_field"] == "vector"
    assert call["search_params"] == {"metric_type": "COSINE", "params": {"ef": 64}}
    assert call["filter"] == (
        'tenantId == "user-a" and knowledgeBaseId in ["kb-a", "kb-b"]'
    )
    assert "ownerUserId" not in call["filter"]
    assert "documentId" not in call["filter"]
    assert hits[0].chunk_id == "chunk-a"
    assert hits[0].distance == 0.91


async def test_two_users_and_special_characters_remain_isolated_and_escaped() -> None:
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

    await store_a.search(_scope('user-"a\\', 'kb-"x\\'), [0.1] * 1024, limit=1)
    await store_b.search(_scope("user-b", 'kb-"x\\'), [0.1] * 1024, limit=1)

    filter_a = client_a.search_calls[0]["filter"]
    filter_b = client_b.search_calls[0]["filter"]
    assert filter_a == 'tenantId == "user-\\"a\\\\" and knowledgeBaseId in ["kb-\\"x\\\\"]'
    assert 'tenantId == "user-b"' in filter_b
    assert filter_a != filter_b


async def test_empty_kb_scope_returns_empty_without_creating_or_accessing_client() -> None:
    client = FakeMilvusClient()
    factory = FakeMilvusClientFactory(client)
    store = MilvusVectorStore(make_vector_store_settings(), client_factory=factory)

    assert await store.search(_scope("user-a"), [0.1] * 1024, limit=5) == []
    assert factory.calls == []
    assert client.search_calls == []
