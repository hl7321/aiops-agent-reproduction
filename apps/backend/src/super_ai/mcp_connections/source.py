from typing import Protocol

from super_ai.mcp_connections.models import McpConnectionRecord, McpConnectionTarget
from super_ai.mcp_connections.settings import ClsMcpServerSettings


class McpConnectionLister(Protocol):
    async def list(self, owner_user_id: str) -> tuple[McpConnectionRecord, ...]: ...


class McpConnectionSource(Protocol):
    async def targets_for(self, owner_user_id: str) -> tuple[McpConnectionTarget, ...]: ...


class ConfiguredMcpConnectionSource:
    def __init__(self, repository: McpConnectionLister, fallback: ClsMcpServerSettings) -> None:
        self._repository = repository
        self._fallback = fallback

    async def targets_for(self, owner_user_id: str) -> tuple[McpConnectionTarget, ...]:
        enabled = tuple(item for item in await self._repository.list(owner_user_id) if item.enabled)
        if enabled:
            return tuple(McpConnectionTarget.from_record(item) for item in enabled)
        if not self._fallback.base_url:
            return ()
        return (
            McpConnectionTarget(
                "cls-fallback",
                "cls-fallback",
                self._fallback.transport,
                self._fallback.base_url,
                self._fallback.timeout_seconds,
                self._fallback.retries,
            ),
        )
