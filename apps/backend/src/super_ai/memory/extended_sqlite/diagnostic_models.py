"""AIOps 诊断规范化 SQLAlchemy models。"""

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


class DiagnosticTaskModel(Base):
    __tablename__ = "diagnostic_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('accepted','running','succeeded','failed','cancelled')",
            name="ck_diagnostic_tasks_status",
        ),
        Index("ix_diagnostic_tasks_owner_updated_id", "owner_user_id", "updated_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    query: Mapped[str | None] = mapped_column(Text(), nullable=True)
    alerts_json: Mapped[object] = mapped_column("alerts", CanonicalJson(), nullable=False)
    current_plan_json: Mapped[object] = mapped_column(
        "current_plan", CanonicalJson(), nullable=False
    )
    plan_version: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    replan_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class DiagnosticStepModel(Base):
    __tablename__ = "diagnostic_steps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_diagnostic_steps_status",
        ),
        UniqueConstraint(
            "owner_user_id",
            "diagnostic_task_id",
            "plan_version",
            "position",
            "attempt",
            name="uq_diagnostic_steps_attempt",
        ),
        Index(
            "ix_diagnostic_steps_owner_task_position",
            "owner_user_id",
            "diagnostic_task_id",
            "plan_version",
            "position",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"), nullable=False
    )
    plan_version: Mapped[int] = mapped_column(Integer(), nullable=False)
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer(), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments_json: Mapped[object] = mapped_column("arguments", CanonicalJson(), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class DiagnosticEvidenceModel(Base):
    __tablename__ = "diagnostic_evidence"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('alert','knowledge','log','metric')", name="ck_diagnostic_evidence_kind"
        ),
        Index(
            "ix_diagnostic_evidence_owner_task_kind",
            "owner_user_id",
            "diagnostic_task_id",
            "kind",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_step_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("diagnostic_steps.id", ondelete="SET NULL"), nullable=True
    )
    tool_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    metadata_json: Mapped[object] = mapped_column("metadata", CanonicalJson(), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class DiagnosticReportModel(Base):
    __tablename__ = "diagnostic_reports"
    __table_args__ = (
        CheckConstraint(
            "generation_mode IN ('model','fallback')", name="ck_diagnostic_reports_mode"
        ),
        UniqueConstraint(
            "owner_user_id", "diagnostic_task_id", "revision", name="uq_diagnostic_reports_revision"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer(), nullable=False)
    markdown: Mapped[str] = mapped_column(Text(), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    uncertainty: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ReportEvidenceLinkModel(Base):
    __tablename__ = "report_evidence_links"
    __table_args__ = (
        UniqueConstraint("report_id", "claim_key", "evidence_id", name="uq_report_evidence_link"),
        Index(
            "ix_report_links_owner_task_report",
            "owner_user_id",
            "diagnostic_task_id",
            "report_id",
            "position",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"), nullable=False
    )
    report_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_reports.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_evidence.id", ondelete="CASCADE"), nullable=False
    )
    claim_key: Mapped[str] = mapped_column(String(120), nullable=False)
    section: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer(), nullable=False)


class GraphCheckpointModel(Base):
    __tablename__ = "graph_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "diagnostic_task_id",
            "checkpoint_version",
            name="uq_graph_checkpoint_version",
        ),
        Index(
            "ix_graph_checkpoints_owner_task_version",
            "owner_user_id",
            "diagnostic_task_id",
            "checkpoint_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    diagnostic_task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"), nullable=False
    )
    checkpoint_version: Mapped[int] = mapped_column(Integer(), nullable=False)
    node: Mapped[str] = mapped_column(String(32), nullable=False)
    state_json: Mapped[object] = mapped_column("state", CanonicalJson(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
