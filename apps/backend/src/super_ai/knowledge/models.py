"""知识文档不可变 records。"""

from dataclasses import dataclass
from datetime import datetime

from super_ai.knowledge.chunking import ChunkingConfig


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
    index_status: str
    chunking_config: ChunkingConfig
    indexable_text: str
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
