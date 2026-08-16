from super_ai.retrieval.bm25 import bm25l_scores, rank_bm25l
from super_ai.retrieval.models import RetrievalChunk
from super_ai.retrieval.tokenizer import tokenize_for_retrieval


def _chunk(chunk_id: str, text: str) -> RetrievalChunk:
    return RetrievalChunk(chunk_id, f"doc-{chunk_id}", "kb-a", "runbook.md", text, {})


def test_tokenizer_emits_chinese_unigrams_bigrams_and_ascii_ops_tokens() -> None:
    tokens = tokenize_for_retrieval(
        "订单服务异常 NullPointerException TRACE_ID service-name 1.2.3"
    )

    assert tokens[:11] == (
        "订", "单", "服", "务", "异", "常", "订单", "单服", "服务", "务异", "异常"
    )
    assert tokens[11:] == (
        "nullpointerexception", "trace_id", "service-name", "1.2.3"
    )


def test_bm25l_small_corpus_has_positive_match_zero_disjoint_and_no_negative_scores() -> None:
    chunks = (_chunk("a", "订单服务 trace_id"), _chunk("b", "数据库容量"))
    scores = bm25l_scores("订单 trace_id", [chunk.excerpt for chunk in chunks])
    ranked = rank_bm25l("订单 trace_id", chunks)

    assert scores[0] > 0
    assert scores[1] == 0
    assert all(score >= 0 for score in scores)
    assert [hit.chunk.chunk_id for hit in ranked] == ["a"]
    assert ranked[0].rank == 1
