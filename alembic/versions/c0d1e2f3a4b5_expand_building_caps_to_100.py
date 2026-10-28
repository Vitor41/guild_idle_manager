"""expand the legacy default building cap to level 100

Revision ID: c0d1e2f3a4b5
Revises: b7c8d9e0f1a2
Create Date: 2026-10-28 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c0d1e2f3a4b5"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This is the stable identity set of the eight initial templates plus
    # Docks. Exactly 50 is their previous global cap; without a change-history
    # field, a built-in intentionally set to exactly 50 cannot be distinguished
    # from that legacy default. Non-built-in templates and non-50 admin caps
    # remain untouched.
    op.create_table(
        "_building_level_cap_compatibility",
        sa.Column("template_id", sa.Integer(), primary_key=True),
        sa.Column("previous_max_level", sa.Integer(), nullable=False),
    )
    op.execute(
        "INSERT INTO _building_level_cap_compatibility (template_id, previous_max_level) "
        "SELECT id, max_level FROM building_templates "
        "WHERE effect_type IN ("
        "'housing', 'training_ground', 'blacksmith', 'warehouse', 'contract_office', "
        "'scouts', 'tavern', 'market', 'docks') AND max_level = 50"
    )
    op.execute(
        "UPDATE building_templates SET max_level = 100 "
        "WHERE id IN (SELECT template_id FROM _building_level_cap_compatibility)"
    )


def downgrade() -> None:
    # Restore only rows still at the migrated value. Admin edits made after the
    # upgrade (for example 70) are kept intact.
    op.execute(
        "UPDATE building_templates SET max_level = ("
        "SELECT previous_max_level FROM _building_level_cap_compatibility "
        "WHERE template_id = building_templates.id) "
        "WHERE id IN (SELECT template_id FROM _building_level_cap_compatibility) "
        "AND max_level = 100"
    )
    op.drop_table("_building_level_cap_compatibility")
