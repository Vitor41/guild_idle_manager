"""Persist timed supply workshop batches and reserve their output capacity."""

from alembic import op
import sqlalchemy as sa


revision = "f3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supply_workshop_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("output_item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False),
        sa.Column("kit_quantity", sa.Integer(), nullable=False),
        sa.Column("meat_per_kit", sa.Integer(), nullable=False),
        sa.Column("herb_per_kit", sa.Integer(), nullable=False),
        sa.Column("seconds_per_kit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_supply_workshop_jobs_id", "supply_workshop_jobs", ["id"])
    op.create_index("ix_supply_workshop_jobs_guild_id", "supply_workshop_jobs", ["guild_id"])
    op.create_index("ix_supply_workshop_jobs_status", "supply_workshop_jobs", ["status"])
    op.create_index("ix_supply_workshop_jobs_ends_at", "supply_workshop_jobs", ["ends_at"])
    op.create_index(
        "uq_supply_workshop_active_guild",
        "supply_workshop_jobs",
        ["guild_id"],
        unique=True,
        sqlite_where=sa.text("status = 'in_progress'"),
        postgresql_where=sa.text("status = 'in_progress'"),
    )


def downgrade() -> None:
    op.drop_index("uq_supply_workshop_active_guild", table_name="supply_workshop_jobs")
    op.drop_index("ix_supply_workshop_jobs_ends_at", table_name="supply_workshop_jobs")
    op.drop_index("ix_supply_workshop_jobs_status", table_name="supply_workshop_jobs")
    op.drop_index("ix_supply_workshop_jobs_guild_id", table_name="supply_workshop_jobs")
    op.drop_index("ix_supply_workshop_jobs_id", table_name="supply_workshop_jobs")
    op.drop_table("supply_workshop_jobs")
