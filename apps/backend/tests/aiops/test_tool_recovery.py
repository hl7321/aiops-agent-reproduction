import httpx
import pytest
from pydantic import BaseModel, ValidationError

from super_ai.aiops.tool_failures import (
    ToolConfigurationError,
    ToolFailureRoute,
    ToolOwnerScopeError,
    ToolSchemaIncompatibleError,
    classify_tool_failure,
)


class RequiredInput(BaseModel):
    Query: str


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.invalid/mcp")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("remote failure", request=request, response=response)


@pytest.mark.parametrize(
    ("error", "phase", "category", "route", "retryable"),
    [
        (
            ValidationError.from_exception_data("RequiredInput", []),
            "input",
            "input_validation",
            "retry_same_step",
            True,
        ),
        (ValueError("空结果"), "empty", "empty_result", "replan", False),
        (httpx.TimeoutException("timeout"), "invoke", "timeout", "retry_same_step", True),
        (_http_error(429), "invoke", "rate_limited", "retry_same_step", True),
        (_http_error(503), "invoke", "provider_unavailable", "retry_same_step", True),
        (_http_error(401), "invoke", "permission", "permanent_failure", False),
        (_http_error(400), "invoke", "permanent", "permanent_failure", False),
        (
            ToolConfigurationError("missing topic"),
            "input",
            "configuration",
            "permanent_failure",
            False,
        ),
        (
            ToolOwnerScopeError("cross owner"),
            "input",
            "owner_scope",
            "permanent_failure",
            False,
        ),
        (
            ToolSchemaIncompatibleError("schema changed"),
            "input",
            "schema_incompatible",
            "permanent_failure",
            False,
        ),
        (ValueError("bad output"), "output", "output_validation", "permanent_failure", False),
    ],
)
def test_failure_classifier_routes_without_guessing(
    error: Exception,
    phase: str,
    category: str,
    route: ToolFailureRoute,
    retryable: bool,
) -> None:
    classified = classify_tool_failure(error, phase=phase, attempt=1)
    assert classified.category == category
    assert classified.route == route
    assert classified.retryable is retryable


def test_transient_backoff_is_bounded_and_deterministic() -> None:
    delays = [
        classify_tool_failure(httpx.TimeoutException("x"), phase="invoke", attempt=attempt).delay
        for attempt in (1, 2, 3)
    ]
    assert delays == [0.2, 0.4, 0.0]


def test_pydantic_validation_error_exposes_only_field_paths_and_types() -> None:
    try:
        RequiredInput.model_validate({"Query": 12345})
    except ValidationError as error:
        classified = classify_tool_failure(error, phase="input", attempt=1)
    else:  # pragma: no cover - test fixture contract
        raise AssertionError("测试输入应触发 Pydantic ValidationError")

    assert "Query" in classified.safe_message
    assert "string_type" in classified.safe_message
    assert "12345" not in classified.safe_message
