"""默认知识库与文档管理用例。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid5

from super_ai.api_responses import AppError
from super_ai.knowledge.chunking import ChunkingConfig, ChunkPreview, DocumentChunkingService
from super_ai.knowledge.files import ExtractedDocument
from super_ai.knowledge.models import KnowledgeDocumentRecord
from super_ai.knowledge.repositories import (
    DuplicateActiveDocumentHashError,
    KnowledgeDocumentRepository,
)
from super_ai.memory.primitives import utc_now
from super_ai.project_config import JsonValue
from super_ai.tenancy.context import OwnerScope

_DEFAULT_KB_NAMESPACE = UUID("f7654427-2347-4f00-8cd1-12bd18b60d0c")


class KnowledgeConflictError(AppError):
    def __init__(self) -> None:
        super().__init__("BUSINESS_CONFLICT")


class DocumentVectorDeleter(Protocol):
    async def delete_document(
        self, scope: OwnerScope, knowledge_base_id: str, document_id: str
    ) -> None: ...


class NoIndexedVectorDeleter:
    async def delete_document(
        self, scope: OwnerScope, knowledge_base_id: str, document_id: str
    ) -> None:
        return None


def default_knowledge_base_id(user_id: str) -> str:
    if not user_id.strip():
        raise ValueError("user_id 不得为空")
    return f"kb_{uuid5(_DEFAULT_KB_NAMESPACE, user_id).hex}"


class KnowledgeDocumentService:
    def __init__(
        self,
        repository: KnowledgeDocumentRepository,
        vector_deleter: DocumentVectorDeleter,
        chunking: DocumentChunkingService | None = None,
    ) -> None:
        self._repository = repository
        self._vector_deleter = vector_deleter
        self._chunking = chunking or DocumentChunkingService()

    def knowledge_base(self, owner_user_id: str) -> str:
        return default_knowledge_base_id(owner_user_id)

    def ensure_knowledge_base(self, owner_user_id: str, knowledge_base_id: str) -> None:
        if knowledge_base_id != self.knowledge_base(owner_user_id):
            raise AppError("AUTH_FORBIDDEN")

    async def list(
        self, owner_user_id: str, knowledge_base_id: str
    ) -> list[KnowledgeDocumentRecord]:
        self.ensure_knowledge_base(owner_user_id, knowledge_base_id)
        return await self._repository.list(owner_user_id, knowledge_base_id)

    async def get(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> KnowledgeDocumentRecord:
        self.ensure_knowledge_base(owner_user_id, knowledge_base_id)
        record = await self._repository.get(owner_user_id, knowledge_base_id, document_id)
        if record is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return record

    async def upload(
        self,
        owner_user_id: str,
        knowledge_base_id: str,
        extracted: ExtractedDocument,
        config: ChunkingConfig,
        *,
        overwrite: bool = False,
        source_metadata: dict[str, JsonValue] | None = None,
    ) -> KnowledgeDocumentRecord:
        self.ensure_knowledge_base(owner_user_id, knowledge_base_id)
        duplicates = await self._repository.find_active_by_hash(
            owner_user_id, knowledge_base_id, extracted.sha256
        )
        if duplicates and not overwrite:
            raise KnowledgeConflictError
        scope = OwnerScope(tenant_id=owner_user_id, owner_user_id=owner_user_id)
        for duplicate in duplicates:
            await self._vector_deleter.delete_document(scope, knowledge_base_id, duplicate.id)
            await self._repository.soft_delete(
                owner_user_id, knowledge_base_id, duplicate.id, utc_now()
            )
        try:
            return await self._repository.add(
                owner_user_id,
                knowledge_base_id,
                extracted,
                strategy=config.strategy,
                max_characters=config.max_characters,
                overlap=config.overlap,
                source_metadata=source_metadata or {},
            )
        except DuplicateActiveDocumentHashError as error:
            raise KnowledgeConflictError from error

    async def delete(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> KnowledgeDocumentRecord:
        record = await self.get(owner_user_id, knowledge_base_id, document_id)
        scope = OwnerScope(tenant_id=owner_user_id, owner_user_id=owner_user_id)
        await self._vector_deleter.delete_document(scope, knowledge_base_id, document_id)
        deleted = await self._repository.soft_delete(
            owner_user_id, knowledge_base_id, document_id, utc_now()
        )
        if deleted is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return record

    async def preview(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> ChunkPreview:
        record = await self.get(owner_user_id, knowledge_base_id, document_id)
        return self._chunking.preview(record.indexable_text, record.chunking_config)
