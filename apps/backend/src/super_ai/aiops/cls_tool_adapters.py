"""官方 CLS MCP 核心工具的显式输入与输出 adapter。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Annotated, cast

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
        alias="Prompt", validation_alias=AliasChoices("Prompt", "Question", "Text")
    )


class SearchLogInput(ClsInputModel):
    region: NonEmpty = Field(alias="Region")
    topic_id: NonEmpty = Field(alias="TopicId")
    from_ms: int = Field(alias="From", ge=0)
    to_ms: int = Field(alias="To", ge=0)
    query: NonEmpty = Field(alias="Query", max_length=12_000)
    limit: int = Field(default=100, alias="Limit", ge=1, le=100)

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
    pkg_log_id: int | NonEmpty = Field(alias="PkgLogId")
    prev_logs: int = Field(default=10, alias="PrevLogs", ge=0, le=100)
    next_logs: int = Field(default=10, alias="NextLogs", ge=0, le=100)


class QueryArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: NonEmpty = Field(alias="Query", validation_alias=AliasChoices("Query", "query"))


class ClsSearchLogHit(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    time: int = Field(alias="Time", ge=0)
    pkg_id: NonEmpty = Field(alias="PkgId")
    pkg_log_id: int | NonEmpty = Field(alias="PkgLogId")
    log_json: NonEmpty = Field(alias="LogJson")

    @field_validator("pkg_log_id")
    @classmethod
    def reject_negative_pkg_log_id(cls, value: int | str) -> int | str:
        if isinstance(value, int) and value < 0:
            raise ValueError("PkgLogId 不得为负数")
        return value


class ClsContextLogLine(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    time: int = Field(alias="Time", ge=0)
    log_json: NonEmpty = Field(alias="LogJson")


class DescribeLogContextResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_logs: list[ClsContextLogLine] = Field(alias="PrevLogs")
    current_log: ClsContextLogLine = Field(alias="CurrentLog")
    next_logs: list[ClsContextLogLine] = Field(alias="NextLogs")

    @property
    def ordered_logs(self) -> tuple[ClsContextLogLine, ...]:
        return (*self.previous_logs, self.current_log, *self.next_logs)


def parse_text_to_search_log_query_result(result: object) -> QueryArtifact:
    payload = unwrap_mcp_payload(result)
    if isinstance(payload, dict):
        typed = cast(dict[str, JsonValue], payload)
        nested = typed.get("data")
        payload = nested if isinstance(nested, dict) else typed
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
    prompt = proposed.get("Prompt", proposed.get("prompt", fallback_prompt))
    return TextToSearchLogQueryInput.model_validate(
        {"Region": region, "TopicId": topic_id, "Prompt": prompt}
    )


def unwrap_mcp_payload(result: object) -> JsonValue:
    if isinstance(result, BaseModel):
        return cast(JsonValue, result.model_dump(mode="json", by_alias=True))
    if isinstance(result, str):
        return _parse_json_text(result)
    if isinstance(result, list):
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
