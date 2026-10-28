from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.item import MissionTemplateItemDrop
    from app.models.mercenary import Mercenary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MissionTemplate(Base):
    __tablename__ = "mission_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    level_band: Mapped[str] = mapped_column(String(20), nullable=False, default="1-20", index=True)
    mission_type: Mapped[str] = mapped_column(String(30), nullable=False, default="standard", index=True)
    content_pack: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    recommended_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recommended_power: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    gathering_family: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    profession_code: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    base_gold_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    base_xp_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    base_success_chance: Mapped[int] = mapped_column(Integer, nullable=False)
    min_party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_guild_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_min_mercenary_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_building_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    required_building_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    runs: Mapped[list["MissionRun"]] = relationship(back_populates="mission_template")
    item_drops: Mapped[list["MissionTemplateItemDrop"]] = relationship(back_populates="mission_template")


class MissionRun(Base):
    __tablename__ = "mission_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    mission_template_id: Mapped[int] = mapped_column(ForeignKey("mission_templates.id"), nullable=False, index=True)
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

    guild: Mapped["Guild"] = relationship(back_populates="mission_runs")
    mission_template: Mapped[MissionTemplate] = relationship(back_populates="runs")
    members: Mapped[list["MissionRunMember"]] = relationship(
        back_populates="mission_run",
        cascade="all, delete-orphan",
    )


class MissionRunMember(Base):
    __tablename__ = "mission_run_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    mission_run_id: Mapped[int] = mapped_column(ForeignKey("mission_runs.id"), nullable=False, index=True)
    mercenary_id: Mapped[int] = mapped_column(ForeignKey("mercenaries.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    mission_run: Mapped[MissionRun] = relationship(back_populates="members")
    mercenary: Mapped["Mercenary"] = relationship(back_populates="mission_run_members")
