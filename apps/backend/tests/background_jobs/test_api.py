from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from super_ai.app import create_app
from super_ai.background_jobs.models import NewBackgroundJob
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.background_job_repositories import (
    SqliteBackgroundJobRepository,
)
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


@asynccontextmanager
async def jobs_client(
    database_url: str,
) -> AsyncGenerator[tuple[httpx.AsyncClient, FastAPI], None]:
    await upgrade_database(database_url)
    app = create_app(
        DatabaseSettings(url=database_url),
        worker_settings=WorkerSettings(poll_interval_seconds=60),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app


async def _register_and_login(client: httpx.AsyncClient, email: str) -> tuple[str, str]:
    registered = await client.post(
        "/auth/register", json={"email": email, "password": "correct-password"}
    )
    login = await client.post("/auth/login", json={"email": email, "password": "correct-password"})
    return registered.json()["data"]["id"], login.json()["data"]["token"]


async def test_background_job_api_owner_scope_cancel_retry_and_request_id(
    jobs_database_url: str,
) -> None:
    async with jobs_client(jobs_database_url) as (client, app):
        owner_id, owner_token = await _register_and_login(client, "owner@example.com")
        _, other_token = await _register_and_login(client, "other@example.com")
        persistence = app.state.persistence_runtime
        assert isinstance(persistence, PersistenceRuntime)
        async with transaction_scope(persistence.session_factory) as session:
            job = await SqliteBackgroundJobRepository(session).enqueue(
                owner_id,
                NewBackgroundJob(
                    kind="index.document",
                    resource_type="document",
                    resource_id="doc-1",
                    payload={"documentId": "doc-1"},
                ),
            )

        headers = {"Authorization": f"Bearer {owner_token}", "X-Request-ID": "req-jobs"}
        listed = await client.get("/background-jobs", headers=headers)
        detail = await client.get(f"/background-jobs/{job.id}", headers=headers)
        hidden = await client.get(
            f"/background-jobs/{job.id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        cancelled = await client.post(f"/background-jobs/{job.id}:cancel", headers=headers)
        retried = await client.post(f"/background-jobs/{job.id}:retry", headers=headers)

    assert listed.status_code == detail.status_code == 200
    assert listed.headers["X-Request-ID"] == "req-jobs"
    assert listed.json()["data"]["items"][0]["ownerUserId"] == owner_id
    assert detail.json()["data"]["id"] == job.id
    assert "heartbeatAt" not in detail.json()["data"]
    assert "result" not in detail.json()["data"]
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "BUSINESS_RESOURCE_NOT_FOUND"
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert retried.json()["data"]["status"] == "queued"
    assert retried.json()["data"]["retryOfJobId"] == job.id


async def test_background_job_api_requires_bearer_and_lifespan_cleans_up(
    jobs_database_url: str,
) -> None:
    await upgrade_database(jobs_database_url)
    app = create_app(
        DatabaseSettings(url=jobs_database_url),
        worker_settings=WorkerSettings(poll_interval_seconds=60),
    )
    async with app.router.lifespan_context(app):
        assert isinstance(app.state.persistence_runtime, PersistenceRuntime)
        assert app.state.background_job_worker is not None
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/background-jobs")
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    assert not hasattr(app.state, "background_job_worker")
    assert not hasattr(app.state, "persistence_runtime")
