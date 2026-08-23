from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.background_jobs.handlers import BackgroundJobCancelledError, BackgroundJobContext
from super_ai.background_jobs.security import redact_error
from super_ai.knowledge.chunk_identity import stable_chunk_id
from super_ai.knowledge.chunking import chunk_document_text
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.document_index_task_repositories import (
    SqliteDocumentIndexTaskRepository,
)
from super_ai.memory.extended_sqlite.knowledge_repositories import SqliteKnowledgeDocumentRepository
from super_ai.memory.primitives import dump_json, utc_now
from super_ai.memory.sqlite import transaction_scope
from super_ai.runtime.logging import log_lifecycle
from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.records import VectorChunk


class DocumentEmbeddingProvider(Protocol):
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...


class DocumentVectorStore(Protocol):
    async def initialize(self) -> None: ...
    async def delete_document(
        self, scope: VectorScope, knowledge_base_id: str, document_id: str
    ) -> int: ...
    async def insert(self, scope: VectorScope, chunks: Sequence[VectorChunk]) -> int: ...


class DocumentIndexHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: DocumentEmbeddingProvider,
        vector_store: DocumentVectorStore,
    ) -> None:
        self._sessions = session_factory
        self._embedding = embedding_provider
        self._vectors = vector_store

    async def __call__(self, context: BackgroundJobContext, payload: JsonValue) -> None:
        task_id, kb, document_id = _payload(payload)
        owner = context.owner_user_id
        log_lifecycle("document.indexing", resource_id=task_id, status="running")
        await context.raise_if_cancelled()
        async with transaction_scope(self._sessions) as session:
            tasks = SqliteDocumentIndexTaskRepository(session)
            documents = SqliteKnowledgeDocumentRepository(session)
            task = await tasks.get(owner, kb, document_id, task_id)
            document = await documents.get(owner, kb, document_id)
            if task is None or document is None:
                raise RuntimeError("索引任务或文档不存在")
            await tasks.transition(owner, kb, document_id, task_id, "running")
            await documents.set_index_status(owner, kb, document_id, "running", utc_now())
        try:
            chunks = chunk_document_text(document.indexable_text, document.chunking_config)
            await context.raise_if_cancelled()
            vectors = await self._embedding.embed_documents([chunk.text for chunk in chunks])
            _validate_vectors(chunks, vectors)
            await context.raise_if_cancelled()
            scope = VectorScope(owner, owner, (kb,))
            records = tuple(
                VectorChunk(
                    chunk_id=stable_chunk_id(document_id, chunk.index, chunk.text),
                    document_id=document_id,
                    knowledge_base_id=kb,
                    content=chunk.text,
                    source=document.filename,
                    created_at=document.uploaded_at,
                    metadata={**document.source_metadata, **chunk.metadata},
                    vector=vector,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            )
            await self._vectors.initialize()
            await context.raise_if_cancelled()
            await self._vectors.delete_document(scope, kb, document_id)
            await context.raise_if_cancelled()
            inserted = await self._vectors.insert(scope, records)
            if inserted != len(records):
                raise RuntimeError("Milvus insert 数量与 chunks 不一致")
            await context.raise_if_cancelled()
        except BackgroundJobCancelledError:
            log_lifecycle("document.indexing", resource_id=task_id, status="cancelled")
            async with transaction_scope(self._sessions) as session:
                await SqliteDocumentIndexTaskRepository(session).transition(
                    owner, kb, document_id, task_id, "cancelled"
                )
                await SqliteKnowledgeDocumentRepository(session).set_index_status(
                    owner, kb, document_id, "cancelled", utc_now()
                )
            raise
        except Exception as error:
            log_lifecycle(
                "document.indexing",
                resource_id=task_id,
                status="failed",
                category=type(error).__name__,
            )
            safe = redact_error(str(error), dump_json(payload))
            async with transaction_scope(self._sessions) as session:
                job = await SqliteBackgroundJobStore(session).get(owner, context.job_id)
                terminal = job is None or job.attempt >= job.max_attempts
                status = "failed" if terminal else "pending"
                await SqliteDocumentIndexTaskRepository(session).transition(
                    owner,
                    kb,
                    document_id,
                    task_id,
                    status,
                    failure_reason=safe if terminal else None,
                )
                await SqliteKnowledgeDocumentRepository(session).set_index_status(
                    owner, kb, document_id, status, utc_now()
                )
            raise
        async with transaction_scope(self._sessions) as session:
            await SqliteDocumentIndexTaskRepository(session).transition(
                owner, kb, document_id, task_id, "succeeded"
            )
            await SqliteKnowledgeDocumentRepository(session).set_index_status(
                owner, kb, document_id, "succeeded", utc_now()
            )
        log_lifecycle("document.indexing", resource_id=task_id, status="succeeded")


def _payload(payload: JsonValue) -> tuple[str, str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("索引任务 payload 必须是对象")
    values = tuple(payload.get(key) for key in ("taskId", "knowledgeBaseId", "documentId"))
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("索引任务 payload 缺少定位字段")
    return cast(tuple[str, str, str], values)


def _validate_vectors(chunks: Sequence[object], vectors: Sequence[Sequence[float]]) -> None:
    if len(vectors) != len(chunks):
        raise ValueError("Embedding 返回向量数量与 chunk 数量不一致")
    if any(len(vector) != 1024 for vector in vectors):
        raise ValueError("Embedding 向量必须为 1024 维")
