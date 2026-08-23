"""AIOps 诊断 Repository Protocol。"""

from typing import Protocol

from super_ai.aiops.models import (
    DiagnosticEvidenceRecord,
    DiagnosticReportRecord,
    DiagnosticStatus,
    DiagnosticStepRecord,
    DiagnosticStepStatus,
    DiagnosticTaskRecord,
    GraphCheckpointRecord,
    NewEvidence,
    PlanStep,
    ReportEvidenceLinkRecord,
    ReportMode,
    ReportTrustState,
    ToolErrorCategory,
)
from super_ai.project_config import JsonValue


class DiagnosticRepository(Protocol):
    async def create_task(
        self, owner_user_id: str, query: str | None, alerts: list[dict[str, JsonValue]]
    ) -> DiagnosticTaskRecord: ...
    async def list_tasks(self, owner_user_id: str) -> list[DiagnosticTaskRecord]: ...
    async def get_task(self, owner_user_id: str, task_id: str) -> DiagnosticTaskRecord | None: ...
    async def transition_task(
        self,
        owner_user_id: str,
        task_id: str,
        status: DiagnosticStatus,
        *,
        failure_code: str | None = None,
        failure_reason: str | None = None,
    ) -> DiagnosticTaskRecord | None: ...
    async def save_plan(
        self, owner_user_id: str, task_id: str, plan: tuple[PlanStep, ...], *, replan_count: int
    ) -> DiagnosticTaskRecord | None: ...
    async def start_step(
        self, owner_user_id: str, task_id: str, plan_version: int, step: PlanStep, *, attempt: int
    ) -> DiagnosticStepRecord: ...
    async def finish_step(
        self,
        owner_user_id: str,
        step_id: str,
        status: DiagnosticStepStatus,
        *,
        result_summary: str | None = None,
        error_message: str | None = None,
        error_category: ToolErrorCategory | None = None,
    ) -> DiagnosticStepRecord | None: ...
    async def list_steps(self, owner_user_id: str, task_id: str) -> list[DiagnosticStepRecord]: ...
    async def get_step(
        self, owner_user_id: str, step_id: str
    ) -> DiagnosticStepRecord | None: ...
    async def add_evidence(
        self, owner_user_id: str, task_id: str, evidence: NewEvidence
    ) -> DiagnosticEvidenceRecord: ...
    async def list_evidence(
        self, owner_user_id: str, task_id: str
    ) -> list[DiagnosticEvidenceRecord]: ...
    async def save_checkpoint(
        self, owner_user_id: str, task_id: str, node: str, state: dict[str, JsonValue]
    ) -> GraphCheckpointRecord: ...
    async def latest_checkpoint(
        self, owner_user_id: str, task_id: str
    ) -> GraphCheckpointRecord | None: ...
    async def create_report(
        self,
        owner_user_id: str,
        task_id: str,
        markdown: str,
        mode: ReportMode,
        uncertainty: bool,
        trust_state: ReportTrustState = "insufficient_evidence",
    ) -> DiagnosticReportRecord: ...
    async def latest_report(
        self, owner_user_id: str, task_id: str
    ) -> DiagnosticReportRecord | None: ...
    async def get_report(
        self, owner_user_id: str, report_id: str
    ) -> DiagnosticReportRecord | None: ...
    async def link_evidence(
        self,
        owner_user_id: str,
        task_id: str,
        report_id: str,
        evidence_id: str,
        claim_key: str,
        section: str,
        position: int,
    ) -> ReportEvidenceLinkRecord: ...
    async def list_links(
        self, owner_user_id: str, task_id: str
    ) -> list[ReportEvidenceLinkRecord]: ...
