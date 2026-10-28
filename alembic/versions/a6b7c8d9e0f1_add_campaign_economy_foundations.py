"""add campaign economy foundations

Revision ID: a6b7c8d9e0f1
Revises: a1b2c3d4e5f6
Create Date: 2026-10-28 00:00:00
"""

from collections.abc import Sequence
from hashlib import sha256

from alembic import op
import sqlalchemy as sa


revision: str = "a6b7c8d9e0f1"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REGIONS = (
    "Vale da Fronteira",
    "Bosque de Âmbar",
    "Costa das Brumas",
    "Terras de Cinza",
    "Picos do Norte",
)


def upgrade() -> None:
    op.add_column("campaign_metadata", sa.Column("home_region", sa.String(length=80), nullable=True))
    op.add_column("campaign_metadata", sa.Column("stamina_seconds", sa.Integer(), server_default="28800", nullable=False))
    op.add_column("campaign_metadata", sa.Column("stamina_recharge_remainder_seconds", sa.Integer(), server_default="0", nullable=False))
    op.add_column("campaign_metadata", sa.Column("pending_offline_report", sa.Text(), nullable=True))
    op.add_column("guild_resources", sa.Column("special_crystals", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "offline_return_reports",
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign_metadata.campaign_id"]),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index("ix_offline_return_reports_campaign_id", "offline_return_reports", ["campaign_id"])

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT campaign_id FROM campaign_metadata")).fetchall()
    for (campaign_id,) in rows:
        index = int.from_bytes(sha256(str(campaign_id).encode("utf-8")).digest()[:4], "big") % len(REGIONS)
        connection.execute(
            sa.text("UPDATE campaign_metadata SET home_region = :region WHERE campaign_id = :campaign_id"),
            {"region": REGIONS[index], "campaign_id": campaign_id},
        )
    connection.execute(sa.text("UPDATE building_templates SET max_level = 100"))

    op.create_table(
        "gathering_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("mercenary_id", sa.Integer(), nullable=False),
        sa.Column("resource_family", sa.String(length=30), nullable=False),
        sa.Column("node_code", sa.String(length=80), nullable=False),
        sa.Column("progress_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cycle_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("extra_chance", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rng_seed", sa.Integer(), server_default="1", nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkpoint_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"]),
        sa.ForeignKeyConstraint(["mercenary_id"], ["mercenaries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "resource_family", name="uq_gathering_family_per_guild"),
        sa.UniqueConstraint("mercenary_id", name="uq_gathering_mercenary"),
    )
    op.create_index("ix_gathering_assignments_id", "gathering_assignments", ["id"])
    op.create_index("ix_gathering_assignments_guild_id", "gathering_assignments", ["guild_id"])
    op.create_index("ix_gathering_assignments_mercenary_id", "gathering_assignments", ["mercenary_id"])


def downgrade() -> None:
    op.drop_index("ix_offline_return_reports_campaign_id", table_name="offline_return_reports")
    op.drop_table("offline_return_reports")
    op.drop_index("ix_gathering_assignments_mercenary_id", table_name="gathering_assignments")
    op.drop_index("ix_gathering_assignments_guild_id", table_name="gathering_assignments")
    op.drop_index("ix_gathering_assignments_id", table_name="gathering_assignments")
    op.drop_table("gathering_assignments")
    op.drop_column("guild_resources", "special_crystals")
    op.drop_column("campaign_metadata", "pending_offline_report")
    op.drop_column("campaign_metadata", "stamina_recharge_remainder_seconds")
    op.drop_column("campaign_metadata", "stamina_seconds")
    op.drop_column("campaign_metadata", "home_region")
