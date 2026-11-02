"""Unify crystal balances and persist gameplay snapshots/collection goals."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE guild_resources SET crystals = crystals + special_crystals"
    ))
    with op.batch_alter_table("guild_resources") as batch:
        batch.add_column(sa.Column("crystal_reserve", sa.Integer(), nullable=False, server_default="0"))
    bind.execute(sa.text(
        "UPDATE guild_resources SET crystal_reserve = special_crystals"
    ))
    with op.batch_alter_table("guild_resources") as batch:
        batch.drop_column("special_crystals")
    with op.batch_alter_table("regional_offers") as batch:
        batch.add_column(sa.Column("required_guild_level_snapshot", sa.Integer(), nullable=False, server_default="1"))
    bind.execute(sa.text("""
        UPDATE regional_offers
        SET required_guild_level_snapshot = COALESCE(
            (SELECT required_guild_level FROM mission_templates WHERE mission_templates.id = regional_offers.mission_template_id),
            (SELECT required_guild_level FROM dungeon_templates WHERE dungeon_templates.id = regional_offers.dungeon_template_id),
            1
        )
    """))
    with op.batch_alter_table("gathering_assignments") as batch:
        batch.add_column(sa.Column("target_quantity", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("quantity_collected", sa.Integer(), nullable=False, server_default="0"))
    bind.execute(sa.text(
        "UPDATE tavern_config SET special_spawn_cooldown_hours = 12 WHERE special_spawn_cooldown_hours = 24"
    ))
    bind.execute(sa.text(
        "UPDATE tavern_config SET special_offer_duration_hours = 3 WHERE special_offer_duration_hours = 24"
    ))


def downgrade() -> None:
    with op.batch_alter_table("guild_resources") as batch:
        batch.add_column(sa.Column("special_crystals", sa.Integer(), nullable=False, server_default="0"))
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE guild_resources SET special_crystals = crystal_reserve, crystals = crystals - crystal_reserve"))
    with op.batch_alter_table("guild_resources") as batch:
        batch.drop_column("crystal_reserve")
    with op.batch_alter_table("regional_offers") as batch:
        batch.drop_column("required_guild_level_snapshot")
    with op.batch_alter_table("gathering_assignments") as batch:
        batch.drop_column("quantity_collected")
        batch.drop_column("target_quantity")
    # Consolidated crystals remain in the normal balance on downgrade.
    bind.execute(sa.text(
        "UPDATE tavern_config SET special_spawn_cooldown_hours = 24 WHERE special_spawn_cooldown_hours = 12"
    ))
    bind.execute(sa.text(
        "UPDATE tavern_config SET special_offer_duration_hours = 24 WHERE special_offer_duration_hours = 3"
    ))
