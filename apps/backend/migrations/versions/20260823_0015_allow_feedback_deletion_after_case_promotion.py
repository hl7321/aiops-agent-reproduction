"""允许删除案例提升反馈，同时保留 canonical case 与来源记录。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0015"
down_revision: str | None = "20260823_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
}
_FK_NAME = "fk_diagnostic_case_sources_approval_feedback_id_user_feedback"


def upgrade() -> None:
    with op.batch_alter_table(
        "diagnostic_case_sources",
        recreate="always",
        naming_convention=_NAMING_CONVENTION,
    ) as batch:
        batch.drop_constraint(_FK_NAME, type_="foreignkey")
        batch.alter_column(
            "approval_feedback_id",
            existing_type=sa.String(32),
            nullable=True,
        )
        batch.create_foreign_key(
            _FK_NAME,
            "user_feedback",
            ["approval_feedback_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "diagnostic_case_sources",
        recreate="always",
        naming_convention=_NAMING_CONVENTION,
    ) as batch:
        batch.drop_constraint(_FK_NAME, type_="foreignkey")
        batch.alter_column(
            "approval_feedback_id",
            existing_type=sa.String(32),
            nullable=False,
        )
        batch.create_foreign_key(
            _FK_NAME,
            "user_feedback",
            ["approval_feedback_id"],
            ["id"],
            ondelete="RESTRICT",
        )
