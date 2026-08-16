from super_ai.retrieval.fusion import reciprocal_rank_fusion
from super_ai.retrieval.models import BranchHit, RetrievalChunk


def _hit(chunk_id: str, rank: int, score: float) -> BranchHit:
    chunk = RetrievalChunk(chunk_id, f"doc-{chunk_id}", "kb-a", "source.md", chunk_id, {})
    return BranchHit(chunk, rank, score)


def test_rrf_uses_k_60_and_preserves_nullable_single_branch_evidence() -> None:
    fused = reciprocal_rank_fusion((_hit("both", 1, 0.9),), (_hit("both", 2, 2.0),))
    single = reciprocal_rank_fusion((_hit("vector-only", 1, 0.8),), ())

    assert abs(fused[0].rrf_score - (1 / 61 + 1 / 62)) < 1e-12
    assert fused[0].vector_rank == 1 and fused[0].bm25_rank == 2
    assert single[0].bm25_rank is None and single[0].bm25_score is None


def test_rrf_ties_are_sorted_by_chunk_id_and_candidates_are_limited_to_20() -> None:
    vector = tuple(_hit(f"chunk-{index:02d}", 1, 1.0) for index in range(25, -1, -1))
    fused = reciprocal_rank_fusion(vector, (), limit=20)

    assert [item.chunk.chunk_id for item in fused] == [
        f"chunk-{index:02d}" for index in range(20)
    ]
