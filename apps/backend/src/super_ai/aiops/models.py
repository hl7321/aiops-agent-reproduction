"""AIOps 诊断不可变领域 records。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

from super_ai.project_config import JsonValue

DiagnosticStatus: TypeAlias = Literal["accepted", "running", "succeeded", "failed", "cancelled"]
DiagnosticStepStatus: TypeAlias = Literal["pending", "running", "succeeded", "failed", "cancelled"]
EvidenceKind: TypeAlias = Literal["alert", "knowledge", "log", "metric"]
ReportMode: TypeAlias = Literal["model", "fallback"]


@dataclass(frozen=True, slots=True)
class PlanStep:
    position: int
    tool_name: str
    purpose: str
    arguments: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class DiagnosticTaskRecord:
    id: str
    owner_user_id: str
    status: DiagnosticStatus
    query: str | None
    alerts: tuple[dict[str, JsonValue], ...]
    current_plan: tuple[PlanStep, ...]
    plan_version: int
    replan_count: int
    failure_code: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class DiagnosticStepRecord:
    id: str
    owner_user_id: str
    diagnostic_task_id: str
    plan_version: int
    position: int
    attempt: int
    tool_name: str
    arguments: dict[str, JsonValue]
    status: DiagnosticStepStatus
    result_summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DiagnosticEvidenceRecord:
    id: str
    owner_user_id: str
    diagnostic_task_id: str
    diagnostic_step_id: str | None
    tool_call_id: str | None
    kind: EvidenceKind
    source: str
    title: str
    summary: str
    content: str
    metadata: dict[str, JsonValue]
    observed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewEvidence:
    kind: EvidenceKind
    source: str
    title: str
    summary: str
    content: str
    metadata: dict[str, JsonValue]
    diagnostic_step_id: str | None = None
    tool_call_id: str | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticReportRecord:
    id: str
    owner_user_id: str
    diagnostic_task_id: str
    revision: int
    markdown: str
    generation_mode: ReportMode
    uncertainty: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReportEvidenceLinkRecord:
    id: str
    owner_user_id: str
    diagnostic_task_id: str
    report_id: str
    evidence_id: str
    claim_key: str
    section: str
    position: int


@dataclass(frozen=True, slots=True)
class GraphCheckpointRecord:
    id: str
    owner_user_id: str
    diagnostic_task_id: str
    checkpoint_version: int
    node: str
    state: dict[str, JsonValue]
    created_at: datetime
