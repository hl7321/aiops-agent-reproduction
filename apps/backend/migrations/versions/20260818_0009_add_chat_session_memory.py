"""为 Chat session 增加持久记忆压缩状态。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import UTCDateTime

revision: str = "20260818_0009"
down_revision: str | None = "20260818_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.add_column(
            sa.Column(
                "memory_mode",
                sa.String(32),
                nullable=False,
                server_default="context_70_percent",
            )
        )
        batch.add_column(sa.Column("memory_summary", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "compacted_message_count", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.add_column(
            sa.Column("context_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("last_compacted_at", UTCDateTime(), nullable=True))
        batch.create_check_constraint(
            "ck_chat_sessions_memory_mode",
            "memory_mode IN ('every_30_turns','context_70_percent','manual')",
        )
        batch.create_check_constraint(
            "ck_chat_sessions_compacted_message_count",
            "compacted_message_count >= 0",
        )
        batch.create_check_constraint(
            "ck_chat_sessions_context_tokens",
            "context_tokens >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_constraint("ck_chat_sessions_context_tokens", type_="check")
        batch.drop_constraint("ck_chat_sessions_compacted_message_count", type_="check")
        batch.drop_constraint("ck_chat_sessions_memory_mode", type_="check")
        batch.drop_column("last_compacted_at")
        batch.drop_column("context_tokens")
        batch.drop_column("compacted_message_count")
        batch.drop_column("memory_summary")
        batch.drop_column("memory_mode")
