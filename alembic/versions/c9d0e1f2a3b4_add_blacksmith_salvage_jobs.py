"""add blacksmith salvage jobs

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-22 21:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guild_salvage_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("item_template_id", sa.Integer(), nullable=False),
        sa.Column("material_template_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("gold_cost", sa.Integer(), nullable=False),
        sa.Column("result_quantity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("slot_number BETWEEN 1 AND 3", name="ck_salvage_slot_number"),
        sa.CheckConstraint("quantity > 0", name="ck_salvage_quantity"),
        sa.CheckConstraint("gold_cost > 0", name="ck_salvage_gold_cost"),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"]),
        sa.ForeignKeyConstraint(["item_template_id"], ["item_templates.id"]),
        sa.ForeignKeyConstraint(["material_template_id"], ["item_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guild_salvage_jobs_guild_id", "guild_salvage_jobs", ["guild_id"])
    op.create_index("ix_guild_salvage_jobs_status", "guild_salvage_jobs", ["status"])
    op.create_index("ix_guild_salvage_jobs_ends_at", "guild_salvage_jobs", ["ends_at"])
    op.create_index(
        "uq_guild_salvage_active_slot",
        "guild_salvage_jobs",
        ["guild_id", "slot_number"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
        sqlite_where=sa.text("status = 'in_progress'"),
    )


def downgrade() -> None:
    op.drop_index("uq_guild_salvage_active_slot", table_name="guild_salvage_jobs")
    op.drop_index("ix_guild_salvage_jobs_ends_at", table_name="guild_salvage_jobs")
    op.drop_index("ix_guild_salvage_jobs_status", table_name="guild_salvage_jobs")
    op.drop_index("ix_guild_salvage_jobs_guild_id", table_name="guild_salvage_jobs")
    op.drop_table("guild_salvage_jobs")
