"""认证领域的 SQLAlchemy ORM models。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base, IdTimestampMixin
from super_ai.memory.sqlite.types import UTCDateTime


class UserModel(IdTimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text(), nullable=False)


class AuthSessionModel(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="ck_auth_sessions_token_hash_length"),
        Index("ix_auth_sessions_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
