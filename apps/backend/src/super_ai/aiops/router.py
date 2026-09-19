"""owner-scoped AIOps 诊断 JSON API 与持久 SSE 回放。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import JsonValue

from super_ai.agent_audit.models import AgentToolCallAuditRecord
from super_ai.aiops.dependencies import get_diagnostic_service
from super_ai.aiops.models import (
    DiagnosticEvidenceRecord,
    DiagnosticReportRecord,
    DiagnosticStepRecord,
    DiagnosticTaskRecord,
    ReportEvidenceLinkRecord,
)
from super_ai.aiops.service import DiagnosticEvidenceChain, DiagnosticService
from super_ai.api_contracts import (
    SSE_COMPLETE_TYPE,
    SSE_ERROR_TYPE,
    SSE_FINISH_REASON_ERROR,
    SSE_REFERENCE_SOURCE_TYPE,
    SSE_REPORT_TYPE,
    SSE_TASK_STATUS_TYPE,
    SSE_TOOL_CALL_TYPE,
    ActiveAlert,
    AgentToolCallAudit,
    BackgroundJob,
    CreateDiagnosticRequest,
    DiagnosticCreateData,
    DiagnosticDetailData,
    DiagnosticEvidence,
    DiagnosticEvidenceChainData,
    DiagnosticExecutionResult,
    DiagnosticListData,
    DiagnosticPlanStep,
    DiagnosticReport,
    DiagnosticStep,
    DiagnosticStreamRequest,
    DiagnosticTask,
    FailureEnvelope,
    ReportEvidenceLink,
    SuccessEnvelope,
)
from super_ai.api_responses import success_response
from super_ai.background_jobs.models import BackgroundJobEventRecord, BackgroundJobRecord
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope
from super_ai.request_id import get_request_id
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.dependencies import get_current_user

router = APIRouter(prefix="/aiops/diagnostics", tags=["aiops-diagnostics"])
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": FailureEnvelope},
    403: {"model": FailureEnvelope},
    404: {"model": FailureEnvelope},
    503: {"model": FailureEnvelope},
}


@router.post(
    "",
    operation_id="createAiopsDiagnostic",
    response_model=SuccessEnvelope[DiagnosticCreateData],
    responses=RESPONSES,
    status_code=202,
)
async def create_diagnostic(
    body: CreateDiagnosticRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DiagnosticService, Depends(get_diagnostic_service)],
) -> JSONResponse:
    raw_alerts = [
        cast(dict[str, JsonValue], item.model_dump(mode="json", by_alias=True))
        for item in body.alerts
    ]
    task, job = await service.create(current_user.owner_user_id, body.query, raw_alerts)
    return success_response(
        DiagnosticCreateData(task=_task(task), backgroundJob=_job(job)),
        get_request_id(request),
        status_code=202,
        exclude_none=False,
    )


@router.get(
    "",
    operation_id="listAiopsDiagnostics",
    response_model=SuccessEnvelope[DiagnosticListData],
    responses=RESPONSES,
)
async def list_diagnostics(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DiagnosticService, Depends(get_diagnostic_service)],
) -> JSONResponse:
    items = await service.list(current_user.owner_user_id)
    return success_response(
        DiagnosticListData(items=[_task(item) for item in items]), get_request_id(request)
    )


@router.get(
    "/{id}",
    operation_id="getAiopsDiagnostic",
    response_model=SuccessEnvelope[DiagnosticDetailData],
    responses=RESPONSES,
)
async def get_diagnostic(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DiagnosticService, Depends(get_diagnostic_service)],
) -> JSONResponse:
    detail = await service.detail(current_user.owner_user_id, id)
    return success_response(
        DiagnosticDetailData(
            task=_task(detail.task),
            backgroundJob=_job(detail.job),
            steps=[_step(item) for item in detail.steps],
            report=_report(detail.report) if detail.report else None,
        ),
        get_request_id(request),
        exclude_none=False,
    )


@router.get(
    "/{id}/evidence-chain",
    operation_id="getAiopsDiagnosticEvidenceChain",
    response_model=SuccessEnvelope[DiagnosticEvidenceChainData],
    responses=RESPONSES,
)
async def get_evidence_chain(
    id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DiagnosticService, Depends(get_diagnostic_service)],
) -> JSONResponse:
    chain = await service.evidence_chain(current_user.owner_user_id, id)
    return success_response(_chain(chain), get_request_id(request), exclude_none=False)


@router.post(
    "/{id}:stream",
    operation_id="streamAiopsDiagnostic",
    response_model=None,
    responses={
        **RESPONSES,
        200: {
            "description": "从持久 background job events 回放并轮询的共享 SSE",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
    },
)
async def stream_diagnostic(
    id: str,
    body: DiagnosticStreamRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DiagnosticService, Depends(get_diagnostic_service)],
) -> StreamingResponse:
    detail = await service.detail(current_user.owner_user_id, id)
    runtime = getattr(request.app.state, "persistence_runtime", None)
    if not isinstance(runtime, PersistenceRuntime):
        raise RuntimeError("持久化 runtime 尚未初始化")
    return StreamingResponse(
        _stream_events(
            runtime,
            current_user.owner_user_id,
            detail.job.id,
            id,
            body.after_sequence,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Request-ID": get_request_id(request)},
    )


async def _stream_events(
    runtime: PersistenceRuntime,
    owner_user_id: str,
    job_id: str,
    task_id: str,
    after_sequence: int,
) -> AsyncIterator[str]:
    cursor = after_sequence
    complete_sent = False
    while not complete_sent:
        async with transaction_scope(runtime.session_factory) as session:
            store = SqliteBackgroundJobStore(session)
            events = await store.list_events(owner_user_id, job_id, after_sequence=cursor)
            job = await store.get(owner_user_id, job_id)
        if events is None or job is None:
            return
        for event in events:
            cursor = event.sequence
            for payload in map_job_event_to_sse(event, task_id):
                if payload["type"] == SSE_COMPLETE_TYPE:
                    complete_sent = True
                yield _encode_sse(payload)
        if complete_sent:
            return
        if job.status in {"succeeded", "failed", "cancelled"} and not events:
            return
        await asyncio.sleep(0.2)


def map_job_event_to_sse(
    event: BackgroundJobEventRecord, task_id: str
) -> tuple[dict[str, object], ...]:
    base = {
        "id": f"{event.job_id}:{event.sequence}",
        "sequence": event.sequence,
        "channel": "aiops",
        "timestamp": _timestamp(event.created_at) or "",
    }
    if event.type == "progress" and isinstance(event.data, dict):
        event_type = event.data.get("eventType")
        data = event.data.get("data")
        if (
            isinstance(event_type, str)
            and event_type
            in {
                SSE_TASK_STATUS_TYPE,
                SSE_TOOL_CALL_TYPE,
                SSE_REFERENCE_SOURCE_TYPE,
                SSE_REPORT_TYPE,
                SSE_ERROR_TYPE,
            }
            and isinstance(data, dict)
        ):
            return ({**base, "type": event_type, "data": data},)
        return ()
    if event.type in {"queued", "running"}:
        return (
            {
                **base,
                "type": SSE_TASK_STATUS_TYPE,
                "data": {"taskId": task_id, "status": event.type},
            },
        )
    if event.type == "succeeded":
        return ({**base, "type": SSE_COMPLETE_TYPE, "data": {"finishReason": "stop"}},)
    if event.type == "cancelled":
        return ({**base, "type": SSE_COMPLETE_TYPE, "data": {"finishReason": "cancelled"}},)
    complete_payload: dict[str, object] = {
        **base,
        "type": SSE_COMPLETE_TYPE,
        "data": {"finishReason": SSE_FINISH_REASON_ERROR},
    }
    return (complete_payload,)


def _encode_sse(payload: dict[str, object]) -> str:
    return (
        f"id: {payload['id']}\n"
        f"event: {payload['type']}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _task(record: DiagnosticTaskRecord) -> DiagnosticTask:
    return DiagnosticTask(
        id=record.id,
        ownerUserId=record.owner_user_id,
        status=record.status,
        query=record.query,
        alerts=[ActiveAlert.model_validate(item) for item in record.alerts],
        currentPlan=[
            DiagnosticPlanStep(
                position=item.position,
                toolName=item.tool_name,
                purpose=item.purpose,
                arguments=item.arguments,
            )
            for item in record.current_plan
        ],
        planVersion=record.plan_version,
        replanCount=record.replan_count,
        failureCode=record.failure_code,
        failureReason=record.failure_reason,
        createdAt=_timestamp(record.created_at) or "",
        updatedAt=_timestamp(record.updated_at) or "",
        startedAt=_timestamp(record.started_at),
        completedAt=_timestamp(record.completed_at),
    )


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


def _step(record: DiagnosticStepRecord) -> DiagnosticStep:
    return DiagnosticStep(
        id=record.id,
        diagnosticTaskId=record.diagnostic_task_id,
        planVersion=record.plan_version,
        position=record.position,
        attempt=record.attempt,
        toolName=record.tool_name,
        arguments=record.arguments,
        status=record.status,
        resultSummary=record.result_summary,
        errorMessage=record.error_message,
        errorCategory=record.error_category,
        startedAt=_timestamp(record.started_at),
        completedAt=_timestamp(record.completed_at),
        createdAt=_timestamp(record.created_at) or "",
    )


def _evidence(record: DiagnosticEvidenceRecord) -> DiagnosticEvidence:
    return DiagnosticEvidence(
        id=record.id,
        diagnosticTaskId=record.diagnostic_task_id,
        diagnosticStepId=record.diagnostic_step_id,
        toolCallId=record.tool_call_id,
        kind=record.kind,
        source=record.source,
        title=record.title,
        summary=record.summary,
        content=record.content,
        metadata=record.metadata,
        observedAt=_timestamp(record.observed_at),
        createdAt=_timestamp(record.created_at) or "",
    )


def _report(record: DiagnosticReportRecord) -> DiagnosticReport:
    return DiagnosticReport(
        id=record.id,
        diagnosticTaskId=record.diagnostic_task_id,
        revision=record.revision,
        markdown=record.markdown,
        generationMode=record.generation_mode,
        uncertainty=record.uncertainty,
        trustState=record.trust_state,
        createdAt=_timestamp(record.created_at) or "",
    )


def _link(record: ReportEvidenceLinkRecord) -> ReportEvidenceLink:
    return ReportEvidenceLink(
        id=record.id,
        diagnosticTaskId=record.diagnostic_task_id,
        reportId=record.report_id,
        evidenceId=record.evidence_id,
        claimKey=record.claim_key,
        section=record.section,
        position=record.position,
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
        startedAt=_timestamp(record.started_at) or "",
        completedAt=_timestamp(record.completed_at),
        durationMs=record.duration_ms,
    )


def _chain(chain: DiagnosticEvidenceChain) -> DiagnosticEvidenceChainData:
    return DiagnosticEvidenceChainData(
        taskId=chain.task.id,
        evidence=[_evidence(item) for item in chain.evidence],
        reportEvidenceLinks=[_link(item) for item in chain.links],
        toolAudits=[_audit(item) for item in chain.audits],
        executionResult=(
            None
            if chain.execution_result is None
            else DiagnosticExecutionResult.model_validate(chain.execution_result)
        ),
    )
