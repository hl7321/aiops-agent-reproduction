"""兼容标准 JSON Schema 与 langchain-mcp-adapters 的字段映射形态。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast


def tool_schema_properties(schema: Mapping[str, object]) -> Mapping[str, object]:
    wrapped = schema.get("properties")
    if isinstance(wrapped, Mapping):
        return cast(Mapping[str, object], wrapped)
    if schema and all(isinstance(value, Mapping) for value in schema.values()):
        return schema
    return {}


def tool_schema_required(schema: Mapping[str, object]) -> tuple[str, ...]:
    raw = schema.get("required")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in cast(list[object], raw) if isinstance(item, str))
