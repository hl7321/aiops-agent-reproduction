"""后台任务错误信息脱敏。"""

import re

from super_ai.memory.primitives import load_json
from super_ai.project_config import JsonValue

_SENSITIVE_KEYS = ("password", "secret", "token", "apikey", "authorization")


def redact_error(message: str, serialized_payload: str) -> str:
    redacted = message
    payload = load_json(serialized_payload)
    for secret in _secret_values(payload):
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    redacted = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [redacted]", redacted)
    pattern = r"(?i)(password|secret|token|api[_-]?key|authorization)(\s*[:=]\s*)[^\s,;]+"
    redacted = re.sub(pattern, r"\1\2[redacted]", redacted)
    return redacted[:1000]


def _secret_values(value: JsonValue) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if any(marker in key.casefold() for marker in _SENSITIVE_KEYS) and isinstance(
                item, str
            ):
                found.append(item)
            else:
                found.extend(_secret_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_secret_values(item))
    return found
