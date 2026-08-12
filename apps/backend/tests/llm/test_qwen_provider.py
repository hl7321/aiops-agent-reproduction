from __future__ import annotations

import importlib
from typing import Any, cast

from langchain_core.language_models import BaseChatModel
from llm_settings_factory import make_settings


def test_qwen_provider_satisfies_runtime_llm_protocol() -> None:
    provider_module = importlib.import_module("super_ai.llm.provider")
    provider = provider_module.QwenOpenAIProvider(make_settings())

    assert isinstance(provider, provider_module.LlmProvider)


def test_chat_factory_receives_locked_defaults_and_capability_profile() -> None:
    provider_module = importlib.import_module("super_ai.llm.provider")
    captured: dict[str, Any] = {}
    sentinel = cast(BaseChatModel, object())

    def chat_factory(**kwargs: Any) -> BaseChatModel:
        captured.update(kwargs)
        return sentinel

    provider = provider_module.QwenOpenAIProvider(
        make_settings(),
        chat_factory=chat_factory,
    )

    assert provider.create_chat_model() is sentinel
    assert captured == {
        "model": "qwen3.7-max",
        "temperature": 0.2,
        "timeout": 120.0,
        "max_retries": 2,
        "api_key": "test-api-key",
        "base_url": "https://dashscope.example/compatible-mode/v1",
        "profile": {"max_input_tokens": 262144},
    }


def test_chat_model_override_uses_matching_profile_without_changing_defaults() -> None:
    provider_module = importlib.import_module("super_ai.llm.provider")
    captured: dict[str, Any] = {}

    def chat_factory(**kwargs: Any) -> BaseChatModel:
        captured.update(kwargs)
        return cast(BaseChatModel, object())

    provider = provider_module.QwenOpenAIProvider(
        make_settings(chat_model="qwen-next"),
        chat_factory=chat_factory,
    )

    provider.create_chat_model()

    assert captured["model"] == "qwen-next"
    assert captured["temperature"] == 0.2
    assert captured["profile"] == {"max_input_tokens": 131072}
