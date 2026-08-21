"""知识文档不可变 records。"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from super_ai.knowledge.chunking import ChunkingConfig
from super_ai.project_config import JsonValue

if TYPE_CHECKING:
    from super_ai.api_contracts import DocumentIndexStatus


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentRecord:
    id: str
    owner_user_id: str
    knowledge_base_id: str
    filename: str
    size_bytes: int
    mime_type: str
    sha256: str
    uploaded_at: datetime
    index_status: "DocumentIndexStatus"
    chunking_config: ChunkingConfig
    indexable_text: str
    source_metadata: dict[str, JsonValue]
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
