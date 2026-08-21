"""Owner-scoped 结构化反馈 JSON API。"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from super_ai.api_contracts import (
    FailureEnvelope,
    FeedbackDeleteData,
    FeedbackListData,
    FeedbackTargetType,
    SuccessEnvelope,
    UserFeedback,
    UserFeedbackUpsertRequest,
)
from super_ai.api_responses import success_response
from super_ai.feedback.dependencies import get_feedback_service
from super_ai.feedback.models import FeedbackRecord
from super_ai.feedback.service import FeedbackService
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/feedback", tags=["feedback"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
    404: {"model": FailureEnvelope},
    422: {"model": FailureEnvelope},
}


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _item(record: FeedbackRecord) -> UserFeedback:
    return UserFeedback(
        id=record.id,
        targetType=record.target_type,
        targetId=record.target_id,
        subjectId=record.subject_key or None,
        rating=record.rating,
        reason=record.reason,
        comment=record.comment,
        correction=record.correction,
        createdAt=_iso(record.created_at),
        updatedAt=_iso(record.updated_at),
    )


@router.get(
    "",
    operation_id="listUserFeedback",
    response_model=SuccessEnvelope[FeedbackListData],
    responses=RESPONSES,
)
async def list_feedback(
    request: Request,
    target_type: Annotated[FeedbackTargetType, Query(alias="targetType")],
    target_id: Annotated[str, Query(alias="targetId", min_length=1, max_length=128)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
) -> JSONResponse:
    records = await service.list(current_user.owner_user_id, target_type, target_id)
    return success_response(
        FeedbackListData(items=[_item(item) for item in records]), get_request_id(request),
        exclude_none=False,
    )


@router.post(
    "",
    operation_id="upsertUserFeedback",
    response_model=SuccessEnvelope[UserFeedback],
    responses=RESPONSES,
)
async def upsert_feedback(
    body: UserFeedbackUpsertRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
) -> JSONResponse:
    record = await service.upsert(
        current_user.owner_user_id,
        body.target_type,
        body.target_id,
        body.subject_id,
        body.rating,
        body.reason,
        body.comment,
        body.correction,
    )
    return success_response(_item(record), get_request_id(request), exclude_none=False)


@router.delete(
    "/{id}",
    operation_id="deleteUserFeedback",
    response_model=SuccessEnvelope[FeedbackDeleteData],
    responses=RESPONSES,
)
async def delete_feedback(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
) -> JSONResponse:
    await service.delete(current_user.owner_user_id, id)
    return success_response(
        FeedbackDeleteData(feedbackId=id), get_request_id(request), exclude_none=False
    )
