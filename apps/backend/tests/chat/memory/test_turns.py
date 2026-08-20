from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from super_ai.chat.memory.context import assemble_memory_context
from super_ai.chat.memory.turns import complete_turn_boundary
from super_ai.chat.models import (
    ChatMessageRecord,
    ChatMessageRole,
    ChatSessionDetailRecord,
    ChatSessionRecord,
)
from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot, SkillCatalogEntry

NOW = datetime(2026, 8, 18, tzinfo=timezone.utc)


def message(sequence: int, role: ChatMessageRole, content: str) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=f"m-{sequence}", owner_user_id="user-a", session_id="session-a",
        role=role, content=content, sequence=sequence, metadata={}, created_at=NOW,
    )


def detail(
    messages: tuple[ChatMessageRecord, ...], *, high_water: int = 0
) -> ChatSessionDetailRecord:
    return ChatSessionDetailRecord(
        ChatSessionRecord(
            id="session-a", owner_user_id="user-a", title="会话",
            memory_mode="context_70_percent", memory_summary="既有摘要" if high_water else None,
            compacted_message_count=high_water, context_tokens=0, last_compacted_at=None,
            created_at=NOW, updated_at=NOW,
        ),
        messages,
    )


def test_complete_turn_boundary_ignores_trailing_user_and_counts_after_high_water() -> None:
    messages = (
        message(1, "user", "旧问题"), message(2, "assistant", "旧回答"),
        message(3, "user", "新问题"), message(4, "tool", "工具结果"),
        message(5, "assistant", "新回答"), message(6, "user", "未完成"),
    )

    boundary = complete_turn_boundary(messages, after_sequence=2)

    assert boundary is not None
    assert boundary.sequence == 5
    assert boundary.complete_turn_count == 1
    assert [item.sequence for item in boundary.messages] == [3, 4, 5]


def test_assemble_memory_context_uses_summary_uncompacted_messages_and_candidate() -> None:
    snapshot = ChatAgentConfigurationSnapshot(
        user_prompt="简洁回答",
        skills=(SkillCatalogEntry("knowledge-search", "检索知识"),),
    )
    record = detail(
        (message(1, "user", "旧问题"), message(2, "assistant", "旧回答"),
         message(3, "user", "新问题")),
        high_water=2,
    )

    result = assemble_memory_context(record, snapshot, candidate_content="候选问题")

    assert isinstance(result[0], SystemMessage)
    assert "knowledge-search" in str(result[0].content)
    assert isinstance(result[1], SystemMessage) and "既有摘要" in str(result[1].content)
    assert isinstance(result[2], HumanMessage) and result[2].content == "新问题"
    assert isinstance(result[3], HumanMessage) and result[3].content == "候选问题"
    assert all("旧问题" not in str(item.content) for item in result)


def test_assemble_memory_context_rejects_cross_owner_history() -> None:
    foreign = message(1, "user", "越权")
    object.__setattr__(foreign, "owner_user_id", "user-b")
    snapshot = ChatAgentConfigurationSnapshot(user_prompt=None, skills=())

    try:
        assemble_memory_context(detail((foreign,)), snapshot)
    except ValueError as error:
        assert "owner scope" in str(error)
    else:
        raise AssertionError("跨 owner 历史必须被拒绝")
