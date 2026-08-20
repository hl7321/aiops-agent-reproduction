import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone

import pytest
from langchain_core.messages import BaseMessage

from super_ai.api_contracts import ChatReference, ChatStreamMessageRequest, SseEvent
from super_ai.api_responses import AppError
from super_ai.chat.agent_events import AgentEventMapper
from super_ai.chat.agent_runner import AgentRunResult
from super_ai.chat.memory.service import ChatMemoryService
from super_ai.chat.stream_service import AgentChatStreamService
from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot
from super_ai.llm.errors import ModelProviderError
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.chat_models import ChatSessionModel
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database
from super_ai.tenancy.context import CurrentUser

NOW = datetime(2026, 8, 18, tzinfo=timezone.utc)


class ScriptedRunner:
    def __init__(
        self,
        mapper: AgentEventMapper,
        emit: Callable[[SseEvent], Awaitable[None]],
        *,
        answer: str | None,
        reference: ChatReference | None,
    ) -> None:
        self.mapper = mapper
        self.emit = emit
        self.answer = answer
        self.reference_value = reference
        self.messages: Sequence[BaseMessage] = ()

    async def run(self, messages: Sequence[BaseMessage]) -> AgentRunResult:
        self.messages = messages
        if self.answer is None:
            raise ModelProviderError("provider failed SECRET_SENTINEL")
        if self.reference_value is not None:
            await self.emit(self.mapper.tool_call("call-1", "knowledge_retrieval", "started"))
            await self.emit(self.mapper.tool_call("call-1", "knowledge_retrieval", "completed"))
            await self.emit(self.mapper.reference(self.reference_value))
        return AgentRunResult(
            self.answer,
            self.mapper.context.references,
            self.mapper.context.tool_call_ids,
        )


class ScriptedRunnerFactory:
    def __init__(self, outcomes: list[tuple[str | None, ChatReference | None]]) -> None:
        self.outcomes = outcomes
        self.runners: list[ScriptedRunner] = []
        self.configurations: list[ChatAgentConfigurationSnapshot] = []

    def __call__(
        self,
        current_user: CurrentUser,
        session_id: str,
        mapper: AgentEventMapper,
        emit: Callable[[SseEvent], Awaitable[None]],
        configuration: ChatAgentConfigurationSnapshot,
    ) -> ScriptedRunner:
        answer, reference = self.outcomes.pop(0)
        runner = ScriptedRunner(mapper, emit, answer=answer, reference=reference)
        self.runners.append(runner)
        self.configurations.append(configuration)
        return runner


class AppErrorRunner:
    async def run(self, messages: Sequence[BaseMessage]) -> AgentRunResult:
        raise AppError("CHAT_CONTEXT_LIMIT_REACHED")


class AppErrorRunnerFactory:
    def __call__(
        self,
        current_user: CurrentUser,
        session_id: str,
        mapper: AgentEventMapper,
        emit: Callable[[SseEvent], Awaitable[None]],
        configuration: ChatAgentConfigurationSnapshot,
    ) -> AppErrorRunner:
        return AppErrorRunner()


class FakeConfigurationStore:
    async def load_snapshot(self, owner_user_id: str) -> ChatAgentConfigurationSnapshot:
        return ChatAgentConfigurationSnapshot(user_prompt="简洁回答", skills=())


class FakeSummarizer:
    async def summarize(self, previous_summary: str | None, messages: Sequence[str]) -> str:
        return f"{previous_summary or ''}{' '.join(messages)}"


def make_service(
    runtime: PersistenceRuntime,
    factory: ScriptedRunnerFactory,
    *,
    context_window_tokens: int = 1000,
    estimate_tokens: Callable[[Sequence[BaseMessage]], int] | None = None,
) -> AgentChatStreamService:
    memory = ChatMemoryService(
        runtime.session_factory,
        FakeConfigurationStore(),
        FakeSummarizer(),
        context_window_tokens=context_window_tokens,
        estimate_tokens=estimate_tokens or (lambda messages: len(messages) * 2),
        now=lambda: NOW,
    )
    return AgentChatStreamService(runtime.session_factory, factory, memory, now=lambda: NOW)


