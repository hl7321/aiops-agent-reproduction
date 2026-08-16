from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

DocumentIndexStatus: TypeAlias = Literal["pending", "running", "succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class NewDocumentIndexTask:
    knowledge_base_id: str
    document_id: str
    retry_of_task_id: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentIndexTaskRecord:
    id: str
    owner_user_id: str
    knowledge_base_id: str
    document_id: str
    status: DocumentIndexStatus
    failure_reason: str | None
    retry_of_task_id: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
