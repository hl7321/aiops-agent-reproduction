"""新增通用 owner-scoped Agent 工具调用审计。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

revision: str = "20260817_0007"
down_revision: str | None = "20260817_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_call_audits",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("tool_call_id", sa.String(128), nullable=False),
        sa.Column("chat_session_id", sa.String(32), nullable=True),
        sa.Column("diagnostic_task_id", sa.String(32), nullable=True),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("arguments", CanonicalJson(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_summary", sa.String(1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", UTCDateTime(), nullable=False),
        sa.Column("completed_at", UTCDateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(chat_session_id IS NOT NULL AND diagnostic_task_id IS NULL) OR "
            "(chat_session_id IS NULL AND diagnostic_task_id IS NOT NULL)",
            name="ck_agent_audits_exactly_one_parent",
        ),
        sa.CheckConstraint(
            "status IN ('started','completed','failed')", name="ck_agent_audits_status"
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_audits_duration"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_agent_audits_owner_chat_started_id",
        "agent_tool_call_audits",
        ["owner_user_id", "chat_session_id", "started_at", "id"],
    )
    op.create_index(
        "ix_agent_audits_owner_diagnostic_started_id",
        "agent_tool_call_audits",
        ["owner_user_id", "diagnostic_task_id", "started_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_audits_owner_diagnostic_started_id", table_name="agent_tool_call_audits"
    )
    op.drop_index("ix_agent_audits_owner_chat_started_id", table_name="agent_tool_call_audits")
    op.drop_table("agent_tool_call_audits")
