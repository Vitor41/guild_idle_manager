"""Track planned and executed CPU guild actions per Vigília.

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("regional_cpu_cycle_plans") as batch:
        batch.add_column(sa.Column("planned_actions", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("eligible_actions", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("started_actions", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("resolved_actions", sa.Integer(), nullable=False, server_default="0"))
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE regional_cpu_cycle_plans
        SET planned_actions = actions,
            eligible_actions = actions,
            started_actions = actions,
            resolved_actions = actions
    """))


def downgrade() -> None:
    with op.batch_alter_table("regional_cpu_cycle_plans") as batch:
        batch.drop_column("resolved_actions")
        batch.drop_column("started_actions")
        batch.drop_column("eligible_actions")
        batch.drop_column("planned_actions")
