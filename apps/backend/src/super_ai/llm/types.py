"""模型 provider 的可注入协议与不可变 record。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from langchain_core.language_models import BaseChatModel

from super_ai.llm.readiness import ProviderCapability, ProviderReadiness
from super_ai.llm.rerank import RerankResult


class EmbeddingClient(Protocol):
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class LlmProvider(Protocol):
    def create_chat_model(self) -> BaseChatModel: ...

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int,
    ) -> list[RerankResult]: ...

    async def readiness(self, capability: ProviderCapability) -> ProviderReadiness: ...
