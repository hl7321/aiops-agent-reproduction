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


async def test_chat_uses_its_own_endpoint_and_key_while_embedding_keeps_top_level() -> None:
    """chat 换厂商不能牵动 embedding：一个走 chat 覆盖值，另一个仍走顶层值。"""
    provider_module = importlib.import_module("super_ai.llm.provider")
    chat_captured: dict[str, Any] = {}
    embedding_captured: dict[str, Any] = {}

    def chat_factory(**kwargs: Any) -> BaseChatModel:
        chat_captured.update(kwargs)
        return cast(BaseChatModel, object())

    class FakeEmbedding:
        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0] for _text in texts]

    def embedding_factory(**kwargs: Any) -> Any:
        embedding_captured.update(kwargs)
        return FakeEmbedding()

    settings = make_settings(
        chat_model="deepseek-chat",
        chat_base_url="https://chat.example/v1",
        chat_api_key="chat-secret-key",
    )
    provider = provider_module.QwenOpenAIProvider(
        settings,
        chat_factory=chat_factory,
        embedding_factory=embedding_factory,
    )

    provider.create_chat_model()

    assert chat_captured["base_url"] == "https://chat.example/v1"
    assert chat_captured["api_key"] == "chat-secret-key"
    assert chat_captured["model"] == "deepseek-chat"

    await provider.embed_documents(["ping"])
    assert embedding_captured["base_url"] == "https://dashscope.example/compatible-mode/v1"
    assert embedding_captured["api_key"] == "test-api-key"


def test_blank_chat_overrides_fall_back_to_top_level_values() -> None:
    """模板里的空串等于没覆盖，行为与只配置顶层值完全一致。"""
    provider_module = importlib.import_module("super_ai.llm.provider")
    captured: dict[str, Any] = {}

    def chat_factory(**kwargs: Any) -> BaseChatModel:
        captured.update(kwargs)
        return cast(BaseChatModel, object())

    settings = make_settings(chat_base_url="", chat_api_key="")
    provider = provider_module.QwenOpenAIProvider(settings, chat_factory=chat_factory)

    provider.create_chat_model()

    assert settings.chat_base_url() == "https://dashscope.example/compatible-mode/v1"
    assert settings.chat_api_key() == "test-api-key"
    assert captured["base_url"] == "https://dashscope.example/compatible-mode/v1"
    assert captured["api_key"] == "test-api-key"
