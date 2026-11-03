"""Add a versioned regional risk snapshot for CPU offer resolution.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("regional_offers") as batch:
        batch.add_column(sa.Column(
            "cpu_failure_risk_snapshot", sa.Integer(), nullable=False, server_default="0",
        ))


def downgrade() -> None:
    with op.batch_alter_table("regional_offers") as batch:
        batch.drop_column("cpu_failure_risk_snapshot")
