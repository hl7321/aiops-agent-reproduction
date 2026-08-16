from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import UTCDateTime


class DocumentIndexTaskModel(Base):
    __tablename__ = "document_index_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_document_index_tasks_status",
        ),
        Index(
            "ix_document_index_tasks_owner_document_created",
            "owner_user_id",
            "knowledge_base_id",
            "document_id",
            "created_at",
        ),
        Index(
            "uq_document_index_tasks_active",
            "owner_user_id",
            "knowledge_base_id",
            "document_id",
            unique=True,
            sqlite_where=text("status IN ('pending','running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    retry_of_task_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("document_index_tasks.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
