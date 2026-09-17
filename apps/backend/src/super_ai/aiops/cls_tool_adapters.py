"""官方 CLS MCP 核心工具的显式输入与输出 adapter。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Annotated, Literal, cast

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from super_ai.aiops.planning import SearchLogQueryDefaults
from super_ai.project_config import JsonValue

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ClsInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TextToSearchLogQueryInput(ClsInputModel):
    region: NonEmpty = Field(alias="Region")
    topic_id: NonEmpty = Field(alias="TopicId")
    prompt: NonEmpty = Field(
        alias="Text", validation_alias=AliasChoices("Text", "Prompt", "Question")
    )


class SearchLogInput(ClsInputModel):
    region: NonEmpty = Field(alias="Region")
    topic_id: NonEmpty = Field(alias="TopicId")
    from_ms: int = Field(alias="From", ge=0)
    to_ms: int = Field(alias="To", ge=0)
    query: NonEmpty = Field(alias="Query", max_length=12_000)
    limit: int = Field(default=100, alias="Limit", ge=1, le=100)
    sort: Literal["asc", "desc"] = Field(default="desc", alias="Sort")
    offset: int = Field(default=0, alias="Offset", ge=0)
    sampling_rate: float = Field(default=1, alias="SamplingRate", ge=0, le=1)

    @model_validator(mode="after")
    def validate_range(self) -> SearchLogInput:
        if self.from_ms >= self.to_ms:
            raise ValueError("From 必须小于 To")
        return self


class DescribeLogContextInput(ClsInputModel):
    region: NonEmpty = Field(alias="Region")
    topic_id: NonEmpty = Field(alias="TopicId")
    time: int = Field(alias="Time", ge=0)
    pkg_id: NonEmpty = Field(alias="PkgId")
    pkg_log_id: int = Field(alias="PkgLogId", ge=0)
    prev_logs: int = Field(default=10, alias="PrevLogs", ge=0, le=100)
    next_logs: int = Field(default=10, alias="NextLogs", ge=0, le=100)


class QueryArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: NonEmpty = Field(alias="Query", validation_alias=AliasChoices("Query", "query"))


class ClsSearchLogHit(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    time: int = Field(alias="Time", ge=0)
    pkg_id: NonEmpty | None = Field(default=None, alias="PkgId")
    pkg_log_id: int | None = Field(default=None, alias="PkgLogId", ge=0)
    log_json: NonEmpty = Field(alias="LogJson")

    @field_validator("pkg_id", mode="before")
    @classmethod
    def normalize_empty_pkg_id(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("pkg_log_id", mode="before")
    @classmethod
    def normalize_pkg_log_id(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.isdecimal():
                return int(stripped)
        return value

    @property
    def has_context_locator(self) -> bool:
        return self.pkg_id is not None and self.pkg_log_id is not None


class ClsContextLogLine(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    time: int = Field(alias="Time", validation_alias=AliasChoices("Time", "BTime"), ge=0)
    log_json: NonEmpty = Field(
        alias="LogJson", validation_alias=AliasChoices("LogJson", "Content")
    )


class DescribeLogContextResult(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    context_logs: list[ClsContextLogLine] = Field(alias="LogContextInfos")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_shape(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        typed = cast(dict[str, object], value)
        if "LogContextInfos" in typed:
            return typed
        previous = typed.get("PrevLogs", [])
        current = typed.get("CurrentLog")
        following = typed.get("NextLogs", [])
        if not isinstance(previous, list) or not isinstance(following, list):
            return typed
        combined: list[object] = [*cast(list[object], previous)]
        if current is not None:
            combined.append(current)
        combined.extend(cast(list[object], following))
        return {"LogContextInfos": combined}

    @property
    def ordered_logs(self) -> tuple[ClsContextLogLine, ...]:
        return tuple(self.context_logs)


def parse_text_to_search_log_query_result(result: object) -> QueryArtifact:
    payload = unwrap_mcp_payload(result)
    if isinstance(payload, dict):
        typed = cast(dict[str, JsonValue], payload)
        nested = typed.get("data")
        payload = nested if isinstance(nested, dict) else typed
        choices = typed.get("Choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("Message")
            if isinstance(message, dict):
                content = message.get("Content")
                if isinstance(content, str) and content.strip():
                    payload = {"Query": _extract_generated_query(content)}
    elif isinstance(payload, str) and payload.strip():
        payload = {"Query": _extract_generated_query(payload)}
    if isinstance(payload, dict):
        typed_payload = cast(dict[str, JsonValue], payload)
        raw_query = typed_payload.get("Query", typed_payload.get("query"))
        if isinstance(raw_query, str):
            payload = {"Query": _extract_generated_query(raw_query)}
    try:
        return QueryArtifact.model_validate(payload)
    except Exception as error:
        raise ValueError("TextToSearchLogQuery 输出无法解析") from error


def parse_search_log_result(result: object) -> tuple[ClsSearchLogHit, ...]:
    payload = unwrap_mcp_payload(result)
    if isinstance(payload, dict):
        typed = cast(dict[str, JsonValue], payload)
        for key in ("Results", "results", "Records", "records", "data"):
            candidate = typed.get(key)
            if isinstance(candidate, list):
                payload = candidate
                break
    if not isinstance(payload, list):
        raise ValueError("SearchLog 输出无法解析为原始日志列表")
    try:
        hits = tuple(ClsSearchLogHit.model_validate(item) for item in payload)
    except Exception as error:
        message = str(error)
        label = "PkgId" if "PkgId" in message or "pkg_id" in message else "字段"
        raise ValueError(f"SearchLog 输出缺少或包含无效 {label}") from error
    return hits


def parse_describe_log_context_result(result: object) -> DescribeLogContextResult:
    try:
        payload = unwrap_mcp_payload(result)
        if isinstance(payload, dict):
            typed = cast(dict[str, JsonValue], payload)
            nested = typed.get("data")
            payload = nested if isinstance(nested, dict) else typed
        return DescribeLogContextResult.model_validate(payload)
    except Exception as error:
        raise ValueError("DescribeLogContext 输出无法解析") from error


def build_describe_log_context_input(
    hit: ClsSearchLogHit,
    defaults: SearchLogQueryDefaults,
    *,
    proposed: Mapping[str, JsonValue],
) -> DescribeLogContextInput:
    region = defaults.region.strip()
    topic_id = defaults.topic_id.strip()
    if not region or not topic_id:
        raise ValueError("clsLogUpload region/topicId 配置缺失")
    if not hit.has_context_locator:
        raise ValueError("SearchLog 命中缺少 DescribeLogContext 定位字段")
    prev_logs = proposed.get("PrevLogs", proposed.get("prevLogs", 10))
    next_logs = proposed.get("NextLogs", proposed.get("nextLogs", 10))
    return DescribeLogContextInput.model_validate(
        {
            "Region": region,
            "TopicId": topic_id,
            "Time": hit.time,
            "PkgId": hit.pkg_id,
            "PkgLogId": hit.pkg_log_id,
            "PrevLogs": prev_logs,
            "NextLogs": next_logs,
        }
    )


def build_text_to_search_log_query_input(
    proposed: Mapping[str, JsonValue],
    defaults: SearchLogQueryDefaults,
    *,
    fallback_prompt: str,
) -> TextToSearchLogQueryInput:
    region = defaults.region.strip()
    topic_id = defaults.topic_id.strip()
    if not region or not topic_id:
        raise ValueError("clsLogUpload region/topicId 配置缺失")
    prompt = proposed.get(
        "Text", proposed.get("Prompt", proposed.get("prompt", fallback_prompt))
    )
    return TextToSearchLogQueryInput.model_validate(
        {"Region": region, "TopicId": topic_id, "Text": prompt}
    )


def unwrap_mcp_payload(result: object) -> JsonValue:
    if isinstance(result, BaseModel):
        return cast(JsonValue, result.model_dump(mode="json", by_alias=True))
    if isinstance(result, str):
        return _parse_json_text(result)
    if isinstance(result, list):
        for block in cast(list[object], result):
            if isinstance(block, dict):
                text = cast(dict[str, object], block).get("text")
                if isinstance(text, str):
                    return _parse_json_text_or_value(text)
        return cast(JsonValue, result)
    if not isinstance(result, dict):
        raise ValueError("MCP 输出不是可解析的 JSON/content wrapper")
    typed = cast(dict[object, object], result)
    for key in ("structuredContent", "structured_content", "artifact"):
        candidate = typed.get(key)
        if candidate is not None:
            return unwrap_mcp_payload(candidate)
    content = typed.get("content")
    if isinstance(content, list):
        for block in cast(list[object], content):
            if isinstance(block, dict):
                text = cast(dict[object, object], block).get("text")
                if isinstance(text, str):
                    return _parse_json_text(text)
    return cast(JsonValue, result)


def _parse_json_text(value: str) -> JsonValue:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("MCP text content 不是 JSON") from error
    if parsed is None or isinstance(parsed, (bool, int, float, str, list, dict)):
        return cast(JsonValue, parsed)
    raise ValueError("MCP text content JSON 类型无效")


def _parse_json_text_or_value(value: str) -> JsonValue:
    try:
        return _parse_json_text(value)
    except ValueError:
        if value.strip():
            return value.strip()
        raise


def _extract_generated_query(value: str) -> str:
    fenced = re.findall(r"```(?:sql|cql)?\s*(.*?)```", value, flags=re.IGNORECASE | re.DOTALL)
    if len(fenced) > 1:
        raise ValueError("TextToSearchLogQuery 返回了多个查询代码块")
    # 工具返回把生成的 CQL 嵌在 JSON 字符串里，围栏代码块会连同转义序列一起被取出；
    # 必须在切分与判空之前还原，否则字面量 \n、\" 会被当成查询语法送进 SearchLog。
    query = _unescape_generated_query(fenced[0] if fenced else value).strip()
    query = re.split(r"\s+\|\s+(?=SELECT\b)", query, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if not query:
        raise ValueError("TextToSearchLogQuery 返回了空查询")
    return query


_JSON_ESCAPE_LITERALS: Mapping[str, str] = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "b": "\b",
    "f": "\f",
    '"': '"',
    "\\": "\\",
    "/": "/",
}
_ESCAPE_SEQUENCE = re.compile(r"\\(.)")


def _unescape_generated_query(value: str) -> str:
    """把 JSON 转义文本还原成可直接执行的查询。

    策略是三段式：

    1. 文本里没有反斜杠时原样返回；
    2. 有反斜杠时先尝试按 JSON 字符串严格解码，能解出来就用解码结果；
    3. 严格解码失败时退化为逐序列替换，只还原已知转义，保留 `\\d` 这类合法反斜杠。

    第 3 步是必需的：查询里本来就可能出现 CLS 自己的反斜杠（例如正则片段），
    严格解码会失败，此处绝不能抛错把整次诊断打挂。
    """
    if "\\" not in value:
        return value
    try:
        decoded = json.loads(f'"{value}"')
    except (TypeError, ValueError):
        decoded = None
    if isinstance(decoded, str) and decoded:
        return decoded
    return _ESCAPE_SEQUENCE.sub(
        lambda match: _JSON_ESCAPE_LITERALS.get(match.group(1), match.group(0)), value
    )
