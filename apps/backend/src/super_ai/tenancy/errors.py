"""不泄露其他 owner 资源存在性的错误映射。"""

from typing import TypeVar

from super_ai.api_responses import AppError

T = TypeVar("T")


def require_scoped_resource(value: T | None) -> T:
    if value is None:
        raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
    return value


def require_scoped_parent(value: T | None) -> T:
    if value is None:
        raise AppError("AUTH_FORBIDDEN")
    return value
