"""owner-scoped 知识文档 Repository Protocol。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from super_ai.knowledge.files import ExtractedDocument
from super_ai.knowledge.models import KnowledgeDocumentRecord


class DuplicateActiveDocumentHashError(Exception):
    """数据库唯一约束拒绝活动重复 hash。"""


class KnowledgeDocumentRepository(Protocol):
    async def list(
        self, owner_user_id: str, knowledge_base_id: str
    ) -> list[KnowledgeDocumentRecord]: ...

    async def get(
        self, owner_user_id: str, knowledge_base_id: str, document_id: str
    ) -> KnowledgeDocumentRecord | None: ...

    async def find_active_by_hash(
        self, owner_user_id: str, knowledge_base_id: str, sha256: str
    ) -> list[KnowledgeDocumentRecord]: ...

    async def add(
        self,
        owner_user_id: str,
        knowledge_base_id: str,
        extracted: ExtractedDocument,
        *,
        strategy: str,
        max_characters: int | None,
        overlap: int | None,
    ) -> KnowledgeDocumentRecord: ...

    async def soft_delete(
        self,
        owner_user_id: str,
        knowledge_base_id: str,
        document_id: str,
        deleted_at: datetime,
    ) -> KnowledgeDocumentRecord | None: ...
