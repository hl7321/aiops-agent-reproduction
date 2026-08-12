import asyncio
from datetime import timedelta

from super_ai.background_jobs.models import NewBackgroundJob
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.background_job_repositories import (
    SqliteBackgroundJobRepository,
    SqliteBackgroundJobStore,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


async def _enqueue(runtime: PersistenceRuntime, owner: str = "user-a") -> str:
    async with transaction_scope(runtime.session_factory) as session:
        if await session.get(UserModel, owner) is None:
            now = utc_now()
            session.add(
                UserModel(
                    id=owner,
                    email=f"{owner}@example.com",
                    password_hash="$argon2id$test",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
        record = await SqliteBackgroundJobRepository(session).enqueue(
            owner,
            NewBackgroundJob(
                kind="test.index",
                resource_type="document",
                resource_id="doc-1",
                payload={"token": "sentinel-secret", "value": 1},
                max_attempts=2,
                timeout_seconds=2,
            ),
        )
        return record.id


async def test_owner_scope_events_cancel_and_retry(jobs_database_url: str) -> None:
    await upgrade_database(jobs_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=jobs_database_url))
    try:
        job_id = await _enqueue(runtime)
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteBackgroundJobRepository(session)
            assert await repository.get("user-b", job_id) is None
            assert await repository.request_cancel("user-b", job_id) is None
            assert await repository.list_events("user-b", job_id, after_sequence=0) is None
            cancelled = await repository.request_cancel("user-a", job_id)
            assert cancelled is not None and cancelled.status == "cancelled"
            events = await repository.list_events("user-a", job_id, after_sequence=0)
            assert events is not None
            assert [event.sequence for event in events] == sorted(
                event.sequence for event in events
            )
            remaining = await repository.list_events(
                "user-a", job_id, after_sequence=events[0].sequence
            )
            assert remaining == events[1:]
            retried = await repository.retry("user-a", job_id)
            assert retried is not None
            assert retried.retry_of_job_id == job_id
            assert retried.status == "queued"
    finally:
        await runtime.close()


async def test_atomic_claim_heartbeat_expiry_and_backoff(jobs_database_url: str) -> None:
    await upgrade_database(jobs_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=jobs_database_url))
    try:
        job_id = await _enqueue(runtime)

        async def claim(worker: str):
            async with transaction_scope(runtime.session_factory) as session:
                return await SqliteBackgroundJobStore(session).claim_next(
                    worker, now=utc_now(), lease_seconds=1
                )

        first, second = await asyncio.gather(claim("worker-a"), claim("worker-b"))
        claimed = [record for record in (first, second) if record is not None]
        assert len(claimed) == 1
        worker = claimed[0].lease_owner
        assert worker is not None

        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteBackgroundJobStore(session)
            heartbeat = await repository.heartbeat(job_id, worker, now=utc_now(), lease_seconds=30)
            assert heartbeat is not None and heartbeat.lease_expires_at is not None
            retrying = await repository.fail_execution(
                job_id,
                worker,
                now=utc_now(),
                error_message="apiKey=sentinel-secret Authorization: Bearer raw-token",
            )
            assert retrying is not None and retrying.status == "queued"
            assert retrying.available_at > utc_now()
            assert "sentinel-secret" not in (retrying.error_message or "")
            assert "raw-token" not in (retrying.error_message or "")

        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteBackgroundJobStore(session)
            recovered = await repository.claim_next(
                "worker-restart", now=utc_now() + timedelta(seconds=31), lease_seconds=30
            )
            assert recovered is not None and recovered.id == job_id
            assert recovered.attempt == 2
    finally:
        await runtime.close()
