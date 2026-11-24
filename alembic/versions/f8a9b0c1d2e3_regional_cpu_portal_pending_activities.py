"""Persist pending CPU portal work and per-event diagnostics."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f8a9b0c1d2e3"
down_revision: str | Sequence[str] | None = "f31a9c7d2b84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regional_cpu_cycle_plans",
        sa.Column(
            "event_diagnostics_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("regional_event_activities", sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("regional_event_activities", sa.Column("due_at_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("regional_event_activities", sa.Column("snapshot_json", sa.Text(), nullable=True))
    op.add_column("regional_event_activities", sa.Column("reason_code", sa.String(length=40), nullable=True))
    op.add_column("regional_event_activities", sa.Column("reason_detail", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_regional_event_activity_cpu_pending_due",
        "regional_event_activities",
        ["source_type", "status", "due_at_utc"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regional_event_activity_cpu_pending_due",
        table_name="regional_event_activities",
    )
    op.drop_column("regional_event_activities", "reason_detail")
    op.drop_column("regional_event_activities", "reason_code")
    op.drop_column("regional_event_activities", "snapshot_json")
    op.drop_column("regional_event_activities", "due_at_utc")
    op.drop_column("regional_event_activities", "started_at_utc")
    op.drop_column("regional_cpu_cycle_plans", "event_diagnostics_json")
