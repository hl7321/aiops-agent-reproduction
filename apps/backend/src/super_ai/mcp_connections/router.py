from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from super_ai.api_contracts import (
    CreateMcpConnectionRequest,
    FailureEnvelope,
    McpConnection,
    McpConnectionCheckResult,
    McpConnectionDeleteData,
    McpConnectionListData,
    McpDiscoveredTool,
    SuccessEnvelope,
    UpdateMcpConnectionRequest,
)
from super_ai.api_responses import success_response
from super_ai.mcp_connections.dependencies import get_mcp_connection_service
from super_ai.mcp_connections.models import CreateMcpConnection, McpConnectionRecord
from super_ai.mcp_connections.service import McpCheckResult, McpConnectionService
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/mcp", tags=["mcp"])
AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
}
CREATE_RESPONSES = {
    **AUTH_RESPONSES,
    409: {"model": FailureEnvelope},
    422: {"model": FailureEnvelope},
}
UPDATE_RESPONSES = {
    **CREATE_RESPONSES,
    404: {"model": FailureEnvelope},
}
RESOURCE_RESPONSES = {
    **AUTH_RESPONSES,
    404: {"model": FailureEnvelope},
    422: {"model": FailureEnvelope},
}
CHECK_RESPONSES = {
    **RESOURCE_RESPONSES,
    502: {"model": FailureEnvelope},
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _required_iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _connection(record: McpConnectionRecord) -> McpConnection:
    return McpConnection(
        id=record.id,
        name=record.name,
        transport=record.transport,
        url=record.url,
        enabled=record.enabled,
        timeoutSeconds=record.timeout_seconds,
        retries=record.retries,
        lastCheck=_iso(record.last_check),
        lastError=record.last_error,
        discoveredTools=[
            McpDiscoveredTool(name=item.name, description=item.description)
            for item in record.discovered_tools
        ],
        createdAt=_required_iso(record.created_at),
        updatedAt=_required_iso(record.updated_at),
    )


def _values(body: CreateMcpConnectionRequest) -> CreateMcpConnection:
    return CreateMcpConnection(
        body.name, body.transport, body.url, body.enabled, body.timeout_seconds, body.retries
    )


@router.get(
    "/connections",
    operation_id="listMcpConnections",
    response_model=SuccessEnvelope[McpConnectionListData],
    responses=AUTH_RESPONSES,
)
async def list_connections(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[McpConnectionService, Depends(get_mcp_connection_service)],
) -> JSONResponse:
    records = await service.list(current_user.owner_user_id)
    data = McpConnectionListData(connections=[_connection(item) for item in records])
    return success_response(data, get_request_id(request), exclude_none=False)


@router.post(
    "/connections",
    status_code=201,
    operation_id="createMcpConnection",
    response_model=SuccessEnvelope[McpConnection],
    responses=CREATE_RESPONSES,
)
async def create_connection(
    body: CreateMcpConnectionRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[McpConnectionService, Depends(get_mcp_connection_service)],
) -> JSONResponse:
    created = await service.create(current_user.owner_user_id, _values(body))
    return success_response(
        _connection(created), get_request_id(request), status_code=201, exclude_none=False
    )


@router.put(
    "/connections/{id}",
    operation_id="updateMcpConnection",
    response_model=SuccessEnvelope[McpConnection],
    responses=UPDATE_RESPONSES,
)
async def update_connection(
    id: str,
    body: UpdateMcpConnectionRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[McpConnectionService, Depends(get_mcp_connection_service)],
) -> JSONResponse:
    updated = await service.update(current_user.owner_user_id, id, _values(body))
    return success_response(_connection(updated), get_request_id(request), exclude_none=False)


@router.delete(
    "/connections/{id}",
    operation_id="deleteMcpConnection",
    response_model=SuccessEnvelope[McpConnectionDeleteData],
    responses=RESOURCE_RESPONSES,
)
async def delete_connection(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[McpConnectionService, Depends(get_mcp_connection_service)],
) -> JSONResponse:
    await service.delete(current_user.owner_user_id, id)
    return success_response(McpConnectionDeleteData(connectionId=id), get_request_id(request))


def _check(result: McpCheckResult) -> McpConnectionCheckResult:
    return McpConnectionCheckResult(
        status=result.status,
        connection=_connection(result.connection),
        tools=[
            McpDiscoveredTool(name=item.name, description=item.description) for item in result.tools
        ],
        error=result.error,
    )


@router.post(
    "/connections/{id}:check",
    operation_id="checkMcpConnection",
    response_model=SuccessEnvelope[McpConnectionCheckResult],
    responses=CHECK_RESPONSES,
)
async def check_connection(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[McpConnectionService, Depends(get_mcp_connection_service)],
) -> JSONResponse:
    result = await service.check(current_user.owner_user_id, id)
    return success_response(_check(result), get_request_id(request), exclude_none=False)
