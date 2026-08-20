"""聊天会话不可变 records。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

from super_ai.project_config import JsonValue

ChatMessageRole: TypeAlias = Literal["user", "assistant", "system", "tool"]
ChatMemoryMode: TypeAlias = Literal["every_30_turns", "context_70_percent", "manual"]


@dataclass(frozen=True, slots=True)
class ChatSessionRecord:
    id: str
    owner_user_id: str
    title: str
    memory_mode: ChatMemoryMode
    memory_summary: str | None
    compacted_message_count: int
    context_tokens: int
    last_compacted_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChatMessageRecord:
    id: str
    owner_user_id: str
    session_id: str
    role: ChatMessageRole
    content: str
    sequence: int
    metadata: dict[str, JsonValue]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChatSessionDetailRecord:
    session: ChatSessionRecord
    messages: tuple[ChatMessageRecord, ...]
