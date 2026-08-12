"""qwen3-vl-rerank 的独立异步 HTTP 合同。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from super_ai.llm.config import RerankSettings
from super_ai.llm.errors import ModelProviderError


@dataclass(frozen=True, slots=True)
class RerankResult:
    index: int
    document: str
    relevance_score: float


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


class _RawResult(_ResponseModel):
    index: int = Field(ge=0)
    relevance_score: float = Field(ge=0, le=1)


class _RawOutput(_ResponseModel):
    results: list[_RawResult]


class _RawResponse(_ResponseModel):
    output: _RawOutput


async def rerank_documents(
    client: httpx.AsyncClient,
    *,
    settings: RerankSettings,
    api_key: str,
    query: str,
    documents: list[str],
    top_n: int,
) -> list[RerankResult]:
    if not documents:
        return []
    if not query.strip():
        raise ModelProviderError("Rerank query 不能为空")
    if top_n <= 0:
        raise ModelProviderError("Rerank top_n 必须大于零")
    payload: dict[str, Any] = {
        "model": settings.model,
        "input": {
            "query": {"text": query},
            "documents": [{"text": document} for document in documents],
        },
        "parameters": {"return_documents": False, "top_n": top_n},
    }
    response: httpx.Response | None = None
    for attempt in range(settings.max_retries + 1):
        try:
            response = await client.post(
                settings.endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=settings.timeout_seconds,
            )
            break
        except httpx.TransportError as error:
            if attempt == settings.max_retries:
                raise ModelProviderError(str(error)) from error
    if response is None:  # pragma: no cover - 循环总会返回响应或抛出异常
        raise ModelProviderError("Rerank 未返回响应")
    try:
        response.raise_for_status()
        parsed = _RawResponse.model_validate(response.json())
    except (httpx.HTTPStatusError, ValueError, ValidationError) as error:
        raise ModelProviderError(f"Rerank 响应无效: {error}") from error
    seen_indices: set[int] = set()
    results: list[RerankResult] = []
    for item in parsed.output.results:
        if item.index >= len(documents) or item.index in seen_indices:
            raise ModelProviderError("Rerank 响应包含无效或重复 index")
        seen_indices.add(item.index)
        results.append(RerankResult(
            index=item.index,
            document=documents[item.index],
            relevance_score=item.relevance_score,
        ))
    return results
