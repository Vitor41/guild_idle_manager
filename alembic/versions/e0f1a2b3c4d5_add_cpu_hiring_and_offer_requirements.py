"""Add snapshots for CPU eligibility and recruitment telemetry.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e0f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("regional_offers") as batch:
        batch.add_column(sa.Column(
            "required_min_mercenary_level_snapshot", sa.Integer(), nullable=False, server_default="1",
        ))
        batch.add_column(sa.Column(
            "required_total_power_snapshot", sa.Integer(), nullable=False, server_default="0",
        ))
        batch.add_column(sa.Column("required_class_code_snapshot", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column(
            "required_tank_count_snapshot", sa.Integer(), nullable=False, server_default="0",
        ))
        batch.add_column(sa.Column(
            "required_support_count_snapshot", sa.Integer(), nullable=False, server_default="0",
        ))
        batch.add_column(sa.Column(
            "required_damage_count_snapshot", sa.Integer(), nullable=False, server_default="0",
        ))
        batch.add_column(sa.Column(
            "required_equipment_tier_snapshot", sa.Integer(), nullable=False, server_default="0",
        ))

    with op.batch_alter_table("regional_cpu_cycle_plans") as batch:
        batch.add_column(sa.Column("hired_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("hire_gold_spent", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("regional_cpu_cycle_plans") as batch:
        batch.drop_column("hire_gold_spent")
        batch.drop_column("hired_count")
    with op.batch_alter_table("regional_offers") as batch:
        batch.drop_column("required_equipment_tier_snapshot")
        batch.drop_column("required_damage_count_snapshot")
        batch.drop_column("required_support_count_snapshot")
        batch.drop_column("required_tank_count_snapshot")
        batch.drop_column("required_class_code_snapshot")
        batch.drop_column("required_total_power_snapshot")
        batch.drop_column("required_min_mercenary_level_snapshot")
