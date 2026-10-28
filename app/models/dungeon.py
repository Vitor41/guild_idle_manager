from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.item import DungeonTemplateItemDrop
    from app.models.mercenary import Mercenary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DungeonTemplate(Base):
    __tablename__ = "dungeon_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="dungeon", index=True)
    content_pack: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    level_band: Mapped[str] = mapped_column(String(20), nullable=False, default="1-20", index=True)
    recommended_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    biome: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    base_gold_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    base_xp_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    base_success_chance: Mapped[int] = mapped_column(Integer, nullable=False)
    min_party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    required_guild_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_min_mercenary_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_building_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    required_building_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_total_power: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_class_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    required_tank_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_support_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_damage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_equipment_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    runs: Mapped[list["DungeonRun"]] = relationship(back_populates="dungeon_template")
    item_drops: Mapped[list["DungeonTemplateItemDrop"]] = relationship(back_populates="dungeon_template")


class DungeonRun(Base):
    __tablename__ = "dungeon_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    dungeon_template_id: Mapped[int] = mapped_column(ForeignKey("dungeon_templates.id"), nullable=False, index=True)
    regional_offer_id: Mapped[int | None] = mapped_column(ForeignKey("regional_offers.id"), nullable=True, unique=True)
    rank_snapshot: Mapped[str | None] = mapped_column(String(2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="in_progress", index=True)
    run_multiplier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    gold_reward: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xp_reward: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="dungeon_runs")
    dungeon_template: Mapped[DungeonTemplate] = relationship(back_populates="runs")
    members: Mapped[list["DungeonRunMember"]] = relationship(
        back_populates="dungeon_run",
        cascade="all, delete-orphan",
    )


class DungeonRunMember(Base):
    __tablename__ = "dungeon_run_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dungeon_run_id: Mapped[int] = mapped_column(ForeignKey("dungeon_runs.id"), nullable=False, index=True)
    mercenary_id: Mapped[int] = mapped_column(ForeignKey("mercenaries.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    dungeon_run: Mapped[DungeonRun] = relationship(back_populates="members")
    mercenary: Mapped["Mercenary"] = relationship(back_populates="dungeon_run_members")
