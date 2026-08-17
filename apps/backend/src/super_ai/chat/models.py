"""聊天会话不可变 records。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

from super_ai.project_config import JsonValue

ChatMessageRole: TypeAlias = Literal["user", "assistant", "system", "tool"]


@dataclass(frozen=True, slots=True)
class ChatSessionRecord:
    id: str
    owner_user_id: str
    title: str
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
