"""聊天 Repository 的 SQLite adapter。"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.chat.models import (
    ChatMemoryMode,
    ChatMessageRecord,
    ChatMessageRole,
    ChatSessionDetailRecord,
    ChatSessionRecord,
)
from super_ai.memory.extended_sqlite.chat_models import ChatMessageModel, ChatSessionModel
from super_ai.memory.primitives import new_id, utc_now
from super_ai.project_config import JsonValue


class SqliteChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, owner_user_id: str) -> ChatSessionDetailRecord:
        now = utc_now()
        model = ChatSessionModel(
            id=new_id(), owner_user_id=owner_user_id, title="新会话",
            created_at=now, updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return ChatSessionDetailRecord(_session_record(model), ())

    async def list(self, owner_user_id: str) -> list[ChatSessionRecord]:
        models = (
            await self._session.scalars(
                select(ChatSessionModel)
                .where(ChatSessionModel.owner_user_id == owner_user_id)
                .order_by(ChatSessionModel.updated_at.desc(), ChatSessionModel.id.desc())
            )
        ).all()
        return [_session_record(model) for model in models]

    async def list_details(self, owner_user_id: str) -> list[ChatSessionDetailRecord]:
        sessions = (
            await self._session.scalars(
                select(ChatSessionModel)
                .where(ChatSessionModel.owner_user_id == owner_user_id)
                .order_by(ChatSessionModel.updated_at.desc(), ChatSessionModel.id.desc())
            )
        ).all()
        if not sessions:
            return []
        session_ids = [item.id for item in sessions]
        messages = (
            await self._session.scalars(
                select(ChatMessageModel)
                .where(
                    ChatMessageModel.owner_user_id == owner_user_id,
                    ChatMessageModel.session_id.in_(session_ids),
                )
                .order_by(ChatMessageModel.session_id, ChatMessageModel.sequence)
            )
        ).all()
        grouped: dict[str, list[ChatMessageRecord]] = {item.id: [] for item in sessions}
        for message in messages:
            grouped[message.session_id].append(_message_record(message))
        return [
            ChatSessionDetailRecord(_session_record(item), tuple(grouped[item.id]))
            for item in sessions
        ]

    async def get(
        self, owner_user_id: str, session_id: str
    ) -> ChatSessionDetailRecord | None:
        session = await self._session.scalar(
            select(ChatSessionModel).where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
            )
        )
        if session is None:
            return None
        messages = (
            await self._session.scalars(
                select(ChatMessageModel)
                .where(
                    ChatMessageModel.owner_user_id == owner_user_id,
                    ChatMessageModel.session_id == session_id,
                )
                .order_by(ChatMessageModel.sequence)
            )
        ).all()
        return ChatSessionDetailRecord(
            _session_record(session), tuple(_message_record(item) for item in messages)
        )

    async def append(
        self,
        owner_user_id: str,
        session_id: str,
        role: ChatMessageRole,
        content: str,
        metadata: dict[str, JsonValue],
    ) -> ChatSessionDetailRecord | None:
        session = await self._session.scalar(
            select(ChatSessionModel)
            .where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
            )
            .with_for_update()
        )
        if session is None:
            return None
        next_sequence = (
            await self._session.scalar(
                select(func.coalesce(func.max(ChatMessageModel.sequence), 0) + 1).where(
                    ChatMessageModel.owner_user_id == owner_user_id,
                    ChatMessageModel.session_id == session_id,
                )
            )
        )
        had_user = bool(
            await self._session.scalar(
                select(func.count())
                .select_from(ChatMessageModel)
                .where(
                    ChatMessageModel.owner_user_id == owner_user_id,
                    ChatMessageModel.session_id == session_id,
                    ChatMessageModel.role == "user",
                )
            )
        )
        now = utc_now()
        self._session.add(
            ChatMessageModel(
                id=new_id(), owner_user_id=owner_user_id, session_id=session_id,
                role=role, content=content, sequence=int(next_sequence or 1),
                metadata_json=metadata, created_at=now,
            )
        )
        values: dict[str, object] = {"updated_at": now}
        if role == "user" and not had_user:
            values["title"] = " ".join(content.split())[:48]
        await self._session.execute(
            update(ChatSessionModel)
            .where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
            )
            .values(**values)
        )
        await self._session.flush()
        return await self.get(owner_user_id, session_id)

    async def clear(
        self, owner_user_id: str, session_id: str
    ) -> ChatSessionDetailRecord | None:
        now = utc_now()
        updated = await self._session.scalar(
            update(ChatSessionModel)
            .where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
            )
            .values(
                title="新会话",
                memory_summary=None,
                compacted_message_count=0,
                context_tokens=0,
                last_compacted_at=None,
                updated_at=now,
            )
            .returning(ChatSessionModel.id)
        )
        if updated is None:
            return None
        await self._session.execute(
            delete(ChatMessageModel).where(
                ChatMessageModel.owner_user_id == owner_user_id,
                ChatMessageModel.session_id == session_id,
            )
        )
        await self._session.flush()
        return await self.get(owner_user_id, session_id)

    async def update_memory_mode(
        self, owner_user_id: str, session_id: str, memory_mode: ChatMemoryMode
    ) -> ChatSessionDetailRecord | None:
        updated = await self._session.scalar(
            update(ChatSessionModel)
            .where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
            )
            .values(memory_mode=memory_mode)
            .returning(ChatSessionModel.id)
        )
        if updated is None:
            return None
        await self._session.flush()
        return await self.get(owner_user_id, session_id)

    async def update_context_tokens(
        self, owner_user_id: str, session_id: str, context_tokens: int
    ) -> bool:
        if context_tokens < 0:
            raise ValueError("context_tokens 不得为负数")
        updated = await self._session.scalar(
            update(ChatSessionModel)
            .where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
            )
            .values(context_tokens=context_tokens)
            .returning(ChatSessionModel.id)
        )
        return updated is not None

    async def commit_compaction(
        self,
        owner_user_id: str,
        session_id: str,
        *,
        expected_compacted_message_count: int,
        compacted_message_count: int,
        memory_summary: str,
        compacted_at: datetime,
    ) -> bool:
        if compacted_message_count <= expected_compacted_message_count:
            raise ValueError("压缩高水位必须前进")
        boundary_exists = await self._session.scalar(
            select(ChatMessageModel.id).where(
                ChatMessageModel.owner_user_id == owner_user_id,
                ChatMessageModel.session_id == session_id,
                ChatMessageModel.sequence == compacted_message_count,
                ChatMessageModel.role == "assistant",
            )
        )
        if boundary_exists is None:
            return False
        updated = await self._session.scalar(
            update(ChatSessionModel)
            .where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
                ChatSessionModel.compacted_message_count == expected_compacted_message_count,
            )
            .values(
                memory_summary=memory_summary,
                compacted_message_count=compacted_message_count,
                last_compacted_at=compacted_at,
            )
            .returning(ChatSessionModel.id)
        )
        return updated is not None

    async def delete(self, owner_user_id: str, session_id: str) -> bool:
        deleted = await self._session.scalar(
            delete(ChatSessionModel)
            .where(
                ChatSessionModel.owner_user_id == owner_user_id,
                ChatSessionModel.id == session_id,
            )
            .returning(ChatSessionModel.id)
        )
        return deleted is not None


def _session_record(model: ChatSessionModel) -> ChatSessionRecord:
    return ChatSessionRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        title=model.title,
        memory_mode=cast(ChatMemoryMode, model.memory_mode),
        memory_summary=model.memory_summary,
        compacted_message_count=model.compacted_message_count,
        context_tokens=model.context_tokens,
        last_compacted_at=model.last_compacted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _message_record(model: ChatMessageModel) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        session_id=model.session_id,
        role=cast(ChatMessageRole, model.role),
        content=model.content,
        sequence=model.sequence,
        metadata=cast(dict[str, JsonValue], model.metadata_json),
        created_at=model.created_at,
    )
