from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest
from langchain_core.messages import BaseMessage

from super_ai.api_responses import AppError
from super_ai.chat.memory.service import (
    ChatMemoryService,
    at_context_limit,
    should_auto_compact,
)
from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database

NOW = datetime(2026, 8, 18, tzinfo=timezone.utc)


class FakeConfigurationStore:
    async def load_snapshot(self, owner_user_id: str) -> ChatAgentConfigurationSnapshot:
        assert owner_user_id == "user-a"
        return ChatAgentConfigurationSnapshot(user_prompt="简洁回答", skills=())


class FakeSummarizer:
    def __init__(self, result: str | Exception = "摘要") -> None:
        self.result = result
        self.calls: list[tuple[str | None, tuple[str, ...]]] = []

    async def summarize(self, previous_summary: str | None, messages: Sequence[str]) -> str:
        self.calls.append((previous_summary, tuple(messages)))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class SequenceEstimator:
    def __init__(self, *results: int) -> None:
        self.results = list(results)

    def __call__(self, _messages: Sequence[BaseMessage]) -> int:
        if not self.results:
            raise AssertionError("unexpected estimate")
        return self.results.pop(0)


async def create_runtime(tmp_path: Path) -> tuple[PersistenceRuntime, str]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'memory.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    async with transaction_scope(runtime.session_factory) as session:
        session.add(UserModel(
            id="user-a", email="a@example.com", password_hash="hash",
            created_at=NOW, updated_at=NOW,
        ))
    async with transaction_scope(runtime.session_factory) as session:
        created = await SqliteChatRepository(session).create("user-a")
    return runtime, created.session.id


async def append_complete_turn(runtime: PersistenceRuntime, session_id: str, number: int) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        repository = SqliteChatRepository(session)
        await repository.append("user-a", session_id, "user", f"问题 {number}", {})
        await repository.append("user-a", session_id, "assistant", f"回答 {number}", {})


def test_policy_uses_exact_29_30_and_69_70_95_boundaries() -> None:
    assert not should_auto_compact("every_30_turns", complete_turn_count=29, tokens=1, window=100)
    assert should_auto_compact("every_30_turns", complete_turn_count=30, tokens=1, window=100)
    assert not should_auto_compact(
        "context_70_percent", complete_turn_count=1, tokens=69, window=100
    )
    assert should_auto_compact("context_70_percent", complete_turn_count=1, tokens=70, window=100)
    assert not should_auto_compact("manual", complete_turn_count=30, tokens=70, window=100)
    assert not at_context_limit(tokens=94, window=100)
    assert at_context_limit(tokens=95, window=100)


async def test_context_70_compacts_then_persists_candidate(tmp_path: Path) -> None:
    runtime, session_id = await create_runtime(tmp_path)
    summarizer = FakeSummarizer()
    try:
        await append_complete_turn(runtime, session_id, 1)
        service = ChatMemoryService(
            runtime.session_factory, FakeConfigurationStore(), summarizer,
            context_window_tokens=100, estimate_tokens=SequenceEstimator(70, 20), now=lambda: NOW,
        )

        prepared = await service.prepare_candidate("user-a", session_id, "下一问")

        assert len(summarizer.calls) == 1
        assert prepared.projection.detail.session.memory_summary == "摘要"
        assert prepared.projection.detail.session.compacted_message_count == 2
        assert prepared.projection.detail.messages[-1].content == "下一问"
        assert prepared.projection.detail.session.context_tokens == 20
    finally:
        await runtime.close()


