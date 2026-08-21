"""知识文档 Repository 的 SQLite adapter。"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.api_contracts import DocumentIndexStatus
from super_ai.knowledge.chunking import ChunkingConfig, ChunkingStrategy
from super_ai.knowledge.files import ExtractedDocument
from super_ai.knowledge.models import KnowledgeDocumentRecord
from super_ai.knowledge.repositories import DuplicateActiveDocumentHashError
from super_ai.memory.extended_sqlite.knowledge_models import KnowledgeDocumentModel
from super_ai.memory.primitives import new_id, utc_now
from super_ai.project_config import JsonValue


class SqliteKnowledgeDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self, owner_user_id: str, knowledge_base_id: str
    ) -> list[KnowledgeDocumentRecord]:
        models = (
            await self._session.scalars(
                select(KnowledgeDocumentModel)
                .where(
                    KnowledgeDocumentModel.owner_user_id == owner_user_id,
                    KnowledgeDocumentModel.knowledge_base_id == knowledge_base_id,
                    KnowledgeDocumentModel.deleted_at.is_(None),
                )
                .order_by(KnowledgeDocumentModel.uploaded_at.desc())
            )
        ).all()
        return [_record(model) for model in models]

    async def get(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> KnowledgeDocumentRecord | None:
        model = await self._session.scalar(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.owner_user_id == owner_user_id,
                KnowledgeDocumentModel.knowledge_base_id == knowledge_base_id,
                KnowledgeDocumentModel.id == document_id,
                KnowledgeDocumentModel.deleted_at.is_(None),
            )
        )
        return _record(model) if model is not None else None

    async def list_retrieval_corpus(
        self,
        owner_user_id: str,
        knowledge_base_ids: tuple[str, ...],
        *,
        document_ids: tuple[str, ...] | None = None,
    ) -> list[KnowledgeDocumentRecord]:
        if not owner_user_id.strip():
            raise ValueError("owner_user_id 不得为空")
        if not knowledge_base_ids or document_ids == ():
            return []
        conditions = [
            KnowledgeDocumentModel.owner_user_id == owner_user_id,
            KnowledgeDocumentModel.knowledge_base_id.in_(knowledge_base_ids),
            KnowledgeDocumentModel.index_status == "succeeded",
            KnowledgeDocumentModel.deleted_at.is_(None),
        ]
        if document_ids is not None:
            conditions.append(KnowledgeDocumentModel.id.in_(document_ids))
        models = (
            await self._session.scalars(
                select(KnowledgeDocumentModel)
                .where(*conditions)
                .order_by(KnowledgeDocumentModel.id)
            )
        ).all()
        return [_record(model) for model in models]

    async def find_active_by_hash(
        self, owner_user_id: str, knowledge_base_id: str, sha256: str
    ) -> list[KnowledgeDocumentRecord]:
        models = (
            await self._session.scalars(
                select(KnowledgeDocumentModel).where(
                    KnowledgeDocumentModel.owner_user_id == owner_user_id,
                    KnowledgeDocumentModel.knowledge_base_id == knowledge_base_id,
                    KnowledgeDocumentModel.sha256 == sha256,
                    KnowledgeDocumentModel.deleted_at.is_(None),
                )
            )
        ).all()
        return [_record(model) for model in models]

    async def add(
        self,
        owner_user_id: str,
        knowledge_base_id: str,
        extracted: ExtractedDocument,
        *,
        strategy: str,
        max_characters: int | None,
        overlap: int | None,
        source_metadata: dict[str, JsonValue] | None = None,
    ) -> KnowledgeDocumentRecord:
        now = utc_now()
        model = KnowledgeDocumentModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            filename=extracted.filename,
            size_bytes=extracted.size_bytes,
            mime_type=extracted.mime_type,
            sha256=extracted.sha256,
            uploaded_at=now,
            index_status="pending",
            chunking_strategy=strategy,
            max_characters=max_characters,
            overlap=overlap,
            indexable_text=extracted.text,
            source_metadata=source_metadata or {},
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise DuplicateActiveDocumentHashError from error
        return _record(model)

    async def soft_delete(
        self,
        owner_user_id: str,
        knowledge_base_id: str,
        document_id: str,
        deleted_at: datetime,
    ) -> KnowledgeDocumentRecord | None:
        model = await self._session.scalar(
            update(KnowledgeDocumentModel)
            .where(
                KnowledgeDocumentModel.owner_user_id == owner_user_id,
                KnowledgeDocumentModel.knowledge_base_id == knowledge_base_id,
                KnowledgeDocumentModel.id == document_id,
                KnowledgeDocumentModel.deleted_at.is_(None),
            )
            .values(deleted_at=deleted_at, updated_at=deleted_at)
            .returning(KnowledgeDocumentModel)
        )
        return _record(model) if model is not None else None

    async def set_index_status(
        self,
        owner_user_id: str,
        knowledge_base_id: str,
        document_id: str,
        status: DocumentIndexStatus,
        updated_at: datetime,
    ) -> KnowledgeDocumentRecord | None:
        model = await self._session.scalar(
            update(KnowledgeDocumentModel)
            .where(
                KnowledgeDocumentModel.owner_user_id == owner_user_id,
                KnowledgeDocumentModel.knowledge_base_id == knowledge_base_id,
                KnowledgeDocumentModel.id == document_id,
                KnowledgeDocumentModel.deleted_at.is_(None),
            )
            .values(index_status=status, updated_at=updated_at)
            .returning(KnowledgeDocumentModel)
        )
        return _record(model) if model is not None else None


def _record(model: KnowledgeDocumentModel) -> KnowledgeDocumentRecord:
    strategy = cast(ChunkingStrategy, model.chunking_strategy)
    values: dict[str, object] = {"strategy": strategy}
    if strategy == "fixed-character":
        values.update(maxCharacters=model.max_characters, overlap=model.overlap)
    return KnowledgeDocumentRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        knowledge_base_id=model.knowledge_base_id,
        filename=model.filename,
        size_bytes=model.size_bytes,
        mime_type=model.mime_type,
        sha256=model.sha256,
        uploaded_at=model.uploaded_at,
        index_status=cast(DocumentIndexStatus, model.index_status),
        chunking_config=ChunkingConfig.model_validate(values),
        indexable_text=model.indexable_text,
        source_metadata=model.source_metadata,
        deleted_at=model.deleted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
