"""owner-scoped 后台任务管理 API。"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from super_ai.api_contracts import (
    BackgroundJob,
    BackgroundJobListData,
    FailureEnvelope,
    SuccessEnvelope,
)
from super_ai.api_responses import success_response
from super_ai.background_jobs.dependencies import get_background_job_service
from super_ai.background_jobs.models import BackgroundJobRecord
from super_ai.background_jobs.service import BackgroundJobService
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/background-jobs", tags=["background-jobs"])
PROTECTED_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope, "description": "需要有效 bearer token"},
    403: {"model": FailureEnvelope, "description": "当前用户无权访问"},
    404: {"model": FailureEnvelope, "description": "任务不存在或不可见"},
}
RETRY_RESPONSES = {
    **PROTECTED_RESPONSES,
    409: {"model": FailureEnvelope, "description": "任务不可重试"},
}


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _job(record: BackgroundJobRecord) -> BackgroundJob:
    return BackgroundJob(
        id=record.id,
        ownerUserId=record.owner_user_id,
        kind=record.kind,
        resourceType=record.resource_type,
        resourceId=record.resource_id,
        status=record.status,
        payload=record.payload,
        attempt=record.attempt,
        maxAttempts=record.max_attempts,
        timeoutSeconds=record.timeout_seconds,
        availableAt=_timestamp(record.available_at) or "",
        leaseOwner=record.lease_owner,
        leaseExpiresAt=_timestamp(record.lease_expires_at),
        cancelRequestedAt=_timestamp(record.cancel_requested_at),
        retryOfJobId=record.retry_of_job_id,
        errorMessage=record.error_message,
        createdAt=_timestamp(record.created_at) or "",
        updatedAt=_timestamp(record.updated_at) or "",
        startedAt=_timestamp(record.started_at),
        completedAt=_timestamp(record.completed_at),
    )


@router.get(
    "",
    operation_id="listBackgroundJobs",
    response_model=SuccessEnvelope[BackgroundJobListData],
    responses=PROTECTED_RESPONSES,
)
async def list_background_jobs(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BackgroundJobService, Depends(get_background_job_service)],
) -> JSONResponse:
    records = await service.list(current_user.owner_user_id)
    return success_response(
        BackgroundJobListData(items=[_job(item) for item in records]), get_request_id(request)
    )


@router.get(
    "/{id}",
    operation_id="getBackgroundJob",
    response_model=SuccessEnvelope[BackgroundJob],
    responses=PROTECTED_RESPONSES,
)
async def get_background_job(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BackgroundJobService, Depends(get_background_job_service)],
) -> JSONResponse:
    return success_response(
        _job(await service.get(current_user.owner_user_id, id)), get_request_id(request)
    )


@router.post(
    "/{id}:cancel",
    operation_id="cancelBackgroundJob",
    response_model=SuccessEnvelope[BackgroundJob],
    responses=PROTECTED_RESPONSES,
)
async def cancel_background_job(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BackgroundJobService, Depends(get_background_job_service)],
) -> JSONResponse:
    return success_response(
        _job(await service.cancel(current_user.owner_user_id, id)), get_request_id(request)
    )


@router.post(
    "/{id}:retry",
    operation_id="retryBackgroundJob",
    response_model=SuccessEnvelope[BackgroundJob],
    responses=RETRY_RESPONSES,
)
async def retry_background_job(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[BackgroundJobService, Depends(get_background_job_service)],
) -> JSONResponse:
    return success_response(
        _job(await service.retry(current_user.owner_user_id, id)), get_request_id(request)
    )
