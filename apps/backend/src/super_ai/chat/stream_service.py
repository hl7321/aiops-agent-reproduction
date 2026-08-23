"""请求级 Agent turn 的消息事务与 SSE 事件编排。"""

import asyncio
import inspect
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from langchain_core.messages import BaseMessage
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.api_contracts import (
    ApiErrorModel,
    ChatStreamMessageRequest,
    SseEvent,
)
from super_ai.api_responses import AppError
from super_ai.chat.agent_events import AgentEventMapper, TurnContext
from super_ai.chat.agent_runner import AgentRunResult
from super_ai.chat.memory.service import ChatMemoryService
from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.primitives import new_id
from super_ai.memory.sqlite import transaction_scope
from super_ai.project_config import JsonValue
from super_ai.runtime.logging import log_lifecycle
from super_ai.tenancy.context import CurrentUser

logger = logging.getLogger(__name__)


class AgentTurnRunner(Protocol):
    async def run(self, messages: Sequence[BaseMessage]) -> AgentRunResult: ...


class AgentTurnRunnerFactory(Protocol):
    def __call__(
        self,
        current_user: CurrentUser,
        session_id: str,
        mapper: AgentEventMapper,
        emit: Callable[[SseEvent], Awaitable[None]],
        configuration: ChatAgentConfigurationSnapshot,
    ) -> AgentTurnRunner | Awaitable[AgentTurnRunner]: ...


@dataclass(frozen=True, slots=True)
class PreparedAgentTurn:
    current_user: CurrentUser
    session_id: str
    model_messages: tuple[BaseMessage, ...]
    configuration: ChatAgentConfigurationSnapshot


_STREAM_END = object()


class AgentChatStreamService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        runner_factory: AgentTurnRunnerFactory,
        memory_service: ChatMemoryService,
        *,
        now: Callable[[], datetime],
    ) -> None:
        self._sessions = session_factory
        self._runner_factory = runner_factory
        self._memory_service = memory_service
        self._now = now

    async def prepare(
        self,
        current_user: CurrentUser,
        session_id: str,
        body: ChatStreamMessageRequest,
    ) -> PreparedAgentTurn:
        metadata_json = body.metadata.model_dump(mode="json", by_alias=True)
        metadata = cast(
            dict[str, JsonValue],
            {key: value for key, value in metadata_json.items() if value is not None},
        )
        prepared = await self._memory_service.prepare_candidate(
            current_user.owner_user_id,
            session_id,
            body.content,
            metadata,
        )
        return PreparedAgentTurn(
            current_user,
            session_id,
            prepared.model_messages[1:],
            prepared.configuration,
        )

    async def stream(self, prepared: PreparedAgentTurn) -> AsyncGenerator[SseEvent, None]:
        queue: asyncio.Queue[SseEvent | object] = asyncio.Queue()
        context = TurnContext(turn_id=new_id(), now=self._now)
        mapper = AgentEventMapper(context)

        async def emit(event: SseEvent) -> None:
            await queue.put(event)

        task = asyncio.create_task(self._run_turn(prepared, mapper, emit, queue))
        try:
            while True:
                item = await queue.get()
                if item is _STREAM_END:
                    break
                yield cast(SseEvent, item)
            await task
        finally:
            if not task.done():
                task.add_done_callback(_consume_task_result)

    async def _run_turn(
        self,
        prepared: PreparedAgentTurn,
        mapper: AgentEventMapper,
        emit: Callable[[SseEvent], Awaitable[None]],
        queue: asyncio.Queue[SseEvent | object],
    ) -> None:
        turn_id = mapper.context.turn_id
        log_lifecycle("chat.turn", resource_id=turn_id, status="running")
        try:
            candidate = self._runner_factory(
                prepared.current_user,
                prepared.session_id,
                mapper,
                emit,
                prepared.configuration,
            )
            runner = await candidate if inspect.isawaitable(candidate) else candidate
            result = await runner.run(prepared.model_messages)
            if not result.final_text:
                raise RuntimeError("模型未返回最终回答")
            metadata: dict[str, JsonValue] = {
                "references": [
                    cast(
                        JsonValue,
                        reference.model_dump(mode="json", by_alias=True),
                    )
                    for reference in result.references
                ],
                "toolCallIds": list(result.tool_call_ids),
            }
            async with transaction_scope(self._sessions) as session:
                saved = await SqliteChatRepository(session).append(
                    prepared.current_user.owner_user_id,
                    prepared.session_id,
                    "assistant",
                    result.final_text,
                    metadata,
                )
                if saved is None:
                    raise AppError("AUTH_FORBIDDEN")
            for event in mapper.content(result.final_text):
                await queue.put(event)
            await queue.put(mapper.complete())
            log_lifecycle("chat.turn", resource_id=turn_id, status="succeeded")
        except Exception as error:
            log_lifecycle(
                "chat.turn",
                resource_id=turn_id,
                status="failed",
                category=type(error).__name__,
            )
            logger.error(
                "agent chat turn failed error_type=%s validation_issues=%s",
                type(error).__name__,
                _safe_validation_issues(error),
            )
            await queue.put(mapper.error(_safe_error(error)))
        finally:
            await queue.put(_STREAM_END)


def _safe_error(error: Exception) -> ApiErrorModel:
    if isinstance(error, AppError):
        from super_ai.api_contracts import ERROR_DEFINITIONS

        definition = ERROR_DEFINITIONS[error.code]
        return ApiErrorModel(
            code=error.code,
            category=definition.category,
            httpStatus=definition.http_status,
            message=error.safe_message,
            details=error.details,
        )
    return ApiErrorModel(
        code="SYSTEM_INTERNAL_ERROR",
        category="system",
        httpStatus=500,
        message="服务暂时不可用",
    )


def _safe_validation_issues(error: Exception) -> tuple[tuple[str, str], ...]:
    if not isinstance(error, ValidationError):
        return ()
    return tuple(
        (
            ".".join(str(part) for part in issue["loc"]),
            str(issue["type"]),
        )
        for issue in error.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
    )


def _consume_task_result(task: asyncio.Task[None]) -> None:
    if not task.cancelled():
        task.exception()
