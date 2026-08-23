"""诊断 case 不可变领域 records。"""

from dataclasses import dataclass
from datetime import datetime

from super_ai.project_config import JsonValue


@dataclass(frozen=True, slots=True)
class CaseMaterial:
    alert_name: str
    service: str
    keywords: tuple[str, ...]
    root_cause: str
    remediation: str
    summary: str
    evidence_ids: tuple[str, ...]
    markdown: str
    source_metadata: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class DiagnosisCaseRecord:
    id: str
    owner_user_id: str
    task_id: str
    report_id: str
    document_id: str
    index_task_id: str
    alert_name: str
    service: str
    keywords: tuple[str, ...]
    root_cause: str
    remediation: str
    summary: str
    evidence_ids: tuple[str, ...]
    created_at: datetime
    incident_fingerprint: str | None = None
    knowledge_fingerprint: str | None = None
    fingerprint_version: str | None = None
    promotion_status: str = "legacy"


@dataclass(frozen=True, slots=True)
class DiagnosticCaseSourceRecord:
    id: str
    owner_user_id: str
    case_id: str
    diagnostic_task_id: str
    report_id: str
    approval_feedback_id: str | None
    evidence_ids: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DiagnosisCaseCandidate:
    item: DiagnosisCaseRecord
    similarity_score: float


@dataclass(frozen=True, slots=True)
class DiagnosisCasePromotionResult:
    status: str
    item: DiagnosisCaseRecord | None
    candidates: tuple[DiagnosisCaseCandidate, ...] = ()
