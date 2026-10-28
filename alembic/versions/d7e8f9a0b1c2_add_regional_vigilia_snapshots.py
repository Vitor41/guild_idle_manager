"""add campaign-scoped regional cycles, snapshots, and outcomes

Revision ID: d7e8f9a0b1c2
Revises: c0d1e2f3a4b5
Create Date: 2026-10-28 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: str | None = "c0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "regional_world_state",
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("last_materialized_cycle", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("last_completed_cycle", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("rules_version", sa.String(40), nullable=False, server_default="vigilia-v1"),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.PrimaryKeyConstraint("campaign_id"),
    )
    op.create_table(
        "regional_region_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("region_code", sa.String(80), nullable=False),
        sa.Column("region_name", sa.String(100), nullable=False),
        sa.Column("security", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("threat", sa.Float(), nullable=False, server_default="25.0"),
        sa.Column("influence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated_cycle", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "region_code", name="uq_region_campaign_code"),
    )
    op.create_index("ix_regional_region_state_campaign_id", "regional_region_state", ["campaign_id"])

    op.create_table(
        "regional_guild_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("region_code", sa.String(80), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False),
        sa.Column("archetype", sa.String(30), nullable=False),
        sa.Column("roster_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("power", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reputation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("influence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "region_code", "slot", name="uq_regional_guild_slot"),
        sa.UniqueConstraint("guild_id"),
    )
    op.create_index("ix_regional_guild_state_campaign_id", "regional_guild_state", ["campaign_id"])
    op.create_index("ix_regional_guild_state_region_code", "regional_guild_state", ["region_code"])
    op.create_index("ix_regional_guild_state_guild_id", "regional_guild_state", ["guild_id"])

    op.create_table(
        "regional_cpu_mercenaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("guild_state_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("class_code", sa.String(80), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rarity", sa.String(30), nullable=False, server_default="common"),
        sa.Column("profession_code", sa.String(60), nullable=True),
        sa.Column("power", sa.Integer(), nullable=False),
        sa.Column("vitality", sa.Integer(), nullable=False),
        sa.Column("agility", sa.Integer(), nullable=False),
        sa.Column("intelligence", sa.Integer(), nullable=False),
        sa.Column("luck", sa.Integer(), nullable=False),
        sa.Column("armor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("equipment_bonus_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["guild_state_id"], ["regional_guild_state.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_state_id", "slot", name="uq_regional_cpu_mercenary_slot"),
    )
    op.create_index("ix_regional_cpu_mercenaries_campaign_id", "regional_cpu_mercenaries", ["campaign_id"])
    op.create_index("ix_regional_cpu_mercenaries_guild_state_id", "regional_cpu_mercenaries", ["guild_state_id"])
    op.create_table(
        "regional_cpu_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("guild_state_id", sa.Integer(), nullable=False),
        sa.Column("resource_code", sa.String(60), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["guild_state_id"], ["regional_guild_state.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_state_id", "resource_code", name="uq_regional_cpu_resource_code"),
    )
    op.create_index("ix_regional_cpu_resources_campaign_id", "regional_cpu_resources", ["campaign_id"])
    op.create_index("ix_regional_cpu_resources_guild_state_id", "regional_cpu_resources", ["guild_state_id"])

    op.create_table(
        "regional_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("starts_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seed", sa.String(64), nullable=False),
        sa.Column("rules_version", sa.String(40), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player_level_snapshot", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("player_power_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank_weights_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("processed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "cycle_number", name="uq_regional_campaign_cycle"),
    )
    op.create_index("ix_regional_cycles_campaign_id", "regional_cycles", ["campaign_id"])

    op.create_table(
        "regional_cpu_cycle_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("guild_state_id", sa.Integer(), nullable=False),
        sa.Column("seed", sa.String(64), nullable=False),
        sa.Column("roster_snapshot_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("resources_before_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("resources_after_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("decisions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("outcomes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gold_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["regional_cycles.id"]),
        sa.ForeignKeyConstraint(["guild_state_id"], ["regional_guild_state.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "guild_state_id", name="uq_regional_cpu_cycle_guild"),
    )
    op.create_index("ix_regional_cpu_cycle_plans_campaign_id", "regional_cpu_cycle_plans", ["campaign_id"])
    op.create_index("ix_regional_cpu_cycle_plans_cycle_id", "regional_cpu_cycle_plans", ["cycle_id"])
    op.create_index("ix_regional_cpu_cycle_plans_guild_state_id", "regional_cpu_cycle_plans", ["guild_state_id"])

    op.create_table(
        "regional_cycle_regions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(80), nullable=False),
        sa.Column("security_before", sa.Float(), nullable=False),
        sa.Column("threat_before", sa.Float(), nullable=False),
        sa.Column("influence_before", sa.Integer(), nullable=False),
        sa.Column("security_after", sa.Float(), nullable=False),
        sa.Column("threat_after", sa.Float(), nullable=False),
        sa.Column("influence_after", sa.Integer(), nullable=False),
        sa.Column("cpu_actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cpu_successes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cpu_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cpu_gold_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cpu_xp_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["regional_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "region_code", name="uq_regional_cycle_region"),
    )
    op.create_index("ix_regional_cycle_regions_campaign_id", "regional_cycle_regions", ["campaign_id"])
    op.create_index("ix_regional_cycle_regions_cycle_id", "regional_cycle_regions", ["cycle_id"])

    op.create_table(
        "regional_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(80), nullable=False),
        sa.Column("offer_type", sa.String(20), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("mission_template_id", sa.Integer(), nullable=True),
        sa.Column("dungeon_template_id", sa.Integer(), nullable=True),
        sa.Column("reserved_by_guild_state_id", sa.Integer(), nullable=True),
        sa.Column("rank", sa.String(2), nullable=False),
        sa.Column("name_snapshot", sa.String(120), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("level_band_snapshot", sa.String(20), nullable=False, server_default="1-20"),
        sa.Column("recommended_level_snapshot", sa.Integer(), nullable=False),
        sa.Column("recommended_power_snapshot", sa.Integer(), nullable=False),
        sa.Column("min_party_size_snapshot", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_party_size_snapshot", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("duration_seconds_snapshot", sa.Integer(), nullable=False),
        sa.Column("gold_reward_snapshot", sa.Integer(), nullable=False),
        sa.Column("xp_reward_snapshot", sa.Integer(), nullable=False),
        sa.Column("success_chance_snapshot", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["regional_cycles.id"]),
        sa.ForeignKeyConstraint(["dungeon_template_id"], ["dungeon_templates.id"]),
        sa.ForeignKeyConstraint(["mission_template_id"], ["mission_templates.id"]),
        sa.ForeignKeyConstraint(["reserved_by_guild_state_id"], ["regional_guild_state.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "region_code", "offer_type", "slot", name="uq_regional_offer_slot"),
    )
    op.create_index("ix_regional_offers_campaign_id", "regional_offers", ["campaign_id"])
    op.create_index("ix_regional_offers_cycle_id", "regional_offers", ["cycle_id"])
    op.create_index("ix_regional_offers_cycle_number", "regional_offers", ["cycle_number"])
    op.create_index("ix_regional_offers_region_code", "regional_offers", ["region_code"])
    op.create_index("ix_regional_offers_reserved_by_guild_state_id", "regional_offers", ["reserved_by_guild_state_id"])

    op.create_table(
        "regional_run_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("guild_state_id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_run_id", sa.Integer(), nullable=False),
        sa.Column("offer_cycle_number", sa.Integer(), nullable=False),
        sa.Column("applied_cycle_number", sa.Integer(), nullable=False),
        sa.Column("rank", sa.String(2), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("contribution", sa.Integer(), nullable=False),
        sa.Column("gold_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["guild_state_id"], ["regional_guild_state.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["regional_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "source_type", "source_run_id", name="uq_regional_run_outcome_source"),
    )
    op.create_index("ix_regional_run_outcomes_campaign_id", "regional_run_outcomes", ["campaign_id"])
    op.create_index("ix_regional_run_outcomes_guild_state_id", "regional_run_outcomes", ["guild_state_id"])
    op.create_index("ix_regional_run_outcomes_offer_id", "regional_run_outcomes", ["offer_id"])

    with op.batch_alter_table("mission_runs") as batch:
        batch.add_column(sa.Column("regional_offer_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rank_snapshot", sa.String(2), nullable=True))
        batch.create_foreign_key("fk_mission_run_regional_offer", "regional_offers", ["regional_offer_id"], ["id"])
        batch.create_unique_constraint("uq_mission_run_regional_offer", ["regional_offer_id"])
    with op.batch_alter_table("dungeon_runs") as batch:
        batch.add_column(sa.Column("regional_offer_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rank_snapshot", sa.String(2), nullable=True))
        batch.create_foreign_key("fk_dungeon_run_regional_offer", "regional_offers", ["regional_offer_id"], ["id"])
        batch.create_unique_constraint("uq_dungeon_run_regional_offer", ["regional_offer_id"])

    op.execute("UPDATE campaign_metadata SET schema_version = 5 WHERE schema_version < 5")


def downgrade() -> None:
    with op.batch_alter_table("dungeon_runs") as batch:
        batch.drop_constraint("uq_dungeon_run_regional_offer", type_="unique")
        batch.drop_constraint("fk_dungeon_run_regional_offer", type_="foreignkey")
        batch.drop_column("rank_snapshot")
        batch.drop_column("regional_offer_id")
    with op.batch_alter_table("mission_runs") as batch:
        batch.drop_constraint("uq_mission_run_regional_offer", type_="unique")
        batch.drop_constraint("fk_mission_run_regional_offer", type_="foreignkey")
        batch.drop_column("rank_snapshot")
        batch.drop_column("regional_offer_id")
    op.drop_table("regional_run_outcomes")
    op.drop_table("regional_offers")
    op.drop_table("regional_cycle_regions")
    op.drop_table("regional_cpu_cycle_plans")
    op.drop_table("regional_cycles")
    op.drop_table("regional_cpu_resources")
    op.drop_table("regional_cpu_mercenaries")
    op.drop_table("regional_guild_state")
    op.drop_table("regional_region_state")
    op.drop_table("regional_world_state")
    op.execute("UPDATE campaign_metadata SET schema_version = 4 WHERE schema_version > 4")
