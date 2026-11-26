"""Add versioned portal spawn policy and campaign-region state."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f31a9c7d2b84"
down_revision: str | None = "e9f8a7b6c5d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regional_cycles",
        sa.Column("portal_spawn_rules_version", sa.String(40), nullable=True),
    )
    op.create_table(
        "regional_portal_spawn_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("region_code", sa.String(80), nullable=False),
        sa.Column("failure_stacks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_evaluated_cycle_number", sa.Integer(), nullable=True),
        sa.Column("last_portal_spawned_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_until_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rules_version", sa.String(40), nullable=False),
        sa.Column("last_result", sa.String(40), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("failure_stacks >= 0", name="ck_portal_spawn_failure_stacks_nonnegative"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "region_code", name="uq_portal_spawn_campaign_region"),
    )
    op.create_index(
        op.f("ix_regional_portal_spawn_state_campaign_id"),
        "regional_portal_spawn_state",
        ["campaign_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_regional_portal_spawn_state_campaign_id"),
        table_name="regional_portal_spawn_state",
    )
    op.drop_table("regional_portal_spawn_state")
    op.drop_column("regional_cycles", "portal_spawn_rules_version")
