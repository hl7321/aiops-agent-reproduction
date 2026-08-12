"""从 bearer principal 派生可信 tenant context 的 FastAPI dependencies。"""

from typing import Annotated

from fastapi import Depends

from super_ai.auth.dependencies import get_current_principal
from super_ai.auth.models import AuthPrincipal
from super_ai.tenancy.context import CurrentUser, TenantContext


async def get_current_user(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> CurrentUser:
    return CurrentUser(user_id=principal.user.id)


async def get_tenant_context(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantContext:
    return TenantContext.from_current_user(current_user)
