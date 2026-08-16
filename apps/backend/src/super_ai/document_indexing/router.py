from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from super_ai.api_contracts import DocumentIndexTaskModel, FailureEnvelope, SuccessEnvelope
from super_ai.api_responses import success_response
from super_ai.document_indexing.dependencies import get_document_index_task_service
from super_ai.document_indexing.models import DocumentIndexTaskRecord
from super_ai.document_indexing.service import DocumentIndexTaskService
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/knowledge-bases", tags=["document-indexing"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
    404: {"model": FailureEnvelope},
    409: {"model": FailureEnvelope},
}


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def _task(record: DocumentIndexTaskRecord) -> DocumentIndexTaskModel:
    return DocumentIndexTaskModel(
        id=record.id,
        knowledgeBaseId=record.knowledge_base_id,
        documentId=record.document_id,
        status=record.status,
        failureReason=record.failure_reason,
        retryOfTaskId=record.retry_of_task_id,
        createdAt=_iso(record.created_at) or "",
        updatedAt=_iso(record.updated_at) or "",
        startedAt=_iso(record.started_at),
        completedAt=_iso(record.completed_at),
    )


@router.post(
    "/{kb}/documents/{document}/index-tasks",
    operation_id="createDocumentIndexTask",
    response_model=SuccessEnvelope[DocumentIndexTaskModel],
    responses=RESPONSES,
    status_code=201,
)
async def create_task(
    kb: str,
    document: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DocumentIndexTaskService, Depends(get_document_index_task_service)],
) -> JSONResponse:
    record = await service.create(current_user.owner_user_id, kb, document)
    return success_response(_task(record), get_request_id(request), status_code=201)


@router.get(
    "/{kb}/documents/{document}/index-tasks/{task}",
    operation_id="getDocumentIndexTask",
    response_model=SuccessEnvelope[DocumentIndexTaskModel],
    responses=RESPONSES,
)
async def get_task(
    kb: str,
    document: str,
    task: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DocumentIndexTaskService, Depends(get_document_index_task_service)],
) -> JSONResponse:
    return success_response(
        _task(await service.get(current_user.owner_user_id, kb, document, task)),
        get_request_id(request),
    )


@router.post(
    "/{kb}/documents/{document}/index-tasks/{task}:retry",
    operation_id="retryDocumentIndexTask",
    response_model=SuccessEnvelope[DocumentIndexTaskModel],
    responses=RESPONSES,
    status_code=201,
)
async def retry_task(
    kb: str,
    document: str,
    task: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DocumentIndexTaskService, Depends(get_document_index_task_service)],
) -> JSONResponse:
    record = await service.retry(current_user.owner_user_id, kb, document, task)
    return success_response(_task(record), get_request_id(request), status_code=201)
