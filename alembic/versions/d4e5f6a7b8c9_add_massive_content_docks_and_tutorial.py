"""add massive content docks professions and tutorial

Revision ID: d4e5f6a7b8c9
Revises: b51f3c8a9210
Create Date: 2026-06-20 18:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "b51f3c8a9210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("item_templates", sa.Column("slug", sa.String(180), nullable=True))
    op.add_column("item_templates", sa.Column("level_band", sa.String(20), server_default="1-20", nullable=False))
    op.add_column("item_templates", sa.Column("content_pack", sa.String(80), nullable=True))
    op.add_column("item_templates", sa.Column("material_family", sa.String(60), nullable=True))
    op.add_column("item_templates", sa.Column("favored_class_code", sa.String(80), nullable=True))
    op.add_column("item_templates", sa.Column("favored_attribute", sa.String(30), nullable=True))
    op.create_index("ix_item_templates_slug", "item_templates", ["slug"], unique=True)
    op.create_index("ix_item_templates_level_band", "item_templates", ["level_band"])
    op.create_index("ix_item_templates_content_pack", "item_templates", ["content_pack"])
    op.create_index("ix_item_templates_material_family", "item_templates", ["material_family"])

    op.add_column("mission_templates", sa.Column("slug", sa.String(180), nullable=True))
    op.add_column("mission_templates", sa.Column("content_pack", sa.String(80), nullable=True))
    op.add_column("mission_templates", sa.Column("recommended_level", sa.Integer(), server_default="1", nullable=False))
    op.add_column("mission_templates", sa.Column("recommended_power", sa.Integer(), server_default="10", nullable=False))
    op.add_column("mission_templates", sa.Column("gathering_family", sa.String(60), nullable=True))
    op.add_column("mission_templates", sa.Column("profession_code", sa.String(60), nullable=True))
    op.create_index("ix_mission_templates_slug", "mission_templates", ["slug"], unique=True)
    op.create_index("ix_mission_templates_content_pack", "mission_templates", ["content_pack"])
    op.create_index("ix_mission_templates_gathering_family", "mission_templates", ["gathering_family"])
    op.create_index("ix_mission_templates_profession_code", "mission_templates", ["profession_code"])

    op.add_column("dungeon_templates", sa.Column("slug", sa.String(180), nullable=True))
    op.add_column("dungeon_templates", sa.Column("content_pack", sa.String(80), nullable=True))
    op.add_column("dungeon_templates", sa.Column("level_band", sa.String(20), server_default="1-20", nullable=False))
    op.add_column("dungeon_templates", sa.Column("recommended_level", sa.Integer(), server_default="1", nullable=False))
    op.add_column("dungeon_templates", sa.Column("biome", sa.String(60), nullable=True))
    op.create_index("ix_dungeon_templates_slug", "dungeon_templates", ["slug"], unique=True)
    op.create_index("ix_dungeon_templates_content_pack", "dungeon_templates", ["content_pack"])
    op.create_index("ix_dungeon_templates_level_band", "dungeon_templates", ["level_band"])
    op.create_index("ix_dungeon_templates_biome", "dungeon_templates", ["biome"])

    op.add_column("users", sa.Column("tutorial_status", sa.String(20), server_default="pending", nullable=False))

    op.create_table(
        "profession_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("material_family", sa.String(60), nullable=False),
        sa.Column("bonus_percent", sa.Integer(), server_default="15", nullable=False),
        sa.Column("training_gold_cost", sa.Integer(), server_default="250", nullable=False),
        sa.Column("training_duration_seconds", sa.Integer(), server_default="3600", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("code"), sa.UniqueConstraint("name"),
    )
    op.create_index("ix_profession_templates_code", "profession_templates", ["code"])
    op.create_index("ix_profession_templates_material_family", "profession_templates", ["material_family"])
    op.add_column("mercenaries", sa.Column("profession_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_mercenaries_profession", "mercenaries", "profession_templates", ["profession_id"], ["id"])
    op.create_index("ix_mercenaries_profession_id", "mercenaries", ["profession_id"])
    op.create_table(
        "profession_trainings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("mercenary_id", sa.Integer(), sa.ForeignKey("mercenaries.id"), nullable=False),
        sa.Column("profession_id", sa.Integer(), sa.ForeignKey("profession_templates.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="in_progress", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_profession_trainings_guild_id", "profession_trainings", ["guild_id"])
    op.create_index("ix_profession_trainings_mercenary_id", "profession_trainings", ["mercenary_id"])
    op.create_index("ix_profession_trainings_status", "profession_trainings", ["status"])

    op.create_table(
        "content_seed_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pack_key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("report_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pack_key", "version", name="uq_content_seed_pack_version"),
    )
    op.create_index("ix_content_seed_runs_pack_key", "content_seed_runs", ["pack_key"])

    op.create_table(
        "merchant_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("merchant_type", sa.String(60), nullable=False),
        sa.Column("min_dock_level", sa.Integer(), server_default="1", nullable=False),
        sa.Column("rotation_weight", sa.Integer(), server_default="100", nullable=False),
        sa.Column("content_pack", sa.String(80), server_default="massivo_v1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("slug"), sa.UniqueConstraint("name"),
    )
    op.create_index("ix_merchant_templates_slug", "merchant_templates", ["slug"])
    op.create_index("ix_merchant_templates_merchant_type", "merchant_templates", ["merchant_type"])
    op.create_table(
        "merchant_offer_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_template_id", sa.Integer(), sa.ForeignKey("merchant_templates.id"), nullable=False),
        sa.Column("item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False),
        sa.Column("base_price", sa.Integer(), nullable=False),
        sa.Column("min_stock", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_stock", sa.Integer(), server_default="1", nullable=False),
        sa.Column("min_dock_level", sa.Integer(), server_default="1", nullable=False),
        sa.Column("weight", sa.Integer(), server_default="100", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("merchant_template_id", "item_template_id", name="uq_merchant_item_offer"),
    )
    op.create_index("ix_merchant_offer_templates_merchant_template_id", "merchant_offer_templates", ["merchant_template_id"])
    op.create_index("ix_merchant_offer_templates_item_template_id", "merchant_offer_templates", ["item_template_id"])
    op.create_table(
        "dock_rotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dock_rotations_guild_id", "dock_rotations", ["guild_id"])
    op.create_index("ix_dock_rotations_status", "dock_rotations", ["status"])
    op.create_index("ix_dock_rotations_ends_at", "dock_rotations", ["ends_at"])
    op.create_table(
        "dock_rotation_merchants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dock_rotation_id", sa.Integer(), sa.ForeignKey("dock_rotations.id"), nullable=False),
        sa.Column("merchant_template_id", sa.Integer(), sa.ForeignKey("merchant_templates.id"), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.UniqueConstraint("dock_rotation_id", "slot", name="uq_dock_rotation_slot"),
    )
    op.create_index("ix_dock_rotation_merchants_dock_rotation_id", "dock_rotation_merchants", ["dock_rotation_id"])
    op.create_table(
        "dock_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dock_rotation_merchant_id", sa.Integer(), sa.ForeignKey("dock_rotation_merchants.id"), nullable=False),
        sa.Column("item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("initial_stock", sa.Integer(), nullable=False),
        sa.Column("remaining_stock", sa.Integer(), nullable=False),
    )
    op.create_index("ix_dock_offers_dock_rotation_merchant_id", "dock_offers", ["dock_rotation_merchant_id"])


def downgrade() -> None:
    op.drop_table("dock_offers")
    op.drop_table("dock_rotation_merchants")
    op.drop_table("dock_rotations")
    op.drop_table("merchant_offer_templates")
    op.drop_table("merchant_templates")
    op.drop_table("content_seed_runs")
    op.drop_table("profession_trainings")
    op.drop_index("ix_mercenaries_profession_id", table_name="mercenaries")
    op.drop_constraint("fk_mercenaries_profession", "mercenaries", type_="foreignkey")
    op.drop_column("mercenaries", "profession_id")
    op.drop_table("profession_templates")
    op.drop_column("users", "tutorial_status")
    for table, columns in {
        "dungeon_templates": ["biome", "recommended_level", "level_band", "content_pack", "slug"],
        "mission_templates": ["profession_code", "gathering_family", "recommended_power", "recommended_level", "content_pack", "slug"],
        "item_templates": ["favored_attribute", "favored_class_code", "material_family", "content_pack", "level_band", "slug"],
    }.items():
        for column in columns:
            op.drop_column(table, column)
