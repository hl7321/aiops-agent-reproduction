from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from sqlalchemy import func, select, update

from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.background_job_models import BackgroundJobModel
from super_ai.memory.extended_sqlite.document_index_task_models import DocumentIndexTaskModel
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


@asynccontextmanager
async def client_for(
    url: str,
) -> AsyncGenerator[tuple[httpx.AsyncClient, PersistenceRuntime], None]:
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url), worker_settings=WorkerSettings(poll_interval_seconds=60)
    )
    async with app.router.lifespan_context(app):
        runtime = app.state.persistence_runtime
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, runtime


async def _auth(client: httpx.AsyncClient, email: str) -> str:
    await client.post("/auth/register", json={"email": email, "password": "correct-password"})
    response = await client.post(
        "/auth/login", json={"email": email, "password": "correct-password"}
    )
    return response.json()["data"]["token"]


async def test_upload_creates_no_job_until_client_explicitly_posts_index_task(
    indexing_database_url: str,
) -> None:
    async with client_for(indexing_database_url) as (client, runtime):
        token = await _auth(client, "owner@example.com")
        headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-index"}
        bases = await client.get("/knowledge-bases", headers=headers)
        kb = bases.json()["data"]["items"][0]["id"]
        uploaded = await client.post(
            f"/knowledge-bases/{kb}/documents",
            files={"file": ("guide.md", "hello", "text/markdown")},
            headers=headers,
        )
        document = uploaded.json()["data"]
        async with transaction_scope(runtime.session_factory) as session:
            assert (
                await session.scalar(select(func.count()).select_from(DocumentIndexTaskModel)) == 0
            )
            assert await session.scalar(select(func.count()).select_from(BackgroundJobModel)) == 0

        created = await client.post(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks", headers=headers
        )
        task = created.json()["data"]
        conflict = await client.post(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks", headers=headers
        )
        detail = await client.get(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks/{task['id']}",
            headers=headers,
        )
        async with transaction_scope(runtime.session_factory) as session:
            job = await session.scalar(
                select(BackgroundJobModel).where(
                    BackgroundJobModel.resource_type == "document_index_task",
                    BackgroundJobModel.resource_id == task["id"],
                )
            )
            assert job is not None and job.status == "queued"
            await session.execute(
                update(DocumentIndexTaskModel)
                .where(DocumentIndexTaskModel.id == task["id"])
                .values(status="failed", failure_reason="safe failure")
            )
        retried = await client.post(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks/{task['id']}:retry",
            headers=headers,
        )

    assert uploaded.status_code == created.status_code == retried.status_code == 201
    assert conflict.status_code == 409
    assert uploaded.json()["data"]["indexStatus"] == "pending"
    assert created.headers["X-Request-ID"] == "req-index"
    assert task["status"] == detail.json()["data"]["status"] == "pending"
    assert "jobId" not in task
    assert retried.json()["data"]["retryOfTaskId"] == task["id"]


async def test_other_user_cannot_read_or_retry_index_task(indexing_database_url: str) -> None:
    async with client_for(indexing_database_url) as (client, _runtime):
        owner = await _auth(client, "owner@example.com")
        other = await _auth(client, "other@example.com")
        owner_headers = {"Authorization": f"Bearer {owner}"}
        other_headers = {"Authorization": f"Bearer {other}"}
        kb = (await client.get("/knowledge-bases", headers=owner_headers)).json()["data"]["items"][
            0
        ]["id"]
        document = (
            await client.post(
                f"/knowledge-bases/{kb}/documents",
                files={"file": ("private.md", "secret", "text/markdown")},
                headers=owner_headers,
            )
        ).json()["data"]
        task = (
            await client.post(
                f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks",
                headers=owner_headers,
            )
        ).json()["data"]
        detail = await client.get(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks/{task['id']}",
            headers=other_headers,
        )
        retry = await client.post(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks/{task['id']}:retry",
            headers=other_headers,
        )
    assert detail.status_code == retry.status_code == 403
    assert detail.json()["error"]["code"] == retry.json()["error"]["code"] == "AUTH_FORBIDDEN"


async def test_owner_can_manually_rebuild_completed_document(
    indexing_database_url: str,
) -> None:
    async with client_for(indexing_database_url) as (client, runtime):
        token = await _auth(client, "rebuild@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        kb = (await client.get("/knowledge-bases", headers=headers)).json()["data"]["items"][0][
            "id"
        ]
        document = (
            await client.post(
                f"/knowledge-bases/{kb}/documents",
                files={"file": ("rebuild.md", "content", "text/markdown")},
                headers=headers,
            )
        ).json()["data"]
        first = (
            await client.post(
                f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks",
                headers=headers,
            )
        ).json()["data"]
        async with transaction_scope(runtime.session_factory) as session:
            await session.execute(
                update(DocumentIndexTaskModel)
                .where(DocumentIndexTaskModel.id == first["id"])
                .values(status="succeeded")
            )
            await session.execute(
                update(BackgroundJobModel)
                .where(BackgroundJobModel.resource_id == first["id"])
                .values(status="succeeded")
            )
        rebuilt = await client.post(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks", headers=headers
        )

    assert rebuilt.status_code == 201
    assert rebuilt.json()["data"]["id"] != first["id"]
    assert rebuilt.json()["data"]["status"] == "pending"
    assert "retryOfTaskId" not in rebuilt.json()["data"]


async def test_queued_job_cancel_maps_domain_task_and_document_to_cancelled(
    indexing_database_url: str,
) -> None:
    async with client_for(indexing_database_url) as (client, runtime):
        token = await _auth(client, "cancel@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        kb = (await client.get("/knowledge-bases", headers=headers)).json()["data"]["items"][0][
            "id"
        ]
        document = (
            await client.post(
                f"/knowledge-bases/{kb}/documents",
                files={"file": ("cancel.md", "content", "text/markdown")},
                headers=headers,
            )
        ).json()["data"]
        task = (
            await client.post(
                f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks",
                headers=headers,
            )
        ).json()["data"]
        async with transaction_scope(runtime.session_factory) as session:
            job = await session.scalar(
                select(BackgroundJobModel).where(BackgroundJobModel.resource_id == task["id"])
            )
            assert job is not None
            job_id = job.id
        cancelled = await client.post(f"/background-jobs/{job_id}:cancel", headers=headers)
        detail = await client.get(
            f"/knowledge-bases/{kb}/documents/{document['id']}/index-tasks/{task['id']}",
            headers=headers,
        )
        document_detail = await client.get(
            f"/knowledge-bases/{kb}/documents/{document['id']}", headers=headers
        )

    assert cancelled.status_code == 200
    assert detail.json()["data"]["status"] == "cancelled"
    assert document_detail.json()["data"]["indexStatus"] == "cancelled"
