"""FastAPI 认证服务与 bearer principal dependencies。"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.auth.models import AuthPrincipal
from super_ai.auth.passwords import PwdlibPasswordManager
from super_ai.auth.service import AuthService, AuthServiceError
from super_ai.memory.extended_sqlite.auth_repositories import (
    SqliteAuthSessionRepository,
    SqliteUserRepository,
)
from super_ai.memory.sqlite import PersistenceRuntime, get_session, transaction_scope

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def get_auth_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AuthService:
    return AuthService(
        SqliteUserRepository(session),
        SqliteAuthSessionRepository(session),
        PwdlibPasswordManager(),
    )


async def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthServiceError("AUTH_REQUIRED")
    runtime = getattr(request.app.state, "persistence_runtime", None)
    if not isinstance(runtime, PersistenceRuntime):
        raise RuntimeError("持久化 runtime 尚未初始化")
    async with transaction_scope(runtime.session_factory) as session:
        return await AuthService(
            SqliteUserRepository(session),
            SqliteAuthSessionRepository(session),
            PwdlibPasswordManager(),
        ).authenticate(credentials.credentials)
