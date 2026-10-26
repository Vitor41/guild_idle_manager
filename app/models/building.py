from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BuildingTemplate(Base):
    __tablename__ = "building_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    effect_type: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    base_upgrade_gold_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    base_upgrade_wood_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    base_upgrade_ore_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    base_upgrade_crystals_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    required_guild_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild_buildings: Mapped[list["GuildBuilding"]] = relationship(back_populates="building_template")


class GuildBuilding(Base):
    __tablename__ = "guild_buildings"
    __table_args__ = (
        UniqueConstraint("guild_id", "building_template_id", name="uq_guild_building_template"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    building_template_id: Mapped[int] = mapped_column(ForeignKey("building_templates.id"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="buildings")
    building_template: Mapped[BuildingTemplate] = relationship(back_populates="guild_buildings")
