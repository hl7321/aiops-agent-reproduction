"""知识文档 FastAPI dependencies。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.knowledge.service import KnowledgeDocumentService, NoIndexedVectorDeleter
from super_ai.memory.extended_sqlite.knowledge_repositories import (
    SqliteKnowledgeDocumentRepository,
)
from super_ai.memory.sqlite import get_session


def get_knowledge_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KnowledgeDocumentService:
    return KnowledgeDocumentService(
        SqliteKnowledgeDocumentRepository(session), NoIndexedVectorDeleter()
    )
