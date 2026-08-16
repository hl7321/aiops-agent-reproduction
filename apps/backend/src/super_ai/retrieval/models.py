from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class RetrievalChunk:
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    source: str
    excerpt: str
    metadata: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        for field_name in (
            "chunk_id", "document_id", "knowledge_base_id", "source", "excerpt"
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} 不得为空")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class BranchHit:
    chunk: RetrievalChunk
    rank: int
    score: float

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("rank 必须从 1 开始")
        if not math.isfinite(self.score):
            raise ValueError("score 必须是有限数")


@dataclass(frozen=True, slots=True)
class FusedCandidate:
    chunk: RetrievalChunk
    vector_rank: int | None
    vector_score: float | None
    bm25_rank: int | None
    bm25_score: float | None
    rrf_score: float
