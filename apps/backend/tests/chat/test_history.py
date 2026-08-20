from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from super_ai.chat.history import trim_chat_history
from super_ai.chat.models import ChatMessageRecord
from super_ai.llm.errors import ModelConfigurationError

NOW = datetime(2026, 8, 18, tzinfo=timezone.utc)


def _message(sequence: int, role: str, content: str, owner: str = "user-a") -> ChatMessageRecord:
    return ChatMessageRecord(
        id=f"message-{sequence}",
        owner_user_id=owner,
        session_id="session-a",
        role=role,  # type: ignore[arg-type]
        content=content,
        sequence=sequence,
        metadata={},
        created_at=NOW,
    )


def test_history_drops_oldest_messages_and_keeps_current_user() -> None:
    messages = [
        _message(1, "user", "1111"),
        _message(2, "assistant", "2222"),
        _message(3, "user", "333"),
    ]

    trimmed = trim_chat_history(
        "user-a",
        messages,
        context_window_tokens=10,
        reserved_tokens=2,
        count_tokens=len,
    )

    assert [message.content for message in trimmed] == ["2222", "333"]
    assert isinstance(trimmed[0], AIMessage)
    assert isinstance(trimmed[1], HumanMessage)


def test_history_rejects_cross_owner_records() -> None:
    with pytest.raises(ValueError, match="owner scope"):
        trim_chat_history(
            "user-a",
            [_message(1, "user", "foreign", owner="user-b")],
            context_window_tokens=100,
            reserved_tokens=10,
            count_tokens=len,
        )


def test_history_fails_safely_when_current_message_exceeds_budget() -> None:
    with pytest.raises(ModelConfigurationError, match="当前消息"):
        trim_chat_history(
            "user-a",
            [_message(1, "user", "123456")],
            context_window_tokens=5,
            reserved_tokens=1,
            count_tokens=len,
        )
