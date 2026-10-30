"""Add backward-compatible supply preparation snapshots to activity runs."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mission_runs") as batch_op:
        batch_op.add_column(sa.Column("preparation_snapshot_json", sa.Text(), nullable=True))
    with op.batch_alter_table("dungeon_runs") as batch_op:
        batch_op.add_column(sa.Column("preparation_snapshot_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("dungeon_runs") as batch_op:
        batch_op.drop_column("preparation_snapshot_json")
    with op.batch_alter_table("mission_runs") as batch_op:
        batch_op.drop_column("preparation_snapshot_json")
