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
            "repair_and_retry",
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


class ToolExecutionError(Exception):
    """模拟 MCP 工具返回的执行错误（服务端原话在消息里）。"""


def test_failure_summary_keeps_server_reason_and_redacts_sensitive_arguments() -> None:
    """失败摘要必须可读，同时抹掉敏感参数的取值。

    只保留异常类型名会让 CLS 的语法错误彻底不可见，排查只能靠外部工具反推；
    而 Region/TopicId 属于服务端权威参数，不该出现在落库的摘要与事件里。
    """
    server_message = (
        "[TencentCloudSDKException]message:SyntaxError [field: nservice, "
        "can not search on this field] region:ap-guangzhou "
        "topicId:96b7b877-35a6-40e9-b043-a8ff59931653"
    )
    arguments = {
        "Region": "ap-guangzhou",
        "TopicId": "96b7b877-35a6-40e9-b043-a8ff59931653",
        "Query": 'service:"auth-service"',
    }

    classified = classify_tool_failure(
        ToolExecutionError(server_message), phase="invoke", attempt=1, arguments=arguments
    )

    # 可读原因保留
    assert "SyntaxError" in classified.safe_message
    assert "nservice" in classified.safe_message
    # 敏感参数取值抹掉
    assert "ap-guangzhou" not in classified.safe_message
    assert "96b7b877-35a6-40e9-b043-a8ff59931653" not in classified.safe_message
    # 分类与路由判定不受影响
    assert classified.category == "transport"
    assert classified.route == "retry_same_step"
    assert classified.retryable is True


def test_failure_summary_redacts_credentials_and_is_bounded() -> None:
    arguments = {"Region": "ap-guangzhou"}
    credential_leak = "Authorization: Bearer sk-super-secret " + "x" * 800

    classified = classify_tool_failure(
        ToolExecutionError(credential_leak), phase="invoke", attempt=1, arguments=arguments
    )

    assert "sk-super-secret" not in classified.safe_message
    assert len(classified.safe_message) <= 500


def test_failure_without_arguments_still_reports_server_reason() -> None:
    classified = classify_tool_failure(
        ToolExecutionError("remote said: field not indexed"), phase="invoke", attempt=1
    )

    assert "field not indexed" in classified.safe_message
    assert classified.category == "transport"


def test_external_input_error_is_repairable_not_retryable_transport() -> None:
    """外部服务以执行错误形式返回的入参问题，必须走"修正后重试"。

    真实运行里 `MCP error -32602: Input validation error: Required at Region`
    被当成可重试的传输错误，同一个必填字段缺失被原样重打满三次。
    """
    error = ToolExecutionError(
        "_MCPToolExecutionError: MCP error -32602: Input validation error: "
        "Invalid arguments for tool DescribeTopics: Required at Region"
    )

    classified = classify_tool_failure(error, phase="invoke", attempt=1)

    assert classified.category == "input_validation"
    assert classified.route == "repair_and_retry"
    assert classified.failure_class == "repair"


@pytest.mark.parametrize(
    ("error", "phase", "expected_class"),
    [
        (httpx.TimeoutException("timeout"), "invoke", "retry"),
        (ValidationError.from_exception_data("RequiredInput", []), "input", "repair"),
        (ToolOwnerScopeError("cross owner"), "input", "permanent"),
        (ValueError("空结果"), "empty", "empty"),
    ],
)
def test_failure_class_is_exposed_for_execution_result(
    error: Exception, phase: str, expected_class: str
) -> None:
    """执行结果需要能读到"原样重试 / 修正后重试 / 不可重试 / 空结果"。"""
    classified = classify_tool_failure(error, phase=phase, attempt=1)

    assert classified.failure_class == expected_class
