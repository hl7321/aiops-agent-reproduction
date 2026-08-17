"""聊天 SQLAlchemy models。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime


class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_owner_updated_id", "owner_user_id", "updated_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="新会话")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant','system','tool')", name="ck_chat_messages_role"
        ),
        CheckConstraint("length(content) > 0", name="ck_chat_messages_content"),
        CheckConstraint("sequence > 0", name="ck_chat_messages_sequence"),
        UniqueConstraint("session_id", "sequence", name="uq_chat_messages_sequence"),
        Index("ix_chat_messages_owner_session_sequence", "owner_user_id", "session_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer(), nullable=False)
    metadata_json: Mapped[object] = mapped_column("metadata", CanonicalJson(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
