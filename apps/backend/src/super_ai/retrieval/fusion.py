from __future__ import annotations

from collections.abc import Sequence

from super_ai.retrieval.models import BranchHit, FusedCandidate


def reciprocal_rank_fusion(
    vector_hits: Sequence[BranchHit],
    bm25_hits: Sequence[BranchHit],
    *,
    limit: int = 20,
    rrf_k: int = 60,
) -> tuple[FusedCandidate, ...]:
    if limit <= 0 or rrf_k <= 0:
        raise ValueError("limit 与 rrf_k 必须大于零")
    vector_by_id = {hit.chunk.chunk_id: hit for hit in vector_hits}
    bm25_by_id = {hit.chunk.chunk_id: hit for hit in bm25_hits}
    candidates: list[FusedCandidate] = []
    for chunk_id in vector_by_id.keys() | bm25_by_id.keys():
        vector = vector_by_id.get(chunk_id)
        bm25 = bm25_by_id.get(chunk_id)
        source = vector or bm25
        if source is None:  # pragma: no cover - union 保证至少一侧存在
            continue
        score = (1 / (rrf_k + vector.rank) if vector else 0.0) + (
            1 / (rrf_k + bm25.rank) if bm25 else 0.0
        )
        candidates.append(
            FusedCandidate(
                chunk=source.chunk,
                vector_rank=vector.rank if vector else None,
                vector_score=vector.score if vector else None,
                bm25_rank=bm25.rank if bm25 else None,
                bm25_score=bm25.score if bm25 else None,
                rrf_score=score,
            )
        )
    return tuple(
        sorted(candidates, key=lambda item: (-item.rrf_score, item.chunk.chunk_id))[:limit]
    )
