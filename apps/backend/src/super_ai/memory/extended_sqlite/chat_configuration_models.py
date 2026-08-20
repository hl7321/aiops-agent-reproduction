from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime


class UserChatPromptModel(Base):
    __tablename__ = "user_chat_prompts"
    __table_args__ = (
        CheckConstraint("length(label) > 0", name="ck_user_chat_prompts_label"),
        CheckConstraint("length(content) > 0", name="ck_user_chat_prompts_content"),
        Index("ix_user_chat_prompts_owner_created_id", "owner_user_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class UserChatConfigurationModel(Base):
    __tablename__ = "user_chat_configurations"
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    selected_prompt_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("user_chat_prompts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class UserChatSkillModel(Base):
    __tablename__ = "user_chat_skills"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_user_chat_skills_owner_name"),
        CheckConstraint("filename = 'SKILL.md'", name="ck_user_chat_skills_filename"),
        Index("ix_user_chat_skills_owner_created_id", "owner_user_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    metadata_json: Mapped[object] = mapped_column("metadata", CanonicalJson(), nullable=False)
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
