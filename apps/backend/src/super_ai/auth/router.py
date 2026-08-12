"""统一 envelope 的用户认证 HTTP 路由。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from super_ai.api_contracts import (
    AuthUser,
    FailureEnvelope,
    LoginData,
    LoginRequest,
    LogoutData,
    RegisterRequest,
    SuccessEnvelope,
)
from super_ai.api_responses import success_response
from super_ai.auth.dependencies import get_auth_service, get_current_principal
from super_ai.auth.models import AuthPrincipal, UserRecord
from super_ai.auth.service import AuthService
from super_ai.request_id import get_request_id

router = APIRouter(prefix="/auth", tags=["auth"])
PROTECTED_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope, "description": "需要有效 bearer token"},
    403: {"model": FailureEnvelope, "description": "当前用户无权访问"},
}


def _auth_user(user: UserRecord) -> AuthUser:
    created_at = user.created_at.isoformat().replace("+00:00", "Z")
    return AuthUser(id=user.id, email=user.email, createdAt=created_at)


@router.post(
    "/register",
    operation_id="registerUser",
    response_model=SuccessEnvelope[AuthUser],
    status_code=201,
)
async def register_user(
    payload: RegisterRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> JSONResponse:
    user = await service.register(payload.email, payload.password)
    return success_response(_auth_user(user), get_request_id(request), status_code=201)


@router.post(
    "/login",
    operation_id="loginUser",
    response_model=SuccessEnvelope[LoginData],
)
async def login_user(
    payload: LoginRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> JSONResponse:
    login = await service.login(payload.email, payload.password)
    return success_response(
        LoginData(user=_auth_user(login.user), token=login.token),
        get_request_id(request),
    )


@router.post(
    "/logout",
    operation_id="logoutUser",
    response_model=SuccessEnvelope[LogoutData],
    responses=PROTECTED_RESPONSES,
)
async def logout_user(
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> JSONResponse:
    await service.logout(principal)
    return success_response(LogoutData(), get_request_id(request))


@router.get(
    "/me",
    operation_id="getCurrentUser",
    response_model=SuccessEnvelope[AuthUser],
    responses=PROTECTED_RESPONSES,
)
async def get_current_user(
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> JSONResponse:
    return success_response(_auth_user(principal.user), get_request_id(request))
