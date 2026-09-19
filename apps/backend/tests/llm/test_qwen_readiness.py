from __future__ import annotations

import json
from typing import Any, cast

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from llm_settings_factory import make_settings

from super_ai.llm.errors import ModelProviderError
from super_ai.llm.provider import QwenOpenAIProvider


class FakeChatModel:
    def __init__(self) -> None:
        self.inputs: list[object] = []

    async def ainvoke(self, value: object) -> object:
        self.inputs.append(value)
        return object()


class FakeReadinessEmbedding:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[1.0] for _text in texts]


async def test_chat_readiness_uses_minimal_async_message_and_returns_metadata() -> None:
    chat = FakeChatModel()

    def chat_factory(**_kwargs: Any) -> BaseChatModel:
        return cast(BaseChatModel, chat)

    provider = QwenOpenAIProvider(
        make_settings(),
        chat_factory=chat_factory,
    )

    result = await provider.readiness("chat")

    assert len(chat.inputs) == 1
    messages = cast(list[HumanMessage], chat.inputs[0])
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "ping"
    assert result.model_dump(by_alias=True) == {
        "provider": "qwen-openai",
        "model": "qwen3.7-max",
        "baseUrl": "https://dashscope.example/compatible-mode/v1",
        "latency": result.latency,
    }
    assert result.latency >= 0


async def test_embedding_readiness_uses_one_raw_ping() -> None:
    embedding = FakeReadinessEmbedding()

    def embedding_factory(**_kwargs: Any) -> FakeReadinessEmbedding:
        return embedding

    provider = QwenOpenAIProvider(
        make_settings(),
        embedding_factory=embedding_factory,
    )

    result = await provider.readiness("embedding")

    assert embedding.batches == [["ping"]]
    assert result.model == "text-embedding-v4"
    assert result.base_url == "https://dashscope.example/compatible-mode/v1"
    assert result.latency >= 0


async def test_rerank_readiness_uses_one_query_and_document() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(cast(dict[str, Any], json.loads(request.content)))
        return httpx.Response(
            200,
            request=request,
            json={"output": {"results": [{"index": 0, "relevance_score": 1.0}]}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = QwenOpenAIProvider(make_settings(), http_client=client)
        result = await provider.readiness("rerank")

    assert captured["input"] == {
        "query": {"text": "ping"},
        "documents": [{"text": "ping"}],
    }
    assert captured["parameters"] == {"return_documents": False, "top_n": 1}
    assert result.model == "qwen3-vl-rerank"
    assert result.base_url == "https://dashscope.example/api/v1/services/rerank"
    assert result.latency >= 0


def test_chat_factory_exception_redacts_every_api_key_occurrence() -> None:
    api_key = "SENTINEL_PROVIDER_API_KEY"

    def failing_factory(**_kwargs: Any) -> BaseChatModel:
        raise RuntimeError(f"bad {api_key}; retry used {api_key}")

    provider = QwenOpenAIProvider(
        make_settings(api_key=api_key),
        chat_factory=failing_factory,
    )

    with pytest.raises(ModelProviderError) as captured:
        provider.create_chat_model()

    assert api_key not in str(captured.value)
    assert str(captured.value).count("[redacted]") == 2


async def test_readiness_exception_redacts_every_api_key_occurrence() -> None:
    api_key = "SENTINEL_READINESS_API_KEY"

    class FailingEmbedding:
        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            assert texts == ["ping"]
            raise RuntimeError(f"key={api_key}; duplicated={api_key}")

    def embedding_factory(**_kwargs: Any) -> FailingEmbedding:
        return FailingEmbedding()

    provider = QwenOpenAIProvider(
        make_settings(api_key=api_key),
        embedding_factory=embedding_factory,
    )

    with pytest.raises(ModelProviderError) as captured:
        await provider.readiness("embedding")

    assert api_key not in str(captured.value)
    assert str(captured.value).count("[redacted]") == 2


async def test_chat_readiness_ainvoke_exception_is_also_redacted() -> None:
    api_key = "SENTINEL_CHAT_READINESS_KEY"

    class FailingChat:
        async def ainvoke(self, _value: object) -> object:
            raise RuntimeError(f"chat key={api_key}; again={api_key}")

    def chat_factory(**_kwargs: Any) -> BaseChatModel:
        return cast(BaseChatModel, FailingChat())

    provider = QwenOpenAIProvider(
        make_settings(api_key=api_key),
        chat_factory=chat_factory,
    )

    with pytest.raises(ModelProviderError) as captured:
        await provider.readiness("chat")

    assert api_key not in str(captured.value)
    assert str(captured.value).count("[redacted]") == 2


async def test_chat_readiness_reports_effective_override_endpoint() -> None:
    """chat 配了独立端点时，readiness 要报 chat 真正打的那个地址，而不是顶层默认地址。"""

    def chat_factory(**_kwargs: Any) -> BaseChatModel:
        return cast(BaseChatModel, FakeChatModel())

    provider = QwenOpenAIProvider(
        make_settings(
            chat_model="deepseek-chat",
            chat_base_url="https://api.deepseek.example/v1",
            chat_api_key="chat-level-key",
        ),
        chat_factory=chat_factory,
    )

    result = await provider.readiness("chat")

    assert result.model == "deepseek-chat"
    assert result.base_url == "https://api.deepseek.example/v1"


async def test_chat_readiness_redacts_both_chat_and_top_level_keys() -> None:
    """两把 key 同时存在时，异常里出现任何一把都必须被替换掉。"""
    top_key = "SENTINEL_TOP_LEVEL_KEY"
    chat_key = "SENTINEL_CHAT_LEVEL_KEY"

    class FailingChat(FakeChatModel):
        async def ainvoke(self, value: object) -> object:
            raise RuntimeError(f"chat={chat_key}; top={top_key}")

    def chat_factory(**_kwargs: Any) -> BaseChatModel:
        return cast(BaseChatModel, FailingChat())

    provider = QwenOpenAIProvider(
        make_settings(api_key=top_key, chat_api_key=chat_key),
        chat_factory=chat_factory,
    )

    with pytest.raises(ModelProviderError) as captured:
        await provider.readiness("chat")

    message = str(captured.value)
    assert chat_key not in message
    assert top_key not in message
    assert message.count("[redacted]") == 2
