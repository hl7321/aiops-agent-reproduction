from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import upgrade_database


@asynccontextmanager
async def _client(tmp_path: Path) -> AsyncGenerator[httpx.AsyncClient, None]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'api.sqlite3'}"
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url),
        worker_settings=WorkerSettings(poll_interval_seconds=60),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


async def _token(client: httpx.AsyncClient, email: str) -> str:
    await client.post("/auth/register", json={"email": email, "password": "secure-password"})
    response = await client.post(
        "/auth/login", json={"email": email, "password": "secure-password"}
    )
    return str(response.json()["data"]["token"])


def _body() -> dict[str, object]:
    return {
        "query": "排查错误率",
        "alerts": [
            {
                "alertName": "HighErrorRate",
                "service": "checkout",
                "severity": "critical",
                "status": "firing",
                "startsAt": "2026-08-20T00:00:00Z",
                "labels": {},
                "annotations": {},
                "source": {"name": "prometheus", "type": "prometheus-v1"},
                "rawContext": {},
            }
        ],
    }


async def test_create_list_detail_evidence_chain_and_owner_scope(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        owner = await _token(client, "owner@example.com")
        other = await _token(client, "other@example.com")
        headers = {"Authorization": f"Bearer {owner}", "X-Request-ID": "req-aiops"}
        created = await client.post("/aiops/diagnostics", json=_body(), headers=headers)
        task_id = created.json()["data"]["task"]["id"]
        listed = await client.get("/aiops/diagnostics", headers=headers)
        detail = await client.get(f"/aiops/diagnostics/{task_id}", headers=headers)
        chain = await client.get(f"/aiops/diagnostics/{task_id}/evidence-chain", headers=headers)
        hidden = await client.get(
            f"/aiops/diagnostics/{task_id}",
            headers={"Authorization": f"Bearer {other}"},
        )
    assert created.status_code == 202
    assert created.headers["X-Request-ID"] == "req-aiops"
    assert created.json()["data"]["task"]["status"] == "accepted"
    assert created.json()["data"]["backgroundJob"]["resourceId"] == task_id
    assert listed.json()["data"]["items"][0]["id"] == task_id
    assert detail.json()["data"]["backgroundJob"]["status"] == "queued"
    assert chain.json()["data"]["evidence"][0]["kind"] == "alert"
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "BUSINESS_RESOURCE_NOT_FOUND"


async def test_api_requires_authentication(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.get("/aiops/diagnostics")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


async def test_create_from_manual_query_without_alert_or_context(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        token = await _token(client, "manual@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = await client.post(
            "/aiops/diagnostics",
            json={"query": " 手工排查 checkout 延迟 ", "alerts": []},
            headers=headers,
        )
        rejected = await client.post(
            "/aiops/diagnostics", json={"query": " ", "alerts": []}, headers=headers
        )
    assert created.status_code == 202
    assert created.json()["data"]["task"]["query"] == "手工排查 checkout 延迟"
    assert created.json()["data"]["task"]["alerts"] == []
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_REQUEST_INVALID"


async def test_generic_background_cancel_and_retry_reconcile_diagnostic_status(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as client:
        token = await _token(client, "retry@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = await client.post("/aiops/diagnostics", json=_body(), headers=headers)
        task_id = created.json()["data"]["task"]["id"]
        job_id = created.json()["data"]["backgroundJob"]["id"]
        cancelled = await client.post(f"/background-jobs/{job_id}:cancel", headers=headers)
        cancelled_detail = await client.get(f"/aiops/diagnostics/{task_id}", headers=headers)
        retried = await client.post(f"/background-jobs/{job_id}:retry", headers=headers)
        retried_detail = await client.get(f"/aiops/diagnostics/{task_id}", headers=headers)
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled_detail.json()["data"]["task"]["status"] == "cancelled"
    assert retried.json()["data"]["status"] == "queued"
    assert retried_detail.json()["data"]["task"]["status"] == "accepted"