async def test_every_30_turns_only_compacts_after_thirtieth_complete_turn(
    tmp_path: Path,
) -> None:
    runtime, session_id = await create_runtime(tmp_path)
    summarizer = FakeSummarizer()
    try:
        for number in range(29):
            await append_complete_turn(runtime, session_id, number)
        service = ChatMemoryService(
            runtime.session_factory,
            FakeConfigurationStore(),
            summarizer,
            context_window_tokens=100,
            estimate_tokens=SequenceEstimator(1),
            now=lambda: NOW,
        )
        async with transaction_scope(runtime.session_factory) as session:
            await SqliteChatRepository(session).update_memory_mode(
                "user-a", session_id, "every_30_turns"
            )

        await service.prepare_candidate("user-a", session_id, "第 30 轮后的候选问题")

        assert summarizer.calls == []

        async with transaction_scope(runtime.session_factory) as session:
            second = await SqliteChatRepository(session).create("user-a")
        for number in range(30):
            await append_complete_turn(runtime, second.session.id, number)
        async with transaction_scope(runtime.session_factory) as session:
            await SqliteChatRepository(session).update_memory_mode(
                "user-a", second.session.id, "every_30_turns"
            )
        service = ChatMemoryService(
            runtime.session_factory,
            FakeConfigurationStore(),
            summarizer,
            context_window_tokens=100,
            estimate_tokens=SequenceEstimator(1, 1),
            now=lambda: NOW,
        )

        prepared = await service.prepare_candidate(
            "user-a", second.session.id, "第 31 轮候选问题"
        )

        assert len(summarizer.calls) == 1
        assert prepared.projection.detail.session.compacted_message_count == 60
        assert prepared.projection.detail.messages[-1].content == "第 31 轮候选问题"
    finally:
        await runtime.close()


async def test_auto_compaction_still_rejects_95_without_persisting_candidate(
    tmp_path: Path,
) -> None:
    runtime, session_id = await create_runtime(tmp_path)
    summarizer = FakeSummarizer()
    try:
        await append_complete_turn(runtime, session_id, 1)
        service = ChatMemoryService(
            runtime.session_factory,
            FakeConfigurationStore(),
            summarizer,
            context_window_tokens=100,
            estimate_tokens=SequenceEstimator(70, 95),
            now=lambda: NOW,
        )

        with pytest.raises(AppError) as caught:
            await service.prepare_candidate("user-a", session_id, "仍然超限")

        assert caught.value.code == "CHAT_CONTEXT_LIMIT_REACHED"
        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", session_id)
        assert detail is not None
        assert [item.content for item in detail.messages] == ["问题 1", "回答 1"]
        assert detail.session.memory_summary == "摘要"
        assert detail.session.compacted_message_count == 2
    finally:
        await runtime.close()


async def test_manual_95_rejects_before_persisting_candidate(tmp_path: Path) -> None:
    runtime, session_id = await create_runtime(tmp_path)
    summarizer = FakeSummarizer()
    try:
        async with transaction_scope(runtime.session_factory) as session:
            await SqliteChatRepository(session).update_memory_mode("user-a", session_id, "manual")
        service = ChatMemoryService(
            runtime.session_factory, FakeConfigurationStore(), summarizer,
            context_window_tokens=100, estimate_tokens=SequenceEstimator(95), now=lambda: NOW,
        )

        with pytest.raises(AppError) as caught:
            await service.prepare_candidate("user-a", session_id, "不能落盘")

        assert caught.value.code == "CHAT_CONTEXT_LIMIT_REACHED"
        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", session_id)
        assert detail is not None and detail.messages == ()
        assert summarizer.calls == []
    finally:
        await runtime.close()


async def test_summary_failure_keeps_history_and_memory_state(tmp_path: Path) -> None:
    runtime, session_id = await create_runtime(tmp_path)
    summarizer = FakeSummarizer(RuntimeError("provider failed"))
    try:
        await append_complete_turn(runtime, session_id, 1)
        service = ChatMemoryService(
            runtime.session_factory, FakeConfigurationStore(), summarizer,
            context_window_tokens=100, estimate_tokens=SequenceEstimator(70), now=lambda: NOW,
        )

        with pytest.raises(RuntimeError, match="provider failed"):
            await service.prepare_candidate("user-a", session_id, "下一问")

        async with transaction_scope(runtime.session_factory) as session:
            detail = await SqliteChatRepository(session).get("user-a", session_id)
        assert detail is not None
        assert [item.content for item in detail.messages] == ["问题 1", "回答 1"]
        assert detail.session.memory_summary is None
        assert detail.session.compacted_message_count == 0
        assert detail.session.context_tokens == 0
    finally:
        await runtime.close()
