from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from super_ai.aiops.evidence import alert_evidence, normalize_tool_evidence
from super_ai.aiops.models import DiagnosticEvidenceRecord
from super_ai.aiops.planning import (
    PlanDraft,
    PlanStepDraft,
    ReportDraft,
    SearchLogQueryDefaults,
    ToolArgumentRepairDraft,
    create_validated_plan,
    find_search_log_tool,
    normalize_search_log_arguments,
    validate_plan,
)
from super_ai.aiops.reporting import build_fallback_report, validate_report
from super_ai.aiops.router import map_job_event_to_sse
from super_ai.aiops.runtime import _latest_query_artifact  # pyright: ignore[reportPrivateUsage]
from super_ai.aiops.tool_adapters import (
    adapt_allowed_tool_output,
    inject_server_provided_arguments,
    validate_tool_arguments,
)
from super_ai.aiops.tool_policy import ToolCapabilityDescriptor
from super_ai.api_contracts import ERROR_DEFINITIONS, CreateDiagnosticRequest, TaskStatusData
from super_ai.app import create_app
from super_ai.background_jobs.models import BackgroundJobEventRecord
from super_ai.project_config import JsonValue


def _evidence(title: str, source: str, metadata: dict[str, JsonValue]) -> DiagnosticEvidenceRecord:
    now = datetime(2026, 9, 17, tzinfo=timezone.utc)
    return DiagnosticEvidenceRecord(
        id=f"evidence-{title}",
        owner_user_id="owner",
        diagnostic_task_id="task",
        diagnostic_step_id=None,
        tool_call_id=None,
        kind="query_artifact",
        source=source,
        title=title,
        summary=title,
        content=title,
        metadata=metadata,
        observed_at=None,
        created_at=now,
    )


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


def test_request_requires_query_or_real_alert_and_bounded_progress() -> None:
    request = CreateDiagnosticRequest(alerts=[], query=" 手工排查 checkout ")
    assert request.query == "手工排查 checkout"
    with pytest.raises(ValueError):
        CreateDiagnosticRequest(alerts=[])
    with pytest.raises(ValueError):
        CreateDiagnosticRequest(alerts=[], query="   ")
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


def test_plan_requires_query_builder_only_for_untrusted_query() -> None:
    direct = PlanDraft(
        steps=[PlanStepDraft(toolName="SearchLog", purpose="查询真实日志", arguments={})]
    )
    with pytest.raises(ValueError, match="TextToSearchLogQuery"):
        validate_plan(
            direct,
            ("TextToSearchLogQuery", "SearchLog"),
            query_is_trusted=False,
        )

    built = PlanDraft(
        steps=[
            PlanStepDraft(
                toolName="TextToSearchLogQuery", purpose="生成查询", arguments={}
            ),
            PlanStepDraft(toolName="SearchLog", purpose="查询真实日志", arguments={}),
        ]
    )
    assert len(
        validate_plan(
            built,
            ("TextToSearchLogQuery", "SearchLog"),
            query_is_trusted=False,
        )
    ) == 2
    with pytest.raises(ValueError, match="无需重复"):
        validate_plan(
            built,
            ("TextToSearchLogQuery", "SearchLog"),
            query_is_trusted=True,
        )


def test_temporal_claim_requires_context_after_search() -> None:
    missing = PlanDraft(
        requiresTemporalContext=True,
        steps=[PlanStepDraft(toolName="SearchLog", purpose="查询日志", arguments={})],
    )
    with pytest.raises(ValueError, match="DescribeLogContext"):
        validate_plan(
            missing,
            ("SearchLog", "DescribeLogContext"),
            query_is_trusted=True,
        )

    valid = PlanDraft(
        requiresTemporalContext=True,
        steps=[
            PlanStepDraft(toolName="SearchLog", purpose="查询日志", arguments={}),
            PlanStepDraft(
                toolName="DescribeLogContext", purpose="验证调用时序", arguments={}
            ),
        ],
    )
    assert [step.tool_name for step in validate_plan(
        valid,
        ("SearchLog", "DescribeLogContext"),
        query_is_trusted=True,
    )] == ["SearchLog", "DescribeLogContext"]


