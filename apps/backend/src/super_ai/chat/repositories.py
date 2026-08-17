"""owner-scoped 聊天 Repository Protocol。"""

from typing import Protocol

from super_ai.chat.models import (
    ChatMessageRole,
    ChatSessionDetailRecord,
    ChatSessionRecord,
)
from super_ai.project_config import JsonValue


class ChatRepository(Protocol):
    async def create(self, owner_user_id: str) -> ChatSessionDetailRecord: ...
    async def list(self, owner_user_id: str) -> list[ChatSessionRecord]: ...
    async def get(self, owner_user_id: str, session_id: str) -> ChatSessionDetailRecord | None: ...
    async def append(
        self,
        owner_user_id: str,
        session_id: str,
        role: ChatMessageRole,
        content: str,
        metadata: dict[str, JsonValue],
    ) -> ChatSessionDetailRecord | None: ...
    async def clear(
        self, owner_user_id: str, session_id: str
    ) -> ChatSessionDetailRecord | None: ...
    async def delete(self, owner_user_id: str, session_id: str) -> bool: ...
