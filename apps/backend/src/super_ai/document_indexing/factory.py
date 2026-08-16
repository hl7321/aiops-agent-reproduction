from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.background_jobs.handlers import BackgroundJobHandler
from super_ai.document_indexing.handler import (
    DocumentEmbeddingProvider,
    DocumentIndexHandler,
    DocumentVectorStore,
)
from super_ai.llm.config import LlmSettings
from super_ai.llm.provider import QwenOpenAIProvider
from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.config import VectorStoreSettings

EmbeddingProviderFactory = Callable[[], DocumentEmbeddingProvider]
VectorStoreFactory = Callable[[], DocumentVectorStore]


def create_document_index_handler_factory(
    embedding_provider_factory: EmbeddingProviderFactory,
    vector_store_factory: VectorStoreFactory,
) -> Callable[[async_sessionmaker[AsyncSession]], tuple[str, BackgroundJobHandler]]:
    def factory(
        sessions: async_sessionmaker[AsyncSession],
    ) -> tuple[str, BackgroundJobHandler]:
        handler = DocumentIndexHandler(
            sessions, embedding_provider_factory(), vector_store_factory()
        )
        return "document.index", handler

    return factory


def create_configured_document_index_handler_factory(
    llm_settings: LlmSettings,
    vector_store_settings: VectorStoreSettings,
) -> Callable[[async_sessionmaker[AsyncSession]], tuple[str, BackgroundJobHandler]]:
    return create_document_index_handler_factory(
        lambda: QwenOpenAIProvider(llm_settings),
        lambda: MilvusVectorStore(vector_store_settings),
    )
