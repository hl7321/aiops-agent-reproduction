from datetime import datetime
from typing import Protocol

from super_ai.mcp_connections.models import (
    CreateMcpConnection,
    McpConnectionRecord,
    McpDiscoveredToolRecord,
)


class McpConnectionRepository(Protocol):
    async def list(self, owner_user_id: str) -> tuple[McpConnectionRecord, ...]: ...
    async def get(self, owner_user_id: str, connection_id: str) -> McpConnectionRecord | None: ...
    async def create(
        self, owner_user_id: str, values: CreateMcpConnection
    ) -> McpConnectionRecord: ...
    async def update(
        self, owner_user_id: str, connection_id: str, values: CreateMcpConnection
    ) -> McpConnectionRecord | None: ...
    async def delete(self, owner_user_id: str, connection_id: str) -> bool: ...
    async def save_check(
        self,
        owner_user_id: str,
        connection_id: str,
        checked_at: datetime,
        error: str | None,
        tools: tuple[McpDiscoveredToolRecord, ...],
    ) -> McpConnectionRecord | None: ...
