"""rebalance PRD buildings to level 50

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-22 10:00:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE building_templates SET max_level = 50 WHERE max_level > 50")
    op.execute("UPDATE guild_buildings SET level = 50 WHERE level > 50")
    op.execute("UPDATE class_transition_options SET required_training_ground_level = 50 WHERE required_training_ground_level > 50")
    op.execute("UPDATE crafting_recipes SET required_blacksmith_level = 50 WHERE required_blacksmith_level > 50")


def downgrade() -> None:
    op.execute("UPDATE building_templates SET max_level = 100 WHERE max_level = 50")
