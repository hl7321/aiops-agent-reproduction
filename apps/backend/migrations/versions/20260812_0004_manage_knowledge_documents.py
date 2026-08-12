"""新增 owner-scoped 知识文档表。

Revision ID: 20260812_0004
Revises: 20260812_0003
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import UTCDateTime

revision: str = "20260812_0004"
down_revision: str | None = "20260812_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("knowledge_base_id", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_at", UTCDateTime(), nullable=False),
        sa.Column("index_status", sa.String(24), nullable=False),
        sa.Column("chunking_strategy", sa.String(32), nullable=False),
        sa.Column("max_characters", sa.Integer(), nullable=True),
        sa.Column("overlap", sa.Integer(), nullable=True),
        sa.Column("indexable_text", sa.Text(), nullable=False),
        sa.Column("deleted_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_documents_size"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_documents_sha256"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documents_owner_kb", "knowledge_documents", ["owner_user_id", "knowledge_base_id"]
    )
    op.create_index(
        "uq_documents_active_hash",
        "knowledge_documents",
        ["owner_user_id", "knowledge_base_id", "sha256"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_active_hash", table_name="knowledge_documents")
    op.drop_index("ix_documents_owner_kb", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
