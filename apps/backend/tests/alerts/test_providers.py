from __future__ import annotations

import httpx
import pytest

from super_ai.alerts.dependencies import create_alert_http_client
from super_ai.alerts.providers import (
    AlertmanagerV2AlertProvider,
    AlertProviderError,
    PrometheusV1AlertProvider,
)
from super_ai.alerts.settings import AlertSourceSettings


async def test_prometheus_provider_normalizes_official_active_alert_payload() -> None:
    raw_alert: dict[str, object] = {
        "activeAt": "2026-08-20T12:34:56+08:00",
        "annotations": {"summary": "错误率升高"},
        "labels": {
            "alertname": "HighErrorRate",
            "service": "checkout",
            "severity": "critical",
        },
        "state": "firing",
        "value": "1e+00",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/prometheus/api/v1/alerts"
        return httpx.Response(200, json={"status": "success", "data": {"alerts": [raw_alert]}})

    source = AlertSourceSettings.model_validate(
        {
            "name": "prometheus-main",
            "type": "prometheus-v1",
            "baseUrl": "https://monitor.example.test/prometheus",
            "timeoutSeconds": 5,
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        alerts = await PrometheusV1AlertProvider(source, client).fetch_active_alerts()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_name == "HighErrorRate"
    assert alert.service == "checkout"
    assert alert.severity == "critical"
    assert alert.status == "firing"
    assert alert.starts_at == "2026-08-20T04:34:56Z"
    assert alert.source.name == "prometheus-main"
    assert alert.source.source_type == "prometheus-v1"
    assert alert.raw_context == raw_alert


async def test_prometheus_provider_rejects_unsafe_invalid_payload() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="password-secret and private response")

    source = AlertSourceSettings.model_validate(
        {
            "name": "prometheus-main",
            "type": "prometheus-v1",
            "baseUrl": "https://monitor.example.test",
            "timeoutSeconds": 5,
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AlertProviderError, match="prometheus-main 告警请求失败") as error:
            await PrometheusV1AlertProvider(source, client).fetch_active_alerts()

    assert "password-secret" not in str(error.value)
    assert "private response" not in str(error.value)


@pytest.mark.parametrize(
    ("native_status", "expected_status"),
    [("active", "firing"), ("suppressed", "suppressed"), ("unprocessed", "unprocessed")],
)
async def test_alertmanager_provider_maps_status_and_preserves_raw_context(
    native_status: str, expected_status: str
) -> None:
    raw_alert: dict[str, object] = {
        "annotations": {"description": "实例不可达"},
        "endsAt": "2026-08-21T00:00:00Z",
        "fingerprint": "fingerprint-1",
        "receivers": [{"name": "oncall"}],
        "startsAt": "2026-08-20T01:02:03Z",
        "status": {
            "state": native_status,
            "silencedBy": [],
            "inhibitedBy": [],
            "mutedBy": [],
        },
        "updatedAt": "2026-08-20T01:03:00Z",
        "generatorURL": "https://prometheus.example.test/graph",
        "labels": {"alertname": "InstanceDown", "job": "node", "severity": "warning"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/alertmanager/api/v2/alerts"
        assert request.url.params.get("active") == "true"
        return httpx.Response(200, json=[raw_alert])

    source = AlertSourceSettings.model_validate(
        {
            "name": "alertmanager-local",
            "type": "alertmanager-v2",
            "baseUrl": "https://alerts.example.test/alertmanager",
            "timeoutSeconds": 5,
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        alerts = await AlertmanagerV2AlertProvider(source, client).fetch_active_alerts()

    alert = alerts[0]
    assert alert.alert_name == "InstanceDown"
    assert alert.service is None
    assert alert.severity == "warning"
    assert alert.status == expected_status
    assert alert.starts_at == "2026-08-20T01:02:03Z"
    assert alert.source.source_type == "alertmanager-v2"
    assert alert.raw_context == raw_alert


async def test_alertmanager_provider_rejects_unknown_state() -> None:
    raw_alert = {
        "annotations": {},
        "startsAt": "2026-08-20T01:02:03Z",
        "status": {"state": "mystery"},
        "labels": {"alertname": "BadState"},
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[raw_alert])

    source = AlertSourceSettings.model_validate(
        {
            "name": "alertmanager-local",
            "type": "alertmanager-v2",
            "baseUrl": "https://alerts.example.test",
            "timeoutSeconds": 5,
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AlertProviderError, match="alertmanager-local 告警请求失败"):
            await AlertmanagerV2AlertProvider(source, client).fetch_active_alerts()


async def test_request_scoped_client_applies_basic_auth_and_timeout() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        return httpx.Response(200, json={"status": "success", "data": {"alerts": []}})

    source = AlertSourceSettings.model_validate(
        {
            "name": "authenticated",
            "type": "prometheus-v1",
            "baseUrl": "https://monitor.example.test",
            "timeoutSeconds": 7,
            "basicAuth": {"username": "reader", "password": "private"},
        }
    )
    client = create_alert_http_client(source, transport=httpx.MockTransport(handler))
    async with client:
        assert client.timeout.read == 7
        assert await PrometheusV1AlertProvider(source, client).fetch_active_alerts() == ()

    assert captured["authorization"].startswith("Basic ")
    assert "private" not in captured["authorization"]
