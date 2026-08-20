from collections.abc import Iterable

import pytest
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from super_ai.chat.memory import tokens


def test_estimate_context_tokens_delegates_to_langchain_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = (SystemMessage(content="规则"), HumanMessage(content="问题"))
    received: list[BaseMessage] = []

    def fake_counter(items: Iterable[BaseMessage]) -> int:
        received.extend(items)
        return 70

    monkeypatch.setattr(tokens, "count_tokens_approximately", fake_counter)

    assert tokens.estimate_context_tokens(messages) == 70
    assert received == list(messages)


def test_estimate_context_tokens_rejects_negative_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def negative_counter(_items: Iterable[BaseMessage]) -> int:
        return -1

    monkeypatch.setattr(tokens, "count_tokens_approximately", negative_counter)

    try:
        tokens.estimate_context_tokens((HumanMessage(content="问题"),))
    except ValueError as error:
        assert str(error) == "token estimator 不得返回负数"
    else:
        raise AssertionError("负 token 结果必须被拒绝")
