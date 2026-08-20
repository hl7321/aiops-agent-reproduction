from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.mcp_connections.gateway import (
    LangChainMcpClientFactory,
    LangChainMcpToolGateway,
    McpToolGateway,
)
from super_ai.mcp_connections.service import McpConnectionService
from super_ai.memory.extended_sqlite.mcp_connection_repositories import (
    SqliteMcpConnectionRepository,
)
from super_ai.memory.sqlite import get_session


def get_mcp_connection_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> McpConnectionService:
    injected = getattr(request.app.state, "mcp_gateway", None)
    gateway: McpToolGateway = (
        injected if injected is not None else LangChainMcpToolGateway(LangChainMcpClientFactory())
    )
    return McpConnectionService(SqliteMcpConnectionRepository(session), gateway)
