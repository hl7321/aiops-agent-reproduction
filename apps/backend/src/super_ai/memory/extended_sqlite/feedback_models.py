"""结构化用户反馈 SQLAlchemy model。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import UTCDateTime


class UserFeedbackModel(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('chat_message','citation','diagnostic_step','diagnostic_report')",
            name="ck_user_feedback_target_type",
        ),
        CheckConstraint("rating IN ('positive','negative')", name="ck_user_feedback_rating"),
        CheckConstraint(
            "reason IS NULL OR reason IN "
            "('incorrect','incomplete','irrelevant','unclear','unsafe','other')",
            name="ck_user_feedback_reason",
        ),
        UniqueConstraint(
            "owner_user_id", "target_type", "target_id", "subject_key",
            name="uq_user_feedback_subject",
        ),
        Index(
            "ix_user_feedback_owner_target",
            "owner_user_id", "target_type", "target_id", "subject_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    correction: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
