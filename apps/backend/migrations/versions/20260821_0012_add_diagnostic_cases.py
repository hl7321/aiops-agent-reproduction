"""增加诊断 case 与知识文档来源 metadata。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

revision: str = "20260821_0012"
down_revision: str | None = "20260820_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.add_column(
            sa.Column("source_metadata", CanonicalJson(), nullable=False, server_default="{}")
        )
    op.create_table(
        "aiops_diagnostic_cases",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("diagnostic_tasks.id"), nullable=False),
        sa.Column(
            "report_id", sa.String(32), sa.ForeignKey("diagnostic_reports.id"), nullable=False
        ),
        sa.Column(
            "document_id",
            sa.String(32),
            sa.ForeignKey("knowledge_documents.id"),
            nullable=False,
        ),
        sa.Column(
            "index_task_id",
            sa.String(32),
            sa.ForeignKey("document_index_tasks.id"),
            nullable=False,
        ),
        sa.Column("alert_name", sa.String(500), nullable=False),
        sa.Column("service", sa.String(500), nullable=False),
        sa.Column("keywords", CanonicalJson(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_ids", CanonicalJson(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.UniqueConstraint("task_id", name="uq_aiops_diagnostic_cases_task"),
    )
    op.create_index(
        "ix_aiops_cases_owner_created_id",
        "aiops_diagnostic_cases",
        ["owner_user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_aiops_cases_owner_created_id", table_name="aiops_diagnostic_cases")
    op.drop_table("aiops_diagnostic_cases")
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.drop_column("source_metadata")
