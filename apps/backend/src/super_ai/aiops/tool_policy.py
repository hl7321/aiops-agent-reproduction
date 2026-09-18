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


def _normalized_name(value: str) -> str:
    return re.sub(r"[_\-\s]+", "", value.casefold())


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
        # Time/PkgId/PkgLogId 来自本轮已验证的 SearchLog 命中，模型无法凭空知道。
        server_provided_arguments=("Region", "TopicId", "Time", "PkgId", "PkgLogId"),
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
        super().__init__(f"AIOps 工具当前未发现或未被只读取证 policy 允许: {tool_name}")


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
    """只保留本轮真实发现与静态只读 policy 的交集。"""
    tools: dict[str, BaseTool] = {}
    descriptors: list[ToolCapabilityDescriptor] = []
    for tool in discovered:
        entry = next((item for item in policy if item.matches(tool.name)), None)
        if entry is None or not entry.read_only:
            continue
        if tool.name in tools:
            raise ValueError(f"发现重复 AIOps 工具: {tool.name}")
        tools[tool.name] = tool
        descriptors.append(
            ToolCapabilityDescriptor(
                name=tool.name,
                description=(tool.description or "").strip()[:1000],
                input_schema=_model_visible_schema(
                    tool, frozenset(entry.server_provided_arguments)
                ),
                capability=entry.capability,
                artifact_kind=entry.artifact_kind,
                read_only=entry.read_only,
                dependencies=entry.dependencies,
                required_for_profile=entry.required_for_profile,
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
