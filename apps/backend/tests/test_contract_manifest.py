import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import TypeAdapter

from super_ai.api_contracts import (
    CHAT_SKILL_UPLOAD_POLICY,
    ERROR_DEFINITIONS,
    KNOWLEDGE_UPLOAD_POLICY,
    SSE_EVENT_TYPES,
    TOOL_CALL_LIFECYCLES,
    AgentToolCallAudit,
    ApiErrorModel,
    AuthUser,
    BackgroundJob,
    BackgroundJobEvent,
    ChatConfigurationData,
    ChatPrompt,
    ChatSession,
    ChatSkill,
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
    assert CHAT_SKILL_UPLOAD_POLICY == {
        "multipart": {"file": "file"},
        "filename": "SKILL.md",
        "maxBytes": 262144,
        "maxNameCharacters": 64,
        "maxDescriptionCharacters": 500,
        "maxSummaryCharacters": 240,
        "normalizedNamePattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    }


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
        "/aiops/alerts/active",
        "/aiops/diagnostics",
        "/aiops/diagnostics/{id}",
        "/aiops/diagnostics/{id}/evidence-chain",
        "/aiops/diagnostics/{id}:stream",
        "/auth/register",
        "/auth/login",
        "/auth/logout",
        "/auth/me",
        "/chat/sessions",
        "/chat/sessions/{id}",
        "/chat/sessions/{id}/messages",
        "/chat/sessions/{id}/messages:clear",
        "/chat/sessions/{id}/messages:stream",
        "/chat/sessions/{id}/tool-call-audits",
        "/chat/sessions/{id}/memory",
        "/chat/sessions/{id}/memory:compact",
        "/chat/configuration",
        "/chat/prompts",
        "/chat/prompts/{id}",
        "/chat/skills",
        "/chat/skills/{id}",
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
        "/mcp/connections",
        "/mcp/connections/{id}",
        "/mcp/connections/{id}:check",
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
    for operation in cast(list[dict[str, str]], openapi["mcpOperations"]):
        actual = schema["paths"][operation["path"]][operation["method"].lower()]
        assert actual["operationId"] == operation["operationId"]
        assert actual["security"] == [{"BearerAuth": []}]
    for operation in cast(list[dict[str, str]], openapi["alertOperations"]):
        actual = schema["paths"][operation["path"]][operation["method"].lower()]
        assert actual["operationId"] == operation["operationId"]
        assert actual["security"] == [{"BearerAuth": []}]
    for operation in cast(list[dict[str, str]], openapi["aiopsDiagnosticOperations"]):
        actual = schema["paths"][operation["path"]][operation["method"].lower()]
        assert actual["operationId"] == operation["operationId"]
        assert actual["security"] == [{"BearerAuth": []}]


def test_chat_memory_contract_uses_capability_projection_and_shared_errors() -> None:
    session = ChatSession.model_validate(
        {
            "id": "session-1",
            "title": "新会话",
            "memoryMode": "context_70_percent",
            "memorySummary": None,
            "contextTokens": 140,
            "contextWindowTokens": 1000,
            "contextUsagePercent": 14,
            "compactedMessageCount": 0,
            "lastCompactedAt": None,
            "canCompact": True,
            "createdAt": "2026-08-18T00:00:00Z",
            "updatedAt": "2026-08-18T00:00:00Z",
        }
    )

    assert session.model_dump(mode="json", by_alias=True)["memoryMode"] == "context_70_percent"
    assert ERROR_DEFINITIONS["CHAT_CONTEXT_LIMIT_REACHED"].http_status == 409
    assert ERROR_DEFINITIONS["SYSTEM_MODEL_CAPABILITY_MISSING"].http_status == 500


def test_chat_configuration_models_and_seven_openapi_operations_align() -> None:
    manifest = load_manifest()
    openapi = cast(dict[str, object], manifest["openapi"])
    operations = cast(list[dict[str, object]], openapi["chatConfigurationOperations"])
    prompt = ChatPrompt(
        id="prompt-1",
        label="值班",
        content="简洁回答",
        createdAt="2026-08-18T00:00:00Z",
        updatedAt="2026-08-18T00:00:00Z",
    )
    skill = ChatSkill(
        id="skill-1",
        name="knowledge-search",
        description="检索知识",
        content="BODY",
        metadata={},
        summary="检索知识",
        createdAt="2026-08-18T00:00:00Z",
        updatedAt="2026-08-18T00:00:00Z",
    )
    configuration = ChatConfigurationData(
        prompts=[prompt],
        skills=[skill],
        selectedPromptId=None,
        selectedSkillIds=[skill.id],
    )
    assert configuration.model_dump(mode="json", by_alias=True)["selectedPromptId"] is None
    assert len(operations) == 7

    schema = create_app().openapi()
    for operation in operations:
        path = cast(str, operation["path"])
        method = cast(str, operation["method"]).lower()
        actual = schema["paths"][path][method]
        assert actual["operationId"] == operation["operationId"]
        assert actual["security"] == [{"BearerAuth": []}]
        assert {"401", "403", "404"}.issubset(actual["responses"])


def test_agent_audit_contract_uses_exclusive_parent_and_camel_case_shape() -> None:
    audit = AgentToolCallAudit.model_validate(
        {
            "id": "audit-1",
            "toolCallId": "call-1",
            "chatSessionId": "session-1",
            "diagnosticTaskId": None,
            "toolName": "knowledge_retrieval",
            "arguments": {"query": "订单服务"},
            "status": "completed",
            "resultSummary": "返回 1 条引用",
            "errorMessage": None,
            "startedAt": "2026-08-17T00:00:00Z",
            "completedAt": "2026-08-17T00:00:01Z",
            "durationMs": 1000,
        }
    )

    payload = audit.model_dump(mode="json", by_alias=True)
    assert payload["toolCallId"] == "call-1"
    assert payload["chatSessionId"] == "session-1"
    assert payload["diagnosticTaskId"] is None
    assert "parentCallId" not in payload


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
            "sequence": 1,
            "type": "content.delta",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:00Z",
            "data": {"delta": "hello"},
        },
        {
            "id": "evt-reasoning",
            "sequence": 2,
            "type": "reasoning.delta",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:01Z",
            "data": {"delta": "inspect"},
        },
        {
            "id": "evt-tool",
            "sequence": 3,
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
            "sequence": 4,
            "type": "reference.source",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:03Z",
            "data": {
                "source": {
                    "chunkId": "chunk-1",
                    "documentId": "document-1",
                    "knowledgeBaseId": "knowledge-base-1",
                    "source": "Runbook",
                    "excerpt": "处理步骤",
                    "metadata": {"heading": "处置"},
                    "vectorRank": 1,
                    "vectorScore": 0.91,
                    "bm25Rank": None,
                    "bm25Score": None,
                    "rrfScore": 0.0164,
                    "rerankRank": 1,
                    "rerankScore": 0.97,
                    "score": 0.97,
                }
            },
        },
        {
            "id": "evt-task",
            "sequence": 5,
            "type": "task.status",
            "channel": "aiops",
            "timestamp": "2026-08-07T12:00:04Z",
            "data": {"taskId": "task-1", "status": "running"},
        },
        {
            "id": "evt-report",
            "sequence": 6,
            "type": "report",
            "channel": "aiops",
            "timestamp": "2026-08-07T12:00:05Z",
            "data": {"report": {"summary": "ok"}},
        },
        {
            "id": "evt-complete",
            "sequence": 7,
            "type": "complete",
            "channel": "chat",
            "timestamp": "2026-08-07T12:00:06Z",
            "data": {"finishReason": "stop"},
        },
        {
            "id": "evt-error",
            "sequence": 8,
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

    dumped = parsed.model_dump(mode="json", by_alias=True, exclude_none=True)
    if event["type"] == "reference.source":
        source = dumped["data"]["source"]  # type: ignore[index]
        source["vectorRank"] = event["data"]["source"]["vectorRank"]  # type: ignore[index]
        source["vectorScore"] = event["data"]["source"]["vectorScore"]  # type: ignore[index]
        source["bm25Rank"] = event["data"]["source"]["bm25Rank"]  # type: ignore[index]
        source["bm25Score"] = event["data"]["source"]["bm25Score"]  # type: ignore[index]
    assert dumped == event


def test_sse_error_reuses_http_error_model() -> None:
    event = ErrorEvent.model_validate(
        {
            "id": "evt-error",
            "sequence": 1,
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
