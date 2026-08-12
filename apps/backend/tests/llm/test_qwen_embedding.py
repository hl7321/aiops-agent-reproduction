from __future__ import annotations

import importlib
from typing import Any

import pytest
from llm_settings_factory import make_settings

from super_ai.llm.config import LlmSettings


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[float(text.removeprefix("raw-"))] for text in texts]


async def test_embedding_factory_receives_qwen_v4_raw_string_parameters() -> None:
    provider_module = importlib.import_module("super_ai.llm.provider")
    captured: dict[str, Any] = {}
    client = FakeEmbeddingClient()

    def embedding_factory(**kwargs: Any) -> FakeEmbeddingClient:
        captured.update(kwargs)
        return client

    provider = provider_module.QwenOpenAIProvider(
        make_settings(),
        embedding_factory=embedding_factory,
    )

    assert await provider.embed_documents(["raw-0"]) == [[0.0]]
    assert captured == {
        "model": "text-embedding-v4",
        "dimensions": 1024,
        "chunk_size": 10,
        "check_embedding_ctx_length": False,
        "timeout": 120.0,
        "max_retries": 2,
        "api_key": "test-api-key",
        "base_url": "https://dashscope.example/compatible-mode/v1",
    }
    assert client.batches == [["raw-0"]]


async def test_embedding_over_ten_batches_10_10_3_and_preserves_order() -> None:
    provider_module = importlib.import_module("super_ai.llm.provider")
    client = FakeEmbeddingClient()
    inputs = [f"raw-{index}" for index in range(23)]

    def embedding_factory(**_kwargs: Any) -> FakeEmbeddingClient:
        return client

    provider = provider_module.QwenOpenAIProvider(
        make_settings(),
        embedding_factory=embedding_factory,
    )

    result = await provider.embed_documents(inputs)

    assert [len(batch) for batch in client.batches] == [10, 10, 3]
    assert [item for batch in client.batches for item in batch] == inputs
    assert result == [[float(index)] for index in range(23)]


async def test_empty_embedding_input_does_not_create_client() -> None:
    provider_module = importlib.import_module("super_ai.llm.provider")
    factory_calls = 0

    def forbidden_factory(**_kwargs: Any) -> FakeEmbeddingClient:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("空输入不得创建 embedding client")

    provider = provider_module.QwenOpenAIProvider(
        make_settings(),
        embedding_factory=forbidden_factory,
    )

    assert await provider.embed_documents([]) == []
    assert factory_calls == 0


async def test_embedding_vector_count_mismatch_returns_no_partial_fallback() -> None:
    provider_module = importlib.import_module("super_ai.llm.provider")

    class ShortEmbeddingClient:
        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            assert texts == ["raw-0"]
            return []

    def embedding_factory(**_kwargs: Any) -> ShortEmbeddingClient:
        return ShortEmbeddingClient()

    provider = provider_module.QwenOpenAIProvider(
        make_settings(),
        embedding_factory=embedding_factory,
    )

    with pytest.raises(RuntimeError, match="数量"):
        await provider.embed_documents(["raw-0"])


def test_settings_fixture_is_typed() -> None:
    assert isinstance(make_settings(), LlmSettings)
