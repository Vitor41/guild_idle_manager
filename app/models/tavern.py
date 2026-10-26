from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.mercenary import MercenaryClass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TavernConfig(Base):
    __tablename__ = "tavern_config"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    base_apprentice_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    apprentice_cost_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    apprentice_growth_before_threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    apprentice_growth_after_threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    common_apprentice_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    uncommon_apprentice_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    special_spawn_cooldown_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    special_offer_duration_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    special_spawn_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    special_rare_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    special_epic_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    special_legendary_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    special_mythic_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    special_rare_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=1500)
    special_epic_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=3500)
    special_legendary_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=8000)
    special_mythic_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=15000)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class GuildTavernState(Base):
    __tablename__ = "guild_tavern_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), unique=True, nullable=False, index=True)
    apprentice_hire_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_apprentice_hire_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    next_special_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="tavern_state")


class TavernSpecialOffer(Base):
    __tablename__ = "tavern_special_offers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=False, index=True)
    rarity: Mapped[str] = mapped_column(String(30), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    power: Mapped[int] = mapped_column(Integer, nullable=False)
    vitality: Mapped[int] = mapped_column(Integer, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False)
    luck: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="tavern_special_offers")
    mercenary_class: Mapped["MercenaryClass"] = relationship()
