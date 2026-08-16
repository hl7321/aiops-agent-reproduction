from super_ai.api_responses import AppError
from super_ai.background_jobs.models import NewBackgroundJob
from super_ai.document_indexing.models import (
    DocumentIndexStatus,
    DocumentIndexTaskRecord,
    NewDocumentIndexTask,
)
from super_ai.knowledge.service import default_knowledge_base_id
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.document_index_task_repositories import (
    SqliteDocumentIndexTaskRepository,
)
from super_ai.memory.extended_sqlite.knowledge_repositories import SqliteKnowledgeDocumentRepository


class DocumentIndexTaskService:
    def __init__(
        self,
        tasks: SqliteDocumentIndexTaskRepository,
        documents: SqliteKnowledgeDocumentRepository,
        jobs: SqliteBackgroundJobStore,
    ) -> None:
        self._tasks = tasks
        self._documents = documents
        self._jobs = jobs

    def _ensure_kb(self, owner_user_id: str, kb: str) -> None:
        if default_knowledge_base_id(owner_user_id) != kb:
            raise AppError("AUTH_FORBIDDEN")

    async def create(
        self, owner_user_id: str, kb: str, document_id: str, *, retry_of: str | None = None
    ) -> DocumentIndexTaskRecord:
        self._ensure_kb(owner_user_id, kb)
        document = await self._documents.get(owner_user_id, kb, document_id)
        if document is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        if await self._tasks.has_active(owner_user_id, kb, document_id):
            raise AppError("BUSINESS_CONFLICT")
        if retry_of is not None:
            source = await self._tasks.get(owner_user_id, kb, document_id, retry_of)
            if source is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            if source.status not in ("failed", "cancelled"):
                raise AppError("BUSINESS_RULE_VIOLATION")
        task = await self._tasks.create(
            owner_user_id, NewDocumentIndexTask(kb, document_id, retry_of_task_id=retry_of)
        )
        await self._jobs.enqueue(
            owner_user_id,
            NewBackgroundJob(
                kind="document.index",
                resource_type="document_index_task",
                resource_id=task.id,
                payload={"taskId": task.id, "knowledgeBaseId": kb, "documentId": document_id},
                max_attempts=3,
                timeout_seconds=600,
            ),
        )
        return task

    async def get(
        self, owner_user_id: str, kb: str, document_id: str, task_id: str
    ) -> DocumentIndexTaskRecord:
        self._ensure_kb(owner_user_id, kb)
        task = await self._tasks.get(owner_user_id, kb, document_id, task_id)
        if task is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        job = await self._jobs.get_by_resource(owner_user_id, "document_index_task", task.id)
        if job is not None:
            status_map: dict[str, DocumentIndexStatus] = {
                "queued": "pending",
                "running": "running",
                "succeeded": "succeeded",
                "failed": "failed",
                "cancelled": "cancelled",
            }
            mapped_status = status_map[job.status]
        else:
            mapped_status = None
        if job is not None and mapped_status is not None and task.status != mapped_status:
            task = await self._tasks.transition(
                owner_user_id,
                kb,
                document_id,
                task.id,
                mapped_status,
                failure_reason=job.error_message if mapped_status == "failed" else None,
                now=job.updated_at,
            )
            await self._documents.set_index_status(
                owner_user_id, kb, document_id, mapped_status, job.updated_at
            )
            if task is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return task

    async def retry(
        self, owner_user_id: str, kb: str, document_id: str, task_id: str
    ) -> DocumentIndexTaskRecord:
        return await self.create(owner_user_id, kb, document_id, retry_of=task_id)
