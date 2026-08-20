from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

from super_ai.alerts.dependencies import get_alert_aggregator
from super_ai.alerts.models import ActiveAlertRecord, AlertSourceRecord
from super_ai.api_responses import AppError
from super_ai.app import create_app
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import upgrade_database


class FakeAggregator:
    def __init__(
        self, result: tuple[ActiveAlertRecord, ...] = (), error: AppError | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    async def list_active(self) -> tuple[ActiveAlertRecord, ...]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


async def _token(client: httpx.AsyncClient) -> str:
    await client.post(
        "/auth/register",
        json={"email": "alerts@example.com", "password": "secure-password"},
    )
    login = await client.post(
        "/auth/login",
        json={"email": "alerts@example.com", "password": "secure-password"},
    )
    return str(login.json()["data"]["token"])


@asynccontextmanager
async def _client(
    tmp_path: Path, aggregator: FakeAggregator
) -> AsyncGenerator[httpx.AsyncClient, None]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'alerts-api.sqlite3'}"
    await upgrade_database(database_url)
    app = create_app(DatabaseSettings(url=database_url))
    app.dependency_overrides[get_alert_aggregator] = lambda: aggregator
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


async def test_unauthenticated_request_does_not_read_sources(tmp_path: Path) -> None:
    aggregator = FakeAggregator()
    async with _client(tmp_path, aggregator) as client:
        response = await client.get("/aiops/alerts/active")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    assert aggregator.calls == 0


async def test_authenticated_request_returns_items_only_envelope(tmp_path: Path) -> None:
    aggregator = FakeAggregator(
        (
            ActiveAlertRecord(
                alert_name="HighErrorRate",
                service="checkout",
                severity="critical",
                status="firing",
                starts_at="2026-08-20T00:00:00Z",
                labels={"alertname": "HighErrorRate"},
                annotations={"summary": "错误率升高"},
                source=AlertSourceRecord("prometheus-main", "prometheus-v1"),
                raw_context={"state": "firing"},
            ),
        )
    )
    async with _client(tmp_path, aggregator) as client:
        token = await _token(client)
        response = await client.get(
            "/aiops/alerts/active",
            headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req-alerts"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-alerts"
    assert response.json() == {
        "ok": True,
        "data": {
            "items": [
                {
                    "alertName": "HighErrorRate",
                    "service": "checkout",
                    "severity": "critical",
                    "status": "firing",
                    "startsAt": "2026-08-20T00:00:00Z",
                    "labels": {"alertname": "HighErrorRate"},
                    "annotations": {"summary": "错误率升高"},
                    "source": {"name": "prometheus-main", "type": "prometheus-v1"},
                    "rawContext": {"state": "firing"},
                }
            ]
        },
        "meta": {"requestId": "req-alerts"},
    }
    assert "providerStatuses" not in response.text
    assert aggregator.calls == 1


async def test_all_sources_failure_returns_shared_503(tmp_path: Path) -> None:
    aggregator = FakeAggregator(error=AppError("SYSTEM_ALERT_SOURCES_UNAVAILABLE"))
    async with _client(tmp_path, aggregator) as client:
        token = await _token(client)
        response = await client.get(
            "/aiops/alerts/active", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "SYSTEM_ALERT_SOURCES_UNAVAILABLE",
        "category": "system",
        "httpStatus": 503,
        "message": "活跃告警来源暂时不可用",
    }


def test_active_alert_openapi_is_bearer_protected() -> None:
    operation = create_app().openapi()["paths"]["/aiops/alerts/active"]["get"]
    assert operation["operationId"] == "getActiveAlerts"
    assert operation["security"] == [{"BearerAuth": []}]
    assert {"401", "403", "503"}.issubset(operation["responses"])
