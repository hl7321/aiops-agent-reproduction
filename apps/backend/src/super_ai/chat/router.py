"""owner-scoped 聊天会话 API。"""

from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from super_ai.api_contracts import (
    AppendChatMessageRequest,
    ChatDeleteData,
    ChatMessage,
    ChatMessageMetadata,
    ChatSession,
    ChatSessionDetailData,
    ChatSessionListData,
    FailureEnvelope,
    SuccessEnvelope,
)
from super_ai.api_responses import success_response
from super_ai.chat.dependencies import get_chat_service
from super_ai.chat.models import ChatMessageRecord, ChatSessionDetailRecord, ChatSessionRecord
from super_ai.chat.service import ChatService
from super_ai.project_config import JsonValue
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/chat/sessions", tags=["chat"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
}
APPEND_RESPONSES = {**RESPONSES, 422: {"model": FailureEnvelope}}


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _session(record: ChatSessionRecord) -> ChatSession:
    return ChatSession(
        id=record.id, title=record.title,
        createdAt=_iso(record.created_at), updatedAt=_iso(record.updated_at),
    )


def _message(record: ChatMessageRecord) -> ChatMessage:
    return ChatMessage(
        id=record.id, sessionId=record.session_id, role=record.role, content=record.content,
        sequence=record.sequence, metadata=ChatMessageMetadata.model_validate(record.metadata),
        createdAt=_iso(record.created_at),
    )


def _detail(record: ChatSessionDetailRecord) -> ChatSessionDetailData:
    return ChatSessionDetailData(
        session=_session(record.session), messages=[_message(item) for item in record.messages]
    )


@router.post(
    "", operation_id="createChatSession", status_code=201,
    response_model=SuccessEnvelope[ChatSessionDetailData], responses=RESPONSES,
)
async def create_chat_session(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    return success_response(
        _detail(await service.create(current_user.owner_user_id)),
        get_request_id(request), status_code=201,
    )


@router.get(
    "", operation_id="listChatSessions",
    response_model=SuccessEnvelope[ChatSessionListData], responses=RESPONSES,
)
async def list_chat_sessions(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    return success_response(
        ChatSessionListData(
            sessions=[_session(item) for item in await service.list(current_user.owner_user_id)]
        ),
        get_request_id(request),
    )


@router.get(
    "/{id}", operation_id="getChatSession",
    response_model=SuccessEnvelope[ChatSessionDetailData], responses=RESPONSES,
)
async def get_chat_session(
    id: str, request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    return success_response(
        _detail(await service.get(current_user.owner_user_id, id)), get_request_id(request)
    )


@router.post(
    "/{id}/messages", operation_id="appendChatMessage",
    response_model=SuccessEnvelope[ChatSessionDetailData], responses=APPEND_RESPONSES,
)
async def append_chat_message(
    id: str, body: AppendChatMessageRequest, request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    metadata = cast(
        dict[str, JsonValue],
        body.metadata.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return success_response(
        _detail(
            await service.append(
                current_user.owner_user_id, id, body.role, body.content, metadata
            )
        ),
        get_request_id(request),
    )


@router.post(
    "/{id}/messages:clear", operation_id="clearChatMessages",
    response_model=SuccessEnvelope[ChatSessionDetailData], responses=RESPONSES,
)
async def clear_chat_messages(
    id: str, request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    return success_response(
        _detail(await service.clear(current_user.owner_user_id, id)), get_request_id(request)
    )


@router.delete(
    "/{id}", operation_id="deleteChatSession",
    response_model=SuccessEnvelope[ChatDeleteData], responses=RESPONSES,
)
async def delete_chat_session(
    id: str, request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    await service.delete(current_user.owner_user_id, id)
    return success_response(ChatDeleteData(sessionId=id), get_request_id(request))
