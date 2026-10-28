from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CampaignMetadata(Base):
    __tablename__ = "campaign_metadata"

    campaign_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_clean_shutdown_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_session_state: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    save_format_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tutorial_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    confirmation_preferences: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    apprentice_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    home_region: Mapped[str] = mapped_column(String(80), nullable=False, default="Fronteira do Norte")
    stamina_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=8 * 60 * 60)
    stamina_recharge_remainder_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_offline_report: Mapped[str | None] = mapped_column(Text, nullable=True)


class OfflineReturnReport(Base):
    __tablename__ = "offline_return_reports"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    acknowledged_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
