from datetime import datetime
from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.mcp_connections.models import (
    CreateMcpConnection,
    McpConnectionRecord,
    McpDiscoveredToolRecord,
    McpTransport,
)
from super_ai.memory.extended_sqlite.mcp_connection_models import McpConnectionModel
from super_ai.memory.primitives import new_id, utc_now
from super_ai.project_config import JsonValue


class SqliteMcpConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, owner_user_id: str) -> tuple[McpConnectionRecord, ...]:
        models = (
            await self._session.scalars(
                select(McpConnectionModel)
                .where(McpConnectionModel.owner_user_id == owner_user_id)
                .order_by(McpConnectionModel.updated_at.desc(), McpConnectionModel.id)
            )
        ).all()
        return tuple(_record(model) for model in models)

    async def get(self, owner_user_id: str, connection_id: str) -> McpConnectionRecord | None:
        model = await self._session.scalar(
            select(McpConnectionModel).where(
                McpConnectionModel.owner_user_id == owner_user_id,
                McpConnectionModel.id == connection_id,
            )
        )
        return _record(model) if model else None

    async def create(self, owner_user_id: str, values: CreateMcpConnection) -> McpConnectionRecord:
        now = utc_now()
        model = McpConnectionModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            name=values.name,
            transport=values.transport,
            url=values.url,
            enabled=values.enabled,
            timeout_seconds=values.timeout_seconds,
            retries=values.retries,
            discovered_tools_json=[],
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _record(model)

    async def update(
        self, owner_user_id: str, connection_id: str, values: CreateMcpConnection
    ) -> McpConnectionRecord | None:
        model = await self._session.scalar(
            update(McpConnectionModel)
            .where(
                McpConnectionModel.owner_user_id == owner_user_id,
                McpConnectionModel.id == connection_id,
            )
            .values(
                name=values.name,
                transport=values.transport,
                url=values.url,
                enabled=values.enabled,
                timeout_seconds=values.timeout_seconds,
                retries=values.retries,
                last_check=None,
                last_error=None,
                discovered_tools_json=[],
                updated_at=utc_now(),
            )
            .returning(McpConnectionModel)
        )
        return _record(model) if model else None

    async def delete(self, owner_user_id: str, connection_id: str) -> bool:
        removed = await self._session.scalar(
            delete(McpConnectionModel)
            .where(
                McpConnectionModel.owner_user_id == owner_user_id,
                McpConnectionModel.id == connection_id,
            )
            .returning(McpConnectionModel.id)
        )
        return removed is not None

    async def save_check(
        self,
        owner_user_id: str,
        connection_id: str,
        checked_at: datetime,
        error: str | None,
        tools: tuple[McpDiscoveredToolRecord, ...],
    ) -> McpConnectionRecord | None:
        payload = [{"name": tool.name, "description": tool.description} for tool in tools]
        model = await self._session.scalar(
            update(McpConnectionModel)
            .where(
                McpConnectionModel.owner_user_id == owner_user_id,
                McpConnectionModel.id == connection_id,
            )
            .values(
                last_check=checked_at,
                last_error=error,
                discovered_tools_json=payload,
                updated_at=checked_at,
            )
            .returning(McpConnectionModel)
        )
        return _record(model) if model else None


def _record(model: McpConnectionModel) -> McpConnectionRecord:
    raw = cast(list[dict[str, JsonValue]], model.discovered_tools_json)
    tools = tuple(
        McpDiscoveredToolRecord(str(item["name"]), cast(str | None, item.get("description")))
        for item in raw
    )
    return McpConnectionRecord(
        model.id,
        model.owner_user_id,
        model.name,
        cast(McpTransport, model.transport),
        model.url,
        model.enabled,
        model.timeout_seconds,
        model.retries,
        model.last_check,
        model.last_error,
        tools,
        model.created_at,
        model.updated_at,
    )
