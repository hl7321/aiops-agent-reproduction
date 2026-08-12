"""后台任务 Repository Protocol。"""

from __future__ import annotations

from typing import Protocol

from super_ai.background_jobs.models import (
    BackgroundJobEventRecord,
    BackgroundJobRecord,
    NewBackgroundJob,
)


class BackgroundJobRepository(Protocol):
    async def enqueue(self, owner_user_id: str, job: NewBackgroundJob) -> BackgroundJobRecord: ...
    async def list(self, owner_user_id: str) -> list[BackgroundJobRecord]: ...
    async def get(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord | None: ...
    async def request_cancel(
        self, owner_user_id: str, job_id: str
    ) -> BackgroundJobRecord | None: ...
    async def retry(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord | None: ...
    async def list_events(
        self, owner_user_id: str, job_id: str, *, after_sequence: int
    ) -> list[BackgroundJobEventRecord] | None: ...
