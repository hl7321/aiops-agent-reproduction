"""preview 与未来 indexing 共用的纯文档切分入口。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from super_ai.project_config import JsonValue

ChunkingStrategy: TypeAlias = Literal["fixed-character", "markdown-heading", "paragraph"]


class ChunkingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    strategy: ChunkingStrategy = "fixed-character"
    max_characters: int | None = Field(default=1200, alias="maxCharacters", ge=1, le=100_000)
    overlap: int | None = Field(default=200, ge=0, le=99_999)

    @model_validator(mode="after")
    def validate_strategy_parameters(self) -> ChunkingConfig:
        if self.strategy == "fixed-character":
            if self.max_characters is None or self.overlap is None:
                raise ValueError("fixed-character 需要 maxCharacters 与 overlap")
            if self.overlap >= self.max_characters:
                raise ValueError("overlap 必须小于 maxCharacters")
        elif {"max_characters", "maxCharacters", "overlap"} & self.model_fields_set:
            raise ValueError("只有 fixed-character 接受 maxCharacters/overlap")
        else:
            object.__setattr__(self, "max_characters", None)
            object.__setattr__(self, "overlap", None)
        return self


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    index: int
    text: str
    metadata: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ChunkPreviewItem:
    index: int
    excerpt: str
    metadata: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ChunkPreview:
    total_chunks: int
    items: tuple[ChunkPreviewItem, ...]


def chunk_document_text(text: str, config: ChunkingConfig) -> tuple[DocumentChunk, ...]:
    if config.strategy == "fixed-character":
        raw = _fixed_chunks(text, config.max_characters or 1200, config.overlap or 0)
    elif config.strategy == "markdown-heading":
        return _heading_chunks(text, config.strategy)
    else:
        raw = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    return tuple(
        DocumentChunk(
            index=index, text=value, metadata={"index": index, "strategy": config.strategy}
        )
        for index, value in enumerate(raw)
        if value
    )


class DocumentChunkingService:
    def preview(self, text: str, config: ChunkingConfig) -> ChunkPreview:
        chunks = chunk_document_text(text, config)
        return ChunkPreview(
            total_chunks=len(chunks),
            items=tuple(
                ChunkPreviewItem(
                    index=chunk.index,
                    excerpt=chunk.text[:400],
                    metadata=chunk.metadata,
                )
                for chunk in chunks[:12]
            ),
        )


def _fixed_chunks(text: str, maximum: int, overlap: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    step = maximum - overlap
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        chunks.append(normalized[start : start + maximum])
        if start + maximum >= len(normalized):
            break
        start += step
    return chunks


def _heading_chunks(text: str, strategy: ChunkingStrategy) -> tuple[DocumentChunk, ...]:
    headings: list[str] = []
    sections: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_path = ""
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            if current_lines and "\n".join(current_lines).strip():
                sections.append((current_path, "\n".join(current_lines).strip()))
            level = len(match.group(1))
            headings[level - 1 :] = [match.group(2).strip()]
            current_path = " > ".join(headings)
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines and "\n".join(current_lines).strip():
        sections.append((current_path, "\n".join(current_lines).strip()))
    return tuple(
        DocumentChunk(
            index=index,
            text=value,
            metadata={"index": index, "strategy": strategy, "headingPath": path},
        )
        for index, (path, value) in enumerate(sections)
    )
