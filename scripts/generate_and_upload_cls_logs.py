# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "tencentcloud-cls-sdk-python==1.0.4",
# ]
# ///
"""生成有界结构化日志，并在人工确认目标后显式上传到腾讯 CLS。"""

from __future__ import annotations

import argparse
import importlib
import json
import secrets
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypeAlias, cast
from urllib.parse import urlsplit

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
LogRecord: TypeAlias = dict[str, str]
TraceIdFactory: TypeAlias = Callable[[int], str]

MAX_COUNT = 100
MAX_MESSAGE_CHARACTERS = 240
_MESSAGES = (
    "订单服务检测到短时延迟升高，等待值班人员确认。",
    "网关请求错误率超过演示阈值，已生成安全样例日志。",
    "库存服务健康检查出现波动，当前记录仅用于 AIOps 输入验证。",
)


class ClsLogUploadError(RuntimeError):
    """不泄露当前 CLS 凭据的安全脚本错误。"""


@dataclass(frozen=True, slots=True)
class ClsLogUploadSettings:
    endpoint: str
    region: str
    logset_id: str
    topic_id: str
    secret_id: str
    secret_key: str

    def require_upload_ready(self) -> ClsLogUploadSettings:
        values = (self.endpoint, self.region, self.topic_id, self.secret_id, self.secret_key)
        if any(not value.strip() for value in values):
            raise ClsLogUploadError("clsLogUpload 配置不完整")
        parsed = urlsplit(self.endpoint.strip())
        unsafe = (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or bool(parsed.query)
            or bool(parsed.fragment)
        )
        if unsafe:
            raise ClsLogUploadError("clsLogUpload endpoint 配置无效")
        return self


@dataclass(frozen=True, slots=True)
class UploadResult:
    count: int
    request_id: str


class _SdkResponse(Protocol):
    def get_request_id(self) -> str: ...


class _SdkClient(Protocol):
    def put_log_raw(self, topic_id: str, groups: object) -> _SdkResponse: ...


ClientFactory: TypeAlias = Callable[[str, str, str], _SdkClient]
GroupBuilder: TypeAlias = Callable[[Sequence[LogRecord]], object]


class _Content(Protocol):
    key: str
    value: str


class _ContentCollection(Protocol):
    def add(self) -> _Content: ...


class _Log(Protocol):
    time: int
    contents: _ContentCollection


class _LogCollection(Protocol):
    def add(self) -> _Log: ...


class _Tag(Protocol):
    key: str
    value: str


class _TagCollection(Protocol):
    def add(self) -> _Tag: ...


class _LogGroup(Protocol):
    filename: str
    source: str
    logTags: _TagCollection
    logs: _LogCollection


class _LogGroupCollection(Protocol):
    def add(self) -> _LogGroup: ...


class _LogGroupList(Protocol):
    logGroupList: _LogGroupCollection


class _LogGroupListFactory(Protocol):
    def __call__(self) -> _LogGroupList: ...


def deep_merge(base: Mapping[str, JsonValue], override: Mapping[str, JsonValue]) -> JsonObject:
    merged: JsonObject = deepcopy(dict(base))
    for key, value in override.items():
        current = merged.get(key)
        merged[key] = (
            deep_merge(current, value)
            if isinstance(current, dict) and isinstance(value, dict)
            else deepcopy(value)
        )
    return merged


def load_cls_log_upload_settings(
    project_path: Path, user_path: Path
) -> ClsLogUploadSettings:
    merged = deep_merge(_read_json_object(project_path), _read_json_object(user_path))
    raw = merged.get("clsLogUpload")
    if not isinstance(raw, dict):
        raise ClsLogUploadError("clsLogUpload 配置不完整")
    return ClsLogUploadSettings(
        endpoint=_string(raw, "endpoint"),
        region=_string(raw, "region"),
        logset_id=_string(raw, "logsetId"),
        topic_id=_string(raw, "topicId"),
        secret_id=_string(raw, "secretId"),
        secret_key=_string(raw, "secretKey"),
    )


def validate_count(count: int) -> int:
    if not 1 <= count <= MAX_COUNT:
        raise ClsLogUploadError("count 必须在 1..100 之间")
    return count


