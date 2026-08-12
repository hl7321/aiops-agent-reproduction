"""后台任务 Repository 和 service 的 FastAPI dependencies。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.background_jobs.service import BackgroundJobService
from super_ai.memory.extended_sqlite.background_job_repositories import (
    SqliteBackgroundJobRepository,
)
from super_ai.memory.sqlite import get_session


def get_background_job_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BackgroundJobService:
    return BackgroundJobService(SqliteBackgroundJobRepository(session))
