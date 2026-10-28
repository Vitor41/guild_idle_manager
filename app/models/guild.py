from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.building import GuildBuilding
    from app.models.class_change import ClassChangeRun
    from app.models.dungeon import DungeonRun
    from app.models.item import GuildInventoryItem, GuildItemInstance
    from app.models.mercenary import Mercenary
    from app.models.mission import MissionRun
    from app.models.market import GuildActivity, MarketSale
    from app.models.salvage import GuildSalvageJob
    from app.models.tavern import GuildTavernState, TavernSpecialOffer
    from app.models.user import User
    from app.models.achievement import GuildAchievement, GuildCodexUnlock, GuildStat


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True, index=True)
    campaign_id: Mapped[str | None] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), unique=True, nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reputation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user: Mapped["User | None"] = relationship(back_populates="guild")
    resources: Mapped["GuildResources | None"] = relationship(
        back_populates="guild",
        uselist=False,
        cascade="all, delete-orphan",
    )
    mercenaries: Mapped[list["Mercenary"]] = relationship(back_populates="guild")
    mission_runs: Mapped[list["MissionRun"]] = relationship(back_populates="guild")
    dungeon_runs: Mapped[list["DungeonRun"]] = relationship(back_populates="guild")
    inventory_items: Mapped[list["GuildInventoryItem"]] = relationship(back_populates="guild")
    item_instances: Mapped[list["GuildItemInstance"]] = relationship(back_populates="guild")
    buildings: Mapped[list["GuildBuilding"]] = relationship(back_populates="guild")
    tavern_state: Mapped["GuildTavernState | None"] = relationship(
        back_populates="guild",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tavern_special_offers: Mapped[list["TavernSpecialOffer"]] = relationship(back_populates="guild")
    class_change_runs: Mapped[list["ClassChangeRun"]] = relationship(back_populates="guild")
    activity: Mapped["GuildActivity | None"] = relationship(
        back_populates="guild",
        uselist=False,
        cascade="all, delete-orphan",
    )
    market_sales: Mapped[list["MarketSale"]] = relationship(back_populates="guild")
    salvage_jobs: Mapped[list["GuildSalvageJob"]] = relationship(back_populates="guild")
    achievements: Mapped[list["GuildAchievement"]] = relationship(back_populates="guild")
    codex_unlocks: Mapped[list["GuildCodexUnlock"]] = relationship(back_populates="guild")
    stats: Mapped[list["GuildStat"]] = relationship(back_populates="guild")


class GuildResources(Base):
    __tablename__ = "guild_resources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), unique=True, nullable=False, index=True)
    gold: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    wood: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ore: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crystals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    special_crystals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped[Guild] = relationship(back_populates="resources")
