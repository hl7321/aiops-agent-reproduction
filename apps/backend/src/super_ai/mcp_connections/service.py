from dataclasses import dataclass
from typing import Literal

from langchain_core.tools import BaseTool
from sqlalchemy.exc import IntegrityError

from super_ai.api_responses import AppError
from super_ai.mcp_connections.gateway import McpToolGateway
from super_ai.mcp_connections.models import (
    CreateMcpConnection,
    McpConnectionRecord,
    McpConnectionTarget,
    McpDiscoveredToolRecord,
)
from super_ai.mcp_connections.repositories import McpConnectionRepository
from super_ai.mcp_connections.security import safe_mcp_error, validate_mcp_url
from super_ai.memory.primitives import utc_now

MAX_DISCOVERED_TOOLS = 500
MAX_TOOL_NAME_LENGTH = 255
MAX_TOOL_DESCRIPTION_LENGTH = 2000


@dataclass(frozen=True, slots=True)
class McpCheckResult:
    status: Literal["connected", "failed"]
    connection: McpConnectionRecord
    tools: tuple[McpDiscoveredToolRecord, ...]
    error: str | None


class McpConnectionService:
    def __init__(self, repository: McpConnectionRepository, gateway: McpToolGateway) -> None:
        self._repository = repository
        self._gateway = gateway

    async def list(self, owner_user_id: str) -> tuple[McpConnectionRecord, ...]:
        return await self._repository.list(owner_user_id)

    async def create(self, owner_user_id: str, values: CreateMcpConnection) -> McpConnectionRecord:
        validated = _validated(values)
        try:
            return await self._repository.create(owner_user_id, validated)
        except IntegrityError as error:
            raise AppError("BUSINESS_CONFLICT", message="同名 MCP 连接已存在") from error

    async def update(
        self, owner_user_id: str, connection_id: str, values: CreateMcpConnection
    ) -> McpConnectionRecord:
        try:
            record = await self._repository.update(owner_user_id, connection_id, _validated(values))
        except IntegrityError as error:
            raise AppError("BUSINESS_CONFLICT", message="同名 MCP 连接已存在") from error
        if record is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return record

    async def delete(self, owner_user_id: str, connection_id: str) -> None:
        if not await self._repository.delete(owner_user_id, connection_id):
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")

    async def check(self, owner_user_id: str, connection_id: str) -> McpCheckResult:
        connection = await self._repository.get(owner_user_id, connection_id)
        if connection is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        target = McpConnectionTarget.from_record(connection)
        checked_at = utc_now()
        try:
            discovered = await self._gateway.discover((target,), builtin_tool_names=frozenset())
            tools = _validated_tool_catalog(discovered.tools)
            updated = await self._repository.save_check(
                owner_user_id, connection_id, checked_at, None, tools
            )
            if updated is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            return McpCheckResult("connected", updated, tools, None)
        except AppError as error:
            if error.code == "BUSINESS_MCP_TOOL_NAME_CONFLICT":
                safe = "MCP 工具名称发生冲突"
            else:
                safe = safe_mcp_error(error)
            updated = await self._repository.save_check(
                owner_user_id, connection_id, checked_at, safe, ()
            )
            if updated is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND") from error
            return McpCheckResult("failed", updated, (), safe)


def _validated(values: CreateMcpConnection) -> CreateMcpConnection:
    return CreateMcpConnection(
        values.name.strip(),
        values.transport,
        validate_mcp_url(values.url),
        values.enabled,
        values.timeout_seconds,
        values.retries,
    )


def _validated_tool_catalog(tools: tuple[BaseTool, ...]) -> tuple[McpDiscoveredToolRecord, ...]:
    if len(tools) > MAX_DISCOVERED_TOOLS:
        raise AppError("SYSTEM_MCP_CONNECTION_FAILED")
    catalog: list[McpDiscoveredToolRecord] = []
    for item in tools:
        name = getattr(item, "name", None)
        description = getattr(item, "description", None)
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > MAX_TOOL_NAME_LENGTH
            or (description is not None and not isinstance(description, str))
            or (isinstance(description, str) and len(description) > MAX_TOOL_DESCRIPTION_LENGTH)
        ):
            raise AppError("SYSTEM_MCP_CONNECTION_FAILED")
        catalog.append(McpDiscoveredToolRecord(name, description or None))
    return tuple(catalog)
