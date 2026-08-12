"""由 FastAPI lifespan 托管的持久后台 worker pool。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.background_jobs.handlers import (
    BackgroundJobCancelledError,
    BackgroundJobContext,
    HandlerRegistry,
)
from super_ai.background_jobs.models import BackgroundJobRecord
from super_ai.memory.extended_sqlite.background_job_repositories import (
    SqliteBackgroundJobStore,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite.runtime import transaction_scope


def _utc_now():
    return utc_now()


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    concurrency: int = 2
    lease_seconds: float = 30.0
    poll_interval_seconds: float = 0.2

    def __post_init__(self) -> None:
        if self.concurrency < 1 or self.lease_seconds <= 0 or self.poll_interval_seconds <= 0:
            raise ValueError("worker 并发、租约和轮询间隔必须大于零")


class BackgroundJobWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registry: HandlerRegistry,
        settings: WorkerSettings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry
        self._settings = settings or WorkerSettings()
        self._stop = asyncio.Event()
        self._tasks: tuple[asyncio.Task[None], ...] = ()
        self._runtime_id = uuid4().hex

    async def start(self) -> None:
        if self._tasks:
            return
        self._stop.clear()
        self._tasks = tuple(
            asyncio.create_task(
                self._worker_loop(f"{self._runtime_id}:{index}"),
                name=f"background-job-worker-{index}",
            )
            for index in range(self._settings.concurrency)
        )

    async def stop(self) -> None:
        tasks, self._tasks = self._tasks, ()
        if not tasks:
            return
        self._stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _worker_loop(self, worker_id: str) -> None:
        while not self._stop.is_set():
            job = await self._claim(worker_id)
            if job is None:
                await asyncio.sleep(self._settings.poll_interval_seconds)
                continue
            await self._execute(worker_id, job)

    async def _claim(self, worker_id: str) -> BackgroundJobRecord | None:
        async with transaction_scope(self._session_factory) as session:
            return await SqliteBackgroundJobStore(session).claim_next(
                worker_id,
                now=_utc_now(),
                lease_seconds=self._settings.lease_seconds,
            )

    async def _execute(self, worker_id: str, job: BackgroundJobRecord) -> None:
        if job.cancel_requested_at is not None:
            await self._cancel(job.id, worker_id)
            return
        handler = self._registry.get(job.kind)
        if handler is None:
            await self._fail(job.id, worker_id, f"未注册后台任务 handler: {job.kind}")
            return

        async def cancellation_check() -> bool:
            async with transaction_scope(self._session_factory) as session:
                return await SqliteBackgroundJobStore(session).cancellation_requested(
                    job.id, worker_id
                )

        context = BackgroundJobContext(job.id, job.owner_user_id, cancellation_check)
        handler_task = asyncio.create_task(
            handler(context, job.payload), name=f"background-job-handler-{job.id}"
        )
        started = monotonic()
        heartbeat_interval = max(0.01, self._settings.lease_seconds / 3)
        try:
            while True:
                remaining = job.timeout_seconds - (monotonic() - started)
                if remaining <= 0:
                    handler_task.cancel()
                    await asyncio.gather(handler_task, return_exceptions=True)
                    await self._fail(job.id, worker_id, "后台任务执行超时")
                    return
                done, _ = await asyncio.wait(
                    {handler_task}, timeout=min(heartbeat_interval, remaining)
                )
                if done:
                    await handler_task
                    await self._succeed(job.id, worker_id)
                    return
                current = await self._heartbeat(job.id, worker_id)
                if current is None or current.cancel_requested_at is not None:
                    handler_task.cancel()
                    await asyncio.gather(handler_task, return_exceptions=True)
                    await self._cancel(job.id, worker_id)
                    return
        except BackgroundJobCancelledError:
            await self._cancel(job.id, worker_id)
        except asyncio.CancelledError:
            handler_task.cancel()
            await asyncio.gather(handler_task, return_exceptions=True)
            raise
        except Exception as error:
            await self._fail(job.id, worker_id, str(error))

    async def _heartbeat(self, job_id: str, worker_id: str) -> BackgroundJobRecord | None:
        async with transaction_scope(self._session_factory) as session:
            return await SqliteBackgroundJobStore(session).heartbeat(
                job_id,
                worker_id,
                now=_utc_now(),
                lease_seconds=self._settings.lease_seconds,
            )

    async def _succeed(self, job_id: str, worker_id: str) -> None:
        async with transaction_scope(self._session_factory) as session:
            await SqliteBackgroundJobStore(session).succeed(job_id, worker_id, now=_utc_now())

    async def _cancel(self, job_id: str, worker_id: str) -> None:
        async with transaction_scope(self._session_factory) as session:
            await SqliteBackgroundJobStore(session).cancel_execution(
                job_id, worker_id, now=_utc_now()
            )

    async def _fail(self, job_id: str, worker_id: str, message: str) -> None:
        async with transaction_scope(self._session_factory) as session:
            await SqliteBackgroundJobStore(session).fail_execution(
                job_id, worker_id, now=_utc_now(), error_message=message
            )
