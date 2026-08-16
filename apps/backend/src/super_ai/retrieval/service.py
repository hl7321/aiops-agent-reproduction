from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from typing import Protocol

from super_ai.api_contracts import (
    KnowledgeRetrievalCitation,
    KnowledgeRetrievalToolInput,
    KnowledgeRetrievalToolOutput,
)
from super_ai.background_jobs.security import redact_error
from super_ai.knowledge.service import default_knowledge_base_id
from super_ai.llm.rerank import RerankResult
from super_ai.retrieval.bm25 import rank_bm25l
from super_ai.retrieval.errors import KnowledgeRetrievalError, RetrievalStage
from super_ai.retrieval.fusion import reciprocal_rank_fusion
from super_ai.retrieval.models import BranchHit, FusedCandidate, RetrievalChunk
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.records import VectorSearchHit


class RetrievalCorpusSource(Protocol):
    async def load(
        self,
        owner_user_id: str,
        knowledge_base_ids: tuple[str, ...],
        document_ids: tuple[str, ...] | None,
    ) -> tuple[RetrievalChunk, ...]: ...


class RetrievalProvider(Protocol):
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    async def rerank(
        self, query: str, documents: Sequence[str], *, top_n: int
    ) -> list[RerankResult]: ...


class RetrievalVectorStore(Protocol):
    async def initialize(self) -> None: ...
    async def search(
        self, scope: VectorScope, query_vector: Sequence[float], *, limit: int
    ) -> list[VectorSearchHit]: ...


class KeywordRetriever(Protocol):
    async def retrieve(
        self, query: str, chunks: Sequence[RetrievalChunk]
    ) -> tuple[BranchHit, ...]: ...


class InMemoryBm25LRetriever:
    async def retrieve(
        self, query: str, chunks: Sequence[RetrievalChunk]
    ) -> tuple[BranchHit, ...]:
        return await asyncio.to_thread(rank_bm25l, query, chunks, limit=20)


class KnowledgeRetrievalService:
    def __init__(
        self,
        corpus: RetrievalCorpusSource,
        provider: RetrievalProvider,
        vector_store: RetrievalVectorStore,
        keyword_retriever: KeywordRetriever | None = None,
    ) -> None:
        self._corpus = corpus
        self._provider = provider
        self._vectors = vector_store
        self._keywords = keyword_retriever or InMemoryBm25LRetriever()

    async def retrieve(
        self, current_user: CurrentUser, tool_input: KnowledgeRetrievalToolInput
    ) -> KnowledgeRetrievalToolOutput:
        allowed_kbs = _allowed_knowledge_bases(current_user, tool_input.knowledge_base_ids)
        if not allowed_kbs:
            return KnowledgeRetrievalToolOutput(results=[])
        document_ids = _normalized_filter(tool_input.document_ids)
        if tool_input.document_ids is not None and not document_ids:
            return KnowledgeRetrievalToolOutput(results=[])
        try:
            chunks = await self._corpus.load(
                current_user.owner_user_id, allowed_kbs, document_ids
            )
        except Exception as error:
            raise _safe_error("bm25", error) from error
        if not chunks:
            return KnowledgeRetrievalToolOutput(results=[])
        vector_result, keyword_result = await asyncio.gather(
            self._vector_branch(current_user, tool_input.query, allowed_kbs, chunks),
            self._keyword_branch(tool_input.query, chunks),
            return_exceptions=True,
        )
        if isinstance(vector_result, BaseException):
            raise vector_result
        if isinstance(keyword_result, BaseException):
            raise keyword_result
        fused = reciprocal_rank_fusion(vector_result, keyword_result, limit=20, rrf_k=60)
        if not fused:
            return KnowledgeRetrievalToolOutput(results=[])
        results = await self._rerank(tool_input.query, fused, top_k=tool_input.top_k)
        return KnowledgeRetrievalToolOutput(results=results)

    async def _vector_branch(
        self,
        current_user: CurrentUser,
        query: str,
        allowed_kbs: tuple[str, ...],
        chunks: Sequence[RetrievalChunk],
    ) -> tuple[BranchHit, ...]:
        try:
            embedded = await self._provider.embed_documents([query])
            if len(embedded) != 1 or len(embedded[0]) != 1024:
                raise ValueError("query embedding 必须恰好返回一个 1024 维向量")
        except Exception as error:
            raise _safe_error("embedding", error) from error
        try:
            await self._vectors.initialize()
            scope = VectorScope(
                current_user.tenant_id, current_user.owner_user_id, allowed_kbs
            )
            raw_hits = await self._vectors.search(scope, embedded[0], limit=20)
            return _rank_vector_hits(raw_hits, chunks)
        except Exception as error:
            raise _safe_error("vector", error) from error

    async def _keyword_branch(
        self, query: str, chunks: Sequence[RetrievalChunk]
    ) -> tuple[BranchHit, ...]:
        try:
            return await self._keywords.retrieve(query, chunks)
        except Exception as error:
            raise _safe_error("bm25", error) from error

    async def _rerank(
        self, query: str, candidates: Sequence[FusedCandidate], *, top_k: int
    ) -> list[KnowledgeRetrievalCitation]:
        top_n = min(top_k, len(candidates), 5)
        try:
            reranked = await self._provider.rerank(
                query, [item.chunk.excerpt for item in candidates], top_n=top_n
            )
            _validate_rerank(reranked, len(candidates))
        except Exception as error:
            raise _safe_error("rerank", error) from error
        return [
            _citation(candidates[item.index], rank, item.relevance_score)
            for rank, item in enumerate(reranked[:top_n], start=1)
        ]


