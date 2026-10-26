from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.item import GuildItemInstance, ItemTemplate


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuildActivity(Base):
    __tablename__ = "guild_activity"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), unique=True, nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    session_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    session_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offline_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    guild: Mapped["Guild"] = relationship(back_populates="activity")


class MarketSale(Base):
    __tablename__ = "market_sales"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    item_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("guild_item_instances.id"), unique=True, nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_value: Mapped[int] = mapped_column(Integer, nullable=False)
    total_value: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    guild: Mapped["Guild"] = relationship(back_populates="market_sales")
    item_template: Mapped["ItemTemplate"] = relationship(back_populates="market_sales")
    item_instance: Mapped["GuildItemInstance | None"] = relationship(back_populates="market_sale")
