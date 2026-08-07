"""本机 JSON 项目配置加载。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import TypeAlias, cast

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


def deep_merge(base: Mapping[str, JsonValue], override: Mapping[str, JsonValue]) -> JsonObject:
    """递归合并对象；数组和标量由 override 整体替换。"""
    merged: JsonObject = deepcopy(dict(base))
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = deep_merge(base_value, override_value)
        else:
            merged[key] = deepcopy(override_value)
    return merged


def load_project_config(project_path: Path, user_path: Path) -> JsonObject:
    """读取显式 JSON 路径，并以用户配置递归覆盖项目配置。"""
    return deep_merge(_read_json_object(project_path), _read_json_object(user_path))


def _read_json_object(path: Path) -> JsonObject:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    value = _normalize_json(raw)
    if not isinstance(value, dict):
        raise ValueError(f"配置文件顶层必须是 JSON object: {path}")
    return value


def _normalize_json(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_normalize_json(item) for item in items]
    if isinstance(value, dict):
        items = cast(dict[object, object], value)
        normalized: JsonObject = {}
        for key, item in items.items():
            if not isinstance(key, str):
                raise ValueError("JSON object key 必须是字符串")
            normalized[key] = _normalize_json(item)
        return normalized
    raise ValueError(f"不支持的 JSON 值类型: {type(value).__name__}")
