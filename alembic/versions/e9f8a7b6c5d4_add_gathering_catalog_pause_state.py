"""Persist gathering catalog pauses across requests and reloads."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e9f8a7b6c5d4"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gathering_assignments",
        sa.Column("catalog_paused", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("gathering_assignments", "catalog_paused")
