"""AIOps 工具错误分类；Pydantic 发现结构错误，本模块决定恢复路线。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

import httpx
from pydantic import ValidationError

from super_ai.aiops.models import ToolErrorCategory
from super_ai.background_jobs.security import redact_error

ToolFailureRoute: TypeAlias = Literal[
    "retry_same_step", "repair_and_retry", "replan", "permanent_failure"
]
# 执行结果对外暴露的失败类别：原样重试 / 修正后重试 / 不可重试，外加空结果。
ToolFailureClass: TypeAlias = Literal["retry", "repair", "permanent", "empty"]
ToolFailurePhase: TypeAlias = Literal["input", "invoke", "output", "empty"]

_CLASS_BY_ROUTE: dict[ToolFailureRoute, ToolFailureClass] = {
    "retry_same_step": "retry",
    "repair_and_retry": "repair",
    "replan": "empty",
    "permanent_failure": "permanent",
}

# 按已落库的错误分类反推失败类别：执行结果需要它来说明"这次失败重试有没有用"。
_CLASS_BY_CATEGORY: dict[ToolErrorCategory, ToolFailureClass] = {
    "input_validation": "repair",
    "output_validation": "permanent",
    "empty_result": "empty",
    "timeout": "retry",
    "rate_limited": "retry",
    "transport": "retry",
    "provider_unavailable": "retry",
    "configuration": "permanent",
    "permission": "permanent",
    "owner_scope": "permanent",
    "tool_not_allowed": "permanent",
    "schema_incompatible": "permanent",
    "permanent": "permanent",
}


def failure_class_of(category: ToolErrorCategory | None) -> ToolFailureClass | None:
    return _CLASS_BY_CATEGORY.get(category) if category is not None else None

# 外部服务以执行错误形式返回的参数校验失败。MCP 用 JSON-RPC 的 -32602
# （Invalid params）表示入参问题；这类失败必须走"修正后重试"，而不是被当成
# 可重试的传输错误原样重打——真实运行里它曾让同一个必填字段缺失重试满三次。
_MCP_INPUT_ERROR_MARKERS: tuple[str, ...] = (
    "-32602",
    "invalid arguments",
    "input validation error",
)

# 服务端权威参数：它们的取值既不该由模型修改，也不该出现在失败摘要里。
SENSITIVE_ARGUMENT_KEYS: frozenset[str] = frozenset(
    {"region", "topicid", "topic_id", "logsetid", "logset_id"}
)
_SAFE_DETAIL_LIMIT = 300


class ToolConfigurationError(ValueError):
    pass


class ToolOwnerScopeError(ValueError):
    pass


class ToolSchemaIncompatibleError(ValueError):
    pass


class ToolOutputValidationError(ValueError):
    pass


class ToolEmptyResultError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClassifiedToolFailure:
    category: ToolErrorCategory
    route: ToolFailureRoute
    retryable: bool
    delay: float
    safe_message: str

    @property
    def failure_class(self) -> ToolFailureClass:
        """执行结果里使用的失败类别。"""
        return _CLASS_BY_ROUTE[self.route]


def _is_external_input_error(error: Exception) -> bool:
    message = str(error).casefold()
    return any(marker in message for marker in _MCP_INPUT_ERROR_MARKERS)


def classify_tool_failure(
    error: Exception,
    *,
    phase: ToolFailurePhase | str,
    attempt: int,
    arguments: Mapping[str, object] | None = None,
) -> ClassifiedToolFailure:
    if isinstance(error, ToolConfigurationError):
        return _failure("configuration", "permanent_failure", False, error, arguments=arguments)
    if isinstance(error, ToolOwnerScopeError):
        return _failure("owner_scope", "permanent_failure", False, error, arguments=arguments)
    if isinstance(error, ToolSchemaIncompatibleError):
        return _failure(
            "schema_incompatible", "permanent_failure", False, error, arguments=arguments
        )
    if isinstance(error, ToolEmptyResultError):
        return _failure("empty_result", "replan", False, error, arguments=arguments)
    if isinstance(error, ToolOutputValidationError):
        return _failure("output_validation", "permanent_failure", False, error, arguments=arguments)
    if phase == "input" or isinstance(error, ValidationError):
        return _failure(
            "input_validation", "repair_and_retry", True, error, arguments=arguments
        )
    if _is_external_input_error(error):
        return _failure(
            "input_validation", "repair_and_retry", True, error, arguments=arguments
        )
    if phase == "empty":
        return _failure("empty_result", "replan", False, error, arguments=arguments)
    if isinstance(error, httpx.TimeoutException) or isinstance(error, TimeoutError):
        return _failure(
            "timeout", "retry_same_step", True, error, _delay(attempt), arguments=arguments
        )
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 429:
            return _failure(
                "rate_limited", "retry_same_step", True, error, _delay(attempt), arguments=arguments
            )
        if status >= 500:
            return _failure(
                "provider_unavailable",
                "retry_same_step",
                True,
                error,
                _delay(attempt),
                arguments=arguments,
            )
        if status in {401, 403}:
            return _failure("permission", "permanent_failure", False, error, arguments=arguments)
        return _failure("permanent", "permanent_failure", False, error, arguments=arguments)
    if phase == "output":
        return _failure("output_validation", "permanent_failure", False, error, arguments=arguments)
    return _failure(
        "transport", "retry_same_step", True, error, _delay(attempt), arguments=arguments
    )


def _delay(attempt: int) -> float:
    if attempt >= 3:
        return 0.0
    return min(0.2 * (2 ** max(0, attempt - 1)), 1.0)


def _failure(
    category: ToolErrorCategory,
    route: ToolFailureRoute,
    retryable: bool,
    error: Exception,
    delay: float = 0.0,
    *,
    arguments: Mapping[str, object] | None = None,
) -> ClassifiedToolFailure:
    safe_detail = _safe_detail(error, arguments)
    if isinstance(error, ValidationError):
        safe_detail = _validation_detail(error)
    return ClassifiedToolFailure(
        category=category,
        route=route,
        retryable=retryable,
        delay=delay,
        safe_message=f"{category}: {safe_detail}"[:500],
    )


def _safe_detail(error: Exception, arguments: Mapping[str, object] | None) -> str:
    """保留可读的失败原因，同时在落库前完成脱敏与截断。

    只记录异常类型名会让服务端的可读错误（例如 CLS 的语法错误）彻底消失，
    排查时只能看到 transport 这类笼统分类。这里保留有界摘要，但先过两道脱敏：
    密钥类取值与敏感参数取值都不能出现在摘要里。
    """
    base = type(error).__name__
    message = str(error).strip()
    if not message:
        return base
    return f"{base}: {_redact_arguments(_redact_secrets(message), arguments)}"[:_SAFE_DETAIL_LIMIT]


def _redact_secrets(message: str) -> str:
    return redact_error(message, "{}")


def _redact_arguments(message: str, arguments: Mapping[str, object] | None) -> str:
    if not arguments:
        return message
    redacted = message
    for key, value in arguments.items():
        if not isinstance(value, str) or not value.strip():
            continue
        if str(key).strip().casefold().replace("-", "_") in SENSITIVE_ARGUMENT_KEYS:
            redacted = redacted.replace(value, "[redacted]")
    return redacted


def _validation_detail(error: ValidationError) -> str:
    fields: list[str] = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        fields.append(f"{location}:{item['type']}")
    return "fields=" + ",".join(fields[:20])
