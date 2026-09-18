from langchain_core.tools import tool

from super_ai.aiops.tool_policy import (
    DEFAULT_AIOPS_TOOL_POLICY,
    AiopsToolUnavailableError,
    build_aiops_tool_registry,
)


def _tool_named(name: str):
    @tool(name)
    def fake_tool(Query: str = "*") -> dict[str, str]:
        """测试工具。"""
        return {"query": Query}

    return fake_tool


def test_registry_takes_every_discovered_read_only_tool() -> None:
    """工具集合来自真实发现：已登记的保留语义，未登记的只读工具同样可被规划。"""
    search = _tool_named("SearchLog")
    metric = _tool_named("QueryMetric")
    listing = _tool_named("DescribeTopics")
    write_alert = _tool_named("CreateAlert")
    registry = build_aiops_tool_registry(
        (search, metric, listing, write_alert), policy=DEFAULT_AIOPS_TOOL_POLICY
    )

    assert tuple(registry.tools) == ("SearchLog", "QueryMetric", "DescribeTopics")
    assert all(item.read_only for item in registry.catalog)
    catalog = {item.name: item for item in registry.catalog}
    assert catalog["SearchLog"].capability == "log_search"
    # 未登记的工具按只读辅助工具处理，产物落中间产物
    assert catalog["DescribeTopics"].capability == "auxiliary"
    assert catalog["DescribeTopics"].artifact_kind == "query_artifact"
    assert "CreateAlert" not in registry.tools


def test_unknown_or_side_effect_tool_is_not_executable() -> None:
    registry = build_aiops_tool_registry(
        (_tool_named("SearchLog"), _tool_named("DeleteLogTopic")),
        policy=DEFAULT_AIOPS_TOOL_POLICY,
    )

    for forbidden in ("DeleteLogTopic", "tool-from-another-owner"):
        try:
            registry.require(forbidden)
        except AiopsToolUnavailableError as error:
            assert error.tool_name == forbidden
        else:
            raise AssertionError("未登记工具不得进入 AIOps Executor")


def test_restored_plan_fails_if_previously_allowed_tool_disappeared() -> None:
    original = build_aiops_tool_registry(
        (_tool_named("SearchLog"), _tool_named("DescribeLogContext")),
        policy=DEFAULT_AIOPS_TOOL_POLICY,
    )
    restored = build_aiops_tool_registry(
        (_tool_named("SearchLog"),), policy=DEFAULT_AIOPS_TOOL_POLICY
    )
    assert original.require("DescribeLogContext").name == "DescribeLogContext"
    try:
        restored.require("DescribeLogContext")
    except AiopsToolUnavailableError:
        pass
    else:
        raise AssertionError("恢复时不得调用已经 disabled 或消失的 MCP 工具")


def test_catalog_hides_server_provided_fields_and_keeps_field_constraints() -> None:
    """模型可见的参数说明：保留官方字段约束，移除服务端注入的 Region/TopicId。"""
    search = _tool_named("SearchLog")
    search.args_schema = {
        "type": "object",
        "properties": {
            "From": {"type": "number", "description": "起始时间，毫秒时间戳"},
            "To": {"type": "number", "description": "结束时间，毫秒时间戳"},
            "Query": {"type": "string", "description": "检索语句"},
            "Limit": {"type": "number", "default": 10, "description": "返回条数，1-100"},
            "TopicId": {"type": "string", "description": "日志主题 ID"},
            "Region": {"type": "string", "description": "地域，如 ap-guangzhou"},
        },
        "required": ["From", "To", "Query", "Region", "TopicId"],
    }
    registry = build_aiops_tool_registry((search,))
    schema = registry.catalog[0].input_schema
    assert schema["properties"] == {
        "From": {"type": "number", "description": "起始时间，毫秒时间戳"},
        "To": {"type": "number", "description": "结束时间，毫秒时间戳"},
        "Query": {"type": "string", "description": "检索语句"},
        "Limit": {"type": "number", "default": 10, "description": "返回条数，1-100"},
    }
    # 服务端注入的字段同时从必填列表移除，避免出现"必填但看不见"
    assert schema["required"] == ["From", "To", "Query"]