async def test_planner_validation_correction_is_bounded_to_three_attempts() -> None:
    descriptor = ToolCapabilityDescriptor(
        name="SearchLog",
        description="查询日志",
        input_schema={"type": "object", "properties": {}, "required": []},
        capability="log_search",
        artifact_kind="log_hit",
        read_only=True,
        dependencies=(),
        required_for_profile=True,
    )

    class CorrectingModel:
        def __init__(self, succeeds: bool) -> None:
            self.succeeds = succeeds
            self.errors: list[tuple[str, ...]] = []

        async def plan(
            self,
            *,
            context: str,
            tool_catalog: Sequence[ToolCapabilityDescriptor],
            validation_errors: Sequence[str] = (),
        ) -> PlanDraft:
            assert context and tool_catalog
            self.errors.append(tuple(validation_errors))
            name = "SearchLog" if self.succeeds and len(self.errors) == 3 else "UnknownTool"
            return PlanDraft(
                steps=[PlanStepDraft(toolName=name, purpose="查询", arguments={})]
            )

        async def replan(self, **_kwargs: object):  # pragma: no cover - protocol filler
            raise AssertionError

        async def repair_tool_arguments(
            self, **_kwargs: object
        ) -> ToolArgumentRepairDraft:  # pragma: no cover - protocol filler
            raise AssertionError

        async def report(self, **_kwargs: object):  # pragma: no cover - protocol filler
            raise AssertionError

    corrected = CorrectingModel(True)
    plan = await create_validated_plan(
        corrected,
        context="安全上下文",
        tool_catalog=(descriptor,),
        query_is_trusted=True,
    )
    assert plan[0].tool_name == "SearchLog"
    assert corrected.errors[0] == ()
    assert "未注册工具" in corrected.errors[1][0]
    assert len(corrected.errors) == 3

    never_valid = CorrectingModel(False)
    with pytest.raises(ValueError, match="三次校验纠错"):
        await create_validated_plan(
            never_valid,
            context="安全上下文",
            tool_catalog=(descriptor,),
            query_is_trusted=True,
        )
    assert len(never_valid.errors) == 3


def test_search_log_arguments_only_inject_server_authoritative_fields() -> None:
    """规范化只做两件事：注入 Region/TopicId、过滤官方 schema 之外的键。

    模型给出的时间与查询原样保留：不再补默认值、不再改写键名、不再换算单位。
    """
    schema = {
        "type": "object",
        "properties": {
            "From": {"type": "number"},
            "To": {"type": "number"},
            "Query": {"type": "string"},
            "TopicId": {"type": "string"},
            "Limit": {"type": "number"},
            "Region": {"type": "string"},
        },
        "required": ["From", "To", "Query", "Region"],
        "additionalProperties": False,
    }

    normalized = normalize_search_log_arguments(
        {
            "Query": "trace_id:4a0001",
            "From": 1_787_476_500_000,
            "To": 1_787_480_100_000,
            "Limit": 50,
            "Region": "model-region",
            "TopicId": "model-topic",
            "logset": "payment-service",   # 官方 schema 之外的键会被过滤
        },
        schema=schema,
        defaults=SearchLogQueryDefaults(region="ap-guangzhou", topic_id="topic-real"),
    )

    assert normalized == {
        "From": 1_787_476_500_000,
        "To": 1_787_480_100_000,
        "Query": "trace_id:4a0001",
        "TopicId": "topic-real",
        "Limit": 50,
        "Region": "ap-guangzhou",
    }

    with pytest.raises(ValueError, match="region/topicId"):
        normalize_search_log_arguments(
            {"Query": "*"},
            schema=schema,
            defaults=SearchLogQueryDefaults(region="", topic_id=""),
        )


def test_search_log_arguments_reject_lowercase_alias_keys() -> None:
    """别名映射已删除：官方 schema 用 Query，模型写 query 属于缺必填，应当直接失败。"""
    schema = {
        "type": "object",
        "properties": {
            "From": {"type": "number"},
            "To": {"type": "number"},
            "Query": {"type": "string"},
            "TopicId": {"type": "string"},
            "Region": {"type": "string"},
            "Limit": {"type": "number", "default": 10},
        },
        "required": ["From", "To", "Query", "Region"],
    }
    with pytest.raises(ValueError, match="缺少必填字段"):
        normalize_search_log_arguments(
            {"query": 'trace_id:"trace-1"'},
            schema=schema,
            defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
        )


def test_search_log_arguments_keep_model_time_units_untouched() -> None:
    """秒级换算已删除：官方 schema 写明单位是毫秒，模型填错应当失败而不是被偷偷换算。"""
    schema = {
        "From": {"type": "number"},
        "To": {"type": "number"},
        "Query": {"type": "string"},
        "Region": {"type": "string"},
    }
    normalized = normalize_search_log_arguments(
        {"From": 1_787_472_000, "To": 1_787_480_100, "Query": "*"},
        schema=schema,
        defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
    )
    assert normalized["From"] == 1_787_472_000
    assert normalized["To"] == 1_787_480_100


