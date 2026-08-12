import pytest
from fakes import FakeMilvusClient, FakeMilvusClientFactory
from settings_factory import make_vector_store_settings

from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.errors import VectorStoreNotConnectedError


async def test_client_is_lazy_and_connect_is_idempotent() -> None:
    client = FakeMilvusClient()
    factory = FakeMilvusClientFactory(client)
    store = MilvusVectorStore(make_vector_store_settings(), client_factory=factory)

    assert factory.calls == []
    assert await store.connect() is client
    assert await store.connect() is client
    assert factory.calls == [
        {"uri": "http://milvus.example:19530", "token": "local-token"}
    ]


async def test_initialize_creates_schema_and_indexes_once_then_loads_idempotently() -> None:
    client = FakeMilvusClient(collection_exists=False)
    factory = FakeMilvusClientFactory(client)
    store = MilvusVectorStore(make_vector_store_settings(), client_factory=factory)

    await store.initialize()
    await store.initialize()

    assert len(factory.calls) == 1
    assert client.has_collection_calls == ["super_ai_chunks", "super_ai_chunks"]
    assert len(client.create_collection_calls) == 1
    created = client.create_collection_calls[0]
    assert created["collection_name"] == "super_ai_chunks"
    assert created["schema"].to_dict()["enable_dynamic_field"] is False
    assert len(list(created["index_params"])) == 4
    assert client.load_collection_calls == ["super_ai_chunks", "super_ai_chunks"]


async def test_connected_operation_is_rejected_before_explicit_connection() -> None:
    store = MilvusVectorStore(
        make_vector_store_settings(),
        client_factory=FakeMilvusClientFactory(FakeMilvusClient()),
    )

    with pytest.raises(VectorStoreNotConnectedError):
        await store.health()
