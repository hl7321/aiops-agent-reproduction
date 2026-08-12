"""不连接 Milvus 的 tenant metadata、search 与 delete scope 合同。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from pydantic import JsonValue

from super_ai.tenancy.context import TenantContext

HitT = TypeVar("HitT")
PROTECTED_METADATA_FIELDS = frozenset(
    {"tenantId", "ownerUserId", "knowledgeBaseId", "documentId"}
)


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不得为空")
    return normalized


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class VectorScope:
    tenant_id: str
    owner_user_id: str
    allowed_knowledge_base_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        tenant_id = _required(self.tenant_id, "tenant_id")
        owner_user_id = _required(self.owner_user_id, "owner_user_id")
        if tenant_id != owner_user_id:
            raise ValueError("当前本地模型要求 tenant_id 等于 owner_user_id")
        normalized_knowledge_base_ids = {
            _required(value, "knowledge_base_id") for value in self.allowed_knowledge_base_ids
        }
        knowledge_base_ids = tuple(sorted(normalized_knowledge_base_ids))
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "owner_user_id", owner_user_id)
        object.__setattr__(self, "allowed_knowledge_base_ids", knowledge_base_ids)

    @classmethod
    def from_tenant_context(
        cls,
        context: TenantContext,
        allowed_knowledge_base_ids: Sequence[str],
    ) -> VectorScope:
        return cls(
            tenant_id=context.tenant_id,
            owner_user_id=context.owner_scope.owner_user_id,
            allowed_knowledge_base_ids=tuple(allowed_knowledge_base_ids),
        )


def build_vector_metadata(
    scope: VectorScope,
    *,
    knowledge_base_id: str,
    document_id: str,
    extra: Mapping[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    knowledge_base_id = _allowed_knowledge_base(scope, knowledge_base_id)
    document_id = _required(document_id, "document_id")
    supplied = dict(extra or {})
    overlap = PROTECTED_METADATA_FIELDS.intersection(supplied)
    if overlap:
        raise ValueError(f"额外 metadata 不得覆盖受保护字段: {', '.join(sorted(overlap))}")
    return {
        **supplied,
        "tenantId": scope.tenant_id,
        "ownerUserId": scope.owner_user_id,
        "knowledgeBaseId": knowledge_base_id,
        "documentId": document_id,
    }


def build_search_filter(scope: VectorScope) -> str | None:
    if not scope.allowed_knowledge_base_ids:
        return None
    knowledge_bases = ", ".join(_quote(value) for value in scope.allowed_knowledge_base_ids)
    return f"tenantId == {_quote(scope.tenant_id)} and knowledgeBaseId in [{knowledge_bases}]"


async def scoped_vector_search(
    scope: VectorScope,
    search: Callable[[str], Awaitable[Sequence[HitT]]],
) -> list[HitT]:
    search_filter = build_search_filter(scope)
    if search_filter is None:
        return []
    return list(await search(search_filter))


def post_filter_hits(
    hits: Sequence[Mapping[str, JsonValue]],
    *,
    allowed_document_ids: frozenset[str] | None = None,
    metadata_filter: Mapping[str, JsonValue] | None = None,
) -> list[Mapping[str, JsonValue]]:
    metadata_filter = metadata_filter or {}

    def document_is_allowed(hit: Mapping[str, JsonValue]) -> bool:
        document_id = hit.get("documentId")
        return allowed_document_ids is None or (
            isinstance(document_id, str) and document_id in allowed_document_ids
        )

    return [
        hit
        for hit in hits
        if document_is_allowed(hit)
        and all(hit.get(key) == value for key, value in metadata_filter.items())
    ]


def build_delete_filter(
    scope: VectorScope,
    *,
    knowledge_base_id: str,
    document_id: str,
) -> str:
    knowledge_base_id = _allowed_knowledge_base(scope, knowledge_base_id)
    document_id = _required(document_id, "document_id")
    return (
        f"tenantId == {_quote(scope.tenant_id)} "
        f"and knowledgeBaseId == {_quote(knowledge_base_id)} "
        f"and documentId == {_quote(document_id)}"
    )


def _allowed_knowledge_base(scope: VectorScope, knowledge_base_id: str) -> str:
    normalized = _required(knowledge_base_id, "knowledge_base_id")
    if normalized not in scope.allowed_knowledge_base_ids:
        raise ValueError("knowledge_base_id 不在当前允许 scope 中")
    return normalized
