"""通过真实认证 API 上传并索引十份 Java 电商合成 SOP。"""

from __future__ import annotations

import argparse
import importlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias, cast
from urllib.parse import quote, urlsplit

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class SopSeedError(RuntimeError):
    """不泄露密码、bearer 或响应正文的 SOP seed 错误。"""


@dataclass(frozen=True, slots=True)
class AiopsDemoSettings:
    backend_base_url: str
    email: str
    password: str
    poll_interval_seconds: float
    index_wait_seconds: float

    def validate(self) -> AiopsDemoSettings:
        parsed = urlsplit(self.backend_base_url.strip())
        unsafe = (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or bool(parsed.query)
            or bool(parsed.fragment)
        )
        if unsafe:
            raise SopSeedError("aiopsDemo backendBaseUrl 配置无效")
        if not self.email.strip() or not self.password:
            raise SopSeedError("aiopsDemo 认证配置不完整")
        if not 0 < self.poll_interval_seconds <= 60:
            raise SopSeedError("pollIntervalSeconds 必须在 0..60 之间")
        if not 0 < self.index_wait_seconds <= 3600:
            raise SopSeedError("indexWaitSeconds 必须在 0..3600 之间")
        return self


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes


@dataclass(frozen=True, slots=True)
class SeedResult:
    uploaded: int
    indexed: int
    knowledge_base_id: str


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HttpResponse: ...


class _Incident(Protocol):
    incident_id: str


class _SopDocument(Protocol):
    filename: str
    content: str


class UrllibTransport:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(response.status, response.read(1024 * 1024))
        except urllib.error.HTTPError as error:
            return HttpResponse(error.code, error.read(1024 * 1024))


def load_aiops_demo_settings(project_path: Path, user_path: Path) -> AiopsDemoSettings:
    merged = _deep_merge(_read_json_object(project_path), _read_json_object(user_path))
    raw = merged.get("aiopsDemo")
    if not isinstance(raw, dict):
        raise SopSeedError("aiopsDemo 配置不完整")
    return AiopsDemoSettings(
        backend_base_url=_string(raw, "backendBaseUrl"),
        email=_string(raw, "email"),
        password=_string(raw, "password"),
        poll_interval_seconds=_number(raw, "pollIntervalSeconds"),
        index_wait_seconds=_number(raw, "indexWaitSeconds"),
    ).validate()


