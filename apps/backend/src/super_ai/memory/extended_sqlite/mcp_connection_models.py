from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime


class McpConnectionModel(Base):
    __tablename__ = "mcp_connections"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_mcp_connections_owner_name"),
        CheckConstraint(
            "transport IN ('sse','streamable_http')",
            name="ck_mcp_connections_transport",
        ),
        CheckConstraint("timeout_seconds BETWEEN 1 AND 300", name="ck_mcp_connections_timeout"),
        CheckConstraint("retries BETWEEN 0 AND 5", name="ck_mcp_connections_retries"),
        Index("ix_mcp_connections_owner_updated_id", "owner_user_id", "updated_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text(), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer(), nullable=False, default=30)
    retries: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    last_check: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    discovered_tools_json: Mapped[object] = mapped_column(
        "discovered_tools", CanonicalJson(), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
