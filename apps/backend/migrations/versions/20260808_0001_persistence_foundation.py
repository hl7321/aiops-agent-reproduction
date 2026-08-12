"""建立 persistence foundation 的迁移链基线。

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08
"""

from collections.abc import Sequence

revision: str = "20260808_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """P03 不创建任何领域或通用 JSON 表。"""


def downgrade() -> None:
    """空 baseline 无业务 schema 可移除。"""
