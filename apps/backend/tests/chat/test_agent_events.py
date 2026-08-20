from datetime import datetime, timezone

import pytest

from super_ai.api_contracts import ApiErrorModel, ChatReference
from super_ai.chat.agent_events import AgentEventMapper, TurnContext

NOW = datetime(2026, 8, 18, 0, 0, tzinfo=timezone.utc)


def test_turn_context_assigns_stable_monotonic_ids_and_single_terminal() -> None:
    context = TurnContext(turn_id="turn-1", now=lambda: NOW)
    mapper = AgentEventMapper(context)

    reasoning = mapper.reasoning("检查告警")
    started = mapper.tool_call("call-1", "knowledge_retrieval", "started")
    complete = mapper.complete()

    assert [event.sequence for event in (reasoning, started, complete)] == [1, 2, 3]
    assert [event.id for event in (reasoning, started, complete)] == [
        "turn-1:1", "turn-1:2", "turn-1:3",
    ]
    assert all(
        event.timestamp == "2026-08-18T00:00:00Z"
        for event in (reasoning, started, complete)
    )
    with pytest.raises(RuntimeError, match="已经终结"):
        mapper.complete()
    with pytest.raises(RuntimeError, match="已经终结"):
        mapper.reasoning("不得继续")


def test_final_content_is_split_by_unicode_character_without_splitting_other_events() -> None:
    mapper = AgentEventMapper(TurnContext(turn_id="turn-unicode", now=lambda: NOW))
    tool_delta = mapper.tool_call("call-1", "knowledge_retrieval", "delta", delta="完整工具片段")
    content = mapper.content("中🙂e\u0301")

    assert [event.data.delta for event in content] == ["中", "🙂", "e", "\u0301"]
    assert tool_delta.data.delta == "完整工具片段"
    assert [event.sequence for event in [tool_delta, *content]] == [1, 2, 3, 4, 5]


def test_mapper_emits_current_turn_reference_and_safe_error_without_complete() -> None:
    context = TurnContext(turn_id="turn-error", now=lambda: NOW)
    mapper = AgentEventMapper(context)
    reference = ChatReference(
        chunkId="chunk-1",
        documentId="doc-1",
        knowledgeBaseId="kb-1",
        source="runbook.md",
        excerpt="处理步骤",
    )

    reference_event = mapper.reference(reference)
    error_event = mapper.error(
        ApiErrorModel(
            code="SYSTEM_INTERNAL_ERROR",
            category="system",
            httpStatus=500,
            message="服务暂时不可用",
        )
    )

    assert reference_event.data.source.id == "chunk-1"
    assert reference_event.data.source.title == "runbook.md"
    assert context.references == (reference,)
    assert error_event.data.error.code == "SYSTEM_INTERNAL_ERROR"
    with pytest.raises(RuntimeError, match="已经终结"):
        mapper.complete()


def test_new_turn_does_not_inherit_previous_references_or_tool_calls() -> None:
    first = TurnContext(turn_id="turn-1", now=lambda: NOW)
    first_mapper = AgentEventMapper(first)
    first_mapper.tool_call("call-1", "knowledge_retrieval", "started")
    first_mapper.reference(
        ChatReference(
            chunkId="chunk-1",
            documentId="doc-1",
            knowledgeBaseId="kb-1",
            source="runbook.md",
        )
    )

    second = TurnContext(turn_id="turn-2", now=lambda: NOW)

    assert first.tool_call_ids == ("call-1",)
    assert second.references == ()
    assert second.tool_call_ids == ()