def generate_log_records(
    settings: ClsLogUploadSettings,
    count: int,
    *,
    now: datetime | None = None,
    trace_id_factory: TraceIdFactory | None = None,
) -> tuple[LogRecord, ...]:
    selected_count = validate_count(count)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    def random_trace_id(_index: int) -> str:
        return secrets.token_hex(16)

    make_trace_id: TraceIdFactory = trace_id_factory or random_trace_id
    records: list[LogRecord] = []
    for index in range(selected_count):
        records.append(
            {
                "region": settings.region,
                "service": ("gateway", "checkout", "inventory")[index % 3],
                "severity": ("info", "warning", "critical")[index % 3],
                "level": ("INFO", "WARN", "ERROR")[index % 3],
                "traceId": make_trace_id(index),
                "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                "message": _MESSAGES[index % len(_MESSAGES)][:MAX_MESSAGE_CHARACTERS],
            }
        )
    return tuple(records)


def build_log_group_list(records: Sequence[LogRecord]) -> object:
    module = importlib.import_module("tencentcloud.log.cls_pb2")
    factory = cast(_LogGroupListFactory, module.LogGroupList)
    groups = factory()
    group = groups.logGroupList.add()
    group.filename = "super-ai-generated.log"
    group.source = "super-ai-cls-log-generator"
    if records:
        tag = group.logTags.add()
        tag.key = "region"
        tag.value = records[0]["region"]
    for record in records:
        log = group.logs.add()
        parsed_time = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
        log.time = int(parsed_time.timestamp() * 1_000_000)
        for key, value in record.items():
            content = log.contents.add()
            content.key = key
            content.value = value
    return groups


def default_client_factory(endpoint: str, secret_id: str, secret_key: str) -> _SdkClient:
    module = importlib.import_module("tencentcloud.log.logclient")
    factory = cast(ClientFactory, module.LogClient)
    return factory(endpoint, secret_id, secret_key)


def upload_logs(
    settings: ClsLogUploadSettings,
    count: int,
    *,
    client_factory: ClientFactory = default_client_factory,
    group_builder: GroupBuilder = build_log_group_list,
    now: datetime | None = None,
    trace_id_factory: TraceIdFactory | None = None,
) -> UploadResult:
    selected_count = validate_count(count)
    settings.require_upload_ready()
    try:
        records = generate_log_records(
            settings,
            selected_count,
            now=now,
            trace_id_factory=trace_id_factory,
        )
        groups = group_builder(records)
        client = client_factory(settings.endpoint, settings.secret_id, settings.secret_key)
        response = client.put_log_raw(settings.topic_id, groups)
        return UploadResult(selected_count, response.get_request_id())
    except ClsLogUploadError:
        raise
    except Exception as error:
        safe = _redact(str(error), settings.secret_id, settings.secret_key)
        raise ClsLogUploadError(f"CLS 日志上传失败: {safe}") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="人工生成并上传安全的 CLS 结构化日志")
    parser.add_argument("--project-config", type=Path, default=Path("config/project.json"))
    parser.add_argument("--user-config", type=Path, default=Path("config/user.project.json"))
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--confirm-target", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_target:
        parser.error("真实 CLS 写入必须显式提供 --confirm-target")
    try:
        settings = load_cls_log_upload_settings(args.project_config, args.user_config)
        result = upload_logs(settings, args.count)
    except ClsLogUploadError as error:
        parser.error(str(error))
    print(f"uploaded={result.count} requestId={result.request_id}")
    return 0


def _read_json_object(path: Path) -> JsonObject:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ClsLogUploadError(f"无法读取有效 JSON 配置: {path}") from None
    return _normalize_object(raw)


def _normalize_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise ClsLogUploadError("配置文件顶层必须是 JSON object")
    normalized: JsonObject = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            raise ClsLogUploadError("JSON object key 必须是字符串")
        normalized[key] = _normalize_json(item)
    return normalized


def _normalize_json(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [_normalize_json(item) for item in cast(list[object], value)]
    if isinstance(value, dict):
        return _normalize_object(cast(dict[object, object], value))
    raise ClsLogUploadError("配置包含不支持的 JSON 值")


def _string(value: JsonObject, key: str) -> str:
    candidate = value.get(key, "")
    if not isinstance(candidate, str):
        raise ClsLogUploadError("clsLogUpload 配置字段类型无效")
    return candidate


def _redact(message: str, *secrets_to_hide: str) -> str:
    safe = message
    for secret in secrets_to_hide:
        if secret:
            safe = safe.replace(secret, "[redacted]")
    return safe


if __name__ == "__main__":
    raise SystemExit(main())
