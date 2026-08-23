import pytest
from pydantic import ValidationError

from super_ai.aiops.cls_tool_adapters import (
    DescribeLogContextInput,
    SearchLogInput,
    TextToSearchLogQueryInput,
    build_describe_log_context_input,
    parse_describe_log_context_result,
    parse_search_log_result,
    parse_text_to_search_log_query_result,
)
from super_ai.aiops.planning import SearchLogQueryDefaults
from super_ai.aiops.tool_adapters import (
    adapt_allowed_tool_output,
    ensure_core_tool_schema_compatible,
)


def test_core_cls_inputs_are_explicit_and_forbid_unknown_fields() -> None:
    query = TextToSearchLogQueryInput(
        Region="ap-guangzhou", TopicId="topic-1", Prompt="查询 payment 错误"
    )
    assert query.prompt == "查询 payment 错误"
    search = SearchLogInput(
        Region="ap-guangzhou",
        TopicId="topic-1",
        From=1000,
        To=2000,
        Query='incident_id:"java-ecom-001"',
        Limit=100,
    )
    assert search.query.startswith("incident_id")
    with pytest.raises(ValidationError):
        SearchLogInput.model_validate(
            {
                "Region": "ap-guangzhou",
                "TopicId": "topic-1",
                "From": 1000,
                "To": 2000,
                "Query": "*",
                "invented": "not-allowed",
            }
        )


def test_query_builder_parses_structured_and_text_wrappers() -> None:
    structured = parse_text_to_search_log_query_result(
        {"structuredContent": {"Query": 'service:"payment-service" AND level:ERROR'}}
    )
    wrapped = parse_text_to_search_log_query_result(
        {"content": [{"type": "text", "text": '{"Query":"trace_id:trace-001"}'}]}
    )
    assert structured.query.startswith("service:")
    assert wrapped.query == "trace_id:trace-001"


def test_search_log_parses_official_raw_hit_and_rejects_missing_locator() -> None:
    result = {
        "content": [
            {
                "type": "text",
                "text": (
                    '[{"Time":1787478950899,"PkgId":"pkg-1",'
                    '"PkgLogId":2,"LogJson":"{\\"incident_id\\":\\"java-ecom-001\\"}"}]'
                ),
            }
        ]
    }
    hits = parse_search_log_result(result)
    assert (hits[0].time, hits[0].pkg_id, hits[0].pkg_log_id) == (
        1787478950899,
        "pkg-1",
        2,
    )
    with pytest.raises(ValueError, match="PkgId"):
        parse_search_log_result(
            {"structuredContent": [{"Time": 1, "PkgId": "", "PkgLogId": 0, "LogJson": "{}"}]}
        )


def test_context_input_uses_only_local_defaults_and_validated_hit() -> None:
    hit = parse_search_log_result(
        [{"Time": 1787478950899, "PkgId": "pkg-1", "PkgLogId": 2, "LogJson": "{}"}]
    )[0]
    value = build_describe_log_context_input(
        hit,
        SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
        proposed={"Region": "model-region", "TopicId": "model-topic", "PrevLogs": 5},
    )
    assert value == DescribeLogContextInput(
        Region="ap-guangzhou",
        TopicId="topic-real",
        Time=1787478950899,
        PkgId="pkg-1",
        PkgLogId=2,
        PrevLogs=5,
        NextLogs=10,
    )
    with pytest.raises(ValueError, match="region/topicId"):
        build_describe_log_context_input(
            hit, SearchLogQueryDefaults("", ""), proposed={}
        )


def test_context_and_metric_outputs_use_separate_adapters() -> None:
    context = parse_describe_log_context_result(
        {
            "structuredContent": {
                "PrevLogs": [{"Time": 10, "LogJson": "before"}],
                "CurrentLog": {"Time": 11, "LogJson": "failed"},
                "NextLogs": [{"Time": 12, "LogJson": "retry"}],
            }
        }
    )
    metric = adapt_allowed_tool_output(
        "QueryMetric",
        {"structuredContent": {"series": [{"metric": "error_rate", "value": 0.31}]}},
    )
    assert [item.log_json for item in context.ordered_logs] == ["before", "failed", "retry"]
    assert metric.kind == "metric"
    with pytest.raises(ValueError, match="无法解析"):
        parse_describe_log_context_result({"content": [{"type": "text", "text": "ok"}]})


def test_core_runtime_schema_rejects_unknown_required_authority_field() -> None:
    ensure_core_tool_schema_compatible(
        "SearchLog",
        {
            "type": "object",
            "properties": {
                "Region": {"type": "string"},
                "TopicId": {"type": "string"},
                "From": {"type": "number"},
                "To": {"type": "number"},
                "Query": {"type": "string"},
            },
            "required": ["Region", "From", "To", "Query"],
        },
    )
    with pytest.raises(ValueError, match="未知必填字段"):
        ensure_core_tool_schema_compatible(
            "SearchLog",
            {
                "type": "object",
                "properties": {
                    "Region": {"type": "string"},
                    "Query": {"type": "string"},
                    "Authorization": {"type": "string"},
                },
                "required": ["Region", "Query", "Authorization"],
            },
        )
