from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.chat_configuration.models import (
    ChatConfigurationRecord,
    ChatPromptRecord,
    ChatSkillRecord,
    ParsedSkillDocument,
)
from super_ai.memory.extended_sqlite.chat_configuration_models import (
    UserChatConfigurationModel,
    UserChatPromptModel,
    UserChatSkillModel,
)
from super_ai.memory.primitives import new_id, utc_now
from super_ai.project_config import JsonValue


class SqliteChatConfigurationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, owner_user_id: str) -> ChatConfigurationRecord:
        configuration = await self._session.get(UserChatConfigurationModel, owner_user_id)
        prompts = (
            await self._session.scalars(
                select(UserChatPromptModel)
                .where(UserChatPromptModel.owner_user_id == owner_user_id)
                .order_by(UserChatPromptModel.created_at, UserChatPromptModel.id)
            )
        ).all()
        skills = (
            await self._session.scalars(
                select(UserChatSkillModel)
                .where(UserChatSkillModel.owner_user_id == owner_user_id)
                .order_by(UserChatSkillModel.created_at, UserChatSkillModel.id)
            )
        ).all()
        return ChatConfigurationRecord(
            configuration.selected_prompt_id if configuration else None,
            tuple(_prompt(item) for item in prompts),
            tuple(_skill(item) for item in skills),
        )

    async def create_prompt(self, owner_user_id: str, label: str, content: str) -> ChatPromptRecord:
        now = utc_now()
        model = UserChatPromptModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            label=label,
            content=content,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _prompt(model)

    async def update_prompt(
        self, owner_user_id: str, prompt_id: str, label: str, content: str
    ) -> ChatPromptRecord | None:
        model = await self._session.scalar(
            update(UserChatPromptModel)
            .where(
                UserChatPromptModel.owner_user_id == owner_user_id,
                UserChatPromptModel.id == prompt_id,
            )
            .values(label=label, content=content, updated_at=utc_now())
            .returning(UserChatPromptModel)
        )
        return _prompt(model) if model else None

    async def delete_prompt(self, owner_user_id: str, prompt_id: str) -> bool:
        await self._session.execute(
            update(UserChatConfigurationModel)
            .where(
                UserChatConfigurationModel.owner_user_id == owner_user_id,
                UserChatConfigurationModel.selected_prompt_id == prompt_id,
            )
            .values(selected_prompt_id=None, updated_at=utc_now())
        )
        removed = await self._session.scalar(
            delete(UserChatPromptModel)
            .where(
                UserChatPromptModel.owner_user_id == owner_user_id,
                UserChatPromptModel.id == prompt_id,
            )
            .returning(UserChatPromptModel.id)
        )
        return removed is not None

    async def create_skill(
        self, owner_user_id: str, parsed: ParsedSkillDocument
    ) -> ChatSkillRecord:
        now = utc_now()
        model = UserChatSkillModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            name=parsed.name,
            description=parsed.description,
            filename=parsed.filename,
            content=parsed.content,
            metadata_json=parsed.metadata,
            summary=parsed.summary,
            is_selected=False,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _skill(model)

    async def delete_skill(self, owner_user_id: str, skill_id: str) -> bool:
        removed = await self._session.scalar(
            delete(UserChatSkillModel)
            .where(
                UserChatSkillModel.owner_user_id == owner_user_id, UserChatSkillModel.id == skill_id
            )
            .returning(UserChatSkillModel.id)
        )
        return removed is not None

    async def replace_selection(
        self, owner_user_id: str, prompt_id: str | None, skill_ids: list[str]
    ) -> bool:
        unique_ids = list(dict.fromkeys(skill_ids))
        if prompt_id is not None:
            exists = await self._session.scalar(
                select(UserChatPromptModel.id).where(
                    UserChatPromptModel.owner_user_id == owner_user_id,
                    UserChatPromptModel.id == prompt_id,
                )
            )
            if exists is None:
                return False
        if unique_ids:
            owned = set(
                (
                    await self._session.scalars(
                        select(UserChatSkillModel.id).where(
                            UserChatSkillModel.owner_user_id == owner_user_id,
                            UserChatSkillModel.id.in_(unique_ids),
                        )
                    )
                ).all()
            )
            if owned != set(unique_ids):
                return False
        now = utc_now()
        existing = await self._session.get(UserChatConfigurationModel, owner_user_id)
        if existing is None:
            self._session.add(
                UserChatConfigurationModel(
                    owner_user_id=owner_user_id,
                    selected_prompt_id=prompt_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            existing.selected_prompt_id = prompt_id
            existing.updated_at = now
        await self._session.execute(
            update(UserChatSkillModel)
            .where(UserChatSkillModel.owner_user_id == owner_user_id)
            .values(is_selected=False, updated_at=now)
        )
        if unique_ids:
            await self._session.execute(
                update(UserChatSkillModel)
                .where(
                    UserChatSkillModel.owner_user_id == owner_user_id,
                    UserChatSkillModel.id.in_(unique_ids),
                )
                .values(is_selected=True, updated_at=now)
            )
        await self._session.flush()
        return True

    async def get_skill_content(self, owner_user_id: str, normalized_name: str) -> str | None:
        return await self._session.scalar(
            select(UserChatSkillModel.content).where(
                UserChatSkillModel.owner_user_id == owner_user_id,
                UserChatSkillModel.name == normalized_name,
            )
        )


def _prompt(model: UserChatPromptModel) -> ChatPromptRecord:
    return ChatPromptRecord(
        model.id,
        model.owner_user_id,
        model.label,
        model.content,
        model.created_at,
        model.updated_at,
    )


def _skill(model: UserChatSkillModel) -> ChatSkillRecord:
    return ChatSkillRecord(
        model.id,
        model.owner_user_id,
        model.name,
        model.description,
        model.filename,
        model.content,
        cast(dict[str, JsonValue], model.metadata_json),
        model.summary,
        model.is_selected,
        model.created_at,
        model.updated_at,
    )
