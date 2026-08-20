from typing import Protocol

from super_ai.chat_configuration.models import (
    ChatConfigurationRecord,
    ChatPromptRecord,
    ChatSkillRecord,
    ParsedSkillDocument,
)


class ChatConfigurationRepository(Protocol):
    async def get(self, owner_user_id: str) -> ChatConfigurationRecord: ...
    async def create_prompt(
        self, owner_user_id: str, label: str, content: str
    ) -> ChatPromptRecord: ...
    async def update_prompt(
        self, owner_user_id: str, prompt_id: str, label: str, content: str
    ) -> ChatPromptRecord | None: ...
    async def delete_prompt(self, owner_user_id: str, prompt_id: str) -> bool: ...
    async def create_skill(
        self, owner_user_id: str, parsed: ParsedSkillDocument
    ) -> ChatSkillRecord: ...
    async def delete_skill(self, owner_user_id: str, skill_id: str) -> bool: ...
    async def replace_selection(
        self, owner_user_id: str, prompt_id: str | None, skill_ids: list[str]
    ) -> bool: ...
    async def get_skill_content(self, owner_user_id: str, normalized_name: str) -> str | None: ...
