"""AIOps 工具错误分类；Pydantic 发现结构错误，本模块决定恢复路线。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

import httpx
from pydantic import ValidationError

from super_ai.aiops.models import ToolErrorCategory

ToolFailureRoute: TypeAlias = Literal[
    "retry_same_step", "replan", "permanent_failure"
]
ToolFailurePhase: TypeAlias = Literal["input", "invoke", "output", "empty"]


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


def classify_tool_failure(
    error: Exception,
    *,
    phase: ToolFailurePhase | str,
    attempt: int,
) -> ClassifiedToolFailure:
    if isinstance(error, ToolConfigurationError):
        return _failure("configuration", "permanent_failure", False, error)
    if isinstance(error, ToolOwnerScopeError):
        return _failure("owner_scope", "permanent_failure", False, error)
    if isinstance(error, ToolSchemaIncompatibleError):
        return _failure("schema_incompatible", "permanent_failure", False, error)
    if isinstance(error, ToolEmptyResultError):
        return _failure("empty_result", "replan", False, error)
    if isinstance(error, ToolOutputValidationError):
        return _failure("output_validation", "permanent_failure", False, error)
    if phase == "input" or isinstance(error, ValidationError):
        return _failure("input_validation", "retry_same_step", True, error)
    if phase == "empty":
        return _failure("empty_result", "replan", False, error)
    if isinstance(error, httpx.TimeoutException) or isinstance(error, TimeoutError):
        return _failure("timeout", "retry_same_step", True, error, _delay(attempt))
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 429:
            return _failure("rate_limited", "retry_same_step", True, error, _delay(attempt))
        if status >= 500:
            return _failure(
                "provider_unavailable", "retry_same_step", True, error, _delay(attempt)
            )
        if status in {401, 403}:
            return _failure("permission", "permanent_failure", False, error)
        return _failure("permanent", "permanent_failure", False, error)
    if phase == "output":
        return _failure("output_validation", "permanent_failure", False, error)
    return _failure("transport", "retry_same_step", True, error, _delay(attempt))


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
) -> ClassifiedToolFailure:
    safe_detail = type(error).__name__
    if isinstance(error, ValidationError):
        fields: list[str] = []
        for item in error.errors(include_url=False, include_context=False, include_input=False):
            location = ".".join(str(part) for part in item["loc"]) or "<root>"
            fields.append(f"{location}:{item['type']}")
        safe_detail = "fields=" + ",".join(fields[:20])
    return ClassifiedToolFailure(
        category=category,
        route=route,
        retryable=retryable,
        delay=delay,
        safe_message=f"{category}: {safe_detail}"[:500],
    )
