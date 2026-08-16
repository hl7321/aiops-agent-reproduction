"""持久后台任务 Repository 的 SQLite adapter。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.background_jobs.models import (
    BackgroundJobEventRecord,
    BackgroundJobEventType,
    BackgroundJobRecord,
    BackgroundJobStatus,
    NewBackgroundJob,
)
from super_ai.background_jobs.security import redact_error
from super_ai.memory.extended_sqlite.background_job_models import (
    BackgroundJobEventModel,
    BackgroundJobModel,
)
from super_ai.memory.primitives import dump_json, load_json, new_id, utc_now


class SqliteBackgroundJobStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, owner_user_id: str, job: NewBackgroundJob) -> BackgroundJobRecord:
        _require_owner(owner_user_id)
        now = utc_now()
        model = BackgroundJobModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            kind=job.kind,
            resource_type=job.resource_type,
            resource_id=job.resource_id,
            status="queued",
            payload=dump_json(job.payload),
            attempt=0,
            max_attempts=job.max_attempts,
            timeout_seconds=job.timeout_seconds,
            available_at=job.available_at or now,
            lease_owner=None,
            lease_expires_at=None,
            cancel_requested_at=None,
            retry_of_job_id=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
        )
        self._session.add(model)
        await self._session.flush()
        await self._add_event(model, "queued", {})
        return _job_record(model)

    async def list(self, owner_user_id: str) -> list[BackgroundJobRecord]:
        _require_owner(owner_user_id)
        models = (
            await self._session.scalars(
                select(BackgroundJobModel)
                .where(BackgroundJobModel.owner_user_id == owner_user_id)
                .order_by(BackgroundJobModel.created_at.desc(), BackgroundJobModel.id.desc())
            )
        ).all()
        return [_job_record(model) for model in models]

    async def get(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord | None:
        model = await self._owned(owner_user_id, job_id)
        return _job_record(model) if model is not None else None

    async def get_by_resource(
        self, owner_user_id: str, resource_type: str, resource_id: str
    ) -> BackgroundJobRecord | None:
        _require_owner(owner_user_id)
        model = await self._session.scalar(
            select(BackgroundJobModel)
            .where(
                BackgroundJobModel.owner_user_id == owner_user_id,
                BackgroundJobModel.resource_type == resource_type,
                BackgroundJobModel.resource_id == resource_id,
            )
            .order_by(BackgroundJobModel.created_at.desc())
            .limit(1)
        )
        return _job_record(model) if model is not None else None

    async def request_cancel(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord | None:
        model = await self._owned(owner_user_id, job_id)
        if model is None:
            return None
        now = utc_now()
        if model.status == "queued":
            model.status = "cancelled"
            model.cancel_requested_at = now
            model.completed_at = now
            model.updated_at = now
            await self._add_event(model, "cancelled", {})
        elif model.status == "running" and model.cancel_requested_at is None:
            model.cancel_requested_at = now
            model.updated_at = now
        await self._session.flush()
        return _job_record(model)

    async def retry(self, owner_user_id: str, job_id: str) -> BackgroundJobRecord | None:
        source = await self._owned(owner_user_id, job_id)
        if source is None:
            return None
        if source.status not in ("failed", "cancelled"):
            raise ValueError("只有 failed 或 cancelled 任务可以重试")
        now = utc_now()
        retried = BackgroundJobModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            kind=source.kind,
            resource_type=source.resource_type,
            resource_id=source.resource_id,
            status="queued",
            payload=source.payload,
            attempt=0,
            max_attempts=source.max_attempts,
            timeout_seconds=source.timeout_seconds,
            available_at=now,
            lease_owner=None,
            lease_expires_at=None,
            cancel_requested_at=None,
            retry_of_job_id=source.id,
            error_message=None,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
        )
        self._session.add(retried)
        await self._session.flush()
        await self._add_event(retried, "queued", {"retryOfJobId": source.id})
        return _job_record(retried)

    async def list_events(
        self, owner_user_id: str, job_id: str, *, after_sequence: int
    ) -> list[BackgroundJobEventRecord] | None:
        if await self._owned(owner_user_id, job_id) is None:
            return None
        models = (
            await self._session.scalars(
                select(BackgroundJobEventModel)
                .where(
                    BackgroundJobEventModel.owner_user_id == owner_user_id,
                    BackgroundJobEventModel.job_id == job_id,
                    BackgroundJobEventModel.sequence > after_sequence,
                )
                .order_by(BackgroundJobEventModel.sequence)
            )
        ).all()
        return [_event_record(model) for model in models]

    async def claim_next(
        self, lease_owner: str, *, now: datetime, lease_seconds: float
    ) -> BackgroundJobRecord | None:
        if not lease_owner.strip() or lease_seconds <= 0:
            raise ValueError("lease owner 与租约时长必须有效")
        await self._reap_exhausted(now)
        claimable = or_(
            and_(BackgroundJobModel.status == "queued", BackgroundJobModel.available_at <= now),
            and_(
                BackgroundJobModel.status == "running",
                BackgroundJobModel.lease_expires_at.is_not(None),
                BackgroundJobModel.lease_expires_at <= now,
            ),
        )
        candidate = (
            select(BackgroundJobModel.id)
            .where(claimable, BackgroundJobModel.attempt < BackgroundJobModel.max_attempts)
            .order_by(BackgroundJobModel.available_at, BackgroundJobModel.created_at)
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            update(BackgroundJobModel)
            .where(BackgroundJobModel.id == candidate, claimable)
            .values(
                status="running",
                attempt=BackgroundJobModel.attempt + 1,
                lease_owner=lease_owner,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                started_at=func.coalesce(BackgroundJobModel.started_at, now),
                updated_at=now,
                error_message=None,
            )
            .returning(BackgroundJobModel)
        )
        model = await self._session.scalar(statement)
        if model is None:
            return None
        await self._add_event(model, "running", {"attempt": model.attempt})
        return _job_record(model)

    async def heartbeat(
        self, job_id: str, lease_owner: str, *, now: datetime, lease_seconds: float
    ) -> BackgroundJobRecord | None:
        model = await self._session.scalar(
            update(BackgroundJobModel)
            .where(
                BackgroundJobModel.id == job_id,
                BackgroundJobModel.status == "running",
                BackgroundJobModel.lease_owner == lease_owner,
            )
            .values(lease_expires_at=now + timedelta(seconds=lease_seconds), updated_at=now)
            .returning(BackgroundJobModel)
        )
        return _job_record(model) if model is not None else None

    async def cancellation_requested(self, job_id: str, lease_owner: str) -> bool:
        model = await self._leased(job_id, lease_owner)
        return model is None or model.cancel_requested_at is not None

    async def succeed(
        self, job_id: str, lease_owner: str, *, now: datetime
    ) -> BackgroundJobRecord | None:
        return await self._finish(job_id, lease_owner, now=now, status="succeeded")

    async def cancel_execution(
        self, job_id: str, lease_owner: str, *, now: datetime
    ) -> BackgroundJobRecord | None:
        return await self._finish(job_id, lease_owner, now=now, status="cancelled")

    async def fail_execution(
        self, job_id: str, lease_owner: str, *, now: datetime, error_message: str
    ) -> BackgroundJobRecord | None:
        model = await self._leased(job_id, lease_owner)
        if model is None:
            return None
        safe_error = redact_error(error_message, model.payload)
        model.error_message = safe_error
        model.lease_owner = None
        model.lease_expires_at = None
        model.updated_at = now
        if model.cancel_requested_at is not None:
            model.status = "cancelled"
            model.completed_at = now
            await self._add_event(model, "cancelled", {})
        elif model.attempt < model.max_attempts:
            model.status = "queued"
            model.available_at = now + timedelta(seconds=min(30, 2 ** (model.attempt - 1)))
            await self._add_event(
                model, "queued", {"attempt": model.attempt, "errorMessage": safe_error}
            )
        else:
            model.status = "failed"
            model.completed_at = now
            await self._add_event(model, "failed", {"errorMessage": safe_error})
        await self._session.flush()
        return _job_record(model)

    async def _finish(
        self,
        job_id: str,
        lease_owner: str,
        *,
        now: datetime,
        status: BackgroundJobStatus,
    ) -> BackgroundJobRecord | None:
        model = await self._leased(job_id, lease_owner)
        if model is None:
            return None
        model.status = status
        model.completed_at = now
        model.updated_at = now
        model.lease_owner = None
        model.lease_expires_at = None
        await self._add_event(model, status, {})
        await self._session.flush()
        return _job_record(model)

    async def _reap_exhausted(self, now: datetime) -> None:
        models = (
            await self._session.scalars(
                select(BackgroundJobModel).where(
                    BackgroundJobModel.status == "running",
                    BackgroundJobModel.lease_expires_at <= now,
                    BackgroundJobModel.attempt >= BackgroundJobModel.max_attempts,
                )
            )
        ).all()
        for model in models:
            if model.cancel_requested_at is not None:
                model.status = "cancelled"
                model.error_message = None
                event_type: BackgroundJobEventType = "cancelled"
                event_data: object = {}
            else:
                model.status = "failed"
                model.error_message = "worker 租约过期且已达到最大尝试次数"
                event_type = "failed"
                event_data = {"errorMessage": model.error_message}
            model.completed_at = now
            model.updated_at = now
            model.lease_owner = None
            model.lease_expires_at = None
            await self._add_event(model, event_type, event_data)

    async def _owned(self, owner_user_id: str, job_id: str) -> BackgroundJobModel | None:
        _require_owner(owner_user_id)
        return await self._session.scalar(
            select(BackgroundJobModel).where(
                BackgroundJobModel.owner_user_id == owner_user_id,
                BackgroundJobModel.id == job_id,
            )
        )

    async def _leased(self, job_id: str, lease_owner: str) -> BackgroundJobModel | None:
        return await self._session.scalar(
            select(BackgroundJobModel).where(
                BackgroundJobModel.id == job_id,
                BackgroundJobModel.status == "running",
                BackgroundJobModel.lease_owner == lease_owner,
            )
        )

    async def _add_event(
        self, job: BackgroundJobModel, event_type: BackgroundJobEventType, data: object
    ) -> None:
        self._session.add(
            BackgroundJobEventModel(
                job_id=job.id,
                owner_user_id=job.owner_user_id,
                type=event_type,
                data=dump_json(data),
                created_at=utc_now(),
            )
        )
        await self._session.flush()


def _require_owner(owner_user_id: str) -> None:
    if not owner_user_id.strip():
        raise ValueError("owner_user_id 不得为空")


def _job_record(model: BackgroundJobModel) -> BackgroundJobRecord:
    return BackgroundJobRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        kind=model.kind,
        resource_type=model.resource_type,
        resource_id=model.resource_id,
        status=cast(BackgroundJobStatus, model.status),
        payload=load_json(model.payload),
        attempt=model.attempt,
        max_attempts=model.max_attempts,
        timeout_seconds=model.timeout_seconds,
        available_at=model.available_at,
        lease_owner=model.lease_owner,
        lease_expires_at=model.lease_expires_at,
        cancel_requested_at=model.cancel_requested_at,
        retry_of_job_id=model.retry_of_job_id,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )


def _event_record(model: BackgroundJobEventModel) -> BackgroundJobEventRecord:
    return BackgroundJobEventRecord(
        sequence=model.sequence,
        job_id=model.job_id,
        owner_user_id=model.owner_user_id,
        type=cast(BackgroundJobEventType, model.type),
        data=load_json(model.data),
        created_at=model.created_at,
    )


class SqliteBackgroundJobRepository(SqliteBackgroundJobStore):
    """只通过 owner-scoped Protocol 暴露给用户领域服务的 adapter 名称。"""
