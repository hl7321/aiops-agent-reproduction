from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime
from super_ai.project_config import JsonValue


class DiagnosisCaseModel(Base):
    __tablename__ = "aiops_diagnostic_cases"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_aiops_diagnostic_cases_task"),
        UniqueConstraint(
            "owner_user_id",
            "incident_fingerprint",
            name="uq_aiops_cases_owner_incident_fingerprint",
        ),
        UniqueConstraint(
            "owner_user_id",
            "knowledge_fingerprint",
            name="uq_aiops_cases_owner_knowledge_fingerprint",
        ),
        CheckConstraint(
            "promotion_status IN ('legacy','canonical')",
            name="ck_aiops_cases_promotion_status",
        ),
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
    incident_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    knowledge_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    promotion_status: Mapped[str] = mapped_column(String(16), default="legacy")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class DiagnosticCaseSourceModel(Base):
    __tablename__ = "diagnostic_case_sources"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "report_id", name="uq_diagnostic_case_sources_owner_report"
        ),
        Index(
            "ix_diagnostic_case_sources_owner_case_created",
            "owner_user_id",
            "case_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("aiops_diagnostic_cases.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"), nullable=False
    )
    report_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_reports.id", ondelete="CASCADE"), nullable=False
    )
    approval_feedback_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("user_feedback.id", ondelete="SET NULL"), nullable=True
    )
    evidence_ids: Mapped[list[JsonValue]] = mapped_column(CanonicalJson())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
