"""AIOps request-scoped 只读取证工具 policy。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from super_ai.aiops.tool_schema import tool_schema_properties, tool_schema_required
from super_ai.project_config import JsonValue

ToolCapability = Literal[
    "knowledge_retrieval",
    "query_builder",
    "log_search",
    "log_context",
    "metric_query",
    "auxiliary",
]
# 只读辅助工具：允许规划与调用，产出作为中间产物进入模型可见上下文，
# 但不参与证据充分性判断（那种判断只看 log_hit / log_context / metric）。
AUXILIARY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ConvertTimestampToTimeString",
        "ConvertTimeStringToTimestamp",
        "GetRegionCodeByName",
        "DescribeIndex",
        "DescribeAlarms",
        "DescribeAlertRecordHistory",
        "DescribeTopics",
        "DescribeLogsets",
    }
)
ToolArtifactKind = Literal["knowledge", "query_artifact", "log_hit", "log_context", "metric"]

# 由服务端无条件注入、因此不出现在模型可见参数说明里的字段。
# 只包含"账号级权威配置"：它们的取值来自 ignored 本地 JSON，模型既不该知道也不该覆盖。
# 跨步骤产出（例如日志上下文需要的 Time/PkgId/PkgLogId）不在此列——那类值由执行者
# 依据前序真实产出填写。
SERVER_PROVIDED_ARGUMENTS: frozenset[str] = frozenset({"Region", "TopicId"})

# 只读判定：真实发现工具的 MCP readOnlyHint 注解没有被 langchain-mcp-adapters 保留
# （实测 Tool 上没有 annotations 字段），所以只能用真实发现给出的名称判定。
# 这里采用白名单：只有以已知只读动词开头的工具才允许进入计划，未识别的默认排除。
# 语义登记表里的显式登记优先于该判定——`TextToSearchLogQuery` 这类名字不含只读动词、
# 但确实是只读查询的工具，靠登记放行。
_READ_ONLY_NAME_PREFIXES: tuple[str, ...] = (
    "get",
    "describe",
    "list",
    "query",
    "search",
    "read",
    "fetch",
    "convert",
)


def _normalized_name(value: str) -> str:
    return re.sub(r"[_\-\s]+", "", value.casefold())


def _looks_read_only(tool_name: str) -> bool:
    return tool_name.strip().casefold().startswith(_READ_ONLY_NAME_PREFIXES)


@dataclass(frozen=True, slots=True)
class AiopsToolPolicyEntry:
    canonical_name: str
    capability: ToolCapability
    artifact_kind: ToolArtifactKind
    read_only: bool
    dependencies: tuple[ToolCapability, ...] = ()
    required_for_profile: bool = False
    # 由服务端注入、因此不进入模型可见参数说明的字段（同时从必填列表移除）。
    server_provided_arguments: tuple[str, ...] = ()

    def matches(self, actual_name: str) -> bool:
        return _normalized_name(actual_name) == _normalized_name(self.canonical_name)


@dataclass(frozen=True, slots=True)
class ToolCapabilityDescriptor:
    name: str
    description: str
    input_schema: dict[str, JsonValue]
    capability: ToolCapability
    artifact_kind: ToolArtifactKind
    read_only: bool
    dependencies: tuple[ToolCapability, ...]
    required_for_profile: bool


DEFAULT_AIOPS_TOOL_POLICY: tuple[AiopsToolPolicyEntry, ...] = (
    AiopsToolPolicyEntry(
        "TextToSearchLogQuery",
        "query_builder",
        "query_artifact",
        True,
        server_provided_arguments=("Region", "TopicId"),
    ),
    AiopsToolPolicyEntry(
        "SearchLog",
        "log_search",
        "log_hit",
        True,
        required_for_profile=True,
        server_provided_arguments=("Region", "TopicId"),
    ),
    AiopsToolPolicyEntry(
        "DescribeLogContext",
        "log_context",
        "log_context",
        True,
        ("log_search",),
        # Time/PkgId/PkgLogId 来自本轮已验证的 SearchLog 命中：它们不再是"服务端权威值"，
        # 而是跨步骤产出，由执行者依据前序真实产出填写，因此必须对模型可见。
        server_provided_arguments=("Region", "TopicId"),
    ),
    AiopsToolPolicyEntry(
        "QueryMetric",
        "metric_query",
        "metric",
        True,
        server_provided_arguments=("Region", "TopicId"),
    ),
    # 官方 server 的这 20 个工具全部是只读查询类；下面登记的是诊断过程中真正
    # 需要配套使用的辅助工具（尤其是官方 SearchLog 说明里要求先调用的时间转换）。
    *(
        AiopsToolPolicyEntry(name, "auxiliary", "query_artifact", True)
        for name in sorted(AUXILIARY_TOOL_NAMES)
    ),
)


class AiopsToolUnavailableError(ValueError):
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"AIOps 工具当前未发现或不是本轮可用的只读工具: {tool_name}")


@dataclass(frozen=True, slots=True)
class AiopsToolRegistry:
    tools: dict[str, BaseTool]
    catalog: tuple[ToolCapabilityDescriptor, ...]

    def require(self, tool_name: str) -> BaseTool:
        tool = self.tools.get(tool_name)
        if tool is None:
            raise AiopsToolUnavailableError(tool_name)
        return tool


def build_aiops_tool_registry(
    discovered: Sequence[BaseTool],
    *,
    policy: Sequence[AiopsToolPolicyEntry] = DEFAULT_AIOPS_TOOL_POLICY,
) -> AiopsToolRegistry:
    """以本轮真实发现作为工具集合，policy 只提供语义登记。

    与旧实现的区别：不再用静态名单决定"谁可以被规划"。真实发现的只读工具全部进入
    registry 与模型可见目录；语义登记表只负责说明已知工具的能力、依赖、产物类型与
    服务端注入字段。未登记的工具按"只读动词前缀"判定，产物按中间产物处理。
    """
    tools: dict[str, BaseTool] = {}
    descriptors: list[ToolCapabilityDescriptor] = []
    for tool in discovered:
        entry = next((item for item in policy if item.matches(tool.name)), None)
        read_only = entry.read_only if entry is not None else _looks_read_only(tool.name)
        if not read_only:
            continue
        if tool.name in tools:
            raise ValueError(f"发现重复 AIOps 工具: {tool.name}")
        capability: ToolCapability = entry.capability if entry is not None else "auxiliary"
        artifact_kind: ToolArtifactKind = (
            entry.artifact_kind if entry is not None else "query_artifact"
        )
        hidden = (
            SERVER_PROVIDED_ARGUMENTS.union(entry.server_provided_arguments)
            if entry is not None
            else SERVER_PROVIDED_ARGUMENTS
        )
        tools[tool.name] = tool
        descriptors.append(
            ToolCapabilityDescriptor(
                name=tool.name,
                description=(tool.description or "").strip()[:1000],
                input_schema=_model_visible_schema(tool, hidden),
                capability=capability,
                artifact_kind=artifact_kind,
                read_only=True,
                dependencies=entry.dependencies if entry is not None else (),
                required_for_profile=(
                    entry.required_for_profile if entry is not None else False
                ),
            )
        )
    return AiopsToolRegistry(tools, tuple(descriptors))


def describe_builtin_knowledge_tool(tool: BaseTool) -> ToolCapabilityDescriptor:
    return ToolCapabilityDescriptor(
        name=tool.name,
        description=(tool.description or "").strip()[:1000],
        input_schema=_model_visible_schema(tool, frozenset()),
        capability="knowledge_retrieval",
        artifact_kind="knowledge",
        read_only=True,
        dependencies=(),
        required_for_profile=False,
    )


_DESCRIPTION_LIMIT = 600
_SCHEMA_KEYWORDS = ("type", "description", "enum", "format", "default", "items")


def _model_visible_schema(tool: BaseTool, hidden: frozenset[str]) -> dict[str, JsonValue]:
    """输出模型可见的工具参数说明。

    与旧实现的区别：这里保留官方 schema 提供的字段用途、类型、枚举、格式与默认值，
    只移除由服务端注入的字段（同时从必填列表移除），让模型看到它真正要填的那些字段的
    完整约束——而不是只剩一个 type，甚至 "unknown"。
    """
    raw = tool.args_schema
    if isinstance(raw, dict):
        schema = cast(Mapping[str, object], raw)
    elif isinstance(raw, type) and issubclass(raw, BaseModel):
        schema = cast(Mapping[str, object], raw.model_json_schema())
    else:
        return {"type": "object", "properties": {}, "required": []}
    raw_properties = tool_schema_properties(schema)
    properties: dict[str, JsonValue] = {}
    for key, value in raw_properties.items():
        if key in hidden or not isinstance(value, dict):
            continue
        properties[key] = _visible_property(cast(dict[str, JsonValue], value))
    required: list[JsonValue] = [
        item for item in tool_schema_required(schema) if item not in hidden
    ]
    return {"type": "object", "properties": properties, "required": required}


def _visible_property(raw: dict[str, JsonValue]) -> JsonValue:
    visible: dict[str, JsonValue] = {
        key: raw[key] for key in _SCHEMA_KEYWORDS if key in raw and key != "description"
    }
    description = raw.get("description")
    if description is not None:
        # 字段用途是保留重点，但单个字段说明设长度上限，避免提示词体积失控。
        visible["description"] = f"{description}"[:_DESCRIPTION_LIMIT]
    return cast(JsonValue, visible)
