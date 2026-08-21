from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.knowledge.chunk_identity import stable_chunk_id
from super_ai.knowledge.chunking import chunk_document_text
from super_ai.memory.extended_sqlite.knowledge_repositories import SqliteKnowledgeDocumentRepository
from super_ai.memory.sqlite import transaction_scope
from super_ai.retrieval.models import RetrievalChunk


class SqliteRetrievalCorpusSource:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def load(
        self,
        owner_user_id: str,
        knowledge_base_ids: tuple[str, ...],
        document_ids: tuple[str, ...] | None,
    ) -> tuple[RetrievalChunk, ...]:
        async with transaction_scope(self._sessions) as session:
            documents = await SqliteKnowledgeDocumentRepository(session).list_retrieval_corpus(
                owner_user_id, knowledge_base_ids, document_ids=document_ids
            )
        return tuple(
            RetrievalChunk(
                chunk_id=stable_chunk_id(document.id, chunk.index, chunk.text),
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                source=document.filename,
                excerpt=chunk.text,
                metadata={**document.source_metadata, **chunk.metadata},
            )
            for document in documents
            for chunk in chunk_document_text(document.indexable_text, document.chunking_config)
        )
