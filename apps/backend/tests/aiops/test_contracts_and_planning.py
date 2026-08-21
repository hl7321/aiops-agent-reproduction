from datetime import datetime, timezone
from pathlib import Path

import pytest

from super_ai.aiops.evidence import alert_evidence, normalize_tool_evidence
from super_ai.aiops.planning import (
    PlanDraft,
    PlanStepDraft,
    ReportDraft,
    find_search_log_tool,
    validate_plan,
)
from super_ai.aiops.reporting import build_fallback_report, validate_report
from super_ai.aiops.router import map_job_event_to_sse
from super_ai.api_contracts import ERROR_DEFINITIONS, CreateDiagnosticRequest, TaskStatusData
from super_ai.app import create_app
from super_ai.background_jobs.models import BackgroundJobEventRecord


def test_contracts_publish_diagnostics_and_shared_status() -> None:
    assert ERROR_DEFINITIONS["SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE"].http_status == 503
    assert TaskStatusData(taskId="task", status="queued", progress=0).progress == 0
    paths = create_app().openapi()["paths"]
    assert "/aiops/diagnostics" in paths
    assert "/aiops/diagnostics/{id}" in paths
    assert "/aiops/diagnostics/{id}/evidence-chain" in paths
    assert "/aiops/diagnostics/{id}:stream" in paths
    assert "/aiops/diagnostics/{id}:cancel" not in paths
    assert "/aiops/diagnostics/{id}:retry" not in paths


def test_request_requires_real_alert_and_bounded_progress() -> None:
    with pytest.raises(ValueError):
        CreateDiagnosticRequest(alerts=[])
    with pytest.raises(ValueError):
        TaskStatusData(taskId="task", status="running", progress=101)


def test_plan_requires_one_registered_search_log() -> None:
    draft = PlanDraft(
        steps=[
            PlanStepDraft(toolName="SearchLog", purpose="查询真实日志", arguments={"q": "x"}),
            PlanStepDraft(toolName="QueryMetric", purpose="查询指标", arguments={}),
        ]
    )
    assert find_search_log_tool(("QueryMetric", "Search_Log")) == "Search_Log"
    assert len(validate_plan(draft, ("SearchLog", "QueryMetric"))) == 2
    with pytest.raises(ValueError, match="只能包含一个"):
        validate_plan(
            PlanDraft(
                steps=[
                    PlanStepDraft(toolName="SearchLog", purpose="一", arguments={}),
                    PlanStepDraft(toolName="search_log", purpose="二", arguments={}),
                ]
            ),
            ("SearchLog", "search_log"),
        )


def test_evidence_rejects_unknown_payload_and_fallback_is_honest() -> None:
    with pytest.raises(ValueError, match="无法安全映射"):
        normalize_tool_evidence(
            tool_name="RestartService", result={"ok": True}, step_id="step", tool_call_id="call"
        )
    markdown, links = build_fallback_report([{"alertName": "HighError"}], [])
    assert "证据不足" in markdown
    assert "# 告警分析报告" in markdown
    assert links == ()

    validated, claims, uncertainty = validate_report(
        ReportDraft(markdown=markdown, claims=[], uncertainty=True), [], alert_count=1
    )
    assert validated == markdown
    assert claims == ()
    assert uncertainty is True
    with pytest.raises(ValueError, match="固定中文字段"):
        validate_report(
            ReportDraft(
                markdown=markdown.replace("- 风险评估：", "- 风险："),
                claims=[],
                uncertainty=True,
            ),
            [],
            alert_count=1,
        )


def test_evidence_normalizes_knowledge_results_and_redacts_secrets() -> None:
    evidence = normalize_tool_evidence(
        tool_name="knowledge_retrieval",
        result={
            "results": [
                {
                    "source": "runbook.md",
                    "excerpt": "检查服务错误率",
                    "metadata": {"apiKey": "sentinel-secret"},
                }
            ]
        },
        step_id="step",
        tool_call_id="call",
    )
    assert len(evidence) == 1
    assert evidence[0].kind == "knowledge"
    assert evidence[0].metadata["metadata"] == {"apiKey": "[redacted]"}
    assert "sentinel-secret" not in evidence[0].content

    alert = alert_evidence(
        {
            "alertName": "HighError",
            "source": {"name": "prometheus"},
            "rawContext": {"authorization": "Bearer sentinel-secret"},
        }
    )
    assert alert.source == "prometheus"
    assert "sentinel-secret" not in alert.content


def test_no_production_fake_evidence_modules() -> None:
    root = Path(__file__).parents[2] / "src" / "super_ai" / "aiops"
    sources = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "fake_evidence" not in sources
    assert '"plan.step"' not in sources
    assert '"plan.replan"' not in sources


def test_persisted_terminal_event_maps_to_one_complete_and_shared_error() -> None:
    now = datetime.now(timezone.utc)
    succeeded = BackgroundJobEventRecord(3, "job", "owner", "succeeded", {}, now)
    failed = BackgroundJobEventRecord(4, "job", "owner", "failed", {}, now)
    success_payloads = map_job_event_to_sse(succeeded, "task")
    failed_payloads = map_job_event_to_sse(failed, "task")
    assert [item["type"] for item in success_payloads] == ["complete"]
    assert [item["type"] for item in failed_payloads] == ["complete"]
