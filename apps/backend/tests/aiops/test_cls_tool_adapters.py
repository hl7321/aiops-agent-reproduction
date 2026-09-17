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
    query = TextToSearchLogQueryInput.model_validate(
        {"Region": "ap-guangzhou", "TopicId": "topic-1", "Prompt": "查询 payment 错误"}
    )
    assert query.prompt == "查询 payment 错误"
    assert query.model_dump(mode="json", by_alias=True) == {
        "Region": "ap-guangzhou",
        "TopicId": "topic-1",
        "Text": "查询 payment 错误",
    }
    search = SearchLogInput(
        Region="ap-guangzhou",
        TopicId="topic-1",
        From=1000,
        To=2000,
        Query='incident_id:"java-ecom-001"',
        Limit=100,
        Sort="desc",
        Offset=0,
        SamplingRate=1,
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
                "Sort": "random",
            }
        )
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


def test_query_builder_parses_official_langchain_content_block() -> None:
    artifact = parse_text_to_search_log_query_result(
        [
            {
                "type": "text",
                "id": "response-1",
                "text": (
                    '{"Choices":[{"Message":{"Content":'
                    '"service:payment-service AND level:ERROR"}}]}'
                ),
            }
        ]
    )
    assert artifact.query == "service:payment-service AND level:ERROR"


def test_query_builder_extracts_only_fenced_cql_from_explanatory_markdown() -> None:
    artifact = parse_text_to_search_log_query_result(
        [
            {
                "type": "text",
                "text": (
                    '{"Choices":[{"Message":{"Content":'
                    '"查询说明：\\n\\n```sql\\nservice:\\\"payment-service\\\" '
                    'AND level:ERROR\\n```\\n\\n解释：后续文字不能进入查询。"}}]}'
                ),
            }
        ]
    )
    assert artifact.query == 'service:"payment-service" AND level:ERROR'


def test_query_builder_unescapes_fenced_cql_from_raw_text_response() -> None:
    """官方工具在纯文本响应里返回的代码块带 JSON 转义，必须还原后再当查询用。

    这条覆盖的是真实失败路径：响应以 `SessionId:` 开头、不是合法 JSON，
    解包退化为原文，围栏代码块会连同字面量 \\n 与 \\" 一起被取出。
    还原前 CLS 会把 `\\nservice` 当成字段名 `nservice` 并报语法错误。
    """
    artifact = parse_text_to_search_log_query_result(
        [
            {
                "type": "text",
                "text": (
                    "SessionId: 963dd2a4-d018-4e07-ad66-7d349e2ecb10\n"
                    'Content: {"Choices":[{"Message":{"Content":'
                    '"根据需求生成以下 CQL：\\\\n\\\\n```sql\\\\n'
                    'service:\\\\"auth-service\\\\" AND level:\\\\"ERROR\\\\"'
                    '\\\\n```\\\\n\\\\n解释说明不能进入查询。"}}]}'
                ),
            }
        ]
    )
    assert artifact.query == 'service:"auth-service" AND level:"ERROR"'
    assert "\\n" not in artifact.query
    assert '\\"' not in artifact.query


def test_query_builder_preserves_legitimate_backslashes() -> None:
    """查询里本来就可能含合法反斜杠（例如正则片段），反转义不能误伤它们。"""
    artifact = parse_text_to_search_log_query_result(
        [
            {
                "type": "text",
                "text": '```sql\nservice:"cart-service" AND message:/\\d+/\n```',
            }
        ]
    )
    assert artifact.query == 'service:"cart-service" AND message:/\\d+/'


def test_query_builder_removes_projection_pipeline_to_preserve_raw_log_hits() -> None:
    artifact = parse_text_to_search_log_query_result(
        {
            "Query": (
                'trace_id:"trace-1" AND level:ERROR '
                '| SELECT timestamp, message ORDER BY timestamp DESC LIMIT 50'
            )
        }
    )
    assert artifact.query == 'trace_id:"trace-1" AND level:ERROR'


def test_search_log_parses_official_raw_hit_and_allows_missing_context_locator() -> None:
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
    without_locator = parse_search_log_result(
        [
            {
                "type": "text",
                "text": '[{"Time":1,"PkgId":"","PkgLogId":"","LogJson":"{}"}]',
            }
        ]
    )[0]
    assert without_locator.pkg_id is None
    assert without_locator.pkg_log_id is None
    with pytest.raises(ValueError, match="字段"):
        parse_search_log_result(
            [{"Time": 1, "PkgId": "pkg", "PkgLogId": "not-a-number", "LogJson": "{}"}]
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
    hit_without_locator = parse_search_log_result(
        [{"Time": 1, "PkgId": "", "PkgLogId": "", "LogJson": "{}"}]
    )[0]
    with pytest.raises(ValueError, match="定位字段"):
        build_describe_log_context_input(
            hit_without_locator,
            SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
            proposed={},
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


def test_context_parser_accepts_official_log_context_infos() -> None:
    context = parse_describe_log_context_result(
        [
            {
                "type": "text",
                "text": (
                    '{"LogContextInfos":['
                    '{"BTime":10,"Content":"before"},'
                    '{"BTime":11,"Content":"failed"},'
                    '{"BTime":12,"Content":"retry"}]}'
                ),
            }
        ]
    )
    assert [item.log_json for item in context.ordered_logs] == ["before", "failed", "retry"]


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


def test_core_runtime_schema_accepts_official_flat_field_mapping() -> None:
    ensure_core_tool_schema_compatible(
        "TextToSearchLogQuery",
        {
            "Text": {"type": "string"},
            "Region": {"type": "string"},
            "TopicId": {"type": "string"},
        },
    )
