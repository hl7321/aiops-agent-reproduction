"""FastAPI 应用工厂。"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import JsonValue
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from super_ai.api_contracts import ErrorCode, FoundationStatus, SuccessEnvelope
from super_ai.api_responses import AppError, error_response, success_response
from super_ai.auth.router import router as auth_router
from super_ai.auth.service import AuthServiceError
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import create_persistence_lifespan
from super_ai.request_id import get_request_id, request_id_middleware


async def health(request: Request) -> JSONResponse:
    """返回不依赖外部服务的 foundation 健康状态。"""
    return success_response(FoundationStatus(), get_request_id(request))


async def app_error_handler(request: Request, error: Exception) -> JSONResponse:
    """将已登记应用错误转换为失败 envelope。"""
    if not isinstance(error, AppError):
        raise TypeError("app_error_handler received an unexpected exception")
    return error_response(
        error.code,
        get_request_id(request),
        details=error.details,
        message=error.safe_message,
    )


async def auth_service_error_handler(request: Request, error: Exception) -> JSONResponse:
    """将认证领域错误映射为共享目录失败 envelope。"""
    if not isinstance(error, AuthServiceError):
        raise TypeError("auth_service_error_handler received an unexpected exception")
    return error_response(error.code, get_request_id(request))


async def validation_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """将 FastAPI 验证错误转换为安全字段路径。"""
    if not isinstance(error, RequestValidationError):
        raise TypeError("validation_error_handler received an unexpected exception")
    fields: list[JsonValue] = []
    for issue in error.errors():
        location = issue.get("loc", ())
        path = ".".join(str(part) for part in location)
        fields.append(
            {
                "path": path,
                "type": str(issue.get("type", "validation_error")),
                "message": str(issue.get("msg", "Invalid value")),
            }
        )
    return error_response(
        "VALIDATION_REQUEST_INVALID",
        get_request_id(request),
        details={"fields": fields},
    )


async def unhandled_error_handler(request: Request, _error: Exception) -> JSONResponse:
    """隐藏未处理异常的内部信息。"""
    return error_response("SYSTEM_INTERNAL_ERROR", get_request_id(request))


async def http_error_handler(request: Request, error: Exception) -> JSONResponse:
    """把框架 404/405 转换为已登记失败 envelope。"""
    if not isinstance(error, StarletteHTTPException):
        raise TypeError("http_error_handler received an unexpected exception")
    status_codes: dict[int, ErrorCode] = {
        404: "SYSTEM_ROUTE_NOT_FOUND",
        405: "SYSTEM_METHOD_NOT_ALLOWED",
    }
    code: ErrorCode = status_codes.get(error.status_code, "SYSTEM_INTERNAL_ERROR")
    return error_response(code, get_request_id(request))


def create_app(database_settings: DatabaseSettings | None = None) -> FastAPI:
    """创建无外部连接副作用的最小 FastAPI 应用。"""
    lifespan = (
        create_persistence_lifespan(database_settings) if database_settings is not None else None
    )
    app = FastAPI(title="智能 OnCall Agent", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(AuthServiceError, auth_service_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.add_api_route(
        "/health",
        health,
        methods=["GET"],
        operation_id="getHealth",
        response_model=SuccessEnvelope[FoundationStatus],
    )
    app.include_router(auth_router)
    return app