def _allowed_knowledge_bases(
    current_user: CurrentUser, requested: tuple[str, ...] | None
) -> tuple[str, ...]:
    default_kb = default_knowledge_base_id(current_user.owner_user_id)
    if requested is None:
        return (default_kb,)
    return (default_kb,) if default_kb in {item.strip() for item in requested} else ()


def _normalized_filter(values: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    return tuple(sorted({value.strip() for value in values if value.strip()}))


def _rank_vector_hits(
    hits: Sequence[VectorSearchHit], chunks: Sequence[RetrievalChunk]
) -> tuple[BranchHit, ...]:
    corpus = {chunk.chunk_id: chunk for chunk in chunks}
    best: dict[str, float] = {}
    for hit in hits:
        if hit.chunk_id not in corpus or not math.isfinite(hit.distance):
            continue
        current = best.get(hit.chunk_id)
        if current is None or hit.distance > current:
            best[hit.chunk_id] = hit.distance
    ordered = sorted(best.items(), key=lambda item: (-item[1], item[0]))
    return tuple(
        BranchHit(corpus[chunk_id], rank, score)
        for rank, (chunk_id, score) in enumerate(ordered, start=1)
    )


def _validate_rerank(results: Sequence[RerankResult], candidate_count: int) -> None:
    seen: set[int] = set()
    for result in results:
        if (
            result.index < 0
            or result.index >= candidate_count
            or result.index in seen
            or not math.isfinite(result.relevance_score)
        ):
            raise ValueError("rerank 返回无效 index 或 score")
        seen.add(result.index)


def _citation(
    candidate: FusedCandidate, rerank_rank: int, rerank_score: float
) -> KnowledgeRetrievalCitation:
    chunk = candidate.chunk
    return KnowledgeRetrievalCitation(
        chunkId=chunk.chunk_id,
        documentId=chunk.document_id,
        knowledgeBaseId=chunk.knowledge_base_id,
        source=chunk.source,
        excerpt=chunk.excerpt,
        metadata=dict(chunk.metadata),
        vectorRank=candidate.vector_rank,
        vectorScore=candidate.vector_score,
        bm25Rank=candidate.bm25_rank,
        bm25Score=candidate.bm25_score,
        rrfScore=candidate.rrf_score,
        rerankRank=rerank_rank,
        rerankScore=rerank_score,
        score=rerank_score,
    )


def _safe_error(stage: RetrievalStage, error: Exception) -> KnowledgeRetrievalError:
    safe = redact_error(str(error), "{}")
    return KnowledgeRetrievalError(stage, safe)
