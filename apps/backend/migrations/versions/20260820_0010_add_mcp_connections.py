"""增加 owner-scoped MCP Server 连接。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

revision: str = "20260820_0010"
down_revision: str | None = "20260818_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_connections",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("transport", sa.String(32), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("last_check", UTCDateTime(), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("discovered_tools", CanonicalJson(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_mcp_connections_owner_name"),
        sa.CheckConstraint(
            "transport IN ('sse','streamable_http')",
            name="ck_mcp_connections_transport",
        ),
        sa.CheckConstraint("timeout_seconds BETWEEN 1 AND 300", name="ck_mcp_connections_timeout"),
        sa.CheckConstraint("retries BETWEEN 0 AND 5", name="ck_mcp_connections_retries"),
    )
    op.create_index(
        "ix_mcp_connections_owner_updated_id",
        "mcp_connections",
        ["owner_user_id", "updated_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_connections_owner_updated_id", table_name="mcp_connections")
    op.drop_table("mcp_connections")
