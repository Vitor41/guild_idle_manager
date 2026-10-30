"""add campaign-scoped regional event lifecycle records

Revision ID: e3f4a5b6c7d8
Revises: d7e8f9a0b1c2, f6a7b8c9d0e1
Create Date: 2026-10-28 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: str | Sequence[str] | None = ("d7e8f9a0b1c2", "f6a7b8c9d0e1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("achievement_templates") as batch_op:
        batch_op.add_column(sa.Column("reward_item_template_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_achievement_reward_item_template",
            "item_templates",
            ["reward_item_template_id"],
            ["id"],
        )
    op.create_table(
        "regional_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("region_code", sa.String(length=80), nullable=False),
        sa.Column("trigger_cycle_number", sa.Integer(), nullable=False),
        sa.Column("rules_version", sa.String(length=40), nullable=False),
        sa.Column("seed", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("dungeon_template_id", sa.Integer(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority_ends_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cpu_started_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("player_decision", sa.String(length=20), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.ForeignKeyConstraint(["dungeon_template_id"], ["dungeon_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id", "event_type", "trigger_cycle_number", "region_code",
            name="uq_regional_event_trigger",
        ),
    )
    op.create_index("ix_regional_events_campaign_id", "regional_events", ["campaign_id"])
    op.create_index("ix_regional_events_event_type", "regional_events", ["event_type"])
    op.create_index("ix_regional_events_region_code", "regional_events", ["region_code"])
    op.create_index("ix_regional_events_status", "regional_events", ["status"])
    op.create_index("ix_regional_events_expires_at_utc", "regional_events", ["expires_at_utc"])

    op.create_table(
        "regional_event_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("guild_state_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("contribution", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["regional_events.id"]),
        sa.ForeignKeyConstraint(["guild_state_id"], ["regional_guild_state.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "guild_state_id", name="uq_regional_event_guild_participant"),
    )
    op.create_index("ix_regional_event_participants_event_id", "regional_event_participants", ["event_id"])
    op.create_index("ix_regional_event_participants_guild_state_id", "regional_event_participants", ["guild_state_id"])

    op.create_table(
        "regional_event_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("guild_state_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_run_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("successes", sa.Integer(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("contribution", sa.Integer(), nullable=False),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["regional_events.id"]),
        sa.ForeignKeyConstraint(["guild_state_id"], ["regional_guild_state.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_run_id", name="uq_regional_event_activity_source_run"),
    )
    op.create_index("ix_regional_event_activities_event_id", "regional_event_activities", ["event_id"])
    op.create_index("ix_regional_event_activities_guild_state_id", "regional_event_activities", ["guild_state_id"])


def downgrade() -> None:
    op.drop_index("ix_regional_event_activities_guild_state_id", table_name="regional_event_activities")
    op.drop_index("ix_regional_event_activities_event_id", table_name="regional_event_activities")
    op.drop_table("regional_event_activities")
    op.drop_index("ix_regional_event_participants_guild_state_id", table_name="regional_event_participants")
    op.drop_index("ix_regional_event_participants_event_id", table_name="regional_event_participants")
    op.drop_table("regional_event_participants")
    op.drop_index("ix_regional_events_expires_at_utc", table_name="regional_events")
    op.drop_index("ix_regional_events_status", table_name="regional_events")
    op.drop_index("ix_regional_events_region_code", table_name="regional_events")
    op.drop_index("ix_regional_events_event_type", table_name="regional_events")
    op.drop_index("ix_regional_events_campaign_id", table_name="regional_events")
    op.drop_table("regional_events")
    with op.batch_alter_table("achievement_templates") as batch_op:
        batch_op.drop_constraint("fk_achievement_reward_item_template", type_="foreignkey")
        batch_op.drop_column("reward_item_template_id")
