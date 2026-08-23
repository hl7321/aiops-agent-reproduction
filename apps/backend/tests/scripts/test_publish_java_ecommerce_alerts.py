from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]


def _publisher() -> ModuleType:
    try:
        return importlib.import_module("scripts.publish_java_ecommerce_alerts")
    except ModuleNotFoundError:
        pytest.fail("缺少 Java 电商 Alertmanager 发布脚本")


class _FakeTransport:
    def __init__(self, status: int = 200, body: bytes = b"{}") -> None:
        self.status = status
        self.body = body
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> Any:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
                "timeout": timeout_seconds,
            }
        )
        return type("Response", (), {"status": self.status, "body": self.body})()


@pytest.mark.parametrize(
    "url",
    [
        "ftp://127.0.0.1:9093",
        "http:///missing-host",
        "http://user:password@127.0.0.1:9093",
        "http://127.0.0.1:9093/path",
        "http://127.0.0.1:9093?token=unsafe",
        "http://127.0.0.1:9093#fragment",
    ],
)
def test_rejects_unsafe_target_before_transport(url: str) -> None:
    module = _publisher()
    transport = _FakeTransport()

    with pytest.raises(module.AlertPublishError, match="Alertmanager 目标无效"):
        module.publish_java_alerts(
            url,
            confirmed=True,
            timeout_seconds=10,
            transport=transport,
        )

    assert transport.calls == []


@pytest.mark.parametrize("timeout", [0, -1, 301])
def test_rejects_timeout_outside_bounded_range(timeout: float) -> None:
    module = _publisher()
    transport = _FakeTransport()

    with pytest.raises(module.AlertPublishError, match="timeoutSeconds 必须在 1..300"):
        module.publish_java_alerts(
            "http://127.0.0.1:9093",
            confirmed=True,
            timeout_seconds=timeout,
            transport=transport,
        )

    assert transport.calls == []


def test_requires_explicit_confirmation_before_transport() -> None:
    module = _publisher()
    transport = _FakeTransport()

    with pytest.raises(module.AlertPublishError, match="必须显式确认"):
        module.publish_java_alerts(
            "http://127.0.0.1:9093",
            confirmed=False,
            timeout_seconds=10,
            transport=transport,
        )

    assert transport.calls == []


def test_posts_exactly_ten_correlated_v2_alerts() -> None:
    module = _publisher()
    transport = _FakeTransport()

    result = module.publish_java_alerts(
        "http://127.0.0.1:9093/",
        confirmed=True,
        timeout_seconds=12,
        transport=transport,
        now=datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc),
    )

    assert result.count == 10
    assert result.target_host == "127.0.0.1"
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "http://127.0.0.1:9093/api/v2/alerts"
    assert call["headers"] == {"Content-Type": "application/json"}
    assert call["timeout"] == 12
    payload = json.loads(call["body"])
    assert len(payload) == 10
    assert payload[0]["labels"] == {
        "alertname": "PaymentGatewayTimeoutHigh",
        "service": "payment-service",
        "severity": "critical",
        "incident_id": "java-ecom-001-payment-gateway-timeout",
        "trace_id": "4a000000000000000000000000000001",
        "sop_id": "sop-payment-gateway-timeout",
        "profile": "java-ecommerce",
    }


def test_non_2xx_fails_without_echoing_response_body() -> None:
    module = _publisher()
    transport = _FakeTransport(status=500, body=b"token=server-secret")

    with pytest.raises(module.AlertPublishError) as error:
        module.publish_java_alerts(
            "http://127.0.0.1:9093",
            confirmed=True,
            timeout_seconds=10,
            transport=transport,
        )

    assert "HTTP 500" in str(error.value)
    assert "server-secret" not in str(error.value)
    assert "发布成功" not in str(error.value)


def test_import_has_no_network_side_effect() -> None:
    script_path = str(ROOT / "scripts/publish_java_ecommerce_alerts.py")
    script = f"""
from unittest.mock import patch
import runpy
with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
    runpy.run_path({script_path!r}, run_name='safe_import')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
