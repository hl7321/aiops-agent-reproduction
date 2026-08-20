"""owner-scoped 聊天会话 API。"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from super_ai.agent_audit.models import AgentToolCallAuditRecord
from super_ai.agent_audit.repositories import AgentToolCallAuditRepository
from super_ai.api_contracts import (
    AgentToolCallAudit,
    AgentToolCallAuditListData,
    AppendChatMessageRequest,
    ChatDeleteData,
    ChatMessage,
    ChatMessageMetadata,
    ChatSession,
    ChatSessionDetailData,
    ChatSessionListData,
    ChatStreamMessageRequest,
    FailureEnvelope,
    SuccessEnvelope,
    UpdateChatMemoryRequest,
)
from super_ai.api_responses import success_response
from super_ai.chat.dependencies import (
    get_agent_audit_repository,
    get_agent_chat_stream_service,
    get_chat_memory_service,
    get_chat_service,
    get_stream_current_user,
)
from super_ai.chat.memory.service import ChatMemoryProjection, ChatMemoryService
from super_ai.chat.models import ChatMessageRecord
from super_ai.chat.service import ChatService
from super_ai.chat.stream_service import AgentChatStreamService, PreparedAgentTurn
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


def _success(data: object, request_id: str, *, status_code: int = 200) -> JSONResponse:
    return success_response(data, request_id, status_code=status_code, exclude_none=False)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _session(projection: ChatMemoryProjection) -> ChatSession:
    record = projection.detail.session
    return ChatSession(
        id=record.id, title=record.title,
        memoryMode=record.memory_mode,
        memorySummary=record.memory_summary,
        contextTokens=record.context_tokens,
        contextWindowTokens=projection.context_window_tokens,
        contextUsagePercent=projection.context_usage_percent,
        compactedMessageCount=record.compacted_message_count,
        lastCompactedAt=(
            _iso(record.last_compacted_at) if record.last_compacted_at is not None else None
        ),
        canCompact=projection.can_compact,
        createdAt=_iso(record.created_at), updatedAt=_iso(record.updated_at),
    )


def _message(record: ChatMessageRecord) -> ChatMessage:
    return ChatMessage(
        id=record.id, sessionId=record.session_id, role=record.role, content=record.content,
        sequence=record.sequence, metadata=ChatMessageMetadata.model_validate(record.metadata),
        createdAt=_iso(record.created_at),
    )


def _detail(projection: ChatMemoryProjection) -> ChatSessionDetailData:
    record = projection.detail
    return ChatSessionDetailData(
        session=_session(projection), messages=[_message(item) for item in record.messages]
    )


def _audit(record: AgentToolCallAuditRecord) -> AgentToolCallAudit:
    return AgentToolCallAudit(
        id=record.id,
        toolCallId=record.tool_call_id,
        chatSessionId=record.chat_session_id,
        diagnosticTaskId=record.diagnostic_task_id,
        toolName=record.tool_name,
        arguments=record.arguments,
        status=record.status,
        resultSummary=record.result_summary,
        errorMessage=record.error_message,
        startedAt=_iso(record.started_at),
        completedAt=_iso(record.completed_at) if record.completed_at is not None else None,
        durationMs=record.duration_ms,
    )


@router.post(
    "", operation_id="createChatSession", status_code=201,
    response_model=SuccessEnvelope[ChatSessionDetailData], responses=RESPONSES,
)
async def create_chat_session(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memory: Annotated[ChatMemoryService, Depends(get_chat_memory_service)],
) -> JSONResponse:
    return _success(
        _detail(await memory.create(current_user.owner_user_id)),
        get_request_id(request), status_code=201,
    )


@router.get(
    "", operation_id="listChatSessions",
    response_model=SuccessEnvelope[ChatSessionListData], responses=RESPONSES,
)
async def list_chat_sessions(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memory: Annotated[ChatMemoryService, Depends(get_chat_memory_service)],
) -> JSONResponse:
    return _success(
        ChatSessionListData(
            sessions=[
                _session(item)
                for item in await memory.project_many(current_user.owner_user_id)
            ]
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
    memory: Annotated[ChatMemoryService, Depends(get_chat_memory_service)],
) -> JSONResponse:
    return _success(
        _detail(await memory.project(current_user.owner_user_id, id)), get_request_id(request)
    )


@router.post(
    "/{id}/messages", operation_id="appendChatMessage",
    response_model=SuccessEnvelope[ChatSessionDetailData], responses=APPEND_RESPONSES,
)
async def append_chat_message(
    id: str, body: AppendChatMessageRequest, request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memory: Annotated[ChatMemoryService, Depends(get_chat_memory_service)],
) -> JSONResponse:
    metadata_json = body.metadata.model_dump(mode="json", by_alias=True)
    metadata = cast(
        dict[str, JsonValue],
        {key: value for key, value in metadata_json.items() if value is not None},
    )
    return _success(
        _detail(
            await memory.append(
                current_user.owner_user_id, id, body.role, body.content, metadata
            )
        ),
        get_request_id(request),
    )


@router.post(
    "/{id}/messages:stream",
    operation_id="streamChatMessage",
    response_model=None,
    responses={
        **APPEND_RESPONSES,
        200: {
            "description": "共享 SSE 事件流",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
    },
)
async def stream_chat_message(
    id: str,
    body: ChatStreamMessageRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_stream_current_user)],
    service: Annotated[AgentChatStreamService, Depends(get_agent_chat_stream_service)],
) -> StreamingResponse:
    prepared = await service.prepare(current_user, id, body)
    response = StreamingResponse(
        _encoded_stream(service, prepared),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Request-ID": get_request_id(request),
        },
    )
    return response


async def _encoded_stream(
    service: AgentChatStreamService, prepared: PreparedAgentTurn
) -> AsyncIterator[str]:
    async for event in service.stream(prepared):
        payload = event.model_dump_json(by_alias=True)
        yield f"id: {event.id}\nevent: {event.type}\ndata: {payload}\n\n"


@router.get(
    "/{id}/tool-call-audits",
    operation_id="listAgentToolCallAudits",
    response_model=SuccessEnvelope[AgentToolCallAuditListData],
    responses=RESPONSES,
)
async def list_agent_tool_call_audits(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    repository: Annotated[
        AgentToolCallAuditRepository, Depends(get_agent_audit_repository)
    ],
) -> JSONResponse:
    await chat_service.get(current_user.owner_user_id, id)
    records = await repository.list_for_chat(current_user.owner_user_id, id)
    return _success(
        AgentToolCallAuditListData(items=[_audit(record) for record in records]),
        get_request_id(request),
    )


@router.post(
    "/{id}/messages:clear", operation_id="clearChatMessages",
    response_model=SuccessEnvelope[ChatSessionDetailData], responses=RESPONSES,
)
async def clear_chat_messages(
    id: str, request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memory: Annotated[ChatMemoryService, Depends(get_chat_memory_service)],
) -> JSONResponse:
    return _success(
        _detail(await memory.clear(current_user.owner_user_id, id)), get_request_id(request)
    )


@router.put(
    "/{id}/memory",
    operation_id="updateChatMemory",
    response_model=SuccessEnvelope[ChatSessionDetailData],
    responses={**RESPONSES, 422: {"model": FailureEnvelope}, 500: {"model": FailureEnvelope}},
)
async def update_chat_memory(
    id: str,
    body: UpdateChatMemoryRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memory: Annotated[ChatMemoryService, Depends(get_chat_memory_service)],
) -> JSONResponse:
    projection = await memory.update_mode(
        current_user.owner_user_id, id, body.memory_mode
    )
    return _success(_detail(projection), get_request_id(request))


@router.post(
    "/{id}/memory:compact",
    operation_id="compactChatMemory",
    response_model=SuccessEnvelope[ChatSessionDetailData],
    responses={**RESPONSES, 500: {"model": FailureEnvelope}},
)
async def compact_chat_memory(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memory: Annotated[ChatMemoryService, Depends(get_chat_memory_service)],
) -> JSONResponse:
    return _success(
        _detail(await memory.compact(current_user.owner_user_id, id)), get_request_id(request)
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
    return _success(ChatDeleteData(sessionId=id), get_request_id(request))
