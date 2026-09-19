"""延迟创建 OpenAI-compatible client 的 Qwen provider。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from time import perf_counter
from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from super_ai.llm.config import LlmSettings
from super_ai.llm.errors import ModelProviderError, sanitize_exception
from super_ai.llm.readiness import ProviderCapability, ProviderReadiness
from super_ai.llm.rerank import RerankResult, rerank_documents
from super_ai.llm.types import EmbeddingClient, LlmProvider

ChatFactory = Callable[..., BaseChatModel]
EmbeddingFactory = Callable[..., EmbeddingClient]


def _create_chat_openai(**kwargs: Any) -> BaseChatModel:
    return ChatOpenAI(**kwargs)


def _create_openai_embeddings(**kwargs: Any) -> EmbeddingClient:
    return OpenAIEmbeddings(**kwargs)


class QwenOpenAIProvider:
    def __init__(
        self,
        settings: LlmSettings,
        *,
        chat_factory: ChatFactory = _create_chat_openai,
        embedding_factory: EmbeddingFactory = _create_openai_embeddings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._chat_factory = chat_factory
        self._embedding_factory = embedding_factory
        self._http_client = http_client

    def create_chat_model(self) -> BaseChatModel:
        # chat 有自己的生效端点与生效凭据：可以是另一家 OpenAI-compatible 厂商，
        # 而 embedding / rerank 继续用顶层 baseUrl 与 apiKey。
        api_key = self._settings.chat_api_key()
        chat = self._settings.chat
        capability = self._settings.capability_for_chat()
        try:
            return self._chat_factory(
                model=chat.model,
                temperature=chat.temperature,
                timeout=chat.timeout_seconds,
                max_retries=chat.max_retries,
                api_key=api_key,
                base_url=self._settings.chat_base_url(),
                profile={"max_input_tokens": capability.context_window_tokens},
            )
        except Exception as error:
            raise sanitize_exception(error, *self._settings.chat_redaction_keys()) from error

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        inputs = list(texts)
        if not inputs:
            return []
        api_key = self._settings.require_api_key()
        embedding = self._settings.embedding
        try:
            client = self._embedding_factory(
                model=embedding.model,
                dimensions=embedding.dimensions,
                chunk_size=embedding.batch_size,
                check_embedding_ctx_length=False,
                timeout=embedding.timeout_seconds,
                max_retries=embedding.max_retries,
                api_key=api_key,
                base_url=self._settings.base_url,
            )
            vectors: list[list[float]] = []
            for offset in range(0, len(inputs), embedding.batch_size):
                batch = inputs[offset : offset + embedding.batch_size]
                batch_vectors = await client.aembed_documents(batch)
                if len(batch_vectors) != len(batch):
                    raise ModelProviderError("Embedding 返回向量数量与输入数量不一致")
                vectors.extend(batch_vectors)
            return vectors
        except Exception as error:
            raise sanitize_exception(error, api_key) from error

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int,
    ) -> list[RerankResult]:
        inputs = list(documents)
        if not inputs:
            return []
        api_key = self._settings.require_api_key()
        try:
            if self._http_client is not None:
                return await rerank_documents(
                    self._http_client,
                    settings=self._settings.rerank,
                    api_key=api_key,
                    query=query,
                    documents=inputs,
                    top_n=top_n,
                )
            async with httpx.AsyncClient() as client:
                return await rerank_documents(
                    client,
                    settings=self._settings.rerank,
                    api_key=api_key,
                    query=query,
                    documents=inputs,
                    top_n=top_n,
                )
        except Exception as error:
            raise sanitize_exception(error, api_key) from error

    async def readiness(self, capability: ProviderCapability) -> ProviderReadiness:
        started = perf_counter()
        # 脱敏按这次调用真正会用到的那把 key 生效：chat 可能用的是独立凭据。
        redaction_keys = (
            self._settings.chat_redaction_keys()
            if capability == "chat"
            else (self._settings.require_api_key(),)
        )
        try:
            if capability == "chat":
                model = self.create_chat_model()
                await model.ainvoke([HumanMessage(content="ping")])
                model_name = self._settings.chat.model
                base_url = self._settings.chat_base_url()
            elif capability == "embedding":
                await self.embed_documents(["ping"])
                model_name = self._settings.embedding.model
                base_url = self._settings.base_url
            else:
                await self.rerank("ping", ["ping"], top_n=1)
                model_name = self._settings.rerank.model
                base_url = self._settings.rerank.endpoint
        except Exception as error:
            raise sanitize_exception(error, *redaction_keys) from error
        return ProviderReadiness(
            provider=self._settings.provider,
            model=model_name,
            baseUrl=base_url,
            latency=(perf_counter() - started) * 1000,
        )


__all__ = ["LlmProvider", "QwenOpenAIProvider"]
