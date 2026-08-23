"""公开运行时诊断 endpoints。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, JsonValue

from super_ai.api_contracts import FailureEnvelope, SuccessEnvelope
from super_ai.api_responses import error_response, success_response
from super_ai.llm.config import load_llm_settings
from super_ai.mcp_connections.settings import load_cls_mcp_server_settings
from super_ai.memory.config import load_database_settings
from super_ai.project_config import load_project_config
from super_ai.request_id import get_request_id
from super_ai.runtime.checks import RuntimeChecks
from super_ai.runtime.metrics import ProcessMetricsRegistry
from super_ai.runtime.models import (
    ConfigurationCheckData,
    ConfigurationStatus,
    ProcessMetrics,
    ReadinessData,
    RuntimeDependencies,
    RuntimeDependencyResult,
)
from super_ai.runtime.security import redact_text
from super_ai.vector_store.config import load_vector_store_settings

router = APIRouter(tags=["runtime"])
REQUIRED_SECTIONS = (
    "app",
    "backend",
    "frontend",
    "database",
    "llm",
    "modelCapabilities",
    "vectorStore",
    "mcp",
    "clsMcpServer",
    "prometheusAlerts",
    "clsLogUpload",
    "aiopsDemo",
)


def _checks(request: Request) -> RuntimeChecks:
    checks = getattr(request.app.state, "runtime_checks", None)
    if checks is None:
        raise RuntimeError("运行时依赖检查未配置")
    return checks


def _paths(request: Request) -> tuple[Path, Path]:
    raw: object = getattr(request.app.state, "project_config_paths", None)
    if not isinstance(raw, tuple):
        raise RuntimeError("本地 JSON 配置路径未配置")
    values = cast(tuple[object, ...], raw)
    if len(values) != 2:
        raise RuntimeError("本地 JSON 配置路径未配置")
    project: object = values[0]
    user: object = values[1]
    if not isinstance(project, Path) or not isinstance(user, Path):
        raise RuntimeError("本地 JSON 配置路径无效")
    return project, user


def _details(data: BaseModel) -> JsonValue:
    return data.model_dump(mode="json", by_alias=True, exclude_none=False)


@router.get(
    "/ready",
    operation_id="getRuntimeReadiness",
    response_model=SuccessEnvelope[ReadinessData] | FailureEnvelope,
    responses={503: {"model": FailureEnvelope}},
)
async def ready(request: Request) -> JSONResponse:
    try:
        dependencies = await _checks(request).run()
    except Exception as error:
        unavailable = _all_unavailable(redact_text(str(error)) or "运行时依赖检查未配置")
        data = ReadinessData(status="unavailable", dependencies=unavailable)
        return error_response("SYSTEM_UNAVAILABLE", get_request_id(request), details=_details(data))
    data = ReadinessData(
        status="ready" if dependencies.ready else "unavailable",
        dependencies=dependencies,
    )
    if not dependencies.ready:
        return error_response("SYSTEM_UNAVAILABLE", get_request_id(request), details=_details(data))
    return success_response(data, get_request_id(request), exclude_none=False)


@router.get(
    "/health/mcp",
    operation_id="getMcpHealth",
    response_model=SuccessEnvelope[RuntimeDependencyResult] | FailureEnvelope,
    responses={503: {"model": FailureEnvelope}},
)
async def mcp_health(request: Request) -> JSONResponse:
    try:
        result = await _checks(request).run_mcp()
    except (AttributeError, RuntimeError) as error:
        result = RuntimeDependencyResult(
            name="mcp", status="unavailable", latencyMs=0, error=redact_text(str(error))
        )
    if result.status == "unavailable":
        return error_response(
            "SYSTEM_UNAVAILABLE", get_request_id(request), details=_details(result)
        )
    return success_response(result, get_request_id(request), exclude_none=False)


@router.get(
    "/config/check",
    operation_id="checkRuntimeConfiguration",
    response_model=SuccessEnvelope[ConfigurationCheckData] | FailureEnvelope,
    responses={503: {"model": FailureEnvelope}},
)
async def config_check(request: Request) -> JSONResponse:
    request_id = get_request_id(request)
    try:
        project, user = _paths(request)
        merged = load_project_config(project, user)
        missing = [section for section in REQUIRED_SECTIONS if section not in merged]
        if missing:
            raise ValueError(f"缺少配置 section: {', '.join(missing)}")
        load_database_settings(project, user)
        load_llm_settings(project, user).require_api_key()
        load_vector_store_settings(project, user)
        load_cls_mcp_server_settings(project, user)
    except Exception as error:
        data = ConfigurationCheckData(
            status="configuration_invalid",
            configuration=ConfigurationStatus(
                status="invalid", sections=[], error=redact_text(str(error))
            ),
            dependencies=None,
        )
        return error_response("SYSTEM_UNAVAILABLE", request_id, details=_details(data))
    configuration = ConfigurationStatus(
        status="valid",
        sections=list(REQUIRED_SECTIONS),
        error=None,
    )
    dependencies = await _checks(request).run()
    data = ConfigurationCheckData(
        status="ready" if dependencies.ready else "dependencies_unavailable",
        configuration=configuration,
        dependencies=dependencies,
    )
    if not dependencies.ready:
        return error_response("SYSTEM_UNAVAILABLE", request_id, details=_details(data))
    return success_response(data, request_id, exclude_none=False)


@router.get(
    "/metrics",
    operation_id="getProcessMetrics",
    response_model=SuccessEnvelope[ProcessMetrics],
)
async def metrics(request: Request) -> JSONResponse:
    registry = getattr(request.app.state, "process_metrics", None)
    if not isinstance(registry, ProcessMetricsRegistry):
        raise RuntimeError("进程指标 registry 未配置")
    return success_response(registry.snapshot(), get_request_id(request))


def _all_unavailable(error: str) -> RuntimeDependencies:
    return RuntimeDependencies(
        **{
            name: RuntimeDependencyResult(
                name=name, status="unavailable", latencyMs=0, error=error
            )
            for name in ("sqlite", "milvus", "qwen", "mcp")
        }
    )
