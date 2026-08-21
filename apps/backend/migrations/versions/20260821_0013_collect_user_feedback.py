"""增加 owner-scoped 结构化用户反馈。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import UTCDateTime

revision: str = "20260821_0013"
down_revision: str | None = "20260821_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False, server_default=""),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "target_type IN ('chat_message','citation','diagnostic_step','diagnostic_report')",
            name="ck_user_feedback_target_type",
        ),
        sa.CheckConstraint(
            "rating IN ('positive','negative')", name="ck_user_feedback_rating"
        ),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN "
            "('incorrect','incomplete','irrelevant','unclear','unsafe','other')",
            name="ck_user_feedback_reason",
        ),
        sa.UniqueConstraint(
            "owner_user_id", "target_type", "target_id", "subject_key",
            name="uq_user_feedback_subject",
        ),
    )
    op.create_index(
        "ix_user_feedback_owner_target",
        "user_feedback",
        ["owner_user_id", "target_type", "target_id", "subject_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_feedback_owner_target", table_name="user_feedback")
    op.drop_table("user_feedback")
