from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.retrieval.corpus import SqliteRetrievalCorpusSource
from super_ai.retrieval.service import (
    KnowledgeRetrievalService,
    RetrievalProvider,
    RetrievalVectorStore,
)


def create_knowledge_retrieval_service(
    session_factory: async_sessionmaker[AsyncSession],
    provider: RetrievalProvider,
    vector_store: RetrievalVectorStore,
) -> KnowledgeRetrievalService:
    return KnowledgeRetrievalService(
        SqliteRetrievalCorpusSource(session_factory), provider, vector_store
    )
