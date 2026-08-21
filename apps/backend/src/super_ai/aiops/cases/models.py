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
