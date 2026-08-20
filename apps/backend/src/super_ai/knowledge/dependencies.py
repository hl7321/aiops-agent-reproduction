"""知识文档 FastAPI dependencies。"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.knowledge.service import (
    DocumentVectorDeleter,
    KnowledgeDocumentService,
    NoIndexedVectorDeleter,
)
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


def create_knowledge_service_dependency(
    vector_deleter: DocumentVectorDeleter,
) -> Callable[[AsyncSession], KnowledgeDocumentService]:
    """为 configured app 绑定真实、仍保持网络 lazy 的向量删除端口。"""

    def dependency(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> KnowledgeDocumentService:
        return KnowledgeDocumentService(
            SqliteKnowledgeDocumentRepository(session), vector_deleter
        )

    return dependency
