"""HTTP request ID 解析与中间件。"""

import re
from collections.abc import Awaitable, Callable
from typing import Final
from uuid import uuid4

from fastapi import Request, Response

from super_ai.api_responses import REQUEST_ID_HEADER

REQUEST_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._:-]{1,128}")
CallNext = Callable[[Request], Awaitable[Response]]


def resolve_request_id(candidate: str | None) -> str:
    """透传合法请求 ID，否则生成 UUID。"""
    if candidate is not None and REQUEST_ID_PATTERN.fullmatch(candidate) is not None:
        return candidate
    return str(uuid4())


def get_request_id(request: Request) -> str:
    """读取中间件建立的请求 ID。"""
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return resolve_request_id(None)


async def request_id_middleware(request: Request, call_next: CallNext) -> Response:
    """为每次请求建立并返回相同 request ID。"""
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
