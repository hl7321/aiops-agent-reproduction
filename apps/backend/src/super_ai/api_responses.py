"""统一 HTTP envelope 构造与安全应用错误。"""

from fastapi.responses import JSONResponse
from pydantic import JsonValue

from super_ai.api_contracts import (
    ERROR_DEFINITIONS,
    ApiErrorModel,
    ErrorCode,
    FailureEnvelope,
    RequestMeta,
    SuccessEnvelope,
)

REQUEST_ID_HEADER = "X-Request-ID"
class AppError(Exception):
    """只能引用共享目录 code 的可安全返回应用错误。"""

    def __init__(
        self,
        code: ErrorCode,
        *,
        details: JsonValue | None = None,
        message: str | None = None,
    ) -> None:
        definition = ERROR_DEFINITIONS[code]
        super().__init__(message or definition.default_message)
        self.code: ErrorCode = code
        self.details: JsonValue | None = details
        self.safe_message: str = message or definition.default_message


def success_response(data: object, request_id: str, *, status_code: int = 200) -> JSONResponse:
    """构造成功 envelope。"""
    envelope = SuccessEnvelope[object](data=data, meta=RequestMeta(requestId=request_id))
    return JSONResponse(
        content=envelope.model_dump(mode="json", by_alias=True, exclude_none=True),
        status_code=status_code,
        headers={REQUEST_ID_HEADER: request_id},
    )


def error_response(
    code: ErrorCode,
    request_id: str,
    *,
    details: JsonValue | None = None,
    message: str | None = None,
) -> JSONResponse:
    """按共享目录构造失败 envelope。"""
    definition = ERROR_DEFINITIONS[code]
    error = ApiErrorModel(
        code=code,
        category=definition.category,
        httpStatus=definition.http_status,
        message=message or definition.default_message,
        details=details,
    )
    envelope = FailureEnvelope(error=error, meta=RequestMeta(requestId=request_id))
    return JSONResponse(
        content=envelope.model_dump(mode="json", by_alias=True, exclude_none=True),
        status_code=definition.http_status,
        headers={REQUEST_ID_HEADER: request_id},
    )
