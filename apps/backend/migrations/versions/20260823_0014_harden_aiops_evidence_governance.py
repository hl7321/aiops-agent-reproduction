"""增强 AIOps 证据可信状态与 canonical case provenance。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

revision: str = "20260823_0014"
down_revision: str | None = "20260821_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("diagnostic_steps") as batch:
        batch.add_column(sa.Column("error_category", sa.String(40), nullable=True))
    with op.batch_alter_table("diagnostic_reports") as batch:
        batch.add_column(
            sa.Column(
                "trust_state",
                sa.String(32),
                nullable=False,
                server_default="insufficient_evidence",
            )
        )
        batch.create_check_constraint(
            "ck_diagnostic_reports_trust_state",
            "trust_state IN ('verified_evidence','insufficient_evidence','execution_failed')",
        )
    with op.batch_alter_table("diagnostic_evidence") as batch:
        batch.drop_constraint("ck_diagnostic_evidence_kind", type_="check")
        batch.create_check_constraint(
            "ck_diagnostic_evidence_kind",
            "kind IN ('alert','knowledge','log','log_hit','log_context','query_artifact','metric')",
        )
    with op.batch_alter_table("aiops_diagnostic_cases") as batch:
        batch.add_column(sa.Column("incident_fingerprint", sa.String(64), nullable=True))
        batch.add_column(sa.Column("knowledge_fingerprint", sa.String(64), nullable=True))
        batch.add_column(sa.Column("fingerprint_version", sa.String(16), nullable=True))
        batch.add_column(
            sa.Column("promotion_status", sa.String(16), nullable=False, server_default="legacy")
        )
        batch.create_unique_constraint(
            "uq_aiops_cases_owner_incident_fingerprint",
            ["owner_user_id", "incident_fingerprint"],
        )
        batch.create_unique_constraint(
            "uq_aiops_cases_owner_knowledge_fingerprint",
            ["owner_user_id", "knowledge_fingerprint"],
        )
        batch.create_check_constraint(
            "ck_aiops_cases_promotion_status",
            "promotion_status IN ('legacy','canonical')",
        )
    op.create_table(
        "diagnostic_case_sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(32),
            sa.ForeignKey("aiops_diagnostic_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "diagnostic_task_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            sa.String(32),
            sa.ForeignKey("diagnostic_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "approval_feedback_id",
            sa.String(32),
            sa.ForeignKey("user_feedback.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("evidence_ids", CanonicalJson(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.UniqueConstraint(
            "owner_user_id", "report_id", name="uq_diagnostic_case_sources_owner_report"
        ),
    )
    op.create_index(
        "ix_diagnostic_case_sources_owner_case_created",
        "diagnostic_case_sources",
        ["owner_user_id", "case_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_diagnostic_case_sources_owner_case_created", table_name="diagnostic_case_sources"
    )
    op.drop_table("diagnostic_case_sources")
    with op.batch_alter_table("aiops_diagnostic_cases") as batch:
        batch.drop_constraint("ck_aiops_cases_promotion_status", type_="check")
        batch.drop_constraint(
            "uq_aiops_cases_owner_knowledge_fingerprint", type_="unique"
        )
        batch.drop_constraint("uq_aiops_cases_owner_incident_fingerprint", type_="unique")
        batch.drop_column("promotion_status")
        batch.drop_column("fingerprint_version")
        batch.drop_column("knowledge_fingerprint")
        batch.drop_column("incident_fingerprint")
    with op.batch_alter_table("diagnostic_reports") as batch:
        batch.drop_constraint("ck_diagnostic_reports_trust_state", type_="check")
        batch.drop_column("trust_state")
    with op.batch_alter_table("diagnostic_evidence") as batch:
        batch.drop_constraint("ck_diagnostic_evidence_kind", type_="check")
        batch.create_check_constraint(
            "ck_diagnostic_evidence_kind",
            "kind IN ('alert','knowledge','log','metric')",
        )
    with op.batch_alter_table("diagnostic_steps") as batch:
        batch.drop_column("error_category")
