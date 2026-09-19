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
) -> EvidenceEvaluation:
    """以真实日志命中为唯一锚点的证据充分性门禁。

    判据只依赖当前数据源真实能产出的证据，分三档：

    1. 必需的日志检索真实失败（且不是"空结果"）并且没有任何命中 → `execution_failed`；
    2. 一条真实日志命中都没有 → `insufficient_evidence`；
    3. 至少一条真实日志命中 → `verified_evidence`。

    这里不再要求日志上下文产物，也不再要求"多条命中 + 指标"这类组合。那两类证据在当前
    数据源上无法获得（上传链路不产出上报包 ID，账号内没有指标主题），把它们写成必要条件
    只会把一条规则变成永远无法满足——只要模型声明需要时序依据，诊断就必然判证据不足。
    日志的顺序信息由检索结果自身携带。
    """
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
    # supporting_evidence_ids 的用途是"报告必须引用全部支撑证据"，与充分性判据无关，
    # 因此仍然涵盖三类运行证据；当前数据源只会产生 log_hit。
    supporting = tuple(item.id for item in (*hits, *contexts, *metrics))
    if search_failures and not hits:
        return EvidenceEvaluation("execution_failed", ("log_search",), supporting)
    if not hits:
        return EvidenceEvaluation("insufficient_evidence", ("log_search",), supporting)
    return EvidenceEvaluation("verified_evidence", (), supporting)
