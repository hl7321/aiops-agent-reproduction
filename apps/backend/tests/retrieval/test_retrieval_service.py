import asyncio
from collections.abc import Sequence

import pytest
from pydantic import JsonValue

from super_ai.api_contracts import KnowledgeRetrievalToolInput
from super_ai.knowledge.service import default_knowledge_base_id
from super_ai.llm.rerank import RerankResult
from super_ai.retrieval.errors import KnowledgeRetrievalError
from super_ai.retrieval.models import BranchHit, RetrievalChunk
from super_ai.retrieval.service import KnowledgeRetrievalService
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.records import VectorSearchHit


class FakeCorpus:
    def __init__(self, chunks: Sequence[RetrievalChunk]) -> None:
        self._chunks = tuple(chunks)
        self.calls: list[tuple[str, tuple[str, ...], tuple[str, ...] | None]] = []
        self.error: Exception | None = None

    async def load(
        self,
        owner_user_id: str,
        knowledge_base_ids: tuple[str, ...],
        document_ids: tuple[str, ...] | None,
    ) -> tuple[RetrievalChunk, ...]:
        self.calls.append((owner_user_id, knowledge_base_ids, document_ids))
        if self.error:
            raise self.error
        allowed_documents = set(document_ids) if document_ids is not None else None
        return tuple(
            RetrievalChunk(
                chunk.chunk_id,
                chunk.document_id,
                knowledge_base_ids[0],
                chunk.source,
                chunk.excerpt,
                chunk.metadata,
            )
            for chunk in self._chunks
            if allowed_documents is None or chunk.document_id in allowed_documents
        )


class FakeProvider:
    def __init__(self, rerank: Sequence[tuple[int, float]] = ((0, 0.4),)) -> None:
        self.rerank_results = tuple(rerank)
        self.embed_calls = 0
        self.rerank_calls: list[tuple[str, list[str], int]] = []
        self.embedding_error: Exception | None = None
        self.rerank_error: Exception | None = None

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.embed_calls += 1
        if self.embedding_error:
            raise self.embedding_error
        return [[0.1] * 1024 for _ in texts]

    async def rerank(
        self, query: str, documents: Sequence[str], *, top_n: int
    ) -> list[RerankResult]:
        self.rerank_calls.append((query, list(documents), top_n))
        if self.rerank_error:
            raise self.rerank_error
        return [
            RerankResult(index, documents[index], score)
            for index, score in self.rerank_results
        ]


class FakeVectorStore:
    def __init__(self, hits: Sequence[VectorSearchHit] = ()) -> None:
        self.hits = list(hits)
        self.initialized = 0
        self.search_scopes: list[VectorScope] = []
        self.error: Exception | None = None

    async def initialize(self) -> None:
        self.initialized += 1

    async def search(
        self, scope: VectorScope, query_vector: Sequence[float], *, limit: int
    ) -> list[VectorSearchHit]:
        del query_vector
        assert limit == 20
        self.search_scopes.append(scope)
        if self.error:
            raise self.error
        return self.hits


class FakeKeywordRetriever:
    def __init__(self, hits: Sequence[BranchHit] = ()) -> None:
        self.hits = tuple(hits)
        self.calls = 0
        self.error: Exception | None = None

    async def retrieve(
        self, query: str, chunks: Sequence[RetrievalChunk]
    ) -> tuple[BranchHit, ...]:
        del query, chunks
        self.calls += 1
        if self.error:
            raise self.error
        return self.hits


def _vector_hit(chunk: RetrievalChunk, score: float) -> VectorSearchHit:
    entity: dict[str, JsonValue] = {
        "documentId": chunk.document_id,
        "knowledgeBaseId": chunk.knowledge_base_id,
        "content": chunk.excerpt,
        "source": chunk.source,
        "metadata": dict(chunk.metadata),
    }
    return VectorSearchHit(chunk.chunk_id, score, entity)


async def test_service_defaults_top_k_and_rerank_reorders_without_losing_branch_ranks() -> None:
    user = CurrentUser("user-a")
    kb = default_knowledge_base_id(user.user_id)
    first = RetrievalChunk("a", "doc-a", kb, "a.md", "vector and keyword", {"index": 0})
    second = RetrievalChunk("b", "doc-b", kb, "b.md", "vector only", {"index": 0})
    corpus = FakeCorpus((first, second))
    provider = FakeProvider(((1, 0.01), (0, 0.001)))
    vectors = FakeVectorStore((_vector_hit(first, 0.9), _vector_hit(second, 0.8)))
    keywords = FakeKeywordRetriever((BranchHit(first, 1, 2.5),))
    service = KnowledgeRetrievalService(corpus, provider, vectors, keywords)

    output = await service.retrieve(user, KnowledgeRetrievalToolInput(query="incident"))

    assert [item.chunk_id for item in output.results] == ["b", "a"]
    assert provider.rerank_calls[0][2] == 2
    assert output.results[0].vector_rank == 2
    assert output.results[0].bm25_rank is None
    assert output.results[0].bm25_score is None
    assert output.results[0].rerank_rank == 1
    assert output.results[0].score == output.results[0].rerank_score == 0.01
    assert output.results[1].vector_rank == 1 and output.results[1].bm25_rank == 1
    assert abs(output.results[1].rrf_score - (2 / 61)) < 1e-12
    assert vectors.search_scopes[0].tenant_id == vectors.search_scopes[0].owner_user_id == "user-a"


