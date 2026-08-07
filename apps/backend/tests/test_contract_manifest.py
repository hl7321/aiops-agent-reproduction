import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import TypeAdapter

from super_ai.api_contracts import (
    ERROR_DEFINITIONS,
    SSE_EVENT_TYPES,
    TOOL_CALL_LIFECYCLES,
    ApiErrorModel,
    ErrorEvent,
    SseEvent,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "packages/api-contracts/contract-manifest.json"


def load_manifest() -> dict[str, object]:
    return cast(dict[str, object], json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def test_python_catalogs_match_contract_manifest() -> None:
    manifest = load_manifest()
    sse = cast(dict[str, object], manifest["sse"])

    assert {code: definition.to_contract() for code, definition in ERROR_DEFINITIONS.items()} == (
        manifest["errors"]
    )
    assert list(SSE_EVENT_TYPES) == sse["eventTypes"]
    assert list(TOOL_CALL_LIFECYCLES) == sse["toolCallLifecycles"]


@pytest.mark.parametrize(
    "event",
    [
        {
            "id": "evt-content",
            "type": "content.delta",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:00Z",
            "data": {"delta": "hello"},
        },
        {
            "id": "evt-reasoning",
            "type": "reasoning.delta",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:01Z",
            "data": {"delta": "inspect"},
        },
        {
            "id": "evt-tool",
            "type": "tool.call",
            "channel": "aiops",
            "timestamp": "2026-08-07T12:00:02Z",
            "data": {
                "toolCallId": "call-1",
                "toolName": "query_alerts",
                "lifecycle": "completed",
                "output": {"count": 1},
            },
        },
        {
            "id": "evt-reference",
            "type": "reference.source",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:03Z",
            "data": {"source": {"id": "src-1", "title": "Runbook"}},
        },
        {
            "id": "evt-task",
            "type": "task.status",
            "channel": "aiops",
            "timestamp": "2026-08-07T12:00:04Z",
            "data": {"taskId": "task-1", "status": "running"},
        },
        {
            "id": "evt-report",
            "type": "report",
            "channel": "aiops",
            "timestamp": "2026-08-07T12:00:05Z",
            "data": {"report": {"summary": "ok"}},
        },
        {
            "id": "evt-complete",
            "type": "complete",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:06Z",
            "data": {"finishReason": "stop"},
        },
        {
            "id": "evt-error",
            "type": "error",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:07Z",
            "data": {
                "error": {
                    "code": "SYSTEM_INTERNAL_ERROR",
                    "category": "system",
                    "httpStatus": 500,
                    "message": "服务暂时不可用",
                }
            },
        },
    ],
)
def test_all_sse_event_shapes_round_trip(event: dict[str, object]) -> None:
    adapter: TypeAdapter[SseEvent] = TypeAdapter(SseEvent)
    parsed: SseEvent = adapter.validate_python(event)

    assert parsed.model_dump(mode="json", by_alias=True, exclude_none=True) == event


def test_sse_error_reuses_http_error_model() -> None:
    event = ErrorEvent.model_validate(
        {
            "id": "evt-error",
            "type": "error",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:07Z",
            "data": {
                "error": {
                    "code": "SYSTEM_INTERNAL_ERROR",
                    "category": "system",
                    "httpStatus": 500,
                    "message": "服务暂时不可用",
                }
            },
        }
    )

    assert isinstance(event.data.error, ApiErrorModel)
