"""add confirmation preferences and achievement xp

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-20 22:00:00
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("confirmation_preferences", sa.Text(), server_default="{}", nullable=False))
    op.add_column("achievement_templates", sa.Column("reward_xp", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("achievement_templates", "reward_xp")
    op.drop_column("users", "confirmation_preferences")