def seed_java_sops(
    settings: AiopsDemoSettings,
    *,
    confirmed: bool,
    transport: HttpTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> SeedResult:
    if not confirmed:
        raise SopSeedError("真实 SOP 写入必须显式确认 backend 目标")
    selected = settings.validate()
    active_transport = transport or UrllibTransport()
    base_url = selected.backend_base_url.rstrip("/")
    timeout = min(30.0, selected.index_wait_seconds)
    login = _request_data(
        active_transport,
        "POST",
        f"{base_url}/auth/login",
        headers={"Content-Type": "application/json"},
        body=json.dumps(
            {"email": selected.email, "password": selected.password},
            separators=(",", ":"),
        ).encode(),
        timeout_seconds=timeout,
        stage="登录",
    )
    token = _required_string(login, "token", "登录")
    authorization = {"Authorization": f"Bearer {token}"}
    knowledge = _request_data(
        active_transport,
        "GET",
        f"{base_url}/knowledge-bases",
        headers=authorization,
        body=None,
        timeout_seconds=timeout,
        stage="读取默认知识库",
    )
    knowledge_base_id = _single_knowledge_base_id(knowledge)
    documents = _load_sop_documents()
    pending: list[tuple[str, str, str]] = []
    for incident_id, filename, content in documents:
        document_id = _upload_document(
            active_transport,
            base_url,
            authorization,
            knowledge_base_id,
            incident_id,
            filename,
            content,
            timeout,
        )
        task = _request_data(
            active_transport,
            "POST",
            (
                f"{base_url}/knowledge-bases/{quote(knowledge_base_id, safe='')}"
                f"/documents/{quote(document_id, safe='')}/index-tasks"
            ),
            headers=authorization,
            body=None,
            timeout_seconds=timeout,
            stage="创建索引任务",
            incident_id=incident_id,
        )
        pending.append(
            (incident_id, document_id, _required_string(task, "id", "创建索引任务"))
        )

    deadline = monotonic() + selected.index_wait_seconds
    indexed = 0
    for incident_id, document_id, task_id in pending:
        while True:
            if monotonic() >= deadline:
                raise SopSeedError(f"索引等待超时: incident={incident_id}")
            task = _request_data(
                active_transport,
                "GET",
                (
                    f"{base_url}/knowledge-bases/{quote(knowledge_base_id, safe='')}"
                    f"/documents/{quote(document_id, safe='')}/index-tasks/"
                    f"{quote(task_id, safe='')}"
                ),
                headers=authorization,
                body=None,
                timeout_seconds=timeout,
                stage="轮询索引任务",
                incident_id=incident_id,
            )
            status = _required_string(task, "status", "轮询索引任务")
            if status == "succeeded":
                indexed += 1
                break
            if status in {"failed", "cancelled"}:
                raise SopSeedError(f"索引失败: incident={incident_id}; status={status}")
            if status not in {"pending", "running"}:
                raise SopSeedError(f"索引状态无效: incident={incident_id}")
            sleep(selected.poll_interval_seconds)
    return SeedResult(len(documents), indexed, knowledge_base_id)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通过真实 API seed 十份 Java 电商 SOP")
    parser.add_argument("--project-config", type=Path, default=Path("config/project.json"))
    parser.add_argument("--user-config", type=Path, default=Path("config/user.project.json"))
    parser.add_argument("--confirm-target", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_target:
        parser.error("真实 SOP 写入必须显式提供 --confirm-target")
    try:
        settings = load_aiops_demo_settings(args.project_config, args.user_config)
        result = seed_java_sops(settings, confirmed=True)
    except SopSeedError as error:
        parser.error(str(error))
    host = urlsplit(settings.backend_base_url).hostname or "unknown"
    print(
        f"uploaded={result.uploaded} indexed={result.indexed} "
        f"knowledgeBaseId={result.knowledge_base_id} targetHost={host}"
    )
    return 0


def _upload_document(
    transport: HttpTransport,
    base_url: str,
    authorization: dict[str, str],
    knowledge_base_id: str,
    incident_id: str,
    filename: str,
    content: str,
    timeout_seconds: float,
) -> str:
    boundary = f"super-ai-{incident_id}"
    body = _multipart_body(boundary, filename, content)
    data = _request_data(
        transport,
        "POST",
        f"{base_url}/knowledge-bases/{quote(knowledge_base_id, safe='')}/documents",
        headers={
            **authorization,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        body=body,
        timeout_seconds=timeout_seconds,
        stage="上传 SOP",
        incident_id=incident_id,
    )
    return _required_string(data, "id", "上传 SOP")


def _multipart_body(boundary: str, filename: str, content: str) -> bytes:
    chunking = json.dumps(
        {"strategy": "fixed-character", "maxCharacters": 1200, "overlap": 200},
        separators=(",", ":"),
    )
    parts = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/markdown\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="chunkingConfig"\r\n\r\n'
        f"{chunking}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        "false\r\n"
        f"--{boundary}--\r\n"
    )
    return parts.encode("utf-8")


def _request_data(
    transport: HttpTransport,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: bytes | None,
    timeout_seconds: float,
    stage: str,
    incident_id: str | None = None,
) -> JsonObject:
    suffix = "" if incident_id is None else f": incident={incident_id}"
    try:
        response = transport.request(
            method,
            url,
            headers=headers,
            body=body,
            timeout_seconds=timeout_seconds,
        )
    except Exception:
        raise SopSeedError(f"{stage}请求失败{suffix}") from None
    if not 200 <= response.status < 300:
        raise SopSeedError(f"{stage}失败{suffix}; HTTP {response.status}")
    try:
        raw_payload: object = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SopSeedError(f"{stage}响应无效{suffix}") from None
    payload = _normalize_object(raw_payload)
    if payload.get("ok") is not True:
        raise SopSeedError(f"{stage}响应无效{suffix}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SopSeedError(f"{stage}响应 data 无效{suffix}")
    return data


def _single_knowledge_base_id(data: JsonObject) -> str:
    items = data.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise SopSeedError("默认知识库响应无效")
    return _required_string(items[0], "id", "默认知识库")


def _load_sop_documents() -> tuple[tuple[str, str, str], ...]:
    module_name = (
        "scripts.java_ecommerce_aiops_fixtures"
        if __package__
        else "java_ecommerce_aiops_fixtures"
    )
    module = importlib.import_module(module_name)
    incidents = cast(Sequence[_Incident], module.JAVA_ECOMMERCE_INCIDENTS)
    documents = cast(Sequence[_SopDocument], module.build_java_sop_documents())
    return tuple(
        (
            incident.incident_id,
            document.filename,
            document.content,
        )
        for incident, document in zip(incidents, documents, strict=True)
    )


def _read_json_object(path: Path) -> JsonObject:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SopSeedError(f"无法读取有效 JSON 配置: {path}") from None
    return _normalize_object(raw)


def _normalize_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise SopSeedError("配置或响应必须是 JSON object")
    normalized: JsonObject = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            raise SopSeedError("JSON object key 必须是字符串")
        normalized[key] = _normalize_json(item)
    return normalized


def _normalize_json(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [_normalize_json(item) for item in cast(list[object], value)]
    if isinstance(value, dict):
        return _normalize_object(cast(dict[object, object], value))
    raise SopSeedError("JSON 包含不支持的值")


def _deep_merge(base: Mapping[str, JsonValue], override: Mapping[str, JsonValue]) -> JsonObject:
    merged: JsonObject = deepcopy(dict(base))
    for key, value in override.items():
        current = merged.get(key)
        merged[key] = (
            _deep_merge(current, value)
            if isinstance(current, dict) and isinstance(value, dict)
            else deepcopy(value)
        )
    return merged


def _required_string(value: Mapping[str, JsonValue], key: str, stage: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise SopSeedError(f"{stage}缺少 {key}")
    return candidate


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    candidate = value.get(key, "")
    if not isinstance(candidate, str):
        raise SopSeedError("aiopsDemo 配置字段类型无效")
    return candidate


def _number(value: Mapping[str, JsonValue], key: str) -> float:
    candidate = value.get(key)
    if isinstance(candidate, bool) or not isinstance(candidate, int | float):
        raise SopSeedError("aiopsDemo 配置字段类型无效")
    return float(candidate)


if __name__ == "__main__":
    raise SystemExit(main())
