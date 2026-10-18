"""向用户明确确认的 Alertmanager 发布十条 Java 电商合成告警。"""

from __future__ import annotations

import argparse
import importlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    skipped: bool = False


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
                return HttpResponse(response.status, response.read(65536))
        except urllib.error.HTTPError as error:
            return HttpResponse(error.code, error.read(65536))


def publish_java_alerts(
    alertmanager_url: str,
    *,
    confirmed: bool,
    timeout_seconds: float,
    transport: HttpTransport | None = None,
    now: datetime | None = None,
    active_for: timedelta = timedelta(hours=2),
    ensure: bool = False,
) -> PublishResult:
    if not confirmed:
        raise AlertPublishError("真实告警发布必须显式确认目标")
    endpoint, target_host = _validate_target(alertmanager_url, timeout_seconds)
    active_transport = transport or UrllibTransport()
    if ensure:
        existing = active_transport.request(
            "GET",
            endpoint,
            headers={},
            body=b"",
            timeout_seconds=timeout_seconds,
        )
        if 200 <= existing.status < 300:
            try:
                parsed = json.loads(existing.body.decode("utf-8"))
                if isinstance(parsed, list) and len(parsed) >= 10:
                    return PublishResult(count=0, target_host=target_host, skipped=True)
            except (UnicodeDecodeError, json.JSONDecodeError):
                # 读不懂现有告警就继续发布，确保 ensure 不会把演示卡死。
                pass
    alerts = _build_alerts(now, active_for=active_for)
    body = json.dumps(alerts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
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
    parser.add_argument(
        "--starts-at",
        help="可选：带时区的 ISO 8601 告警开始时间（支持 Z）",
    )
    parser.add_argument(
        "--active-days",
        type=float,
        help="可选：告警有效期（天）；不填时保持 2 小时",
    )
    parser.add_argument("--ensure", action="store_true", help="已有 10 条活跃告警时跳过发布")
    parser.add_argument("--confirm-target", action="store_true")
    args = parser.parse_args(argv)
    try:
        starts_at = _parse_starts_at(args.starts_at) if args.starts_at else None
        if args.active_days is not None and not 0 < args.active_days <= 365:
            raise AlertPublishError("activeDays 必须在 0..365 之间")
        active_for = (
            timedelta(days=args.active_days)
            if args.active_days is not None
            else timedelta(hours=2)
        )
        result = publish_java_alerts(
            args.alertmanager_url,
            confirmed=args.confirm_target,
            timeout_seconds=args.timeout_seconds,
            now=starts_at,
            active_for=active_for,
            ensure=args.ensure,
        )
    except AlertPublishError as error:
        parser.error(str(error))
    if result.skipped:
        print(f"alreadyActive=10 skipped=true targetHost={result.target_host}")
    else:
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


def _parse_starts_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise AlertPublishError("startsAt 不是可解析的 ISO 8601 时间") from error
    if parsed.tzinfo is None:
        raise AlertPublishError("startsAt 必须包含时区")
    return parsed.astimezone(timezone.utc)


def _build_alerts(
    now: datetime | None,
    *,
    active_for: timedelta,
) -> tuple[dict[str, object], ...]:
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
    return builder(now=now, active_for=active_for)


if __name__ == "__main__":
    raise SystemExit(main())
