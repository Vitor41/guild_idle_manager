"""add skills bosses crafting refinement progression and codex

Revision ID: b51f3c8a9210
Revises: c27a934be410
Create Date: 2026-06-20 12:00:00
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "b51f3c8a9210"
down_revision: str | None = "c27a934be410"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dungeon_templates", sa.Column("content_type", sa.String(30), server_default="dungeon", nullable=False))
    op.add_column("dungeon_templates", sa.Column("difficulty", sa.String(30), server_default="normal", nullable=False))
    op.add_column("dungeon_templates", sa.Column("required_total_power", sa.Integer(), server_default="0", nullable=False))
    op.add_column("dungeon_templates", sa.Column("required_class_code", sa.String(80), nullable=True))
    op.add_column("dungeon_templates", sa.Column("required_tank_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("dungeon_templates", sa.Column("required_support_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("dungeon_templates", sa.Column("required_damage_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("dungeon_templates", sa.Column("required_equipment_tier", sa.Integer(), server_default="0", nullable=False))
    op.create_index("ix_dungeon_templates_content_type", "dungeon_templates", ["content_type"])
    op.add_column("guild_item_instances", sa.Column("upgrade_level", sa.Integer(), server_default="0", nullable=False))
    op.add_column("building_templates", sa.Column("required_guild_level", sa.Integer(), server_default="1", nullable=False))

    op.create_table("skill_templates",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("class_id", sa.Integer(), sa.ForeignKey("mercenary_classes.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("effect_type", sa.String(50), nullable=False), sa.Column("effect_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_level", sa.Integer(), server_default="10", nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("class_id", "name", name="uq_skill_class_name"))
    op.create_index("ix_skill_templates_class_id", "skill_templates", ["class_id"])
    op.create_index("ix_skill_templates_effect_type", "skill_templates", ["effect_type"])
    op.create_table("mercenary_skills",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("mercenary_id", sa.Integer(), sa.ForeignKey("mercenaries.id"), nullable=False),
        sa.Column("skill_template_id", sa.Integer(), sa.ForeignKey("skill_templates.id"), nullable=False), sa.Column("level", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("mercenary_id", "skill_template_id", name="uq_mercenary_skill"))
    op.create_index("ix_mercenary_skills_mercenary_id", "mercenary_skills", ["mercenary_id"])
    op.create_index("ix_mercenary_skills_skill_template_id", "mercenary_skills", ["skill_template_id"])

    op.create_table("crafting_recipes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), server_default="", nullable=False), sa.Column("output_item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False),
        sa.Column("output_quantity", sa.Integer(), server_default="1", nullable=False), sa.Column("gold_cost", sa.Integer(), server_default="0", nullable=False),
        sa.Column("required_blacksmith_level", sa.Integer(), server_default="1", nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_crafting_recipes_output_item_template_id", "crafting_recipes", ["output_item_template_id"])
    op.create_table("crafting_recipe_materials",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("crafting_recipes.id"), nullable=False),
        sa.Column("item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint("recipe_id", "item_template_id", name="uq_recipe_material"))
    op.create_index("ix_crafting_recipe_materials_recipe_id", "crafting_recipe_materials", ["recipe_id"])
    op.create_index("ix_crafting_recipe_materials_item_template_id", "crafting_recipe_materials", ["item_template_id"])

    op.create_table("achievement_templates",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("title", sa.String(120), nullable=False), sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("criterion_type", sa.String(60), nullable=False), sa.Column("threshold", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reward_gold", sa.Integer(), server_default="0", nullable=False), sa.Column("is_secret", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_index("ix_achievement_templates_criterion_type", "achievement_templates", ["criterion_type"])
    op.create_table("guild_achievements",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("achievement_template_id", sa.Integer(), sa.ForeignKey("achievement_templates.id"), nullable=False), sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True)), sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("guild_id", "achievement_template_id", name="uq_guild_achievement"))
    op.create_index("ix_guild_achievements_guild_id", "guild_achievements", ["guild_id"])

    op.create_table("codex_entries",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("key", sa.String(140), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False), sa.Column("reference_key", sa.String(120), nullable=False),
        sa.Column("title", sa.String(120), nullable=False), sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("rarity", sa.String(30), server_default="common", nullable=False))
    op.create_index("ix_codex_entries_category", "codex_entries", ["category"])
    op.create_table("guild_codex_unlocks",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("codex_entry_id", sa.Integer(), sa.ForeignKey("codex_entries.id"), nullable=False), sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("guild_id", "codex_entry_id", name="uq_guild_codex_unlock"))
    op.create_index("ix_guild_codex_unlocks_guild_id", "guild_codex_unlocks", ["guild_id"])
    op.create_table("guild_stats",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("key", sa.String(80), nullable=False), sa.Column("value", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("guild_id", "key", name="uq_guild_stat"))
    op.create_index("ix_guild_stats_guild_id", "guild_stats", ["guild_id"])
    op.create_index("ix_guild_stats_key", "guild_stats", ["key"])


def downgrade() -> None:
    for table in ("guild_stats", "guild_codex_unlocks", "codex_entries", "guild_achievements", "achievement_templates",
                  "crafting_recipe_materials", "crafting_recipes", "mercenary_skills", "skill_templates"):
        op.drop_table(table)
    op.drop_column("building_templates", "required_guild_level")
    op.drop_column("guild_item_instances", "upgrade_level")
    op.drop_index("ix_dungeon_templates_content_type", table_name="dungeon_templates")
    for column in ("required_equipment_tier", "required_damage_count", "required_support_count", "required_tank_count",
                   "required_class_code", "required_total_power", "difficulty", "content_type"):
        op.drop_column("dungeon_templates", column)
