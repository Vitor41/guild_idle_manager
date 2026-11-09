"""Persist multiple normal and FORTE bonuses on equipment instances."""

from alembic import op
import sqlalchemy as sa


revision = "0a1b2c3d4e5f"
down_revision = "f3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_item_instances",
        sa.Column("bonus_rolls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("guild_item_instances", "bonus_rolls")
