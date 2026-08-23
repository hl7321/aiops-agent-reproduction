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


def test_registry_is_dynamic_discovery_intersect_read_only_policy() -> None:
    search = _tool_named("SearchLog")
    metric = _tool_named("QueryMetric")
    write_alert = _tool_named("CreateAlert")
    registry = build_aiops_tool_registry(
        (search, metric, write_alert), policy=DEFAULT_AIOPS_TOOL_POLICY
    )

    assert tuple(registry.tools) == ("SearchLog", "QueryMetric")
    assert {item.capability for item in registry.catalog} == {"log_search", "metric_query"}
    assert all(item.read_only for item in registry.catalog)
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
