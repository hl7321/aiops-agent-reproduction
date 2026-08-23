"""AIOps request-scoped 只读取证工具 policy。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from super_ai.project_config import JsonValue

ToolCapability = Literal[
    "knowledge_retrieval", "query_builder", "log_search", "log_context", "metric_query"
]
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
        "TextToSearchLogQuery", "query_builder", "query_artifact", True
    ),
    AiopsToolPolicyEntry(
        "SearchLog", "log_search", "log_hit", True, required_for_profile=True
    ),
    AiopsToolPolicyEntry(
        "DescribeLogContext", "log_context", "log_context", True, ("log_search",)
    ),
    AiopsToolPolicyEntry("QueryMetric", "metric_query", "metric", True),
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
                input_schema=_safe_schema_summary(tool),
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
        input_schema=_safe_schema_summary(tool),
        capability="knowledge_retrieval",
        artifact_kind="knowledge",
        read_only=True,
        dependencies=(),
        required_for_profile=False,
    )


def _safe_schema_summary(tool: BaseTool) -> dict[str, JsonValue]:
    raw = tool.args_schema
    if isinstance(raw, dict):
        schema = cast(Mapping[str, object], raw)
    elif isinstance(raw, type) and issubclass(raw, BaseModel):
        schema = cast(Mapping[str, object], raw.model_json_schema())
    else:
        return {"type": "object", "properties": {}, "required": []}
    raw_properties = schema.get("properties")
    properties: dict[str, JsonValue] = {}
    if isinstance(raw_properties, dict):
        typed_properties = cast(dict[object, object], raw_properties)
        for key, value in list(typed_properties.items())[:40]:
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            typed_value = cast(dict[object, object], value)
            field_type = typed_value.get("type")
            properties[key] = {
                "type": field_type if isinstance(field_type, str) else "unknown"
            }
    raw_required = schema.get("required")
    required: list[JsonValue] = []
    if isinstance(raw_required, list):
        for item in cast(list[object], raw_required):
            if isinstance(item, str):
                required.append(item)
            if len(required) == 40:
                break
    return {"type": "object", "properties": properties, "required": required}
