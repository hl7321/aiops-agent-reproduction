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
from super_ai.aiops.tool_policy import SERVER_PROVIDED_ARGUMENTS
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
    """使用真实发现工具的 args schema，在联网调用前做通用入参校验。

    旧实现走 `tool.get_input_schema().model_validate()`，但 MCP adapter 为工具生成的
    输入模型只有一个 `root` 字段（整份 schema 被包在 root 底下），实测对垃圾键、空对象
    与缺失必填一律放行——等于没有校验。这里改为直接按真实 schema 校验：
    拒绝未声明的键、要求必填齐全、检查值类型与声明过的枚举/范围。
    """
    return validate_tool_arguments(
        tool.name, _json_schema(tool), arguments
    )


def _json_schema(tool: BaseTool) -> Mapping[str, object]:
    schema = tool.args_schema
    if isinstance(schema, Mapping):
        return cast(Mapping[str, object], schema)
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return cast(Mapping[str, object], schema.model_json_schema())
    raise ValueError(f"工具 {tool.name} 缺少可验证的 JSON Schema")


def validate_tool_arguments(
    tool_name: str,
    schema: Mapping[str, object],
    arguments: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    """按真实 runtime schema 做通用入参校验，校验通过后原样返回参数。"""
    properties = tool_schema_properties(schema)
    if not properties:
        return dict(arguments)
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        raise ValueError(f"{tool_name} 参数包含未声明的键: {', '.join(unknown)}")
    missing = [
        key
        for key in tool_schema_required(schema)
        if key not in arguments or arguments[key] is None
    ]
    if missing:
        raise ValueError(f"{tool_name} 参数缺少必填字段: {', '.join(missing)}")
    for key, value in arguments.items():
        spec = properties.get(key)
        if isinstance(spec, Mapping):
            _validate_argument_value(tool_name, key, value, cast(Mapping[str, object], spec))
    return dict(arguments)


_JSON_TYPES: dict[str, tuple[type[object], ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def _validate_argument_value(
    tool_name: str, key: str, value: JsonValue, spec: Mapping[str, object]
) -> None:
    declared = spec.get("type")
    expected = _JSON_TYPES.get(declared) if isinstance(declared, str) else None
    if expected is not None:
        # bool 是 int 的子类，数值字段不接受布尔值。
        if isinstance(value, bool) and "boolean" not in (
            declared if isinstance(declared, str) else ""
        ):
            raise ValueError(f"{tool_name}.{key} 类型应为 {declared}")
        if not isinstance(value, expected):
            raise ValueError(f"{tool_name}.{key} 类型应为 {declared}")
    enum_values = spec.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        raise ValueError(f"{tool_name}.{key} 取值必须属于 {enum_values}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            raise ValueError(f"{tool_name}.{key} 不得小于 {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            raise ValueError(f"{tool_name}.{key} 不得大于 {maximum}")


def inject_server_provided_arguments(
    tool_name: str,
    schema: Mapping[str, object],
    arguments: Mapping[str, JsonValue],
    *,
    region: str,
    topic_id: str,
) -> dict[str, JsonValue]:
    """注入服务端权威字段，并按 schema 过滤掉未声明的键。"""
    allowed = set(tool_schema_properties(schema))
    if not allowed:
        return dict(arguments)
    normalized = {key: value for key, value in arguments.items() if key in allowed}
    injected = {"Region": region.strip(), "TopicId": topic_id.strip()}
    for key, configured in injected.items():
        if key in allowed and key in SERVER_PROVIDED_ARGUMENTS and configured:
            normalized[key] = configured
    return normalized


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
    # 其余真实发现的只读工具：没有专属 adapter，产物统一按中间产物落库——
    # 后续步骤与 Replanner 能用上它的结果，但它不参与证据充分性判断。
    # 这样既不把工具排除在计划之外，也不让通用字符串序列化冒充证据。
    payload = unwrap_mcp_payload(result)
    if not isinstance(payload, dict):
        payload = {"value": cast(JsonValue, payload)}
    return AdaptedToolOutput("query_artifact", cast(JsonValue, payload))
