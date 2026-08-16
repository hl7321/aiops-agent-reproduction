import asyncio
from collections.abc import Sequence

import pytest

from super_ai.background_jobs.handlers import (
    BackgroundJobCancelledError,
    BackgroundJobContext,
    HandlerRegistry,
)
from super_ai.background_jobs.models import NewBackgroundJob
from super_ai.background_jobs.runtime import BackgroundJobWorker, WorkerSettings
from super_ai.document_indexing.handler import DocumentIndexHandler
from super_ai.document_indexing.models import NewDocumentIndexTask
from super_ai.knowledge.files import validate_and_extract
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.document_index_task_repositories import (
    SqliteDocumentIndexTaskRepository,
)
from super_ai.memory.extended_sqlite.knowledge_repositories import SqliteKnowledgeDocumentRepository
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database
from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.records import VectorChunk


class RecordingEmbedder:
    def __init__(self, *, invalid: bool = False) -> None:
        self.batches: list[list[str]] = []
        self.invalid = invalid

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        results: list[list[float]] = []
        values = list(texts)
        for offset in range(0, len(values), 10):
            batch = values[offset : offset + 10]
            self.batches.append(batch)
            results.extend([[float(offset + index)] * 1024 for index in range(len(batch))])
        if self.invalid:
            return results[:-1]
        return results


class FailingEmbedder:
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("apiKey=super-secret provider unavailable")


class RecordingVectorStore:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.inserted: list[VectorChunk] = []
        self.scope: VectorScope | None = None

    async def initialize(self) -> None:
        self.events.append("initialize")

    async def delete_document(
        self, scope: VectorScope, knowledge_base_id: str, document_id: str
    ) -> int:
        self.events.append(f"delete:{knowledge_base_id}:{document_id}")
        self.scope = scope
        return 2

    async def insert(self, scope: VectorScope, chunks: Sequence[VectorChunk]) -> int:
        self.events.append("insert")
        self.scope = scope
        self.inserted = list(chunks)
        return len(chunks)


