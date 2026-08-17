"""新增 owner-scoped 聊天会话与消息。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

revision: str = "20260817_0006"
down_revision: str | None = "20260813_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_chat_sessions_owner_updated_id",
        "chat_sessions",
        ["owner_user_id", "updated_at", "id"],
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("session_id", sa.String(32), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("metadata", CanonicalJson(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "role IN ('user','assistant','system','tool')", name="ck_chat_messages_role"
        ),
        sa.CheckConstraint("length(content) > 0", name="ck_chat_messages_content"),
        sa.CheckConstraint("sequence > 0", name="ck_chat_messages_sequence"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_chat_messages_sequence"),
    )
    op.create_index(
        "ix_chat_messages_owner_session_sequence",
        "chat_messages",
        ["owner_user_id", "session_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_owner_session_sequence", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_owner_updated_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
