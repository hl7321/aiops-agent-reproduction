import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import TypeAdapter

from super_ai.api_contracts import (
    ERROR_DEFINITIONS,
    KNOWLEDGE_UPLOAD_POLICY,
    SSE_EVENT_TYPES,
    TOOL_CALL_LIFECYCLES,
    ApiErrorModel,
    AuthUser,
    BackgroundJob,
    BackgroundJobEvent,
    ErrorEvent,
    LoginData,
    LogoutData,
    SseEvent,
)
from super_ai.app import create_app

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


def test_auth_models_and_openapi_manifest_match_contracts() -> None:
    manifest = load_manifest()
    openapi = cast(dict[str, object], manifest["openapi"])
    paths = cast(dict[str, object], openapi["paths"])

    user = AuthUser(id="user-1", email="user@example.com", createdAt="2026-08-08T00:00:00Z")
    assert LoginData(user=user, token="raw-token").model_dump(by_alias=True) == {
        "user": {"id": "user-1", "email": "user@example.com", "createdAt": "2026-08-08T00:00:00Z"},
        "token": "raw-token",
    }
    assert LogoutData().model_dump(by_alias=True) == {"revoked": True}
    assert openapi["securitySchemes"] == {"BearerAuth": {"type": "http", "scheme": "bearer"}}
    assert set(paths) == {
        "/health",
        "/auth/register",
        "/auth/login",
        "/auth/logout",
        "/auth/me",
        "/chat/sessions",
        "/chat/sessions/{id}",
        "/chat/sessions/{id}/messages",
        "/chat/sessions/{id}/messages:clear",
        "/background-jobs",
        "/background-jobs/{id}",
        "/background-jobs/{id}:cancel",
        "/background-jobs/{id}:retry",
        "/knowledge-bases",
        "/knowledge-bases/{kb}/documents",
        "/knowledge-bases/{kb}/documents/{document}",
        "/knowledge-bases/{kb}/documents/{document}/chunk-preview",
        "/knowledge-bases/{kb}/documents/{document}/index-tasks",
        "/knowledge-bases/{kb}/documents/{document}/index-tasks/{task}",
        "/knowledge-bases/{kb}/documents/{document}/index-tasks/{task}:retry",
    }

    operations = cast(list[dict[str, str]], openapi["knowledgeOperations"])
    schema = create_app().openapi()
    for operation in operations:
        actual = schema["paths"][operation["path"]][operation["method"].lower()]
        assert actual["operationId"] == operation["operationId"]
    for operation in cast(list[dict[str, str]], openapi["documentIndexOperations"]):
        actual = schema["paths"][operation["path"]][operation["method"].lower()]
        assert actual["operationId"] == operation["operationId"]
    for operation in cast(list[dict[str, str]], openapi["chatOperations"]):
        actual = schema["paths"][operation["path"]][operation["method"].lower()]
        assert actual["operationId"] == operation["operationId"]


def test_background_job_python_contracts_use_shared_camel_case_shape() -> None:
    job = BackgroundJob.model_validate(
        {
            "id": "job-1",
            "ownerUserId": "user-1",
            "kind": "index.document",
            "status": "queued",
            "payload": {"documentId": "doc-1"},
            "attempt": 0,
            "maxAttempts": 3,
            "timeoutSeconds": 300,
            "availableAt": "2026-08-12T00:00:00Z",
            "createdAt": "2026-08-12T00:00:00Z",
            "updatedAt": "2026-08-12T00:00:00Z",
        }
    )
    event = BackgroundJobEvent.model_validate(
        {
            "sequence": 1,
            "jobId": job.id,
            "ownerUserId": job.owner_user_id,
            "type": "queued",
            "data": {},
            "createdAt": "2026-08-12T00:00:00Z",
        }
    )
    serialized = job.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert serialized["ownerUserId"] == "user-1"
    assert "heartbeatAt" not in serialized and "result" not in serialized
    assert event.model_dump(mode="json", by_alias=True)["jobId"] == "job-1"


def test_knowledge_upload_policy_matches_typescript_contract() -> None:
    assert KNOWLEDGE_UPLOAD_POLICY == {
        "maxBytes": 10 * 1024 * 1024,
        "allowedTypes": {".md": "text/markdown", ".pdf": "application/pdf"},
        "multipart": {"file": "file", "chunkingConfig": "chunkingConfig", "overwrite": "overwrite"},
        "strategies": ["fixed-character", "markdown-heading", "paragraph"],
    }


def test_fastapi_openapi_paths_and_security_match_manifest() -> None:
    manifest = load_manifest()
    expected_openapi = cast(dict[str, object], manifest["openapi"])
    expected_paths = cast(dict[str, dict[str, object]], expected_openapi["paths"])
    expected_error_definitions = cast(dict[str, dict[str, object]], manifest["errors"])
    schema = create_app().openapi()

    assert schema["components"]["securitySchemes"] == expected_openapi["securitySchemes"]
    for path, expected in expected_paths.items():
        operation = schema["paths"][path][cast(str, expected["method"]).lower()]
        assert operation["operationId"] == expected["operationId"]
        expected_security = expected.get("security", [])
        actual_security = [next(iter(item)) for item in operation.get("security", [])]
        assert actual_security == expected_security
        expected_errors = cast(list[str], expected.get("errors", []))
        actual_errors = sorted(code for code in operation.get("responses", {}) if code != "200")
        error_statuses = sorted(
            str(expected_error_definitions[code]["httpStatus"]) for code in expected_errors
        )
        assert set(error_statuses).issubset(actual_errors)


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
