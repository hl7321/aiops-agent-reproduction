"""Agent 工具调用审计 SQLAlchemy model。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime


class AgentToolCallAuditModel(Base):
    __tablename__ = "agent_tool_call_audits"
    __table_args__ = (
        CheckConstraint(
            "(chat_session_id IS NOT NULL AND diagnostic_task_id IS NULL) OR "
            "(chat_session_id IS NULL AND diagnostic_task_id IS NOT NULL)",
            name="ck_agent_audits_exactly_one_parent",
        ),
        CheckConstraint(
            "status IN ('started','completed','failed')", name="ck_agent_audits_status"
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_audits_duration"
        ),
        Index(
            "ix_agent_audits_owner_chat_started_id",
            "owner_user_id",
            "chat_session_id",
            "started_at",
            "id",
        ),
        Index(
            "ix_agent_audits_owner_diagnostic_started_id",
            "owner_user_id",
            "diagnostic_task_id",
            "started_at",
            "id",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chat_session_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True
    )
    diagnostic_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments_json: Mapped[object] = mapped_column("arguments", CanonicalJson(), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer(), nullable=True)
