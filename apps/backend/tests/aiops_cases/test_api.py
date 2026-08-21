from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

from super_ai.aiops.cases.service import DiagnosisCasePersistor
from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticRepository
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


@asynccontextmanager
async def _client(path: Path) -> AsyncGenerator[tuple[httpx.AsyncClient, PersistenceRuntime], None]:
    url = f"sqlite+aiosqlite:///{path}"
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url), worker_settings=WorkerSettings(poll_interval_seconds=60)
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app.state.persistence_runtime


async def _auth(client: httpx.AsyncClient, email: str) -> tuple[str, str]:
    registered = await client.post(
        "/auth/register", json={"email": email, "password": "correct-password"}
    )
    login = await client.post(
        "/auth/login", json={"email": email, "password": "correct-password"}
    )
    return registered.json()["data"]["id"], login.json()["data"]["token"]


async def _successful_report(runtime: PersistenceRuntime, owner: str) -> tuple[str, str]:
    async with transaction_scope(runtime.session_factory) as session:
        repository = SqliteDiagnosticRepository(session)
        task = await repository.create_task(
            owner, None, [{"alertName": "Latency", "service": "gateway"}]
        )
        report = await repository.create_report(
            owner,
            task.id,
            "# 告警分析报告\n- 根因结论：上游超时\n- 建议：检查依赖",
            "model",
            False,
        )
        await repository.transition_task(owner, task.id, "succeeded")
        return task.id, report.id


async def test_case_list_detail_are_authenticated_and_owner_scoped(tmp_path: Path) -> None:
    async with _client(tmp_path / "api.sqlite3") as (client, runtime):
        owner, token = await _auth(client, "owner@example.com")
        _other, other_token = await _auth(client, "other@example.com")
        task_id, report_id = await _successful_report(runtime, owner)
        case = await DiagnosisCasePersistor(runtime.session_factory).persist(
            owner, task_id, report_id
        )
        headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-case"}
        listed = await client.get("/aiops/diagnostic-cases", headers=headers)
        detail = await client.get(f"/aiops/diagnostic-cases/{case.id}", headers=headers)
        forbidden = await client.get(
            f"/aiops/diagnostic-cases/{case.id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        anonymous = await client.get("/aiops/diagnostic-cases")

    assert listed.status_code == detail.status_code == 200
    assert listed.headers["X-Request-ID"] == "req-case"
    assert listed.json()["data"]["items"][0]["taskId"] == task_id
    assert detail.json()["data"]["item"]["documentId"] == case.document_id
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "BUSINESS_RESOURCE_NOT_FOUND"
    assert anonymous.status_code == 401


async def test_legacy_api_creates_document_and_index_task_but_no_case(tmp_path: Path) -> None:
    async with _client(tmp_path / "legacy-api.sqlite3") as (client, runtime):
        owner, token = await _auth(client, "owner@example.com")
        task_id, _ = await _successful_report(runtime, owner)
        headers = {"Authorization": f"Bearer {token}"}
        saved = await client.post(
            f"/aiops/diagnostics/{task_id}:save-to-knowledge", headers=headers
        )
        duplicate = await client.post(
            f"/aiops/diagnostics/{task_id}:save-to-knowledge", headers=headers
        )
        cases = await DiagnosisCasePersistor(runtime.session_factory).list(owner)

    assert saved.status_code == 201
    assert saved.json()["data"]["document"]["indexStatus"] == "pending"
    assert saved.json()["data"]["indexTask"]["status"] == "pending"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "BUSINESS_CONFLICT"
    assert cases == []
