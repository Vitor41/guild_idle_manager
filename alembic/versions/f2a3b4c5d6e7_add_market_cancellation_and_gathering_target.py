"""Persist collection targets and cancelled market sale state timestamps.

Revision ID: f2a3b4c5d6e7
Revises: f1a2b3c4d5e6
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("gathering_assignments") as batch:
        batch.add_column(sa.Column("target_item_template_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_gathering_assignments_target_item_template_id_item_templates",
            "item_templates", ["target_item_template_id"], ["id"],
        )
        batch.create_index("ix_gathering_assignments_target_item_template_id", ["target_item_template_id"])
    with op.batch_alter_table("market_sales") as batch:
        batch.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("market_sales") as batch:
        batch.drop_column("cancelled_at")
    with op.batch_alter_table("gathering_assignments") as batch:
        batch.drop_index("ix_gathering_assignments_target_item_template_id")
        batch.drop_constraint(
            "fk_gathering_assignments_target_item_template_id_item_templates",
            type_="foreignkey",
        )
        batch.drop_column("target_item_template_id")