async def test_filters_only_narrow_owner_scope_and_empty_intersection_short_circuits() -> None:
    user = CurrentUser("user-a")
    corpus = FakeCorpus(())
    provider = FakeProvider()
    vectors = FakeVectorStore()
    keywords = FakeKeywordRetriever()
    service = KnowledgeRetrievalService(corpus, provider, vectors, keywords)

    output = await service.retrieve(
        user,
        KnowledgeRetrievalToolInput(query="secret", knowledgeBaseIds=("other-user-kb",)),
    )

    assert output.results == []
    assert corpus.calls == []
    assert provider.embed_calls == vectors.initialized == keywords.calls == 0


async def test_empty_corpus_returns_no_fallback_and_does_not_call_external_branches() -> None:
    user = CurrentUser("user-a")
    provider = FakeProvider()
    vectors = FakeVectorStore()
    service = KnowledgeRetrievalService(FakeCorpus(()), provider, vectors, FakeKeywordRetriever())

    output = await service.retrieve(user, KnowledgeRetrievalToolInput(query="missing"))

    assert output.results == []
    assert provider.rerank_calls == []
    assert vectors.initialized == 0


async def test_document_filter_is_owner_scoped_before_external_search() -> None:
    user = CurrentUser("user-a")
    corpus = FakeCorpus(())
    provider = FakeProvider()
    vectors = FakeVectorStore()
    service = KnowledgeRetrievalService(corpus, provider, vectors, FakeKeywordRetriever())

    output = await service.retrieve(
        user,
        KnowledgeRetrievalToolInput(query="private", documentIds=("other-user-doc",)),
    )

    assert output.results == []
    assert corpus.calls[0][2] == ("other-user-doc",)
    assert provider.embed_calls == vectors.initialized == 0


async def test_rerank_may_return_fewer_results_without_threshold_or_fill() -> None:
    user = CurrentUser("user-a")
    kb = default_knowledge_base_id(user.user_id)
    first = RetrievalChunk("a", "doc-a", kb, "a.md", "first", {})
    second = RetrievalChunk("b", "doc-b", kb, "b.md", "second", {})
    provider = FakeProvider(((1, 0.00001),))
    vectors = FakeVectorStore((_vector_hit(first, 0.9), _vector_hit(second, 0.8)))
    service = KnowledgeRetrievalService(
        FakeCorpus((first, second)), provider, vectors, FakeKeywordRetriever()
    )

    output = await service.retrieve(user, KnowledgeRetrievalToolInput(query="incident"))

    assert len(output.results) == 1
    assert output.results[0].chunk_id == "b"
    assert output.results[0].rerank_score == output.results[0].score == 0.00001


async def test_vector_and_keyword_branches_start_concurrently() -> None:
    user = CurrentUser("user-a")
    kb = default_knowledge_base_id(user.user_id)
    chunk = RetrievalChunk("a", "doc-a", kb, "a.md", "incident", {})
    vector_started = asyncio.Event()
    keyword_started = asyncio.Event()

    class ConcurrentProvider(FakeProvider):
        async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
            del texts
            vector_started.set()
            await asyncio.wait_for(keyword_started.wait(), timeout=0.5)
            return [[0.1] * 1024]

    class ConcurrentKeyword(FakeKeywordRetriever):
        async def retrieve(
            self, query: str, chunks: Sequence[RetrievalChunk]
        ) -> tuple[BranchHit, ...]:
            del query, chunks
            keyword_started.set()
            await asyncio.wait_for(vector_started.wait(), timeout=0.5)
            return ()

    provider = ConcurrentProvider(((0, 0.2),))
    service = KnowledgeRetrievalService(
        FakeCorpus((chunk,)),
        provider,
        FakeVectorStore((_vector_hit(chunk, 0.9),)),
        ConcurrentKeyword(),
    )

    output = await service.retrieve(user, KnowledgeRetrievalToolInput(query="incident"))

    assert vector_started.is_set() and keyword_started.is_set()
    assert len(output.results) == 1


@pytest.mark.parametrize("stage", ["embedding", "vector", "bm25", "rerank"])
async def test_required_branch_failure_is_redacted_and_never_returns_partial_success(
    stage: str,
) -> None:
    user = CurrentUser("user-a")
    kb = default_knowledge_base_id(user.user_id)
    chunk = RetrievalChunk("a", "doc-a", kb, "a.md", "incident", {})
    provider = FakeProvider(((0, 0.5),))
    vectors = FakeVectorStore((_vector_hit(chunk, 0.9),))
    keywords = FakeKeywordRetriever((BranchHit(chunk, 1, 1.0),))
    error = RuntimeError("apiKey=super-secret unavailable")
    if stage == "embedding":
        provider.embedding_error = error
    elif stage == "vector":
        vectors.error = error
    elif stage == "bm25":
        keywords.error = error
    else:
        provider.rerank_error = error
    service = KnowledgeRetrievalService(FakeCorpus((chunk,)), provider, vectors, keywords)

    with pytest.raises(KnowledgeRetrievalError) as raised:
        await service.retrieve(user, KnowledgeRetrievalToolInput(query="incident"))

    assert raised.value.stage == stage
    assert "super-secret" not in str(raised.value)
    assert "[redacted]" in str(raised.value)


async def test_corpus_construction_failure_uses_safe_bm25_error_boundary() -> None:
    corpus = FakeCorpus(())
    corpus.error = RuntimeError("token=super-secret corpus unavailable")
    service = KnowledgeRetrievalService(
        corpus, FakeProvider(), FakeVectorStore(), FakeKeywordRetriever()
    )

    with pytest.raises(KnowledgeRetrievalError) as raised:
        await service.retrieve(
            CurrentUser("user-a"), KnowledgeRetrievalToolInput(query="incident")
        )

    assert raised.value.stage == "bm25"
    assert "super-secret" not in str(raised.value)
    assert "[redacted]" in str(raised.value)
