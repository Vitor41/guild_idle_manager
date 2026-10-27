from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
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
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_clean_shutdown_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_session_state: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    save_format_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tutorial_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    confirmation_preferences: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    apprentice_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
