"""知识文档 SQLAlchemy model。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import UTCDateTime


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_documents_size"),
        CheckConstraint("length(sha256) = 64", name="ck_documents_sha256"),
        CheckConstraint(
            "index_status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_knowledge_documents_index_status",
        ),
        Index("ix_documents_owner_kb", "owner_user_id", "knowledge_base_id"),
        Index(
            "uq_documents_active_hash",
            "owner_user_id",
            "knowledge_base_id",
            "sha256",
            unique=True,
            sqlite_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer(), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    index_status: Mapped[str] = mapped_column(String(24), nullable=False)
    chunking_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    max_characters: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    overlap: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    indexable_text: Mapped[str] = mapped_column(Text(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
