"""请求级会话记忆投影、压缩与候选预算编排。"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from langchain_core.messages import BaseMessage
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.api_responses import AppError
from super_ai.chat.memory.context import assemble_memory_context
from super_ai.chat.memory.summarizer import ChatMemorySummarizer
from super_ai.chat.memory.tokens import estimate_context_tokens
from super_ai.chat.memory.turns import CompleteTurnBoundary, complete_turn_boundary
from super_ai.chat.models import (
    ChatMemoryMode,
    ChatSessionDetailRecord,
)
from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.sqlite import transaction_scope
from super_ai.project_config import JsonValue

logger = logging.getLogger(__name__)
TokenEstimator = Callable[[Sequence[BaseMessage]], int]


class ChatConfigurationSnapshotStore(Protocol):
    async def load_snapshot(self, owner_user_id: str) -> ChatAgentConfigurationSnapshot: ...


@dataclass(frozen=True, slots=True)
class ChatMemoryProjection:
    detail: ChatSessionDetailRecord
    context_window_tokens: int
    context_usage_percent: float
    can_compact: bool


@dataclass(frozen=True, slots=True)
class PreparedMemoryTurn:
    projection: ChatMemoryProjection
    model_messages: tuple[BaseMessage, ...]
    configuration: ChatAgentConfigurationSnapshot


def should_auto_compact(
    mode: ChatMemoryMode,
    *,
    complete_turn_count: int,
    tokens: int,
    window: int,
) -> bool:
    _validate_budget(tokens, window)
    if mode == "every_30_turns":
        return complete_turn_count >= 30
    if mode == "context_70_percent":
        return tokens * 100 >= window * 70
    return False


def at_context_limit(*, tokens: int, window: int) -> bool:
    _validate_budget(tokens, window)
    return tokens * 100 >= window * 95


class ChatMemoryService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        configuration_store: ChatConfigurationSnapshotStore,
        summarizer: ChatMemorySummarizer,
        *,
        context_window_tokens: int,
        estimate_tokens: TokenEstimator = estimate_context_tokens,
        now: Callable[[], datetime],
    ) -> None:
        if context_window_tokens <= 0:
            raise AppError("SYSTEM_MODEL_CAPABILITY_MISSING")
        self._sessions = session_factory
        self._configuration_store = configuration_store
        self._summarizer = summarizer
        self._window = context_window_tokens
        self._estimate = estimate_tokens
        self._now = now

    async def project(self, owner_user_id: str, session_id: str) -> ChatMemoryProjection:
        detail = await self._load_required(owner_user_id, session_id)
        snapshot = await self._configuration_store.load_snapshot(owner_user_id)
        return await self._project(owner_user_id, detail, snapshot)

    async def create(self, owner_user_id: str) -> ChatMemoryProjection:
        async with transaction_scope(self._sessions) as session:
            created = await SqliteChatRepository(session).create(owner_user_id)
        return await self.project(owner_user_id, created.session.id)

    async def append(
        self,
        owner_user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, JsonValue],
    ) -> ChatMemoryProjection:
        from typing import cast

        from super_ai.chat.models import ChatMessageRole

        saved = None
        for attempt in range(3):
            try:
                async with transaction_scope(self._sessions) as session:
                    saved = await SqliteChatRepository(session).append(
                        owner_user_id,
                        session_id,
                        cast(ChatMessageRole, role),
                        content,
                        metadata,
                    )
                    if saved is None:
                        raise AppError("AUTH_FORBIDDEN")
                break
            except (IntegrityError, OperationalError):
                if attempt == 2:
                    raise
                await asyncio.sleep(0)
        return await self.project(owner_user_id, session_id)

    async def clear(self, owner_user_id: str, session_id: str) -> ChatMemoryProjection:
        async with transaction_scope(self._sessions) as session:
            cleared = await SqliteChatRepository(session).clear(owner_user_id, session_id)
            if cleared is None:
                raise AppError("AUTH_FORBIDDEN")
        return await self.project(owner_user_id, session_id)

    async def project_many(self, owner_user_id: str) -> tuple[ChatMemoryProjection, ...]:
        async with transaction_scope(self._sessions) as session:
            details = await SqliteChatRepository(session).list_details(owner_user_id)
        snapshot = await self._configuration_store.load_snapshot(owner_user_id)
        projected = [
            (
                detail,
                self._estimate_checked(assemble_memory_context(detail, snapshot)),
            )
            for detail in details
        ]
        async with transaction_scope(self._sessions) as session:
            repository = SqliteChatRepository(session)
            for detail, tokens in projected:
                if not await repository.update_context_tokens(
                    owner_user_id, detail.session.id, tokens
                ):
                    raise AppError("AUTH_FORBIDDEN")
        return tuple(
            self._make_projection(
                ChatSessionDetailRecord(
                    replace(detail.session, context_tokens=tokens),
                    detail.messages,
                )
            )
            for detail, tokens in projected
        )

    async def update_mode(
        self, owner_user_id: str, session_id: str, memory_mode: ChatMemoryMode
    ) -> ChatMemoryProjection:
        async with transaction_scope(self._sessions) as session:
            detail = await SqliteChatRepository(session).update_memory_mode(
                owner_user_id, session_id, memory_mode
            )
            if detail is None:
                raise AppError("AUTH_FORBIDDEN")
        return await self.project(owner_user_id, session_id)

    async def compact(self, owner_user_id: str, session_id: str) -> ChatMemoryProjection:
        detail = await self._load_required(owner_user_id, session_id)
        snapshot = await self._configuration_store.load_snapshot(owner_user_id)
        compacted = await self._compact(owner_user_id, detail)
        return await self._project(owner_user_id, compacted, snapshot)

    async def prepare_candidate(
        self,
        owner_user_id: str,
        session_id: str,
        content: str,
        metadata: dict[str, JsonValue] | None = None,
    ) -> PreparedMemoryTurn:
        detail = await self._load_required(owner_user_id, session_id)
        snapshot = await self._configuration_store.load_snapshot(owner_user_id)
        candidate_messages = assemble_memory_context(
            detail, snapshot, candidate_content=content
        )
        tokens = self._estimate_checked(candidate_messages)
        boundary = complete_turn_boundary(
            detail.messages, after_sequence=detail.session.compacted_message_count
        )
        complete_turn_count = boundary.complete_turn_count if boundary is not None else 0
        if boundary is not None and should_auto_compact(
            detail.session.memory_mode,
            complete_turn_count=complete_turn_count,
            tokens=tokens,
            window=self._window,
        ):
            detail = await self._compact(owner_user_id, detail, boundary=boundary)
            candidate_messages = assemble_memory_context(
                detail, snapshot, candidate_content=content
            )
            tokens = self._estimate_checked(candidate_messages)
        if at_context_limit(tokens=tokens, window=self._window):
            raise AppError("CHAT_CONTEXT_LIMIT_REACHED")

        async with transaction_scope(self._sessions) as session:
            repository = SqliteChatRepository(session)
            saved = await repository.append(
                owner_user_id, session_id, "user", content, metadata or {}
            )
            if saved is None:
                raise AppError("AUTH_FORBIDDEN")
            if not await repository.update_context_tokens(owner_user_id, session_id, tokens):
                raise AppError("AUTH_FORBIDDEN")
            refreshed = await repository.get(owner_user_id, session_id)
            if refreshed is None:
                raise AppError("AUTH_FORBIDDEN")
        projection = self._make_projection(refreshed)
        return PreparedMemoryTurn(projection, candidate_messages, snapshot)

    async def _project(
        self,
        owner_user_id: str,
        detail: ChatSessionDetailRecord,
        snapshot: ChatAgentConfigurationSnapshot,
    ) -> ChatMemoryProjection:
        tokens = self._estimate_checked(assemble_memory_context(detail, snapshot))
        async with transaction_scope(self._sessions) as session:
            repository = SqliteChatRepository(session)
            if not await repository.update_context_tokens(owner_user_id, detail.session.id, tokens):
                raise AppError("AUTH_FORBIDDEN")
            refreshed = await repository.get(owner_user_id, detail.session.id)
            if refreshed is None:
                raise AppError("AUTH_FORBIDDEN")
        return self._make_projection(refreshed)

    async def _compact(
        self,
        owner_user_id: str,
        detail: ChatSessionDetailRecord,
        *,
        boundary: CompleteTurnBoundary | None = None,
    ) -> ChatSessionDetailRecord:
        target = boundary or complete_turn_boundary(
            detail.messages, after_sequence=detail.session.compacted_message_count
        )
        if target is None:
            return detail
        transcript = tuple(f"{item.role}: {item.content}" for item in target.messages)
        summary = await self._summarizer.summarize(
            detail.session.memory_summary, transcript
        )
        if not summary.strip():
            raise RuntimeError("摘要模型未返回内容")
        async with transaction_scope(self._sessions) as session:
            committed = await SqliteChatRepository(session).commit_compaction(
                owner_user_id,
                detail.session.id,
                expected_compacted_message_count=detail.session.compacted_message_count,
                compacted_message_count=target.sequence,
                memory_summary=summary.strip(),
                compacted_at=self._now(),
            )
            if not committed:
                raise RuntimeError("会话记忆状态已变化，请重试")
        logger.info(
            "chat memory compacted owner_id=%s session_id=%s message_count=%d",
            owner_user_id,
            detail.session.id,
            len(target.messages),
        )
        return await self._load_required(owner_user_id, detail.session.id)

    async def _load_required(
        self, owner_user_id: str, session_id: str
    ) -> ChatSessionDetailRecord:
        async with transaction_scope(self._sessions) as session:
            detail = await SqliteChatRepository(session).get(owner_user_id, session_id)
        if detail is None:
            raise AppError("AUTH_FORBIDDEN")
        return detail

    def _estimate_checked(self, messages: Sequence[BaseMessage]) -> int:
        tokens = self._estimate(messages)
        if tokens < 0:
            raise ValueError("token estimator 不得返回负数")
        return tokens

    def _make_projection(self, detail: ChatSessionDetailRecord) -> ChatMemoryProjection:
        boundary = complete_turn_boundary(
            detail.messages, after_sequence=detail.session.compacted_message_count
        )
        usage = round(detail.session.context_tokens / self._window * 100, 2)
        return ChatMemoryProjection(
            detail=detail,
            context_window_tokens=self._window,
            context_usage_percent=usage,
            can_compact=boundary is not None,
        )


def _validate_budget(tokens: int, window: int) -> None:
    if tokens < 0:
        raise ValueError("tokens 不得为负数")
    if window <= 0:
        raise AppError("SYSTEM_MODEL_CAPABILITY_MISSING")
