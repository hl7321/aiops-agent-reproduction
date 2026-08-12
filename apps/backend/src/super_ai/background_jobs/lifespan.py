"""组合持久化与后台 worker 的 FastAPI lifespan。"""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from super_ai.background_jobs.handlers import HandlerRegistry
from super_ai.background_jobs.runtime import BackgroundJobWorker, WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite.runtime import PersistenceRuntime

ApplicationLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_application_lifespan(
    settings: DatabaseSettings,
    registry: HandlerRegistry | None = None,
    worker_settings: WorkerSettings | None = None,
) -> ApplicationLifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        persistence = PersistenceRuntime.start(settings)
        worker = BackgroundJobWorker(
            persistence.session_factory, registry or HandlerRegistry(), worker_settings
        )
        app.state.persistence_runtime = persistence
        app.state.background_job_worker = worker
        await worker.start()
        try:
            yield
        finally:
            await worker.stop()
            delattr(app.state, "background_job_worker")
            delattr(app.state, "persistence_runtime")
            await persistence.close()

    return lifespan
