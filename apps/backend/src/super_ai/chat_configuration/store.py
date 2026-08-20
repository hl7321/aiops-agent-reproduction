from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot, SkillCatalogEntry
from super_ai.memory.extended_sqlite.chat_configuration_models import (
    UserChatConfigurationModel,
    UserChatPromptModel,
    UserChatSkillModel,
)
from super_ai.memory.sqlite import transaction_scope


class SqliteChatAgentConfigurationStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def load_snapshot(self, owner_user_id: str) -> ChatAgentConfigurationSnapshot:
        async with transaction_scope(self._sessions) as session:
            selected_prompt_id = await session.scalar(
                select(UserChatConfigurationModel.selected_prompt_id).where(
                    UserChatConfigurationModel.owner_user_id == owner_user_id
                )
            )
            user_prompt = None
            if selected_prompt_id is not None:
                user_prompt = await session.scalar(
                    select(UserChatPromptModel.content).where(
                        UserChatPromptModel.owner_user_id == owner_user_id,
                        UserChatPromptModel.id == selected_prompt_id,
                    )
                )
            rows = (
                await session.execute(
                    select(UserChatSkillModel.name, UserChatSkillModel.description)
                    .where(
                        UserChatSkillModel.owner_user_id == owner_user_id,
                        UserChatSkillModel.is_selected.is_(True),
                    )
                    .order_by(UserChatSkillModel.created_at, UserChatSkillModel.id)
                )
            ).all()
        return ChatAgentConfigurationSnapshot(
            user_prompt=user_prompt,
            skills=tuple(SkillCatalogEntry(row.name, row.description) for row in rows),
        )

    async def load_content(self, owner_user_id: str, normalized_name: str) -> str | None:
        async with transaction_scope(self._sessions) as session:
            return await session.scalar(
                select(UserChatSkillModel.content).where(
                    UserChatSkillModel.owner_user_id == owner_user_id,
                    UserChatSkillModel.name == normalized_name,
                )
            )
