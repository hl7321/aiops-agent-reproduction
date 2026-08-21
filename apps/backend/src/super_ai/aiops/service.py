"""AIOps 诊断创建、查询和证据链用例。"""

from __future__ import annotations

from dataclasses import dataclass

from super_ai.agent_audit.models import AgentToolCallAuditRecord
from super_ai.agent_audit.repositories import AgentToolCallAuditRepository
from super_ai.aiops.evidence import alert_evidence, sanitize_alert_snapshot
from super_ai.aiops.models import (
    DiagnosticEvidenceRecord,
    DiagnosticReportRecord,
    DiagnosticStepRecord,
    DiagnosticTaskRecord,
    ReportEvidenceLinkRecord,
)
from super_ai.aiops.repositories import DiagnosticRepository
from super_ai.api_responses import AppError
from super_ai.background_jobs.models import BackgroundJobRecord, NewBackgroundJob
from super_ai.background_jobs.repositories import BackgroundJobRepository
from super_ai.project_config import JsonValue


@dataclass(frozen=True, slots=True)
class DiagnosticDetail:
    task: DiagnosticTaskRecord
    job: BackgroundJobRecord
    steps: tuple[DiagnosticStepRecord, ...]
    report: DiagnosticReportRecord | None


@dataclass(frozen=True, slots=True)
class DiagnosticEvidenceChain:
    task: DiagnosticTaskRecord
    evidence: tuple[DiagnosticEvidenceRecord, ...]
    links: tuple[ReportEvidenceLinkRecord, ...]
    audits: tuple[AgentToolCallAuditRecord, ...]


class DiagnosticService:
    def __init__(
        self,
        diagnostics: DiagnosticRepository,
        jobs: BackgroundJobRepository,
        audits: AgentToolCallAuditRepository,
    ) -> None:
        self._diagnostics = diagnostics
        self._jobs = jobs
        self._audits = audits

    async def create(
        self,
        owner_user_id: str,
        query: str | None,
        alerts: list[dict[str, JsonValue]],
    ) -> tuple[DiagnosticTaskRecord, BackgroundJobRecord]:
        safe_alerts = [sanitize_alert_snapshot(alert) for alert in alerts]
        task = await self._diagnostics.create_task(owner_user_id, query, safe_alerts)
        for alert in safe_alerts:
            await self._diagnostics.add_evidence(owner_user_id, task.id, alert_evidence(alert))
        job = await self._jobs.enqueue(
            owner_user_id,
            NewBackgroundJob(
                kind="aiops_diagnosis",
                payload={"taskId": task.id},
                resource_type="diagnostic_task",
                resource_id=task.id,
                max_attempts=3,
                timeout_seconds=600,
            ),
        )
        return task, job

    async def list(self, owner_user_id: str) -> list[DiagnosticTaskRecord]:
        return await self._diagnostics.list_tasks(owner_user_id)

    async def detail(self, owner_user_id: str, task_id: str) -> DiagnosticDetail:
        task = await self._required_task(owner_user_id, task_id)
        job = await self._jobs.get_by_resource(owner_user_id, "diagnostic_task", task_id)
        if job is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return DiagnosticDetail(
            task,
            job,
            tuple(await self._diagnostics.list_steps(owner_user_id, task_id)),
            await self._diagnostics.latest_report(owner_user_id, task_id),
        )

    async def evidence_chain(self, owner_user_id: str, task_id: str) -> DiagnosticEvidenceChain:
        task = await self._required_task(owner_user_id, task_id)
        return DiagnosticEvidenceChain(
            task,
            tuple(await self._diagnostics.list_evidence(owner_user_id, task_id)),
            tuple(await self._diagnostics.list_links(owner_user_id, task_id)),
            tuple(await self._audits.list_for_diagnostic(owner_user_id, task_id)),
        )

    async def _required_task(self, owner_user_id: str, task_id: str) -> DiagnosticTaskRecord:
        task = await self._diagnostics.get_task(owner_user_id, task_id)
        if task is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return task
