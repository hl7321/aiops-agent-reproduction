"""证据充分性判据：以真实日志命中为唯一锚点。"""

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


def test_single_log_hit_is_enough() -> None:
    """单条真实日志命中即视为证据充分。

    判据不再要求"≥2 条命中"或"必须有指标"——这些数量与组合要求在当前数据源上
    无法满足，会把一条规则写成永远无法满足。
    """
    result = evaluate_claim_evidence(evidence=(_evidence("hit", "log_hit"),), steps=())

    assert result.trust_state == "verified_evidence"
    assert result.missing_capabilities == ()


def test_no_log_hit_is_insufficient() -> None:
    """没有任何真实日志命中才是证据不足。"""
    result = evaluate_claim_evidence(
        evidence=(_evidence("sop", "knowledge"),), steps=()
    )

    assert result.trust_state == "insufficient_evidence"
    assert result.missing_capabilities == ("log_search",)


def test_required_search_failure_without_hit_is_execution_failed() -> None:
    """必需的日志检索真实失败且没有命中 → 执行失败。"""
    result = evaluate_claim_evidence(evidence=(), steps=(_failed_search("permission"),))

    assert result.trust_state == "execution_failed"
    assert result.missing_capabilities == ("log_search",)


def test_empty_result_is_not_execution_failed() -> None:
    """空结果是"没查到"，不是"执行失败"。"""
    result = evaluate_claim_evidence(evidence=(), steps=(_failed_search("empty_result"),))

    assert result.trust_state == "insufficient_evidence"


def test_temporal_context_is_no_longer_required() -> None:
    """缺少日志上下文产物不再阻止 verified_evidence。

    日志上下文工具在当前数据源已退役（必填的上报包 ID 拿不到），它的顺序信息
    由检索结果自身携带，因此不能再作为时序结论的前提。
    """
    result = evaluate_claim_evidence(
        evidence=(_evidence("hit", "log_hit"), _evidence("metric-x", "query_artifact")),
        steps=(),
    )

    assert result.trust_state == "verified_evidence"


def test_supporting_ids_cover_runtime_evidence_kinds() -> None:
    """支撑证据 ID 仍涵盖三类运行证据，供报告做"必须引用全部支撑证据"的检查。"""
    result = evaluate_claim_evidence(
        evidence=(
            _evidence("hit", "log_hit"),
            _evidence("context", "log_context"),
            _evidence("metric", "metric"),
            _evidence("sop", "knowledge"),
        ),
        steps=(),
    )

    assert result.supporting_evidence_ids == ("hit", "context", "metric")
