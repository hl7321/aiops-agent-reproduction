"""默认知识库与文档管理 API。"""

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import JsonValue, ValidationError

from super_ai.api_contracts import (
    ChunkingConfigModel,
    ChunkPreviewData,
    ChunkPreviewItemModel,
    FailureEnvelope,
    KnowledgeBaseListData,
    KnowledgeBaseModel,
    KnowledgeDocumentListData,
    KnowledgeDocumentModel,
    SuccessEnvelope,
)
from super_ai.api_responses import AppError, success_response
from super_ai.knowledge.chunking import ChunkingConfig
from super_ai.knowledge.dependencies import get_knowledge_service
from super_ai.knowledge.files import MAX_UPLOAD_BYTES, UploadPolicyError, validate_and_extract
from super_ai.knowledge.models import KnowledgeDocumentRecord
from super_ai.knowledge.service import KnowledgeDocumentService, default_knowledge_base_id
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
    404: {"model": FailureEnvelope},
}
UPLOAD_RESPONSES = {**RESPONSES, 409: {"model": FailureEnvelope}, 422: {"model": FailureEnvelope}}


def _iso(value: object) -> str:
    return value.isoformat().replace("+00:00", "Z")  # type: ignore[union-attr]


def _config(config: ChunkingConfig) -> ChunkingConfigModel:
    return ChunkingConfigModel(
        strategy=config.strategy, maxCharacters=config.max_characters, overlap=config.overlap
    )


def _document(record: KnowledgeDocumentRecord) -> KnowledgeDocumentModel:
    return KnowledgeDocumentModel(
        id=record.id,
        knowledgeBaseId=record.knowledge_base_id,
        filename=record.filename,
        sizeBytes=record.size_bytes,
        mimeType=cast(Literal["text/markdown", "application/pdf"], record.mime_type),
        sha256=record.sha256,
        uploadedAt=_iso(record.uploaded_at),
        indexStatus="not-indexed",
        chunkingConfig=_config(record.chunking_config),
    )


@router.get(
    "",
    operation_id="listKnowledgeBases",
    response_model=SuccessEnvelope[KnowledgeBaseListData],
    responses=RESPONSES,
)
async def list_knowledge_bases(
    request: Request, current_user: Annotated[CurrentUser, Depends(get_current_user)]
) -> JSONResponse:
    return success_response(
        KnowledgeBaseListData(
            items=[KnowledgeBaseModel(id=default_knowledge_base_id(current_user.owner_user_id))]
        ),
        get_request_id(request),
    )


@router.get(
    "/{kb}/documents",
    operation_id="listKnowledgeDocuments",
    response_model=SuccessEnvelope[KnowledgeDocumentListData],
    responses=RESPONSES,
)
async def list_documents(
    kb: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeDocumentService, Depends(get_knowledge_service)],
) -> JSONResponse:
    return success_response(
        KnowledgeDocumentListData(
            items=[_document(item) for item in await service.list(current_user.owner_user_id, kb)]
        ),
        get_request_id(request),
    )


@router.post(
    "/{kb}/documents",
    operation_id="uploadKnowledgeDocument",
    response_model=SuccessEnvelope[KnowledgeDocumentModel],
    responses=UPLOAD_RESPONSES,
    status_code=201,
)
async def upload_document(
    kb: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeDocumentService, Depends(get_knowledge_service)],
    file: Annotated[UploadFile, File()],
    chunking_config: Annotated[str | None, Form(alias="chunkingConfig")] = None,
    overwrite: Annotated[bool, Form()] = False,
) -> JSONResponse:
    service.ensure_knowledge_base(current_user.owner_user_id, kb)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        extracted = validate_and_extract(file.filename or "", file.content_type or "", content)
        config = (
            ChunkingConfig()
            if chunking_config is None
            else ChunkingConfig.model_validate_json(chunking_config)
        )
    except UploadPolicyError as error:
        raise AppError(
            "VALIDATION_REQUEST_INVALID",
            details={"fields": [{"path": "body.file", "message": str(error)}]},
        ) from error
    except ValidationError as error:
        fields: list[JsonValue] = [
            {
                "path": "body.chunkingConfig." + ".".join(str(part) for part in issue["loc"]),
                "message": str(issue["msg"]),
            }
            for issue in error.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise AppError("VALIDATION_REQUEST_INVALID", details={"fields": fields}) from error
    record = await service.upload(
        current_user.owner_user_id, kb, extracted, config, overwrite=overwrite
    )
    return success_response(_document(record), get_request_id(request), status_code=201)


@router.get(
    "/{kb}/documents/{document}",
    operation_id="getKnowledgeDocument",
    response_model=SuccessEnvelope[KnowledgeDocumentModel],
    responses=RESPONSES,
)
async def get_document(
    kb: str,
    document: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeDocumentService, Depends(get_knowledge_service)],
) -> JSONResponse:
    return success_response(
        _document(await service.get(current_user.owner_user_id, kb, document)),
        get_request_id(request),
    )


@router.delete(
    "/{kb}/documents/{document}",
    operation_id="deleteKnowledgeDocument",
    response_model=SuccessEnvelope[KnowledgeDocumentModel],
    responses=RESPONSES,
)
async def delete_document(
    kb: str,
    document: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeDocumentService, Depends(get_knowledge_service)],
) -> JSONResponse:
    return success_response(
        _document(await service.delete(current_user.owner_user_id, kb, document)),
        get_request_id(request),
    )


@router.get(
    "/{kb}/documents/{document}/chunk-preview",
    operation_id="previewKnowledgeDocumentChunks",
    response_model=SuccessEnvelope[ChunkPreviewData],
    responses=RESPONSES,
)
async def preview_document(
    kb: str,
    document: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeDocumentService, Depends(get_knowledge_service)],
) -> JSONResponse:
    preview = await service.preview(current_user.owner_user_id, kb, document)
    data = ChunkPreviewData(
        totalChunks=preview.total_chunks,
        items=[
            ChunkPreviewItemModel(index=item.index, excerpt=item.excerpt, metadata=item.metadata)
            for item in preview.items
        ],
    )
    return success_response(data, get_request_id(request))
