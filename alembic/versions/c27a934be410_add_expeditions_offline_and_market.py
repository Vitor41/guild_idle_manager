"""add expeditions metadata, offline progress and market

Revision ID: c27a934be410
Revises: ef8f80ce71ab
Create Date: 2026-06-19 18:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c27a934be410"
down_revision: str | None = "ef8f80ce71ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mission_templates", sa.Column("difficulty", sa.String(length=30), server_default="normal", nullable=False))
    op.add_column("mission_templates", sa.Column("level_band", sa.String(length=20), server_default="1-20", nullable=False))
    op.add_column("mission_templates", sa.Column("mission_type", sa.String(length=30), server_default="standard", nullable=False))
    op.create_index(op.f("ix_mission_templates_level_band"), "mission_templates", ["level_band"], unique=False)
    op.create_index(op.f("ix_mission_templates_mission_type"), "mission_templates", ["mission_type"], unique=False)

    op.add_column("item_templates", sa.Column("base_sell_value", sa.Integer(), server_default="1", nullable=False))
    op.execute("UPDATE item_templates SET base_sell_value = CASE WHEN item_type = 'equipment' THEN GREATEST(10, tier * 20) ELSE GREATEST(1, tier * 2) END")

    op.create_table(
        "guild_activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id"),
    )
    op.create_index(op.f("ix_guild_activity_id"), "guild_activity", ["id"], unique=False)
    op.create_index(op.f("ix_guild_activity_guild_id"), "guild_activity", ["guild_id"], unique=True)

    op.create_table(
        "market_sales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("item_template_id", sa.Integer(), nullable=False),
        sa.Column("item_instance_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_value", sa.Integer(), nullable=False),
        sa.Column("total_value", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"]),
        sa.ForeignKeyConstraint(["item_instance_id"], ["guild_item_instances.id"]),
        sa.ForeignKeyConstraint(["item_template_id"], ["item_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_instance_id"),
    )
    op.create_index(op.f("ix_market_sales_id"), "market_sales", ["id"], unique=False)
    op.create_index(op.f("ix_market_sales_guild_id"), "market_sales", ["guild_id"], unique=False)
    op.create_index(op.f("ix_market_sales_item_template_id"), "market_sales", ["item_template_id"], unique=False)
    op.create_index(op.f("ix_market_sales_item_instance_id"), "market_sales", ["item_instance_id"], unique=True)
    op.create_index(op.f("ix_market_sales_status"), "market_sales", ["status"], unique=False)
    op.create_index(op.f("ix_market_sales_ends_at"), "market_sales", ["ends_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_market_sales_ends_at"), table_name="market_sales")
    op.drop_index(op.f("ix_market_sales_status"), table_name="market_sales")
    op.drop_index(op.f("ix_market_sales_item_instance_id"), table_name="market_sales")
    op.drop_index(op.f("ix_market_sales_item_template_id"), table_name="market_sales")
    op.drop_index(op.f("ix_market_sales_guild_id"), table_name="market_sales")
    op.drop_index(op.f("ix_market_sales_id"), table_name="market_sales")
    op.drop_table("market_sales")
    op.drop_index(op.f("ix_guild_activity_guild_id"), table_name="guild_activity")
    op.drop_index(op.f("ix_guild_activity_id"), table_name="guild_activity")
    op.drop_table("guild_activity")
    op.drop_column("item_templates", "base_sell_value")
    op.drop_index(op.f("ix_mission_templates_mission_type"), table_name="mission_templates")
    op.drop_index(op.f("ix_mission_templates_level_band"), table_name="mission_templates")
    op.drop_column("mission_templates", "mission_type")
    op.drop_column("mission_templates", "level_band")
    op.drop_column("mission_templates", "difficulty")
