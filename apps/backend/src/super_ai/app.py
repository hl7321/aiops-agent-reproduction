"""FastAPI 应用工厂。"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import JsonValue
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from super_ai.alerts.router import router as alerts_router
from super_ai.alerts.settings import PrometheusAlertsSettings, load_alert_settings
from super_ai.api_contracts import ErrorCode, FoundationStatus, SuccessEnvelope
from super_ai.api_responses import AppError, error_response, success_response
from super_ai.auth.router import router as auth_router
from super_ai.auth.service import AuthServiceError
from super_ai.background_jobs.handlers import HandlerRegistry
from super_ai.background_jobs.lifespan import HandlerFactory, create_application_lifespan
from super_ai.background_jobs.router import router as background_jobs_router
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.chat.memory.summarizer import ChatMemorySummarizer
from super_ai.chat.router import router as chat_router
from super_ai.chat_configuration.router import router as chat_configuration_router
from super_ai.document_indexing.factory import create_configured_document_index_handler_factory
from super_ai.document_indexing.router import router as document_indexing_router
from super_ai.knowledge.dependencies import (
    create_knowledge_service_dependency,
    get_knowledge_service,
)
from super_ai.knowledge.router import router as knowledge_router
from super_ai.knowledge.vector import MilvusDocumentVectorDeleter
from super_ai.llm.config import LlmSettings, load_llm_settings
from super_ai.mcp_connections.gateway import McpToolGateway
from super_ai.mcp_connections.router import router as mcp_router
from super_ai.mcp_connections.settings import ClsMcpServerSettings, load_cls_mcp_server_settings
from super_ai.memory.config import DatabaseSettings, load_database_settings
from super_ai.request_id import get_request_id, request_id_middleware
from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.config import VectorStoreSettings, load_vector_store_settings


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


def create_app(
    database_settings: DatabaseSettings | None = None,
    *,
    background_job_registry: HandlerRegistry | None = None,
    worker_settings: WorkerSettings | None = None,
    document_index_handler_factory: HandlerFactory | None = None,
    llm_settings: LlmSettings | None = None,
    vector_store_settings: VectorStoreSettings | None = None,
    chat_memory_context_window_tokens: int | None = None,
    chat_memory_summarizer: ChatMemorySummarizer | None = None,
    mcp_gateway: McpToolGateway | None = None,
    cls_mcp_server_settings: ClsMcpServerSettings | None = None,
    alert_settings: PrometheusAlertsSettings | None = None,
) -> FastAPI:
    """创建无外部连接副作用的最小 FastAPI 应用。"""
    registry = background_job_registry or HandlerRegistry()
    if (llm_settings is None) != (vector_store_settings is None):
        raise ValueError("文档索引要求同时提供 LLM 与 vectorStore typed settings")
    configured_factory = (
        create_configured_document_index_handler_factory(llm_settings, vector_store_settings)
        if llm_settings is not None and vector_store_settings is not None
        else None
    )
    selected_factory = document_index_handler_factory or configured_factory
    handler_factories = (selected_factory,) if selected_factory is not None else ()
    lifespan = (
        create_application_lifespan(
            database_settings, registry, worker_settings, handler_factories=handler_factories
        )
        if database_settings is not None
        else None
    )
    app = FastAPI(title="智能 OnCall Agent", lifespan=lifespan)
    app.state.agent_llm_settings = llm_settings
    app.state.agent_vector_store_settings = vector_store_settings
    app.state.chat_memory_context_window_tokens = chat_memory_context_window_tokens
    app.state.chat_memory_summarizer = chat_memory_summarizer
    app.state.mcp_gateway = mcp_gateway
    app.state.cls_mcp_server_settings = cls_mcp_server_settings or ClsMcpServerSettings()
    app.state.alert_settings = alert_settings or PrometheusAlertsSettings()
    if vector_store_settings is not None:
        knowledge_vector_store = MilvusVectorStore(vector_store_settings)
        app.dependency_overrides[get_knowledge_service] = create_knowledge_service_dependency(
            MilvusDocumentVectorDeleter(knowledge_vector_store)
        )
    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    app.include_router(background_jobs_router)
    app.include_router(chat_router)
    app.include_router(chat_configuration_router)
    app.include_router(knowledge_router)
    app.include_router(document_indexing_router)
    app.include_router(mcp_router)
    app.include_router(alerts_router)
    return app


def create_configured_app(project_path: Path, user_path: Path) -> FastAPI:
    """只从显式本地 JSON 路径组装可执行应用；外部 client 仍由 handler 延迟创建。"""
    return create_app(
        load_database_settings(project_path, user_path),
        llm_settings=load_llm_settings(project_path, user_path),
        vector_store_settings=load_vector_store_settings(project_path, user_path),
        cls_mcp_server_settings=load_cls_mcp_server_settings(project_path, user_path),
        alert_settings=load_alert_settings(project_path, user_path),
    )
