from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from super_ai.api_contracts import (
    ChatAssetDeleteData,
    ChatConfigurationData,
    ChatPrompt,
    ChatSkill,
    CreateChatPromptRequest,
    FailureEnvelope,
    SuccessEnvelope,
    UpdateChatConfigurationRequest,
    UpdateChatPromptRequest,
)
from super_ai.api_responses import success_response
from super_ai.chat_configuration.dependencies import get_chat_configuration_service
from super_ai.chat_configuration.models import (
    ChatConfigurationRecord,
    ChatPromptRecord,
    ChatSkillRecord,
)
from super_ai.chat_configuration.service import ChatConfigurationService
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/chat", tags=["chat-configuration"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
    404: {"model": FailureEnvelope},
    422: {"model": FailureEnvelope},
}


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _prompt(record: ChatPromptRecord) -> ChatPrompt:
    return ChatPrompt(
        id=record.id,
        label=record.label,
        content=record.content,
        createdAt=_iso(record.created_at),
        updatedAt=_iso(record.updated_at),
    )


def _skill(record: ChatSkillRecord) -> ChatSkill:
    return ChatSkill(
        id=record.id,
        name=record.name,
        description=record.description,
        filename="SKILL.md",
        content=record.content,
        metadata=record.metadata,
        summary=record.summary,
        createdAt=_iso(record.created_at),
        updatedAt=_iso(record.updated_at),
    )


def _configuration(record: ChatConfigurationRecord) -> ChatConfigurationData:
    return ChatConfigurationData(
        prompts=[_prompt(item) for item in record.prompts],
        skills=[_skill(item) for item in record.skills],
        selectedPromptId=record.selected_prompt_id,
        selectedSkillIds=[item.id for item in record.skills if item.is_selected],
    )


def _configuration_response(
    data: ChatConfigurationData, request: Request, *, status_code: int = 200
) -> JSONResponse:
    return success_response(
        data, get_request_id(request), status_code=status_code, exclude_none=False
    )


@router.get(
    "/configuration",
    operation_id="getChatConfiguration",
    response_model=SuccessEnvelope[ChatConfigurationData],
    responses=RESPONSES,
)
async def get_configuration(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatConfigurationService, Depends(get_chat_configuration_service)],
) -> JSONResponse:
    return _configuration_response(
        _configuration(await service.get(current_user.owner_user_id)), request
    )


@router.put(
    "/configuration",
    operation_id="updateChatConfiguration",
    response_model=SuccessEnvelope[ChatConfigurationData],
    responses=RESPONSES,
)
async def update_configuration(
    body: UpdateChatConfigurationRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatConfigurationService, Depends(get_chat_configuration_service)],
) -> JSONResponse:
    return _configuration_response(
        _configuration(
            await service.update(
                current_user.owner_user_id, body.selected_prompt_id, body.selected_skill_ids
            )
        ),
        request,
    )


@router.post(
    "/prompts",
    status_code=201,
    operation_id="createChatPrompt",
    response_model=SuccessEnvelope[ChatConfigurationData],
    responses=RESPONSES,
)
async def create_prompt(
    body: CreateChatPromptRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatConfigurationService, Depends(get_chat_configuration_service)],
) -> JSONResponse:
    return _configuration_response(
        _configuration(
            await service.create_prompt(current_user.owner_user_id, body.label, body.content)
        ),
        request,
        status_code=201,
    )


@router.put(
    "/prompts/{id}",
    operation_id="updateChatPrompt",
    response_model=SuccessEnvelope[ChatConfigurationData],
    responses=RESPONSES,
)
async def update_prompt(
    id: str,
    body: UpdateChatPromptRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatConfigurationService, Depends(get_chat_configuration_service)],
) -> JSONResponse:
    return _configuration_response(
        _configuration(
            await service.update_prompt(current_user.owner_user_id, id, body.label, body.content)
        ),
        request,
    )


@router.delete(
    "/prompts/{id}",
    operation_id="deleteChatPrompt",
    response_model=SuccessEnvelope[ChatAssetDeleteData],
    responses=RESPONSES,
)
async def delete_prompt(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatConfigurationService, Depends(get_chat_configuration_service)],
) -> JSONResponse:
    await service.delete_prompt(current_user.owner_user_id, id)
    return success_response(ChatAssetDeleteData(assetId=id), get_request_id(request))


@router.post(
    "/skills",
    status_code=201,
    operation_id="uploadChatSkill",
    response_model=SuccessEnvelope[ChatConfigurationData],
    responses={**RESPONSES, 409: {"model": FailureEnvelope}},
)
async def upload_skill(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatConfigurationService, Depends(get_chat_configuration_service)],
    file: Annotated[UploadFile, File()],
) -> JSONResponse:
    payload = await file.read(262145)
    return _configuration_response(
        _configuration(
            await service.upload_skill(current_user.owner_user_id, file.filename or "", payload)
        ),
        request,
        status_code=201,
    )


@router.delete(
    "/skills/{id}",
    operation_id="deleteChatSkill",
    response_model=SuccessEnvelope[ChatAssetDeleteData],
    responses=RESPONSES,
)
async def delete_skill(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChatConfigurationService, Depends(get_chat_configuration_service)],
) -> JSONResponse:
    await service.delete_skill(current_user.owner_user_id, id)
    return success_response(ChatAssetDeleteData(assetId=id), get_request_id(request))
