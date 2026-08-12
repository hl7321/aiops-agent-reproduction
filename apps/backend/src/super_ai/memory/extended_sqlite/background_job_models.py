"""持久后台任务 SQLAlchemy models。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import UTCDateTime


class BackgroundJobModel(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="ck_background_jobs_status",
        ),
        CheckConstraint("attempt >= 0 AND max_attempts >= 1", name="ck_background_jobs_attempts"),
        CheckConstraint("timeout_seconds >= 1", name="ck_background_jobs_timeout"),
        Index("ix_background_jobs_owner_created", "owner_user_id", "created_at"),
        Index("ix_background_jobs_claim", "status", "available_at", "lease_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[str] = mapped_column(Text(), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer(), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer(), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer(), nullable=False)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    retry_of_job_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("background_jobs.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class BackgroundJobEventModel(Base):
    __tablename__ = "background_job_events"
    __table_args__ = (
        Index("ix_background_job_events_owner_job_sequence", "owner_user_id", "job_id", "sequence"),
    )

    sequence: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("background_jobs.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    data: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
