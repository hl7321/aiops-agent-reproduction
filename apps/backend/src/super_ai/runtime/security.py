"""递归配置与日志脱敏。"""

from __future__ import annotations

import re

from pydantic import JsonValue

_SENSITIVE_MARKERS = ("password", "token", "key", "secret", "authorization")


def is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "").replace("_", "")
    return any(marker in normalized for marker in _SENSITIVE_MARKERS)


def redact_sensitive(value: JsonValue) -> JsonValue:
    """递归保留形状并替换敏感 key 的值。"""
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if is_sensitive_key(str(key)) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def redact_text(message: str) -> str:
    value = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [redacted]", message)
    pattern = r"(?i)(password|secret|token|api[_-]?key|authorization)(\s*[:=]\s*)[^\s,;]+"
    return re.sub(pattern, r"\1\2[redacted]", value)[:1000]