def test_search_log_arguments_do_not_reset_stale_time_window() -> None:
    """时间窗重置已删除：窗口是否合法交由 SearchLogInput 的 from<to 业务校验判定。"""
    schema = {
        "From": {"type": "number"},
        "To": {"type": "number"},
        "Query": {"type": "string"},
        "Region": {"type": "string"},
    }
    normalized = normalize_search_log_arguments(
        {"From": 1_724_486_988, "To": 1_724_494_188, "Query": "*"},
        schema=schema,
        defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
    )
    assert normalized["From"] == 1_724_486_988
    assert normalized["To"] == 1_724_494_188


def test_auxiliary_tool_output_becomes_intermediate_artifact() -> None:
    """只读辅助工具的产物以 query_artifact 落库，供后续步骤与 Replanner 使用。"""
    structured = adapt_allowed_tool_output(
        "ConvertTimestampToTimeString",
        {"currentTime": "2026-09-17T12:00:00Z"},
    )
    assert structured.kind == "query_artifact"
    assert structured.payload == {"currentTime": "2026-09-17T12:00:00Z"}

    # 标量返回也要能被安全包起来，而不是直接失败
    scalar = adapt_allowed_tool_output(
        "GetRegionCodeByName",
        [{"type": "text", "text": "ap-guangzhou"}],
    )
    assert scalar.kind == "query_artifact"
    assert scalar.payload == {"value": "ap-guangzhou"}


def test_auxiliary_artifact_is_never_used_as_search_query() -> None:
    """辅助产物即使含 Query 字段，也不能被当成 SearchLog 的查询。"""
    auxiliary = _evidence("辅助产物", "ConvertTimestampToTimeString", {"Query": "*"})
    builder = _evidence("查询产物", "TextToSearchLogQuery", {"Query": 'service:"a"'})

    assert _latest_query_artifact((auxiliary, builder)) == 'service:"a"'
    assert _latest_query_artifact((auxiliary,)) is None


def test_unregistered_tool_output_becomes_intermediate_artifact() -> None:
    """未登记 adapter 的只读工具，产物按中间产物落库，不冒充证据。"""
    records = normalize_tool_evidence(
        tool_name="GetAlarmLog",
        result={"Results": [{"Content": "告警执行详情"}]},
        step_id="step",
        tool_call_id="call",
    )

    assert len(records) == 1
    assert records[0].kind == "query_artifact"
    assert records[0].source == "GetAlarmLog"


_GENERIC_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "Region": {"type": "string"},
        "TopicId": {"type": "string"},
        "Limit": {"type": "integer", "minimum": 1, "maximum": 100},
        "Sort": {"type": "string", "enum": ["asc", "desc"]},
    },
    "required": ["Region"],
}


def test_generic_input_validation_rejects_bad_arguments() -> None:
    """通用入参校验：未声明键、缺必填、类型、枚举与范围都要在调用前拦住。"""
    with pytest.raises(ValueError, match="未声明的键"):
        validate_tool_arguments(
            "DescribeTopics", _GENERIC_SCHEMA, {": ": "order-service", "Region": "ap-guangzhou"}
        )
    with pytest.raises(ValueError, match="缺少必填字段"):
        validate_tool_arguments("DescribeTopics", _GENERIC_SCHEMA, {"Limit": 10})
    with pytest.raises(ValueError, match="类型应为 integer"):
        validate_tool_arguments(
            "DescribeTopics", _GENERIC_SCHEMA, {"Region": "ap-guangzhou", "Limit": "10"}
        )
    with pytest.raises(ValueError, match="不得大于"):
        validate_tool_arguments(
            "DescribeTopics", _GENERIC_SCHEMA, {"Region": "ap-guangzhou", "Limit": 500}
        )
    with pytest.raises(ValueError, match="取值必须属于"):
        validate_tool_arguments(
            "DescribeTopics", _GENERIC_SCHEMA, {"Region": "ap-guangzhou", "Sort": "up"}
        )

    accepted = validate_tool_arguments(
        "DescribeTopics", _GENERIC_SCHEMA, {"Region": "ap-guangzhou", "Limit": 10}
    )
    assert accepted == {"Region": "ap-guangzhou", "Limit": 10}


def test_server_provided_arguments_override_model_values() -> None:
    """服务端权威字段无条件注入；模型填的同名值被忽略，未声明键被过滤。"""
    merged = inject_server_provided_arguments(
        "SearchLog",
        _GENERIC_SCHEMA,
        {"Region": "model-value", "TopicId": "model-topic", "Limit": 10, "Unknown": 1},
        region="ap-guangzhou",
        topic_id="topic-real",
    )

    assert merged == {
        "Region": "ap-guangzhou",
        "TopicId": "topic-real",
        "Limit": 10,
    }


def test_fallback_report_is_honest() -> None:
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
