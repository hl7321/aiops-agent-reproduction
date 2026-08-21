from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime
from super_ai.project_config import JsonValue


class DiagnosisCaseModel(Base):
    __tablename__ = "aiops_diagnostic_cases"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_aiops_diagnostic_cases_task"),
        Index("ix_aiops_cases_owner_created_id", "owner_user_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("diagnostic_tasks.id"))
    report_id: Mapped[str] = mapped_column(String(32), ForeignKey("diagnostic_reports.id"))
    document_id: Mapped[str] = mapped_column(String(32), ForeignKey("knowledge_documents.id"))
    index_task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("document_index_tasks.id")
    )
    alert_name: Mapped[str] = mapped_column(String(500))
    service: Mapped[str] = mapped_column(String(500))
    keywords: Mapped[list[JsonValue]] = mapped_column(CanonicalJson())
    root_cause: Mapped[str] = mapped_column(Text())
    remediation: Mapped[str] = mapped_column(Text())
    summary: Mapped[str] = mapped_column(Text())
    evidence_ids: Mapped[list[JsonValue]] = mapped_column(CanonicalJson())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
