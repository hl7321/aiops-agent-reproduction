"""诊断 case 查询与 legacy 手动保存 API。"""

from datetime import datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from super_ai.aiops.cases.models import DiagnosisCaseRecord
from super_ai.aiops.cases.service import DiagnosisCasePersistor, LegacyDiagnosisKnowledgeSaver
from super_ai.api_contracts import (
    ChunkingConfigModel,
    DiagnosticCase,
    DiagnosticCaseDetailData,
    DiagnosticCaseListData,
    DocumentIndexTaskModel,
    FailureEnvelope,
    KnowledgeDocumentModel,
    SaveDiagnosisToKnowledgeData,
    SuccessEnvelope,
)
from super_ai.api_responses import success_response
from super_ai.document_indexing.models import DocumentIndexTaskRecord
from super_ai.knowledge.models import KnowledgeDocumentRecord
from super_ai.memory.sqlite import PersistenceRuntime
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/aiops", tags=["aiops-diagnostic-cases"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
    404: {"model": FailureEnvelope},
    409: {"model": FailureEnvelope},
}
SAVE_RESPONSES = {**RESPONSES, 422: {"model": FailureEnvelope}}


def _runtime(request: Request) -> PersistenceRuntime:
    runtime = getattr(request.app.state, "persistence_runtime", None)
    if not isinstance(runtime, PersistenceRuntime):
        raise RuntimeError("持久化 runtime 尚未初始化")
    return runtime


@router.get(
    "/diagnostic-cases",
    operation_id="listAiopsDiagnosticCases",
    response_model=SuccessEnvelope[DiagnosticCaseListData],
    responses=RESPONSES,
)
async def list_cases(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    records = await DiagnosisCasePersistor(_runtime(request).session_factory).list(
        current_user.owner_user_id
    )
    return success_response(
        DiagnosticCaseListData(items=[_case(item) for item in records]), get_request_id(request)
    )


@router.get(
    "/diagnostic-cases/{id}",
    operation_id="getAiopsDiagnosticCase",
    response_model=SuccessEnvelope[DiagnosticCaseDetailData],
    responses=RESPONSES,
)
async def get_case(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    record = await DiagnosisCasePersistor(_runtime(request).session_factory).get(
        current_user.owner_user_id, id
    )
    return success_response(
        DiagnosticCaseDetailData(item=_case(record)), get_request_id(request)
    )


@router.post(
    "/diagnostics/{id}:save-to-knowledge",
    operation_id="saveAiopsDiagnosticToKnowledge",
    response_model=SuccessEnvelope[SaveDiagnosisToKnowledgeData],
    responses=SAVE_RESPONSES,
    status_code=201,
)
async def save_to_knowledge(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    saved = await LegacyDiagnosisKnowledgeSaver(_runtime(request).session_factory).save(
        current_user.owner_user_id, id
    )
    return success_response(
        SaveDiagnosisToKnowledgeData(
            document=_document(saved.document), indexTask=_index_task(saved.index_task)
        ),
        get_request_id(request),
        status_code=201,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _case(record: DiagnosisCaseRecord) -> DiagnosticCase:
    return DiagnosticCase(
        id=record.id,
        ownerUserId=record.owner_user_id,
        taskId=record.task_id,
        reportId=record.report_id,
        documentId=record.document_id,
        indexTaskId=record.index_task_id,
        alertName=record.alert_name,
        service=record.service,
        keywords=list(record.keywords),
        rootCause=record.root_cause,
        remediation=record.remediation,
        summary=record.summary,
        evidenceIds=list(record.evidence_ids),
        createdAt=_iso(record.created_at) or "",
    )


def _document(record: KnowledgeDocumentRecord) -> KnowledgeDocumentModel:
    return KnowledgeDocumentModel(
        id=record.id,
        knowledgeBaseId=record.knowledge_base_id,
        filename=record.filename,
        sizeBytes=record.size_bytes,
        mimeType=cast(Literal["text/markdown", "application/pdf"], record.mime_type),
        sha256=record.sha256,
        uploadedAt=_iso(record.uploaded_at) or "",
        indexStatus=record.index_status,
        chunkingConfig=ChunkingConfigModel(
            strategy=record.chunking_config.strategy,
            maxCharacters=record.chunking_config.max_characters,
            overlap=record.chunking_config.overlap,
        ),
    )


def _index_task(record: DocumentIndexTaskRecord) -> DocumentIndexTaskModel:
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
