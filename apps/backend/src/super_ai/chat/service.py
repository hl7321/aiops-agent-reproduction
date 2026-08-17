"""聊天会话领域服务。"""

from super_ai.api_responses import AppError
from super_ai.chat.models import ChatMessageRole, ChatSessionDetailRecord, ChatSessionRecord
from super_ai.chat.repositories import ChatRepository
from super_ai.project_config import JsonValue


class ChatService:
    def __init__(self, repository: ChatRepository) -> None:
        self._repository = repository

    async def create(self, owner_user_id: str) -> ChatSessionDetailRecord:
        return await self._repository.create(owner_user_id)

    async def list(self, owner_user_id: str) -> list[ChatSessionRecord]:
        return await self._repository.list(owner_user_id)

    async def get(self, owner_user_id: str, session_id: str) -> ChatSessionDetailRecord:
        return self._required(await self._repository.get(owner_user_id, session_id))

    async def append(
        self, owner_user_id: str, session_id: str, role: ChatMessageRole,
        content: str, metadata: dict[str, JsonValue],
    ) -> ChatSessionDetailRecord:
        return self._required(
            await self._repository.append(owner_user_id, session_id, role, content, metadata)
        )

    async def clear(self, owner_user_id: str, session_id: str) -> ChatSessionDetailRecord:
        return self._required(await self._repository.clear(owner_user_id, session_id))

    async def delete(self, owner_user_id: str, session_id: str) -> None:
        if not await self._repository.delete(owner_user_id, session_id):
            raise AppError("AUTH_FORBIDDEN")

    @staticmethod
    def _required(detail: ChatSessionDetailRecord | None) -> ChatSessionDetailRecord:
        if detail is None:
            raise AppError("AUTH_FORBIDDEN")
        return detail
