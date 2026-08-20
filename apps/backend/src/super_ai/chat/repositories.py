"""owner-scoped 聊天 Repository Protocol。"""

import builtins
from datetime import datetime
from typing import Protocol

from super_ai.chat.models import (
    ChatMemoryMode,
    ChatMessageRole,
    ChatSessionDetailRecord,
    ChatSessionRecord,
)
from super_ai.project_config import JsonValue


class ChatRepository(Protocol):
    async def create(self, owner_user_id: str) -> ChatSessionDetailRecord: ...
    async def list(self, owner_user_id: str) -> list[ChatSessionRecord]: ...
    async def list_details(
        self, owner_user_id: str
    ) -> builtins.list[ChatSessionDetailRecord]: ...
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
    async def update_memory_mode(
        self, owner_user_id: str, session_id: str, memory_mode: ChatMemoryMode
    ) -> ChatSessionDetailRecord | None: ...
    async def update_context_tokens(
        self, owner_user_id: str, session_id: str, context_tokens: int
    ) -> bool: ...
    async def commit_compaction(
        self,
        owner_user_id: str,
        session_id: str,
        *,
        expected_compacted_message_count: int,
        compacted_message_count: int,
        memory_summary: str,
        compacted_at: datetime,
    ) -> bool: ...
    async def delete(self, owner_user_id: str, session_id: str) -> bool: ...
