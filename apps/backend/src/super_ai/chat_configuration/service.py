from sqlalchemy.exc import IntegrityError

from super_ai.api_responses import AppError
from super_ai.chat_configuration.models import ChatConfigurationRecord
from super_ai.chat_configuration.parser import SkillDocumentValidationError, parse_skill_document
from super_ai.chat_configuration.repositories import ChatConfigurationRepository


class ChatConfigurationService:
    def __init__(self, repository: ChatConfigurationRepository) -> None:
        self._repository = repository

    async def get(self, owner_user_id: str) -> ChatConfigurationRecord:
        return await self._repository.get(owner_user_id)

    async def update(
        self, owner_user_id: str, prompt_id: str | None, skill_ids: list[str]
    ) -> ChatConfigurationRecord:
        if not await self._repository.replace_selection(owner_user_id, prompt_id, skill_ids):
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return await self.get(owner_user_id)

    async def create_prompt(
        self, owner_user_id: str, label: str, content: str
    ) -> ChatConfigurationRecord:
        await self._repository.create_prompt(owner_user_id, label, content)
        return await self.get(owner_user_id)

    async def update_prompt(
        self, owner_user_id: str, prompt_id: str, label: str, content: str
    ) -> ChatConfigurationRecord:
        if await self._repository.update_prompt(owner_user_id, prompt_id, label, content) is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return await self.get(owner_user_id)

    async def delete_prompt(self, owner_user_id: str, prompt_id: str) -> None:
        if not await self._repository.delete_prompt(owner_user_id, prompt_id):
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")

    async def upload_skill(
        self, owner_user_id: str, filename: str, payload: bytes
    ) -> ChatConfigurationRecord:
        try:
            parsed = parse_skill_document(filename, payload)
            await self._repository.create_skill(owner_user_id, parsed)
        except SkillDocumentValidationError as error:
            raise AppError("VALIDATION_REQUEST_INVALID", message=str(error)) from error
        except IntegrityError as error:
            raise AppError("BUSINESS_CONFLICT", message="同名 Skill 已存在") from error
        return await self.get(owner_user_id)

    async def delete_skill(self, owner_user_id: str, skill_id: str) -> None:
        if not await self._repository.delete_skill(owner_user_id, skill_id):
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
