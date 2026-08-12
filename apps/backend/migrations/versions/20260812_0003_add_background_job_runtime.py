"""新增持久后台任务与事件表。

Revision ID: 20260812_0003
Revises: 20260808_0002
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import UTCDateTime

revision: str = "20260812_0003"
down_revision: str | None = "20260808_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=True),
        sa.Column("resource_id", sa.String(120), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("available_at", UTCDateTime(), nullable=False),
        sa.Column("lease_owner", sa.String(120), nullable=True),
        sa.Column("lease_expires_at", UTCDateTime(), nullable=True),
        sa.Column("cancel_requested_at", UTCDateTime(), nullable=True),
        sa.Column("retry_of_job_id", sa.String(32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("completed_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="ck_background_jobs_status",
        ),
        sa.CheckConstraint(
            "attempt >= 0 AND max_attempts >= 1", name="ck_background_jobs_attempts"
        ),
        sa.CheckConstraint("timeout_seconds >= 1", name="ck_background_jobs_timeout"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retry_of_job_id"], ["background_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_background_jobs_owner_created", "background_jobs", ["owner_user_id", "created_at"]
    )
    op.create_index(
        "ix_background_jobs_claim",
        "background_jobs",
        ["status", "available_at", "lease_expires_at"],
    )
    op.create_table(
        "background_job_events",
        sa.Column("sequence", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("sequence"),
    )
    op.create_index(
        "ix_background_job_events_owner_job_sequence",
        "background_job_events",
        ["owner_user_id", "job_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_background_job_events_owner_job_sequence", table_name="background_job_events")
    op.drop_table("background_job_events")
    op.drop_index("ix_background_jobs_claim", table_name="background_jobs")
    op.drop_index("ix_background_jobs_owner_created", table_name="background_jobs")
    op.drop_table("background_jobs")