async def _seed(runtime: PersistenceRuntime, owner: str, session_id: str) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        now = utc_now()
        session.add(
            UserModel(
                id=owner,
                email=f"{owner}@example.com",
                password_hash="$argon2id$test",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ChatSessionModel(
                id=session_id,
                owner_user_id=owner,
                title="新会话",
                created_at=now,
                updated_at=now,
            )
        )


async def test_stream_persists_user_before_runner_and_complete_assistant_once(
    chat_database_url: str,
) -> None:
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    factory = ScriptedRunnerFactory([("好🙂", None)])
    try:
        await _seed(runtime, "user-a", "session-a")
        service = make_service(runtime, factory)

        prepared = await service.prepare(
            CurrentUser("user-a"),
            "session-a",
            ChatStreamMessageRequest(content="你好"),
        )
        events = [event async for event in service.stream(prepared)]

        assert [event.type for event in events] == ["content.delta", "content.delta", "complete"]
        assert [event.data.delta for event in events[:-1]] == ["好", "🙂"]  # type: ignore[union-attr]
        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", "session-a")
        assert detail is not None
        assert [message.role for message in detail.messages] == ["user", "assistant"]
        assert detail.messages[1].content == "好🙂"
        assert detail.messages[1].metadata == {"references": [], "toolCallIds": []}
        assert factory.runners[0].messages[-1].content == "你好"
        assert factory.configurations[0].user_prompt == "简洁回答"
    finally:
        await runtime.close()


async def test_provider_failure_keeps_user_and_emits_safe_error_without_assistant(
    chat_database_url: str,
) -> None:
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    factory = ScriptedRunnerFactory([(None, None)])
    try:
        await _seed(runtime, "user-a", "session-a")
        service = make_service(runtime, factory)
        prepared = await service.prepare(
            CurrentUser("user-a"), "session-a", ChatStreamMessageRequest(content="失败测试")
        )

        events = [event async for event in service.stream(prepared)]

        assert [event.type for event in events] == ["error"]
        assert "SECRET_SENTINEL" not in events[0].model_dump_json()
        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", "session-a")
        assert detail is not None
        assert [message.role for message in detail.messages] == ["user"]
    finally:
        await runtime.close()


async def test_prepare_rejects_foreign_parent_before_runner_or_message_write(
    chat_database_url: str,
) -> None:
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    factory = ScriptedRunnerFactory([("不应执行", None)])
    try:
        await _seed(runtime, "user-a", "session-a")
        service = make_service(runtime, factory)

        with pytest.raises(AppError) as captured:
            await service.prepare(
                CurrentUser("user-b"), "session-a", ChatStreamMessageRequest(content="越权")
            )

        assert captured.value.code == "AUTH_FORBIDDEN"
        assert factory.runners == []
        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", "session-a")
        assert detail is not None and detail.messages == ()
    finally:
        await runtime.close()


async def test_two_turns_keep_references_in_their_own_assistant_metadata(
    chat_database_url: str,
) -> None:
    reference = ChatReference(
        chunkId="chunk-1",
        documentId="doc-1",
        knowledgeBaseId="kb-1",
        source="runbook.md",
        excerpt="处理步骤",
        metadata={"heading": "处置"},
        vectorRank=1,
        vectorScore=0.9,
        bm25Rank=2,
        bm25Score=1.2,
        rrfScore=0.032,
        rerankRank=1,
        rerankScore=0.96,
        score=0.96,
    )
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    factory = ScriptedRunnerFactory([("第一轮", reference), ("第二轮", None)])
    try:
        await _seed(runtime, "user-a", "session-a")
        service = make_service(runtime, factory)
        for content in ("问题一", "问题二"):
            prepared = await service.prepare(
                CurrentUser("user-a"), "session-a", ChatStreamMessageRequest(content=content)
            )
            _ = [event async for event in service.stream(prepared)]

        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", "session-a")
        assert detail is not None
        assistants = [message for message in detail.messages if message.role == "assistant"]
        assert assistants[0].metadata["references"] == [
            reference.model_dump(by_alias=True)
        ]
        assert assistants[0].metadata["toolCallIds"] == ["call-1"]
        assert assistants[1].metadata == {"references": [], "toolCallIds": []}
    finally:
        await runtime.close()


async def test_closing_stream_after_live_event_does_not_delete_completed_answer(
    chat_database_url: str,
) -> None:
    reference = ChatReference(
        chunkId="chunk-1",
        documentId="doc-1",
        knowledgeBaseId="kb-1",
        source="runbook.md",
        excerpt="处理步骤",
        metadata={},
        vectorRank=1,
        vectorScore=0.9,
        bm25Rank=None,
        bm25Score=None,
        rrfScore=0.016,
        rerankRank=1,
        rerankScore=0.95,
        score=0.95,
    )
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    factory = ScriptedRunnerFactory([("断线后仍完整", reference)])
    try:
        await _seed(runtime, "user-a", "session-a")
        service = make_service(runtime, factory)
        prepared = await service.prepare(
            CurrentUser("user-a"), "session-a", ChatStreamMessageRequest(content="断线测试")
        )
        stream = service.stream(prepared)

        first_event = await anext(stream)
        await stream.aclose()

        assert first_event.type == "tool.call"
        detail = None
        for _ in range(100):
            async with transaction_scope(runtime.session_factory) as session:
                detail = await SqliteChatRepository(session).get("user-a", "session-a")
            if detail is not None and len(detail.messages) == 2:
                break
            await asyncio.sleep(0.01)
        assert detail is not None
        assert [message.content for message in detail.messages] == ["断线测试", "断线后仍完整"]
    finally:
        await runtime.close()


async def test_stream_started_app_error_reuses_shared_context_limit_shape(
    chat_database_url: str,
) -> None:
    await upgrade_database(chat_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_database_url))
    try:
        await _seed(runtime, "user-a", "session-a")
        factory = AppErrorRunnerFactory()
        memory = ChatMemoryService(
            runtime.session_factory,
            FakeConfigurationStore(),
            FakeSummarizer(),
            context_window_tokens=1000,
            estimate_tokens=lambda messages: len(messages),
            now=lambda: NOW,
        )
        service = AgentChatStreamService(runtime.session_factory, factory, memory, now=lambda: NOW)
        prepared = await service.prepare(
            CurrentUser("user-a"), "session-a", ChatStreamMessageRequest(content="开始后失败")
        )

        events = [event async for event in service.stream(prepared)]

        assert len(events) == 1 and events[0].type == "error"
        payload = events[0].model_dump(mode="json", by_alias=True)
        assert payload["data"]["error"] == {
            "code": "CHAT_CONTEXT_LIMIT_REACHED",
            "category": "business",
            "httpStatus": 409,
            "message": "会话上下文已达到安全上限，请先手动压缩记忆",
            "details": None,
        }
    finally:
        await runtime.close()
