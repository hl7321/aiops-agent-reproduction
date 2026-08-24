"""AIOps 允许工具的输入校验与安全产物 adapter。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict

from super_ai.aiops.cls_tool_adapters import (
    DescribeLogContextInput,
    SearchLogInput,
    TextToSearchLogQueryInput,
    parse_describe_log_context_result,
    parse_search_log_result,
    parse_text_to_search_log_query_result,
    unwrap_mcp_payload,
)
from super_ai.aiops.tool_schema import tool_schema_properties, tool_schema_required
from super_ai.project_config import JsonValue

ArtifactKind = Literal["query_artifact", "log_hit", "log_context", "metric"]


@dataclass(frozen=True, slots=True)
class AdaptedToolOutput:
    kind: ArtifactKind
    payload: JsonValue


class MetricResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    series: list[dict[str, object]]


_CORE_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "texttosearchlogquery": TextToSearchLogQueryInput,
    "searchlog": SearchLogInput,
    "describelogcontext": DescribeLogContextInput,
}


def ensure_core_tool_schema_compatible(
    tool_name: str, schema: Mapping[str, object]
) -> None:
    """区分官方 Schema 升级与某次参数值校验失败。"""
    normalized = tool_name.casefold().replace("_", "").replace("-", "")
    model = _CORE_INPUT_MODELS.get(normalized)
    if model is None:
        return
    raw_properties = tool_schema_properties(schema)
    if not raw_properties:
        raise ValueError(f"{tool_name} runtime Schema 缺少 properties")
    local_schema = model.model_json_schema(by_alias=True)
    local_properties = local_schema.get("properties", {})
    allowed: set[str] = (
        set(cast(Mapping[str, object], local_properties))
        if isinstance(local_properties, Mapping)
        else set()
    )
    required = set(tool_schema_required(schema))
    unknown = sorted(required - allowed)
    if unknown:
        raise ValueError(f"{tool_name} runtime Schema 出现未知必填字段: {', '.join(unknown)}")


def validate_runtime_tool_input(
    tool: BaseTool, arguments: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """使用真实发现工具的 args schema，在联网调用前做第一层校验。"""
    schema_model = cast(type[BaseModel], tool.get_input_schema())
    validated = schema_model.model_validate(arguments)
    return cast(
        dict[str, JsonValue], validated.model_dump(mode="json", by_alias=True, exclude_none=True)
    )


def adapt_allowed_tool_output(tool_name: str, result: object) -> AdaptedToolOutput:
    normalized = tool_name.casefold().replace("_", "").replace("-", "")
    if normalized == "texttosearchlogquery":
        value = parse_text_to_search_log_query_result(result)
        return AdaptedToolOutput(
            "query_artifact", cast(JsonValue, value.model_dump(mode="json", by_alias=True))
        )
    if normalized == "searchlog":
        values = parse_search_log_result(result)
        return AdaptedToolOutput(
            "log_hit",
            cast(JsonValue, [item.model_dump(mode="json", by_alias=True) for item in values]),
        )
    if normalized == "describelogcontext":
        value = parse_describe_log_context_result(result)
        return AdaptedToolOutput(
            "log_context", cast(JsonValue, value.model_dump(mode="json", by_alias=True))
        )
    if normalized == "querymetric":
        payload = unwrap_mcp_payload(result)
        value = MetricResult.model_validate(payload)
        return AdaptedToolOutput("metric", cast(JsonValue, value.model_dump(mode="json")))
    raise ValueError(f"工具 {tool_name} 输出类型无法安全映射：没有 AIOps adapter")
