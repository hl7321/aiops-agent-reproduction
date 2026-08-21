"""只从真实报告与告警快照构造可追溯 case 文档。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from super_ai.aiops.cases.models import CaseMaterial
from super_ai.project_config import JsonValue

_FIELD_LIMIT = 1000
_SUMMARY_LIMIT = 2000


def build_case_material(
    *,
    task_id: str,
    report_id: str,
    report_markdown: str,
    alerts: Sequence[Mapping[str, JsonValue]],
    evidence_ids: Sequence[str],
) -> CaseMaterial:
    """确定性提取；找不到的结论明确标为证据不足。"""
    first: Mapping[str, JsonValue] = alerts[0] if alerts else {}
    alert_name = _text(first.get("alertName")) or "未提供告警名称"
    service = _text(first.get("service")) or "未提供服务名称"
    root_cause = _label_value(report_markdown, "根因结论") or "证据不足，尚无法确认根因"
    remediation = _label_value(report_markdown, "建议") or "证据不足，暂无可确认的处置建议"
    summary = _label_value(report_markdown, "整体评估") or _plain_summary(report_markdown)
    keywords = tuple(dict.fromkeys(value for value in (alert_name, service) if value))[:20]
    ids = tuple(dict.fromkeys(item for item in evidence_ids if item.strip()))[:200]
    markdown = (
        "---\n"
        "knowledgeType: diagnostic-case\n"
        f"sourceTaskId: {task_id}\n"
        f"sourceReportId: {report_id}\n"
        "---\n\n"
        f"# 诊断案例：{alert_name}\n\n"
        f"- 服务：{service}\n"
        f"- 证据 ID：{', '.join(ids) if ids else '无'}\n\n"
        "## 摘要\n\n"
        f"{summary}\n\n"
        "## 根因\n\n"
        f"{root_cause}\n\n"
        "## 处置方案\n\n"
        f"{remediation}\n\n"
        "## 原始成功报告\n\n"
        f"{report_markdown.strip()}\n"
    )
    metadata: dict[str, JsonValue] = {
        "knowledgeType": "diagnostic-case",
        "sourceDiagnosticTaskId": task_id,
        "sourceReportId": report_id,
        "sourceEvidenceIds": list(ids),
    }
    return CaseMaterial(
        alert_name=alert_name[:500],
        service=service[:500],
        keywords=keywords,
        root_cause=root_cause[:_FIELD_LIMIT],
        remediation=remediation[:_FIELD_LIMIT],
        summary=summary[:_SUMMARY_LIMIT],
        evidence_ids=ids,
        markdown=markdown,
        source_metadata=metadata,
    )


def _text(value: JsonValue | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _label_value(markdown: str, label: str) -> str:
    match = re.search(rf"(?:^|\n)\s*[-*]?\s*{re.escape(label)}\s*[：:]\s*(.+)", markdown)
    return match.group(1).strip() if match else ""


def _plain_summary(markdown: str) -> str:
    text = re.sub(r"[#*_`>\[\]()]", " ", markdown)
    text = " ".join(text.split())
    return text[:_SUMMARY_LIMIT] or "成功报告未提供可提取摘要"
