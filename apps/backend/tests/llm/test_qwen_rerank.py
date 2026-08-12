from __future__ import annotations

import json

import httpx
import pytest
from llm_settings_factory import make_settings

from super_ai.llm.errors import ModelProviderError
from super_ai.llm.provider import QwenOpenAIProvider


def _success_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        json={
            "output": {
                "results": [
                    {"index": 2, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.75},
                ]
            },
            "usage": {"total_tokens": 12},
            "request_id": "request-1",
        },
    )


async def test_rerank_sends_qwen_vl_payload_and_uses_real_scores() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return _success_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = QwenOpenAIProvider(make_settings(), http_client=client)
        result = await provider.rerank(
            "什么是重排序？",
            ["文档零", "文档一", "文档二"],
            top_n=2,
        )

    assert captured == {
        "url": "https://dashscope.example/api/v1/services/rerank",
        "authorization": "Bearer test-api-key",
        "payload": {
            "model": "qwen3-vl-rerank",
            "input": {
                "query": {"text": "什么是重排序？"},
                "documents": [{"text": "文档零"}, {"text": "文档一"}, {"text": "文档二"}],
            },
            "parameters": {"return_documents": False, "top_n": 2},
        },
    }
    assert [(item.index, item.document, item.relevance_score) for item in result] == [
        (2, "文档二", 0.91),
        (0, "文档零", 0.75),
    ]


async def test_rerank_retries_two_timeouts_then_returns_third_real_response() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ReadTimeout("temporary timeout", request=request)
        return _success_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await QwenOpenAIProvider(
            make_settings(),
            http_client=client,
        ).rerank("query", ["zero", "one", "two"], top_n=2)

    assert calls == 3
    assert [item.relevance_score for item in result] == [0.91, 0.75]


async def test_rerank_transport_retry_exhaustion_returns_no_fallback() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("network unavailable", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = QwenOpenAIProvider(make_settings(), http_client=client)
        with pytest.raises(ModelProviderError, match="network unavailable"):
            await provider.rerank("query", ["document"], top_n=1)

    assert calls == 3


async def test_rerank_http_error_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, request=request, json={"message": "invalid credential"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = QwenOpenAIProvider(make_settings(), http_client=client)
        with pytest.raises(ModelProviderError):
            await provider.rerank("query", ["document"], top_n=1)

    assert calls == 1


@pytest.mark.parametrize(
    "result",
    [
        {"index": 4, "relevance_score": 0.5},
        {"index": 0, "relevance_score": "fallback"},
    ],
)
async def test_rerank_rejects_malformed_result_without_fallback(result: dict[str, object]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"output": {"results": [result]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = QwenOpenAIProvider(make_settings(), http_client=client)
        with pytest.raises(ModelProviderError, match="响应"):
            await provider.rerank("query", ["document"], top_n=1)


async def test_empty_rerank_documents_do_not_send_http_request() -> None:
    calls = 0

    def forbidden_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise AssertionError("空 documents 不得调用 rerank")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden_handler)) as client:
        provider = QwenOpenAIProvider(make_settings(), http_client=client)
        assert await provider.rerank("query", [], top_n=1) == []

    assert calls == 0
