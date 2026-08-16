from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.document_indexing.service import DocumentIndexTaskService
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.document_index_task_repositories import (
    SqliteDocumentIndexTaskRepository,
)
from super_ai.memory.extended_sqlite.knowledge_repositories import SqliteKnowledgeDocumentRepository
from super_ai.memory.sqlite import get_session


def get_document_index_task_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentIndexTaskService:
    return DocumentIndexTaskService(
        SqliteDocumentIndexTaskRepository(session),
        SqliteKnowledgeDocumentRepository(session),
        SqliteBackgroundJobStore(session),
    )
