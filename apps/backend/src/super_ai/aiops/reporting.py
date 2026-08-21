"""诊断报告结构校验、证据链接与诚实 fallback。"""

from __future__ import annotations

from collections.abc import Sequence

from super_ai.aiops.models import DiagnosticEvidenceRecord, DiagnosticStepRecord
from super_ai.aiops.planning import ReportClaimDraft, ReportDraft
from super_ai.project_config import JsonValue

REPORT_HEADINGS = (
    "# 告警分析报告",
    "## 📋 活跃告警清单",
    "## 📊 结论",
)
ROOT_CAUSE_LABELS = ("详情：", "症状：", "日志证据：", "根因结论：")
SOLUTION_LABELS = ("已执行步骤：", "建议：", "预期效果：")
CONCLUSION_LABELS = (
    "整体评估：",
    "关键发现：",
    "后续建议：",
    "风险评估：",
)


def validate_report(
    draft: ReportDraft,
    evidence: Sequence[DiagnosticEvidenceRecord],
    *,
    alert_count: int,
) -> tuple[str, tuple[ReportClaimDraft, ...], bool]:
    markdown = draft.markdown.strip()
    if not all(heading in markdown for heading in REPORT_HEADINGS):
        raise ValueError("模型报告缺少固定中文结构")
    for index in range(1, alert_count + 1):
        root_heading = f"## 🔍 告警根因分析{index}"
        solution_heading = f"## 🛠️ 处理方案执行{index}"
        if root_heading not in markdown or solution_heading not in markdown:
            raise ValueError("模型报告缺少逐告警编号结构")
        root_start = markdown.index(root_heading)
        solution_start = markdown.index(solution_heading, root_start)
        next_heading = (
            f"## 🔍 告警根因分析{index + 1}"
            if index < alert_count
            else "## 📊 结论"
        )
        solution_end = markdown.index(next_heading, solution_start)
        if not all(label in markdown[root_start:solution_start] for label in ROOT_CAUSE_LABELS):
            raise ValueError("模型报告缺少固定中文字段")
        if not all(label in markdown[solution_start:solution_end] for label in SOLUTION_LABELS):
            raise ValueError("模型报告缺少固定中文字段")
    conclusion = markdown[markdown.index("## 📊 结论") :]
    if not all(label in conclusion for label in CONCLUSION_LABELS):
        raise ValueError("模型报告缺少固定中文字段")
    known = {item.id for item in evidence}
    for claim in draft.claims:
        if any(item not in known for item in claim.evidence_ids):
            raise ValueError("模型报告引用了不存在或越权的证据")
    if any(item.kind != "alert" for item in evidence) and not draft.claims:
        raise ValueError("模型报告关键结论缺少 evidenceIds")
    return markdown, tuple(draft.claims), draft.uncertainty


def build_fallback_report(
    alerts: Sequence[dict[str, JsonValue]],
    evidence: Sequence[DiagnosticEvidenceRecord],
    steps: Sequence[DiagnosticStepRecord] = (),
) -> tuple[str, tuple[str, ...]]:
    alert_lines = [
        f"- {item.get('alertName', '未命名告警')} / {item.get('service', '未知服务')} / "
        f"{item.get('severity', '未知级别')}"
        for item in alerts
    ] or ["- 无可用告警输入"]
    executed_lines = [
        f"  - {item.tool_name}：{item.status}"
        for item in steps
        if item.status in {"succeeded", "failed", "cancelled"}
    ] or ["  - 尚无已完成的工具步骤。"]
    sections: list[str] = ["# 告警分析报告", "", "## 📋 活跃告警清单", *alert_lines]
    for index, alert in enumerate(alerts, start=1):
        related = [item for item in evidence if item.kind != "alert"]
        proof = "\n".join(f"- [{item.id}] {item.summary}" for item in related[:10])
        sections.extend(
            [
                "",
                f"## 🔍 告警根因分析{index}",
                f"- 详情：{alert.get('alertName', '未命名告警')}",
                "- 症状：以活跃告警输入为准。",
                f"- 日志证据：\n{proof}" if proof else "- 日志证据：尚无可用真实证据。",
                "- 根因结论：证据不足，当前无法确定根因。",
                "",
                f"## 🛠️ 处理方案执行{index}",
                "- 已执行步骤：",
                *executed_lines,
                "- 建议：补充真实日志、指标或 SOP 证据后复核。",
                "- 预期效果：待执行并验证，不视为已发生事实。",
            ]
        )
    sections.extend(
        [
            "",
            "## 📊 结论",
            "- 整体评估：证据不足，结论存在不确定性。",
            "- 关键发现：仅能确认上述告警和已持久化证据。",
            "- 后续建议：补充证据并由人工确认处置。",
            "- 风险评估：禁止依据本 fallback 自动执行高风险变更。",
        ]
    )
    ids = tuple(item.id for item in evidence if item.kind != "alert")
    return "\n".join(sections), ids
