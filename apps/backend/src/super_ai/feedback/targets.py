"""四类反馈目标的 owner-scoped resolver。"""

from super_ai.aiops.repositories import DiagnosticRepository
from super_ai.api_responses import AppError
from super_ai.chat.repositories import ChatRepository
from super_ai.project_config import JsonValue


class RepositoryFeedbackTargetResolver:
    def __init__(self, chats: ChatRepository, diagnostics: DiagnosticRepository) -> None:
        self._chats = chats
        self._diagnostics = diagnostics

    async def validate(
        self,
        owner_user_id: str,
        target_type: str,
        target_id: str,
        subject_id: str | None,
    ) -> None:
        if target_type in {"chat_message", "citation"}:
            message = await self._chats.get_message(owner_user_id, target_id)
            if message is None or message.role != "assistant":
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            if target_type == "citation" and not self._has_citation(
                message.metadata, subject_id
            ):
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            return
        if target_type == "diagnostic_step":
            if await self._diagnostics.get_step(owner_user_id, target_id) is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            return
        if target_type == "diagnostic_report":
            if await self._diagnostics.get_report(owner_user_id, target_id) is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            return
        raise ValueError("targetType 不受支持")

    async def validate_parent(
        self, owner_user_id: str, target_type: str, target_id: str
    ) -> None:
        if target_type == "citation":
            await self._validate_citation_parent(owner_user_id, target_id)
            return
        await self.validate(owner_user_id, target_type, target_id, None)

    async def _validate_citation_parent(self, owner_user_id: str, target_id: str) -> None:
        message = await self._chats.get_message(owner_user_id, target_id)
        if message is None or message.role != "assistant":
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")

    @staticmethod
    def _has_citation(metadata: dict[str, JsonValue], subject_id: str | None) -> bool:
        if subject_id is None:
            return False
        references = metadata.get("references")
        if not isinstance(references, list):
            return False
        for item in references:
            if isinstance(item, dict) and item.get("chunkId") == subject_id:
                return True
        return False
