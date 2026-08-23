"""不依赖模型自述的 AIOps claim 证据充分性门禁。"""

from __future__ import annotations

from dataclasses import dataclass

from super_ai.aiops.models import (
    DiagnosticEvidenceRecord,
    DiagnosticStepRecord,
    ReportTrustState,
)
from super_ai.aiops.planning import is_search_log_tool


@dataclass(frozen=True, slots=True)
class EvidenceEvaluation:
    trust_state: ReportTrustState
    missing_capabilities: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]


def evaluate_claim_evidence(
    *,
    evidence: tuple[DiagnosticEvidenceRecord, ...],
    steps: tuple[DiagnosticStepRecord, ...],
    requires_temporal_context: bool,
) -> EvidenceEvaluation:
    search_failures = [
        item
        for item in steps
        if is_search_log_tool(item.tool_name)
        and item.status == "failed"
        and item.error_category not in {None, "empty_result"}
    ]
    hits = tuple(item for item in evidence if item.kind == "log_hit")
    contexts = tuple(item for item in evidence if item.kind == "log_context")
    metrics = tuple(item for item in evidence if item.kind == "metric")
    supporting = tuple(item.id for item in (*hits, *contexts, *metrics))
    if search_failures and not hits:
        return EvidenceEvaluation("execution_failed", ("log_search",), supporting)
    if not hits:
        return EvidenceEvaluation("insufficient_evidence", ("log_search",), supporting)

    independent_temporal_support = len(hits) >= 2 and bool(metrics)
    if requires_temporal_context and not contexts and not independent_temporal_support:
        return EvidenceEvaluation("insufficient_evidence", ("log_context",), supporting)

    non_temporal_support = bool(metrics) or len(hits) >= 2
    if not requires_temporal_context and not non_temporal_support:
        return EvidenceEvaluation("insufficient_evidence", ("independent_evidence",), supporting)
    return EvidenceEvaluation("verified_evidence", (), supporting)
