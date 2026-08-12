"""后台任务用户管理用例。"""

from super_ai.api_responses import AppError
from super_ai.background_jobs.models import BackgroundJobRecord
from super_ai.background_jobs.repositories import BackgroundJobRepository


class BackgroundJobService:
    def __init__(self, repository: BackgroundJobRepository) -> None:
        self._repository = repository

    async def list(self, owner_user_id: str) -> list[BackgroundJobRecord]:
        return await self._repository.list(owner_user_id)

    async def get(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord:
        record = await self._repository.get(owner_user_id, job_id)
        if record is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return record

    async def cancel(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord:
        record = await self._repository.request_cancel(owner_user_id, job_id)
        if record is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return record

    async def retry(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord:
        try:
            record = await self._repository.retry(owner_user_id, job_id)
        except ValueError as error:
            raise AppError("BUSINESS_RULE_VIOLATION") from error
        if record is None:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
        return record
