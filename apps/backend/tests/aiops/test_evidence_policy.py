from datetime import datetime, timezone

from super_ai.aiops.evidence_policy import evaluate_claim_evidence
from super_ai.aiops.models import DiagnosticEvidenceRecord, DiagnosticStepRecord

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def _evidence(identifier: str, kind: str) -> DiagnosticEvidenceRecord:
    return DiagnosticEvidenceRecord(
        identifier,
        "owner",
        "task",
        "step",
        "call",
        kind,  # type: ignore[arg-type]
        "CLS",
        identifier,
        identifier,
        identifier,
        {"artifactKind": kind},
        NOW,
        NOW,
    )


def _failed_search(category: str) -> DiagnosticStepRecord:
    return DiagnosticStepRecord(
        "step",
        "owner",
        "task",
        1,
        0,
        1,
        "SearchLog",
        {},
        "failed",
        None,
        "safe failure",
        NOW,
        NOW,
        NOW,
        category,  # type: ignore[arg-type]
    )


def test_required_search_runtime_failure_is_execution_failed() -> None:
    result = evaluate_claim_evidence(
        evidence=(),
        steps=(_failed_search("permission"),),
        requires_temporal_context=False,
    )
    assert result.trust_state == "execution_failed"
    assert result.missing_capabilities == ("log_search",)


def test_temporal_claim_requires_real_context_or_strong_independent_evidence() -> None:
    hit = _evidence("hit", "log_hit")
    metric = _evidence("metric", "metric")
    insufficient = evaluate_claim_evidence(
        evidence=(hit, metric), steps=(), requires_temporal_context=True
    )
    assert insufficient.trust_state == "insufficient_evidence"
    assert insufficient.missing_capabilities == ("log_context",)

    verified = evaluate_claim_evidence(
        evidence=(hit, _evidence("context", "log_context")),
        steps=(),
        requires_temporal_context=True,
    )
    assert verified.trust_state == "verified_evidence"


def test_non_temporal_claim_uses_explicit_combination_not_tool_count() -> None:
    verified = evaluate_claim_evidence(
        evidence=(
            _evidence("hit-1", "log_hit"),
            _evidence("hit-2", "log_hit"),
            _evidence("metric", "metric"),
        ),
        steps=(),
        requires_temporal_context=False,
    )
    assert verified.trust_state == "verified_evidence"
    assert verified.supporting_evidence_ids == ("hit-1", "hit-2", "metric")

    knowledge_only = evaluate_claim_evidence(
        evidence=(_evidence("sop", "knowledge"),),
        steps=(),
        requires_temporal_context=False,
    )
    assert knowledge_only.trust_state == "insufficient_evidence"
