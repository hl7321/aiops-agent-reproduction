"""增加 owner-scoped AIOps 诊断与证据链。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

revision: str = "20260820_0011"
down_revision: str | None = "20260820_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owner() -> sa.Column[str]:
    return sa.Column(
        "owner_user_id",
        sa.String(32),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "diagnostic_tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        _owner(),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("query", sa.Text()),
        sa.Column("alerts", CanonicalJson(), nullable=False),
        sa.Column("current_plan", CanonicalJson(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("replan_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("failure_reason", sa.String(1000)),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("started_at", UTCDateTime()),
        sa.Column("completed_at", UTCDateTime()),
        sa.CheckConstraint(
            "status IN ('accepted','running','succeeded','failed','cancelled')",
            name="ck_diagnostic_tasks_status",
        ),
    )
    op.create_index(
        "ix_diagnostic_tasks_owner_updated_id",
        "diagnostic_tasks",
        ["owner_user_id", "updated_at", "id"],
    )
    op.create_table(
        "diagnostic_steps",
        sa.Column("id", sa.String(32), primary_key=True),
        _owner(),
        sa.Column(
            "diagnostic_task_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("arguments", CanonicalJson(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_summary", sa.String(1000)),
        sa.Column("error_message", sa.String(1000)),
        sa.Column("started_at", UTCDateTime()),
        sa.Column("completed_at", UTCDateTime()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_diagnostic_steps_status",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "diagnostic_task_id",
            "plan_version",
            "position",
            "attempt",
            name="uq_diagnostic_steps_attempt",
        ),
    )
    op.create_index(
        "ix_diagnostic_steps_owner_task_position",
        "diagnostic_steps",
        ["owner_user_id", "diagnostic_task_id", "plan_version", "position"],
    )
    op.create_table(
        "diagnostic_evidence",
        sa.Column("id", sa.String(32), primary_key=True),
        _owner(),
        sa.Column(
            "diagnostic_task_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "diagnostic_step_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_steps.id", ondelete="SET NULL"),
        ),
        sa.Column("tool_call_id", sa.String(128)),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", CanonicalJson(), nullable=False),
        sa.Column("observed_at", UTCDateTime()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('alert','knowledge','log','metric')", name="ck_diagnostic_evidence_kind"
        ),
    )
    op.create_index(
        "ix_diagnostic_evidence_owner_task_kind",
        "diagnostic_evidence",
        ["owner_user_id", "diagnostic_task_id", "kind", "created_at"],
    )
    op.create_table(
        "diagnostic_reports",
        sa.Column("id", sa.String(32), primary_key=True),
        _owner(),
        sa.Column(
            "diagnostic_task_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("generation_mode", sa.String(16), nullable=False),
        sa.Column("uncertainty", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "generation_mode IN ('model','fallback')", name="ck_diagnostic_reports_mode"
        ),
        sa.UniqueConstraint(
            "owner_user_id", "diagnostic_task_id", "revision", name="uq_diagnostic_reports_revision"
        ),
    )
    op.create_table(
        "report_evidence_links",
        sa.Column("id", sa.String(32), primary_key=True),
        _owner(),
        sa.Column(
            "diagnostic_task_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_key", sa.String(120), nullable=False),
        sa.Column("section", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "report_id", "claim_key", "evidence_id", name="uq_report_evidence_link"
        ),
    )
    op.create_index(
        "ix_report_links_owner_task_report",
        "report_evidence_links",
        ["owner_user_id", "diagnostic_task_id", "report_id", "position"],
    )
    op.create_table(
        "graph_checkpoints",
        sa.Column("id", sa.String(32), primary_key=True),
        _owner(),
        sa.Column(
            "diagnostic_task_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkpoint_version", sa.Integer(), nullable=False),
        sa.Column("node", sa.String(32), nullable=False),
        sa.Column("state", CanonicalJson(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.UniqueConstraint(
            "owner_user_id",
            "diagnostic_task_id",
            "checkpoint_version",
            name="uq_graph_checkpoint_version",
        ),
    )
    op.create_index(
        "ix_graph_checkpoints_owner_task_version",
        "graph_checkpoints",
        ["owner_user_id", "diagnostic_task_id", "checkpoint_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_graph_checkpoints_owner_task_version", table_name="graph_checkpoints")
    op.drop_table("graph_checkpoints")
    op.drop_index("ix_report_links_owner_task_report", table_name="report_evidence_links")
    op.drop_table("report_evidence_links")
    op.drop_table("diagnostic_reports")
    op.drop_index("ix_diagnostic_evidence_owner_task_kind", table_name="diagnostic_evidence")
    op.drop_table("diagnostic_evidence")
    op.drop_index("ix_diagnostic_steps_owner_task_position", table_name="diagnostic_steps")
    op.drop_table("diagnostic_steps")
    op.drop_index("ix_diagnostic_tasks_owner_updated_id", table_name="diagnostic_tasks")
    op.drop_table("diagnostic_tasks")
