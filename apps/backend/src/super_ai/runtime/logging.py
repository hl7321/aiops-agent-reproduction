"""HTTP completion 与安全 lifecycle logging。"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

HTTP_LOGGER = logging.getLogger("super_ai.http")
LIFECYCLE_LOGGER = logging.getLogger("super_ai.lifecycle")


def log_http_completion(
    *, request_id: str, path: str, status: int, duration_ms: float
) -> None:
    HTTP_LOGGER.info(
        json.dumps(
            {
                "event": "http.request.completed",
                "requestId": request_id,
                "path": path,
                "status": status,
                "durationMs": round(max(0.0, duration_ms), 3),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def log_lifecycle(
    event: str,
    *,
    resource_id: str,
    status: str,
    request_id: str | None = None,
    category: str | None = None,
    duration_ms: float | None = None,
    tool_name: str | None = None,
    argument_keys: Sequence[str] = (),
) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "resourceId": resource_id,
        "status": status,
        "argumentKeys": sorted(set(argument_keys)),
    }
    optional: Mapping[str, Any] = {
        "requestId": request_id,
        "category": category,
        "durationMs": duration_ms,
        "toolName": tool_name,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    LIFECYCLE_LOGGER.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
