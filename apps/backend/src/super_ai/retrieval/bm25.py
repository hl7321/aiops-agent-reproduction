from __future__ import annotations

import math
from collections.abc import Sequence

from rank_bm25 import BM25L

from super_ai.retrieval.models import BranchHit, RetrievalChunk
from super_ai.retrieval.tokenizer import tokenize_for_retrieval


def bm25l_scores(query: str, documents: Sequence[str]) -> tuple[float, ...]:
    query_tokens = tokenize_for_retrieval(query)
    corpus = [tokenize_for_retrieval(document) for document in documents]
    if not documents:
        return ()
    if not query_tokens or not any(corpus):
        return tuple(0.0 for _ in documents)
    raw_scores = BM25L(corpus).get_scores(query_tokens)
    query_terms = set(query_tokens)
    scores: list[float] = []
    for tokens, raw in zip(corpus, raw_scores, strict=True):
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("BM25L 返回非有限分数")
        scores.append(max(0.0, value) if query_terms.intersection(tokens) else 0.0)
    return tuple(scores)


def rank_bm25l(
    query: str, chunks: Sequence[RetrievalChunk], *, limit: int = 20
) -> tuple[BranchHit, ...]:
    if limit <= 0:
        raise ValueError("limit 必须大于零")
    scores = bm25l_scores(query, [chunk.excerpt for chunk in chunks])
    ordered = sorted(
        ((chunk, score) for chunk, score in zip(chunks, scores, strict=True) if score > 0),
        key=lambda item: (-item[1], item[0].chunk_id),
    )[:limit]
    return tuple(
        BranchHit(chunk=chunk, rank=rank, score=score)
        for rank, (chunk, score) in enumerate(ordered, start=1)
    )
