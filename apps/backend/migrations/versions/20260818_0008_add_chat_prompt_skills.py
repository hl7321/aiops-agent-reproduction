"""新增 owner-scoped Chat Prompt、Skill 与选择配置。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

revision: str = "20260818_0008"
down_revision: str | None = "20260817_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_chat_prompts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("length(label) > 0", name="ck_user_chat_prompts_label"),
        sa.CheckConstraint("length(content) > 0", name="ck_user_chat_prompts_content"),
    )
    op.create_index(
        "ix_user_chat_prompts_owner_created_id",
        "user_chat_prompts",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_table(
        "user_chat_configurations",
        sa.Column("owner_user_id", sa.String(32), primary_key=True),
        sa.Column("selected_prompt_id", sa.String(32), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["selected_prompt_id"], ["user_chat_prompts.id"], ondelete="SET NULL"
        ),
    )
    op.create_table(
        "user_chat_skills",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("filename", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", CanonicalJson(), nullable=False),
        sa.Column("summary", sa.String(240), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_user_chat_skills_owner_name"),
        sa.CheckConstraint("filename = 'SKILL.md'", name="ck_user_chat_skills_filename"),
    )
    op.create_index(
        "ix_user_chat_skills_owner_created_id",
        "user_chat_skills",
        ["owner_user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_chat_skills_owner_created_id", table_name="user_chat_skills")
    op.drop_table("user_chat_skills")
    op.drop_table("user_chat_configurations")
    op.drop_index("ix_user_chat_prompts_owner_created_id", table_name="user_chat_prompts")
    op.drop_table("user_chat_prompts")