async def _seed(url: str) -> tuple[PersistenceRuntime, str, str, str]:
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    kb = "kb-a"
    async with transaction_scope(runtime.session_factory) as session:
        now = utc_now()
        session.add(
            UserModel(
                id="user-a",
                email="a@example.com",
                password_hash="x",
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()
        document = await SqliteKnowledgeDocumentRepository(session).add(
            "user-a",
            kb,
            validate_and_extract("source.md", "text/markdown", b"abcdefghijklmnopqrstuvw"),
            strategy="fixed-character",
            max_characters=1,
            overlap=0,
        )
        task = await SqliteDocumentIndexTaskRepository(session).create(
            "user-a", NewDocumentIndexTask(kb, document.id)
        )
    return runtime, kb, document.id, task.id


async def test_handler_batches_embedding_and_inserts_all_chunks_once(
    indexing_database_url: str,
) -> None:
    runtime, kb, document_id, task_id = await _seed(indexing_database_url)
    embedder = RecordingEmbedder()
    vectors = RecordingVectorStore()
    handler = DocumentIndexHandler(runtime.session_factory, embedder, vectors)
    context = BackgroundJobContext("job-a", "user-a", lambda: _false())
    try:
        await handler(
            context, {"taskId": task_id, "knowledgeBaseId": kb, "documentId": document_id}
        )
        assert [len(batch) for batch in embedder.batches] == [10, 10, 3]
        assert vectors.events == ["initialize", f"delete:{kb}:{document_id}", "insert"]
        assert len(vectors.inserted) == 23
        assert [chunk.content for chunk in vectors.inserted] == list("abcdefghijklmnopqrstuvw")
        assert len({chunk.chunk_id for chunk in vectors.inserted}) == 23
        first = vectors.inserted[0]
        assert first.document_id == document_id and first.knowledge_base_id == kb
        assert first.source == "source.md"
        assert first.metadata == {"index": 0, "strategy": "fixed-character"}
        assert vectors.scope is not None
        assert vectors.scope.tenant_id == vectors.scope.owner_user_id == "user-a"
        async with transaction_scope(runtime.session_factory) as session:
            task = await SqliteDocumentIndexTaskRepository(session).get(
                "user-a", kb, document_id, task_id
            )
            document = await SqliteKnowledgeDocumentRepository(session).get(
                "user-a", kb, document_id
            )
            assert task is not None and task.status == "succeeded"
            assert document is not None and document.index_status == "succeeded"
    finally:
        await runtime.close()


async def test_invalid_embedding_fails_before_milvus_and_does_not_mark_success(
    indexing_database_url: str,
) -> None:
    runtime, kb, document_id, task_id = await _seed(indexing_database_url)
    vectors = RecordingVectorStore()
    handler = DocumentIndexHandler(
        runtime.session_factory, RecordingEmbedder(invalid=True), vectors
    )
    context = BackgroundJobContext("job-a", "user-a", lambda: _false())
    try:
        with pytest.raises(Exception, match="数量"):
            await handler(
                context, {"taskId": task_id, "knowledgeBaseId": kb, "documentId": document_id}
            )
        assert vectors.events == []
        async with transaction_scope(runtime.session_factory) as session:
            task = await SqliteDocumentIndexTaskRepository(session).get(
                "user-a", kb, document_id, task_id
            )
            document = await SqliteKnowledgeDocumentRepository(session).get(
                "user-a", kb, document_id
            )
            assert task is not None and task.status == "failed"
            assert document is not None and document.index_status == "failed"
    finally:
        await runtime.close()


async def test_terminal_provider_failure_is_redacted_before_persistence(
    indexing_database_url: str,
) -> None:
    runtime, kb, document_id, task_id = await _seed(indexing_database_url)
    handler = DocumentIndexHandler(
        runtime.session_factory, FailingEmbedder(), RecordingVectorStore()
    )
    context = BackgroundJobContext("job-a", "user-a", lambda: _false())
    try:
        with pytest.raises(RuntimeError, match="super-secret"):
            await handler(
                context, {"taskId": task_id, "knowledgeBaseId": kb, "documentId": document_id}
            )
        async with transaction_scope(runtime.session_factory) as session:
            task = await SqliteDocumentIndexTaskRepository(session).get(
                "user-a", kb, document_id, task_id
            )
            document = await SqliteKnowledgeDocumentRepository(session).get(
                "user-a", kb, document_id
            )
            assert task is not None and task.status == "failed"
            assert task.failure_reason == "apiKey=[redacted] provider unavailable"
            assert "super-secret" not in task.failure_reason
            assert document is not None and document.index_status == "failed"
    finally:
        await runtime.close()


async def test_cancelled_handler_marks_task_and_document_cancelled(
    indexing_database_url: str,
) -> None:
    runtime, kb, document_id, task_id = await _seed(indexing_database_url)
    vectors = RecordingVectorStore()
    checks = 0

    async def cancel_after_start() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    handler = DocumentIndexHandler(runtime.session_factory, RecordingEmbedder(), vectors)
    try:
        with pytest.raises(BackgroundJobCancelledError):
            await handler(
                BackgroundJobContext("job-a", "user-a", cancel_after_start),
                {"taskId": task_id, "knowledgeBaseId": kb, "documentId": document_id},
            )
        assert vectors.events == []
        async with transaction_scope(runtime.session_factory) as session:
            task = await SqliteDocumentIndexTaskRepository(session).get(
                "user-a", kb, document_id, task_id
            )
            document = await SqliteKnowledgeDocumentRepository(session).get(
                "user-a", kb, document_id
            )
            assert task is not None and task.status == "cancelled"
            assert document is not None and document.index_status == "cancelled"
    finally:
        await runtime.close()


async def test_expired_worker_lease_resumes_same_domain_task(indexing_database_url: str) -> None:
    runtime, kb, document_id, task_id = await _seed(indexing_database_url)
    vectors = RecordingVectorStore()
    registry = HandlerRegistry()
    registry.register(
        "document.index",
        DocumentIndexHandler(runtime.session_factory, RecordingEmbedder(), vectors),
    )
    try:
        async with transaction_scope(runtime.session_factory) as session:
            job = await SqliteBackgroundJobStore(session).enqueue(
                "user-a",
                NewBackgroundJob(
                    kind="document.index",
                    resource_type="document_index_task",
                    resource_id=task_id,
                    payload={
                        "taskId": task_id,
                        "knowledgeBaseId": kb,
                        "documentId": document_id,
                    },
                    max_attempts=2,
                ),
            )
        async with transaction_scope(runtime.session_factory) as session:
            claimed = await SqliteBackgroundJobStore(session).claim_next(
                "dead-worker", now=utc_now(), lease_seconds=0.02
            )
            assert claimed is not None and claimed.id == job.id
        await asyncio.sleep(0.03)
        worker = BackgroundJobWorker(
            runtime.session_factory,
            registry,
            WorkerSettings(concurrency=1, lease_seconds=1, poll_interval_seconds=0.01),
        )
        await worker.start()
        task = None
        for _ in range(100):
            async with transaction_scope(runtime.session_factory) as session:
                task = await SqliteDocumentIndexTaskRepository(session).get(
                    "user-a", kb, document_id, task_id
                )
            if task is not None and task.status == "succeeded":
                break
            await asyncio.sleep(0.01)
        await worker.stop()
        assert task is not None and task.id == task_id and task.status == "succeeded"
        assert vectors.events[-1] == "insert"
    finally:
        await runtime.close()


async def _false() -> bool:
    return False
