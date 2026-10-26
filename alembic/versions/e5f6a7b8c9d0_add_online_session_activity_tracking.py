"""add online session activity tracking

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-20 20:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("guild_activity", sa.Column("is_online", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("guild_activity", sa.Column("session_token", sa.String(64), nullable=True))
    op.add_column("guild_activity", sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("guild_activity", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("guild_activity", sa.Column("offline_started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_guild_activity_session_token", "guild_activity", ["session_token"])
    op.execute("UPDATE guild_activity SET offline_started_at = last_seen_at")


def downgrade() -> None:
    op.drop_index("ix_guild_activity_session_token", table_name="guild_activity")
    op.drop_column("guild_activity", "offline_started_at")
    op.drop_column("guild_activity", "last_activity_at")
    op.drop_column("guild_activity", "session_started_at")
    op.drop_column("guild_activity", "session_token")
    op.drop_column("guild_activity", "is_online")
