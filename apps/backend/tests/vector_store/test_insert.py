from datetime import datetime, timezone

import pytest
from fakes import FakeMilvusClient, FakeMilvusClientFactory
from settings_factory import make_vector_store_settings

from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.records import VectorChunk


def _scope() -> VectorScope:
    return VectorScope(
        tenant_id="user-a",
        owner_user_id="user-a",
        allowed_knowledge_base_ids=("kb-a",),
    )


def _chunk(**overrides: object) -> VectorChunk:
    values: dict[str, object] = {
        "chunk_id": "chunk-a",
        "document_id": "document-a",
        "knowledge_base_id": "kb-a",
        "content": "正文",
        "source": "manual.pdf",
        "created_at": datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc),
        "metadata": {"page": 1},
        "vector": [0.25] * 1024,
    }
    values.update(overrides)
    return VectorChunk(**values)  # type: ignore[arg-type]


async def test_insert_writes_complete_fields_and_trusted_tenant_owner_metadata() -> None:
    client = FakeMilvusClient(collection_exists=True)
    store = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client)
    )
    await store.connect()

    inserted = await store.insert(_scope(), [_chunk()])

    assert inserted == 1
    entity = client.insert_calls[0]["data"][0]
    assert set(entity) == {
        "chunkId",
        "documentId",
        "knowledgeBaseId",
        "ownerUserId",
        "tenantId",
        "content",
        "source",
        "createdAt",
        "metadata",
        "vector",
    }
    assert entity["tenantId"] == "user-a"
    assert entity["ownerUserId"] == "user-a"
    assert entity["metadata"] == {
        "page": 1,
        "tenantId": "user-a",
        "ownerUserId": "user-a",
        "knowledgeBaseId": "kb-a",
        "documentId": "document-a",
    }
    assert entity["createdAt"] == "2026-08-10T06:00:00Z"


@pytest.mark.parametrize(
    "overrides",
    [
        {"vector": [0.25] * 1023},
        {"metadata": {"tenantId": "attacker"}},
        {"knowledge_base_id": "other-kb"},
    ],
)
async def test_invalid_chunk_or_scope_never_calls_insert(overrides: dict[str, object]) -> None:
    client = FakeMilvusClient(collection_exists=True)
    store = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client)
    )
    await store.connect()

    with pytest.raises(ValueError):
        await store.insert(_scope(), [_chunk(**overrides)])

    assert client.insert_calls == []


async def test_batch_is_fully_validated_before_single_insert() -> None:
    client = FakeMilvusClient(collection_exists=True)
    store = MilvusVectorStore(
        make_vector_store_settings(), client_factory=FakeMilvusClientFactory(client)
    )
    await store.connect()

    with pytest.raises(ValueError):
        await store.insert(_scope(), [_chunk(), _chunk(chunk_id="chunk-b", vector=[1.0])])

    assert client.insert_calls == []
