"""Persist optional regional supply preparation timers."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("regional_offers") as batch_op:
        batch_op.add_column(sa.Column("supply_preparation_started_at_utc", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("supply_preparation_ends_at_utc", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("supply_prepared_at_utc", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("supply_preparation_snapshot_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("regional_offers") as batch_op:
        batch_op.drop_column("supply_preparation_snapshot_json")
        batch_op.drop_column("supply_prepared_at_utc")
        batch_op.drop_column("supply_preparation_ends_at_utc")
        batch_op.drop_column("supply_preparation_started_at_utc")
