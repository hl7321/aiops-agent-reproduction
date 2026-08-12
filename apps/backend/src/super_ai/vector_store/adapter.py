"""显式生命周期的 tenant-safe Milvus adapter。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import timezone
from typing import Any, TypeVar, cast

from pydantic import JsonValue
from pymilvus import MilvusClient

from super_ai.tenancy.vector_scope import (
    VectorScope,
    build_delete_filter,
    build_search_filter,
    build_vector_metadata,
)
from super_ai.vector_store.config import VectorStoreSettings
from super_ai.vector_store.errors import (
    VectorStoreError,
    VectorStoreNotConnectedError,
    sanitize_vector_store_exception,
)
from super_ai.vector_store.records import MilvusHealth, VectorChunk, VectorSearchHit
from super_ai.vector_store.schema import (
    SEARCH_EF,
    VECTOR_DIMENSIONS,
    build_collection_schema,
    build_index_params,
)
from super_ai.vector_store.types import MilvusClientFactory, MilvusClientProtocol

ResultT = TypeVar("ResultT")


def _create_milvus_client(*, uri: str, token: str) -> MilvusClientProtocol:
    return cast(MilvusClientProtocol, MilvusClient(uri=uri, token=token))


class MilvusVectorStore:
    def __init__(
        self,
        settings: VectorStoreSettings,
        *,
        client_factory: MilvusClientFactory = _create_milvus_client,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._client: MilvusClientProtocol | None = None
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> MilvusClientProtocol:
        if self._client is not None:
            return self._client
        async with self._connect_lock:
            if self._client is None:
                token = self._settings.token.get_secret_value()
                self._client = await self._call(
                    self._client_factory,
                    uri=self._settings.uri,
                    token=token,
                )
        return self._client

    async def initialize(self) -> None:
        client = await self.connect()
        collection_name = self._settings.collection_name
        exists = await self._call(client.has_collection, collection_name)
        if not exists:
            await self._call(
                client.create_collection,
                collection_name,
                schema=build_collection_schema(),
                index_params=build_index_params(),
            )
        await self._call(client.load_collection, collection_name)

    async def health(self) -> MilvusHealth:
        client = self._require_client()
        version = await self._call(client.get_server_version)
        return MilvusHealth(healthy=True, server_version=str(version))

    async def insert(self, scope: VectorScope, chunks: Sequence[VectorChunk]) -> int:
        entities = [self._chunk_to_entity(scope, chunk) for chunk in chunks]
        if not entities:
            return 0
        client = self._require_client()
        result = await self._call(
            client.insert,
            self._settings.collection_name,
            entities,
        )
        inserted = result.get("insert_count")
        if not isinstance(inserted, int) or isinstance(inserted, bool):
            raise VectorStoreError("Milvus insert 返回无效计数")
        return inserted

    async def search(
        self,
        scope: VectorScope,
        query_vector: Sequence[float],
        *,
        limit: int,
    ) -> list[VectorSearchHit]:
        search_filter = build_search_filter(scope)
        if search_filter is None:
            return []
        vector = _validated_vector(query_vector)
        if limit <= 0:
            raise ValueError("limit 必须大于零")
        client = self._require_client()
        raw = await self._call(
            client.search,
            collection_name=self._settings.collection_name,
            data=[vector],
            anns_field="vector",
            filter=search_filter,
            limit=limit,
            output_fields=[
                "chunkId",
                "documentId",
                "knowledgeBaseId",
                "ownerUserId",
                "tenantId",
                "content",
                "source",
                "createdAt",
                "metadata",
            ],
            search_params={"metric_type": "COSINE", "params": {"ef": SEARCH_EF}},
        )
        if len(raw) != 1:
            raise VectorStoreError("Milvus search 返回无效批次数量")
        return [_to_search_hit(item) for item in raw[0]]

    async def delete_document(
        self,
        scope: VectorScope,
        knowledge_base_id: str,
        document_id: str,
    ) -> int:
        delete_filter = build_delete_filter(
            scope,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        client = self._require_client()
        result = await self._call(
            client.delete,
            self._settings.collection_name,
            filter=delete_filter,
        )
        deleted = result.get("delete_count")
        if not isinstance(deleted, int) or isinstance(deleted, bool):
            raise VectorStoreError("Milvus delete 返回无效计数")
        return deleted

    def _chunk_to_entity(
        self,
        scope: VectorScope,
        chunk: VectorChunk,
    ) -> dict[str, Any]:
        metadata = build_vector_metadata(
            scope,
            knowledge_base_id=chunk.knowledge_base_id,
            document_id=chunk.document_id,
            extra=chunk.metadata,
        )
        created_at = chunk.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "chunkId": chunk.chunk_id,
            "documentId": chunk.document_id,
            "knowledgeBaseId": chunk.knowledge_base_id,
            "ownerUserId": scope.owner_user_id,
            "tenantId": scope.tenant_id,
            "content": chunk.content,
            "source": chunk.source,
            "createdAt": created_at,
            "metadata": metadata,
            "vector": list(chunk.vector),
        }

    def _require_client(self) -> MilvusClientProtocol:
        if self._client is None:
            raise VectorStoreNotConnectedError("Milvus adapter 尚未显式连接")
        return self._client

    async def _call(
        self,
        function: Callable[..., ResultT],
        *args: Any,
        **kwargs: Any,
    ) -> ResultT:
        try:
            return await asyncio.to_thread(function, *args, **kwargs)
        except Exception as error:
            secret = self._settings.token.get_secret_value()
            raise sanitize_vector_store_exception(error, secret) from error


def _validated_vector(vector: Sequence[float]) -> list[float]:
    values = [float(value) for value in vector]
    if len(values) != VECTOR_DIMENSIONS:
        raise ValueError(f"vector 必须包含 {VECTOR_DIMENSIONS} 维")
    return values


def _to_search_hit(raw: Mapping[str, Any]) -> VectorSearchHit:
    entity_value = raw.get("entity", {})
    if not isinstance(entity_value, dict):
        raise VectorStoreError("Milvus search entity 形状无效")
    entity = cast(dict[str, JsonValue], entity_value)
    chunk_id = raw.get("id", entity.get("chunkId"))
    distance = raw.get("distance")
    if not isinstance(chunk_id, str) or not chunk_id:
        raise VectorStoreError("Milvus search 缺少 chunkId")
    if not isinstance(distance, int | float) or isinstance(distance, bool):
        raise VectorStoreError("Milvus search distance 无效")
    return VectorSearchHit(chunk_id=chunk_id, distance=float(distance), entity=entity)