def test_catalog_accepts_official_flat_schema_shape() -> None:
    """官方扁平 schema（properties 直接铺在顶层）同样要被正确投影。"""
    search = _tool_named("SearchLog")
    search.args_schema = {
        "From": {"type": "number", "description": "起始时间"},
        "To": {"type": "number", "description": "结束时间"},
        "Query": {"type": "string", "description": "检索语句"},
        "TopicId": {"type": "string"},
        "Region": {"type": "string"},
    }
    registry = build_aiops_tool_registry((search,))
    assert registry.catalog[0].input_schema["properties"] == {
        "From": {"type": "number", "description": "起始时间"},
        "To": {"type": "number", "description": "结束时间"},
        "Query": {"type": "string", "description": "检索语句"},
    }


def test_read_only_auxiliary_tools_enter_policy_and_catalog() -> None:
    """只读辅助工具（时间戳转换、索引查询）必须能进入 policy 与模型可见目录。"""
    time_tool = _tool_named("ConvertTimestampToTimeString")
    time_tool.args_schema = {
        "type": "object",
        "properties": {
            "timestamp": {"type": "number", "description": "不传则返回当前时间"},
            "unit": {"type": "string", "enum": ["milliseconds", "seconds"]},
        },
        "required": [],
    }
    index_tool = _tool_named("DescribeIndex")
    index_tool.args_schema = {
        "type": "object",
        "properties": {
            "Region": {"type": "string"},
            "TopicId": {"type": "string"},
        },
        "required": ["Region", "TopicId"],
    }

    registry = build_aiops_tool_registry((time_tool, index_tool))

    assert set(registry.tools) == {"ConvertTimestampToTimeString", "DescribeIndex"}
    catalog = {item.name: item for item in registry.catalog}
    assert catalog["ConvertTimestampToTimeString"].capability == "auxiliary"
    assert catalog["ConvertTimestampToTimeString"].artifact_kind == "query_artifact"
    # 辅助工具不要求出现在诊断 profile 里
    assert catalog["DescribeIndex"].required_for_profile is False


def test_write_verb_tools_stay_out_of_the_catalog() -> None:
    """写动词前缀的工具默认排除；只读动词前缀的未登记工具默认放行。"""
    write_tools = ("DeleteLogTopic", "CreateAlarm", "UpdateIndex", "ModifyWebhook")
    tools = tuple(_tool_named(name) for name in write_tools)

    registry = build_aiops_tool_registry(tools)

    assert registry.tools == {}
    assert registry.catalog == ()


def test_unregistered_read_only_tool_hides_server_provided_fields() -> None:
    """未登记工具的可见说明同样隐藏 Region/TopicId，并从必填列表移除。"""
    listing = _tool_named("DescribeAlarmShields")
    listing.args_schema = {
        "type": "object",
        "properties": {
            "Region": {"type": "string", "description": "地域"},
            "AlarmNoticeId": {"type": "string", "description": "通知渠道组 ID"},
        },
        "required": ["Region", "AlarmNoticeId"],
    }

    registry = build_aiops_tool_registry((listing,))

    schema = registry.catalog[0].input_schema
    assert schema["properties"] == {
        "AlarmNoticeId": {"type": "string", "description": "通知渠道组 ID"}
    }
    assert schema["required"] == ["AlarmNoticeId"]


def test_bound_cross_step_locators_stay_hidden_from_the_model() -> None:
    """计划保证的跨步配对由执行者绑定，模型不需要也看不到这些定位字段。"""
    context = _tool_named("DescribeLogContext")
    context.args_schema = {
        "type": "object",
        "properties": {
            "Region": {"type": "string"},
            "TopicId": {"type": "string"},
            "Time": {"type": "number", "description": "命中时间"},
            "PkgId": {"type": "string", "description": "日志包 ID"},
            "PkgLogId": {"type": "number", "description": "包内序号"},
        },
        "required": ["Region", "TopicId", "Time", "PkgId", "PkgLogId"],
    }

    registry = build_aiops_tool_registry((context,))

    schema = registry.catalog[0].input_schema
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert properties == {}
    assert schema["required"] == []
