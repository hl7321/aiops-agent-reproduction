"""向量存储边界的不可变 records。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import JsonValue


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不得为空")
    return normalized


@dataclass(frozen=True, slots=True)
class VectorChunk:
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    content: str
    source: str
    created_at: datetime
    metadata: Mapping[str, JsonValue]
    vector: Sequence[float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _required(self.chunk_id, "chunk_id"))
        object.__setattr__(self, "document_id", _required(self.document_id, "document_id"))
        object.__setattr__(
            self,
            "knowledge_base_id",
            _required(self.knowledge_base_id, "knowledge_base_id"),
        )
        object.__setattr__(self, "content", _required(self.content, "content"))
        object.__setattr__(self, "source", _required(self.source, "source"))
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at 必须包含时区")
        object.__setattr__(self, "metadata", dict(self.metadata))
        vector = tuple(float(value) for value in self.vector)
        if len(vector) != 1024:
            raise ValueError("vector 必须包含 1024 维")
        object.__setattr__(self, "vector", vector)


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    chunk_id: str
    distance: float
    entity: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class MilvusHealth:
    healthy: bool
    server_version: str
