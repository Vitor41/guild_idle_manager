"""add metadata needed by local offline campaigns

Revision ID: a1b2c3d4e5f6
Revises: c9d0e1f2a3b4
Create Date: 2026-10-26 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_metadata",
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_name", sa.String(length=120), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_clean_shutdown_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_session_state", sa.String(length=30), nullable=False, server_default="created"),
        sa.Column("save_format_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tutorial_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("confirmation_preferences", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("apprentice_preview", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("campaign_id"),
    )
    op.alter_column("guilds", "user_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("guilds", sa.Column("campaign_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_guilds_campaign_id"), "guilds", ["campaign_id"], unique=True)
    op.create_foreign_key(
        "fk_guilds_campaign_id_campaign_metadata",
        "guilds",
        "campaign_metadata",
        ["campaign_id"],
        ["campaign_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_guilds_campaign_id_campaign_metadata", "guilds", type_="foreignkey")
    op.drop_index(op.f("ix_guilds_campaign_id"), table_name="guilds")
    op.drop_column("guilds", "campaign_id")
    op.alter_column("guilds", "user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_table("campaign_metadata")
