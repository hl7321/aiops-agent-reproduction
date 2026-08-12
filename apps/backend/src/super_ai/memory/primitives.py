"""跨持久化 adapter 共享的值表示。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from super_ai.project_config import JsonValue


def new_id() -> str:
    """生成不依赖数据库共享状态的字符串标识。"""
    return uuid4().hex


def utc_now() -> datetime:
    """返回兼容 Python 3.10 的 UTC aware 时间。"""
    return datetime.now(timezone.utc)


def dump_json(value: object) -> str:
    """将合法 JSON 值编码为稳定、紧凑且保留 Unicode 的字符串。"""
    normalized = _normalize_json(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def load_json(value: str) -> JsonValue:
    """解码 JSON 并拒绝 Python JSON 扩展产生的非有限数。"""
    decoded: object = json.loads(value, parse_constant=_reject_non_finite)
    return _normalize_json(decoded)


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"JSON 不允许非有限数: {value}")


def _normalize_json(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("JSON 不允许 NaN 或 Infinity")
        return value
    if isinstance(value, list | tuple):
        return [_normalize_json(item) for item in cast(list[object] | tuple[object, ...], value)]
    if isinstance(value, dict):
        normalized: dict[str, JsonValue] = {}
        for key, item in cast(dict[object, object], value).items():
            if not isinstance(key, str):
                raise ValueError("JSON object key 必须是字符串")
            normalized[key] = _normalize_json(item)
        return normalized
    raise ValueError(f"不支持的 JSON 值类型: {type(value).__name__}")
