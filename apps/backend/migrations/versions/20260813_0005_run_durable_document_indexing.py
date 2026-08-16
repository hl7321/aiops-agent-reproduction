"""新增 durable 文档索引领域任务。

Revision ID: 20260813_0005
Revises: 20260812_0004
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import UTCDateTime

revision: str = "20260813_0005"
down_revision: str | None = "20260812_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE knowledge_documents SET index_status = 'pending' WHERE index_status = 'not-indexed'"
    )
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.create_check_constraint(
            "ck_knowledge_documents_index_status",
            "index_status IN ('pending','running','succeeded','failed','cancelled')",
        )
    op.create_table(
        "document_index_tasks",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("knowledge_base_id", sa.String(64), nullable=False),
        sa.Column("document_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("retry_of_task_id", sa.String(32), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("completed_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_document_index_tasks_status",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["retry_of_task_id"], ["document_index_tasks.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_index_tasks_owner_document_created",
        "document_index_tasks",
        ["owner_user_id", "knowledge_base_id", "document_id", "created_at"],
    )
    op.create_index(
        "uq_document_index_tasks_active",
        "document_index_tasks",
        ["owner_user_id", "knowledge_base_id", "document_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending','running')"),
    )
    op.create_index(
        "ix_background_jobs_resource", "background_jobs", ["resource_type", "resource_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_background_jobs_resource", table_name="background_jobs")
    op.drop_index("uq_document_index_tasks_active", table_name="document_index_tasks")
    op.drop_index(
        "ix_document_index_tasks_owner_document_created",
        table_name="document_index_tasks",
    )
    op.drop_table("document_index_tasks")
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.drop_constraint("ck_knowledge_documents_index_status", type_="check")
