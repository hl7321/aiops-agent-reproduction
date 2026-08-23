"""把真实工具输出规范化为有界、可查询证据。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel

from super_ai.aiops.models import EvidenceKind, NewEvidence
from super_ai.aiops.tool_adapters import AdaptedToolOutput, adapt_allowed_tool_output
from super_ai.background_jobs.security import redact_error
from super_ai.project_config import JsonValue


def normalize_tool_evidence(
    *, tool_name: str, result: object, step_id: str, tool_call_id: str
) -> tuple[NewEvidence, ...]:
    if tool_name.casefold().replace("_", "").replace("-", "") != "knowledgeretrieval":
        adapted = adapt_allowed_tool_output(tool_name, result)
        return normalize_adapted_tool_output(
            tool_name=tool_name,
            adapted=adapted,
            step_id=step_id,
            tool_call_id=tool_call_id,
        )
    payload = _sanitize_json(_json_value(result))
    kind = _kind(tool_name)
    if kind is None:
        raise ValueError("工具输出类型无法安全映射为诊断证据")
    if (
        kind == "knowledge"
        and isinstance(payload, dict)
        and isinstance(payload.get("results"), list)
    ):
        items: list[JsonValue] = cast(list[JsonValue], payload["results"])
    else:
        items = payload if isinstance(payload, list) else [payload]
    normalized: list[NewEvidence] = []
    for index, item in enumerate(items[:100]):
        if not isinstance(item, (dict, str)):
            raise ValueError("工具输出必须是对象、字符串或其数组")
        safe = redact_error(_bounded_text(item, 20_000), "{}")
        metadata = cast(dict[str, JsonValue], item) if isinstance(item, dict) else {}
        normalized.append(
            NewEvidence(
                kind=kind,
                source=tool_name,
                title=f"{tool_name} 结果 {index + 1}",
                summary=safe[:1000],
                content=safe,
                metadata=metadata,
                diagnostic_step_id=step_id,
                tool_call_id=tool_call_id,
            )
        )
    return tuple(normalized)


def normalize_adapted_tool_output(
    *,
    tool_name: str,
    adapted: AdaptedToolOutput,
    step_id: str,
    tool_call_id: str,
) -> tuple[NewEvidence, ...]:
    payload = _sanitize_json(adapted.payload)
    if adapted.kind == "log_hit":
        if not isinstance(payload, list):
            raise ValueError("log_hit adapter 必须返回列表")
        items = cast(list[JsonValue], payload)
    else:
        items = [payload]
    kind = cast(EvidenceKind, adapted.kind)
    normalized: list[NewEvidence] = []
    for index, item in enumerate(items[:100]):
        if not isinstance(item, dict):
            raise ValueError(f"{adapted.kind} adapter 必须返回结构化对象")
        metadata = cast(dict[str, JsonValue], item)
        safe = redact_error(_bounded_text(metadata, 20_000), "{}")
        normalized.append(
            NewEvidence(
                kind=kind,
                source=tool_name,
                title=f"{tool_name} {adapted.kind} {index + 1}"[:500],
                summary=safe[:1000],
                content=safe,
                metadata={"artifactKind": adapted.kind, **metadata},
                diagnostic_step_id=step_id,
                tool_call_id=tool_call_id,
            )
        )
    return tuple(normalized)


def knowledge_evidence(
    citation: Mapping[str, JsonValue], *, tool_call_id: str | None = None
) -> NewEvidence:
    sanitized = cast(dict[str, JsonValue], _sanitize_json(dict(citation)))
    source = str(sanitized.get("source", "知识库"))
    excerpt = str(sanitized.get("excerpt", ""))[:20_000]
    return NewEvidence(
        kind="knowledge",
        source=source,
        title=f"SOP 引用：{source}"[:500],
        summary=excerpt[:1000],
        content=excerpt,
        metadata=sanitized,
        tool_call_id=tool_call_id,
    )


def alert_evidence(alert: Mapping[str, JsonValue]) -> NewEvidence:
    sanitized = sanitize_alert_snapshot(alert)
    name = str(sanitized.get("alertName", "未命名告警"))
    raw_source = sanitized.get("source", "alert-input")
    source = (
        str(raw_source.get("name", "alert-input"))
        if isinstance(raw_source, dict)
        else str(raw_source)
    )
    return NewEvidence(
        kind="alert",
        source=source[:500],
        title=name[:500],
        summary=f"{name} / {sanitized.get('service', '')} / {sanitized.get('severity', '')}"[
            :1000
        ],
        content=_bounded_text(sanitized, 20_000),
        metadata=sanitized,
    )


def sanitize_alert_snapshot(alert: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], _sanitize_json(dict(alert)))


def _kind(tool_name: str) -> EvidenceKind | None:
    normalized = tool_name.casefold()
    if "searchlog" in normalized.replace("_", "").replace("-", ""):
        return "log"
    if "metric" in normalized or "promql" in normalized:
        return "metric"
    if "knowledge" in normalized:
        return "knowledge"
    return None


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return cast(JsonValue, value)
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="json", by_alias=True)
        return cast(JsonValue, dumped)
    raise ValueError("工具返回了无法持久化的类型")


def _bounded_text(value: object, limit: int) -> str:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, dict):
        typed = cast(dict[str, object], value)
        pairs = [f"{key}={typed[key]}" for key in sorted(typed)]
        return "; ".join(pairs)[:limit]
    if isinstance(value, list):
        typed_list = cast(list[object], value)
        return "; ".join(str(item) for item in typed_list)[:limit]
    return str(value)[:limit]


def _sanitize_json(value: JsonValue, *, depth: int = 0) -> JsonValue:
    if depth >= 6:
        return "[truncated]"
    if isinstance(value, str):
        return value[:20_000]
    if isinstance(value, list):
        return [_sanitize_json(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, dict):
        safe: dict[str, JsonValue] = {}
        for key, item in list(value.items())[:100]:
            normalized = key.casefold().replace("_", "").replace("-", "")
            if any(
                marker in normalized
                for marker in ("password", "secret", "token", "apikey", "authorization")
            ):
                safe[key] = "[redacted]"
            else:
                safe[key] = _sanitize_json(item, depth=depth + 1)
        return safe
    return value
