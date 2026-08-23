"""向用户明确确认的 Alertmanager 发布十条 Java 电商合成告警。"""

from __future__ import annotations

import argparse
import importlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast
from urllib.parse import urlsplit


class AlertPublishError(RuntimeError):
    """不回显响应正文或目标敏感信息的发布错误。"""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes


@dataclass(frozen=True, slots=True)
class PublishResult:
    count: int
    target_host: str


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse: ...


class UrllibTransport:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(response.status, response.read(4096))
        except urllib.error.HTTPError as error:
            return HttpResponse(error.code, error.read(4096))


def publish_java_alerts(
    alertmanager_url: str,
    *,
    confirmed: bool,
    timeout_seconds: float,
    transport: HttpTransport | None = None,
    now: datetime | None = None,
) -> PublishResult:
    if not confirmed:
        raise AlertPublishError("真实告警发布必须显式确认目标")
    endpoint, target_host = _validate_target(alertmanager_url, timeout_seconds)
    alerts = _build_alerts(now)
    body = json.dumps(alerts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    active_transport = transport or UrllibTransport()
    try:
        response = active_transport.request(
            "POST",
            endpoint,
            headers={"Content-Type": "application/json"},
            body=body,
            timeout_seconds=timeout_seconds,
        )
    except Exception:
        raise AlertPublishError(
            f"Alertmanager 发布失败: targetHost={target_host}; transport error"
        ) from None
    if not 200 <= response.status < 300:
        raise AlertPublishError(
            f"Alertmanager 发布失败: targetHost={target_host}; HTTP {response.status}"
        )
    return PublishResult(count=len(alerts), target_host=target_host)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发布十条 Java 电商合成 Alertmanager 告警")
    parser.add_argument("--alertmanager-url", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--confirm-target", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = publish_java_alerts(
            args.alertmanager_url,
            confirmed=args.confirm_target,
            timeout_seconds=args.timeout_seconds,
        )
    except AlertPublishError as error:
        parser.error(str(error))
    print(f"published={result.count} targetHost={result.target_host}")
    return 0


def _validate_target(url: str, timeout_seconds: float) -> tuple[str, str]:
    if not 1 <= timeout_seconds <= 300:
        raise AlertPublishError("timeoutSeconds 必须在 1..300 之间")
    parsed = urlsplit(url.strip())
    target_host = parsed.hostname
    unsafe = (
        parsed.scheme not in {"http", "https"}
        or not target_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or bool(parsed.query)
        or bool(parsed.fragment)
    )
    if unsafe:
        raise AlertPublishError("Alertmanager 目标无效")
    assert target_host is not None
    return f"{url.rstrip('/')}/api/v2/alerts", target_host


def _build_alerts(now: datetime | None) -> tuple[dict[str, object], ...]:
    module_name = (
        "scripts.java_ecommerce_aiops_fixtures"
        if __package__
        else "java_ecommerce_aiops_fixtures"
    )
    module = importlib.import_module(module_name)
    builder = cast(
        Callable[..., tuple[dict[str, object], ...]],
        module.build_java_alertmanager_alerts,
    )
    return builder(now=now)


if __name__ == "__main__":
    raise SystemExit(main())
