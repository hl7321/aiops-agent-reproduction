import asyncio

from super_ai.background_jobs.handlers import BackgroundJobContext, HandlerRegistry
from super_ai.background_jobs.models import NewBackgroundJob
from super_ai.background_jobs.runtime import BackgroundJobWorker, WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.background_job_repositories import (
    SqliteBackgroundJobRepository,
    SqliteBackgroundJobStore,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


async def test_worker_completes_and_events_replay_after_client_disconnect(
    jobs_database_url: str,
) -> None:
    await upgrade_database(jobs_database_url)
    persistence = PersistenceRuntime.start(DatabaseSettings(url=jobs_database_url))
    completed = asyncio.Event()

    async def handler(context: BackgroundJobContext, payload: object) -> None:
        assert payload == {"value": 1}
        await context.raise_if_cancelled()
        completed.set()

    registry = HandlerRegistry()
    registry.register("test.success", handler)
    try:
        async with transaction_scope(persistence.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="user-a",
                    email="a@example.com",
                    password_hash="x",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            job = await SqliteBackgroundJobRepository(session).enqueue(
                "user-a", NewBackgroundJob(kind="test.success", payload={"value": 1})
            )
        worker = BackgroundJobWorker(
            persistence.session_factory,
            registry,
            WorkerSettings(concurrency=2, lease_seconds=1, poll_interval_seconds=0.01),
        )
        await worker.start()
        await asyncio.wait_for(completed.wait(), timeout=2)
        for _ in range(100):
            async with transaction_scope(persistence.session_factory) as session:
                current = await SqliteBackgroundJobRepository(session).get("user-a", job.id)
            if current is not None and current.status == "succeeded":
                break
            await asyncio.sleep(0.01)
        await worker.stop()

        async with transaction_scope(persistence.session_factory) as session:
            repository = SqliteBackgroundJobRepository(session)
            record = await repository.get("user-a", job.id)
            events = await repository.list_events("user-a", job.id, after_sequence=0)
            assert record is not None and record.status == "succeeded"
            assert events is not None
            assert [event.type for event in events] == ["queued", "running", "succeeded"]
    finally:
        await persistence.close()


async def test_worker_timeout_and_running_cancel_are_terminal(jobs_database_url: str) -> None:
    await upgrade_database(jobs_database_url)
    persistence = PersistenceRuntime.start(DatabaseSettings(url=jobs_database_url))
    started = asyncio.Event()

    async def blocking(context: BackgroundJobContext, _payload: object) -> None:
        started.set()
        while True:
            await asyncio.sleep(0.01)
            await context.raise_if_cancelled()

    registry = HandlerRegistry()
    registry.register("test.block", blocking)
    try:
        async with transaction_scope(persistence.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="user-a",
                    email="a@example.com",
                    password_hash="x",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            job = await SqliteBackgroundJobRepository(session).enqueue(
                "user-a",
                NewBackgroundJob(kind="test.block", timeout_seconds=5, max_attempts=1),
            )
        worker = BackgroundJobWorker(
            persistence.session_factory,
            registry,
            WorkerSettings(concurrency=1, lease_seconds=1, poll_interval_seconds=0.01),
        )
        await worker.start()
        await asyncio.wait_for(started.wait(), timeout=2)
        async with transaction_scope(persistence.session_factory) as session:
            await SqliteBackgroundJobRepository(session).request_cancel("user-a", job.id)
        current = None
        for _ in range(100):
            async with transaction_scope(persistence.session_factory) as session:
                current = await SqliteBackgroundJobRepository(session).get("user-a", job.id)
            if current is not None and current.status == "cancelled":
                break
            await asyncio.sleep(0.01)
        await worker.stop()
        assert current is not None and current.status == "cancelled"
    finally:
        await persistence.close()


async def test_restart_recovers_expired_lease(jobs_database_url: str) -> None:
    await upgrade_database(jobs_database_url)
    persistence = PersistenceRuntime.start(DatabaseSettings(url=jobs_database_url))
    completed = asyncio.Event()

    async def handler(_context: BackgroundJobContext, _payload: object) -> None:
        completed.set()

    registry = HandlerRegistry()
    registry.register("test.restart", handler)
    try:
        async with transaction_scope(persistence.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="user-a",
                    email="restart@example.com",
                    password_hash="x",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            job = await SqliteBackgroundJobRepository(session).enqueue(
                "user-a", NewBackgroundJob(kind="test.restart", max_attempts=2)
            )
        async with transaction_scope(persistence.session_factory) as session:
            claimed = await SqliteBackgroundJobStore(session).claim_next(
                "dead-process", now=utc_now(), lease_seconds=0.02
            )
            assert claimed is not None and claimed.id == job.id
        await asyncio.sleep(0.03)
        worker = BackgroundJobWorker(
            persistence.session_factory,
            registry,
            WorkerSettings(concurrency=1, lease_seconds=1, poll_interval_seconds=0.01),
        )
        await worker.start()
        await asyncio.wait_for(completed.wait(), timeout=2)
        recovered = None
        for _ in range(100):
            async with transaction_scope(persistence.session_factory) as session:
                recovered = await SqliteBackgroundJobRepository(session).get("user-a", job.id)
            if recovered is not None and recovered.status == "succeeded":
                break
            await asyncio.sleep(0.01)
        await worker.stop()
        assert recovered is not None and recovered.status == "succeeded"
        assert recovered.attempt == 2
    finally:
        await persistence.close()


async def test_worker_retries_fake_handler_with_backoff_then_succeeds(
    jobs_database_url: str,
) -> None:
    await upgrade_database(jobs_database_url)
    persistence = PersistenceRuntime.start(DatabaseSettings(url=jobs_database_url))
    succeeded = asyncio.Event()
    calls = 0

    async def flaky(_context: BackgroundJobContext, _payload: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        succeeded.set()

    registry = HandlerRegistry()
    registry.register("test.retry", flaky)
    try:
        async with transaction_scope(persistence.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="user-a",
                    email="retry@example.com",
                    password_hash="x",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            job = await SqliteBackgroundJobRepository(session).enqueue(
                "user-a", NewBackgroundJob(kind="test.retry", max_attempts=2)
            )
        worker = BackgroundJobWorker(
            persistence.session_factory,
            registry,
            WorkerSettings(concurrency=1, lease_seconds=1, poll_interval_seconds=0.01),
        )
        await worker.start()
        await asyncio.wait_for(succeeded.wait(), timeout=3)
        record = None
        for _ in range(100):
            async with transaction_scope(persistence.session_factory) as session:
                record = await SqliteBackgroundJobRepository(session).get("user-a", job.id)
            if record is not None and record.status == "succeeded":
                break
            await asyncio.sleep(0.01)
        await worker.stop()
        assert calls == 2
        assert record is not None and record.status == "succeeded" and record.attempt == 2
    finally:
        await persistence.close()


async def test_worker_timeout_becomes_failed_at_max_attempts(jobs_database_url: str) -> None:
    await upgrade_database(jobs_database_url)
    persistence = PersistenceRuntime.start(DatabaseSettings(url=jobs_database_url))

    async def slow(_context: BackgroundJobContext, _payload: object) -> None:
        await asyncio.sleep(10)

    registry = HandlerRegistry()
    registry.register("test.timeout", slow)
    try:
        async with transaction_scope(persistence.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="user-a",
                    email="timeout@example.com",
                    password_hash="x",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            job = await SqliteBackgroundJobRepository(session).enqueue(
                "user-a",
                NewBackgroundJob(kind="test.timeout", max_attempts=1, timeout_seconds=1),
            )
        worker = BackgroundJobWorker(
            persistence.session_factory,
            registry,
            WorkerSettings(concurrency=1, lease_seconds=0.3, poll_interval_seconds=0.01),
        )
        await worker.start()
        record = None
        for _ in range(200):
            async with transaction_scope(persistence.session_factory) as session:
                record = await SqliteBackgroundJobRepository(session).get("user-a", job.id)
            if record is not None and record.status == "failed":
                break
            await asyncio.sleep(0.01)
        await worker.stop()
        assert record is not None and record.status == "failed"
        assert record.error_message == "后台任务执行超时"
    finally:
        await persistence.close()
