from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.document_indexing.models import (
    DocumentIndexStatus,
    DocumentIndexTaskRecord,
    NewDocumentIndexTask,
)
from super_ai.memory.extended_sqlite.document_index_task_models import DocumentIndexTaskModel
from super_ai.memory.primitives import new_id, utc_now


class SqliteDocumentIndexTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, owner_user_id: str, task: NewDocumentIndexTask
    ) -> DocumentIndexTaskRecord:
        now = utc_now()
        model = DocumentIndexTaskModel(
            id=new_id(), owner_user_id=owner_user_id,
            knowledge_base_id=task.knowledge_base_id, document_id=task.document_id,
            status="pending", failure_reason=None, retry_of_task_id=task.retry_of_task_id,
            created_at=now, updated_at=now, started_at=None, completed_at=None,
        )
        self._session.add(model)
        await self._session.flush()
        return _record(model)

    async def get(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str, task_id: str
    ) -> DocumentIndexTaskRecord | None:
        model = await self._session.scalar(select(DocumentIndexTaskModel).where(
            DocumentIndexTaskModel.owner_user_id == owner_user_id,
            DocumentIndexTaskModel.knowledge_base_id == knowledge_base_id,
            DocumentIndexTaskModel.document_id == document_id,
            DocumentIndexTaskModel.id == task_id,
        ))
        return _record(model) if model is not None else None

    async def has_active(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> bool:
        model = await self._session.scalar(select(DocumentIndexTaskModel.id).where(
            DocumentIndexTaskModel.owner_user_id == owner_user_id,
            DocumentIndexTaskModel.knowledge_base_id == knowledge_base_id,
            DocumentIndexTaskModel.document_id == document_id,
            DocumentIndexTaskModel.status.in_(("pending", "running")),
        ).limit(1))
        return model is not None

    async def transition(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str, task_id: str,
        status: DocumentIndexStatus, *, failure_reason: str | None = None,
        now: datetime | None = None,
    ) -> DocumentIndexTaskRecord | None:
        model = await self._session.scalar(select(DocumentIndexTaskModel).where(
            DocumentIndexTaskModel.owner_user_id == owner_user_id,
            DocumentIndexTaskModel.knowledge_base_id == knowledge_base_id,
            DocumentIndexTaskModel.document_id == document_id,
            DocumentIndexTaskModel.id == task_id,
        ))
        if model is None:
            return None
        changed = now or utc_now()
        model.status = status
        model.failure_reason = failure_reason
        model.updated_at = changed
        if status == "running" and model.started_at is None:
            model.started_at = changed
        if status in ("succeeded", "failed", "cancelled"):
            model.completed_at = changed
        await self._session.flush()
        return _record(model)


def _record(model: DocumentIndexTaskModel) -> DocumentIndexTaskRecord:
    return DocumentIndexTaskRecord(
        id=model.id, owner_user_id=model.owner_user_id,
        knowledge_base_id=model.knowledge_base_id, document_id=model.document_id,
        status=cast(DocumentIndexStatus, model.status), failure_reason=model.failure_reason,
        retry_of_task_id=model.retry_of_task_id, created_at=model.created_at,
        updated_at=model.updated_at, started_at=model.started_at, completed_at=model.completed_at,
    )
