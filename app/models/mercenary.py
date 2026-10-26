from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.class_change import ClassChangeRun, ClassTransitionOption
    from app.models.dungeon import DungeonRunMember
    from app.models.guild import Guild
    from app.models.item import GuildItemInstance
    from app.models.mission import MissionRunMember
    from app.models.skill import MercenarySkill, SkillTemplate
    from app.models.content import ProfessionTemplate, ProfessionTraining


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MercenaryClass(Base):
    __tablename__ = "mercenary_classes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_class_id: Mapped[int | None] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=True)
    required_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allowed_weapon_profile: Mapped[str] = mapped_column(String(80), nullable=False, default="any")
    role_type: Mapped[str] = mapped_column(String(80), nullable=False, default="balanced")
    base_power: Mapped[int] = mapped_column(Integer, nullable=False)
    base_vitality: Mapped[int] = mapped_column(Integer, nullable=False)
    base_agility: Mapped[int] = mapped_column(Integer, nullable=False)
    base_intelligence: Mapped[int] = mapped_column(Integer, nullable=False)
    base_luck: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    mercenaries: Mapped[list["Mercenary"]] = relationship(back_populates="mercenary_class")
    next_transitions: Mapped[list["ClassTransitionOption"]] = relationship(
        back_populates="from_class",
        foreign_keys="ClassTransitionOption.from_class_id",
    )
    class_change_targets: Mapped[list["ClassChangeRun"]] = relationship(
        back_populates="to_class",
        foreign_keys="ClassChangeRun.to_class_id",
    )
    skill_templates: Mapped[list["SkillTemplate"]] = relationship(back_populates="mercenary_class")


class Mercenary(Base):
    __tablename__ = "mercenaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=False, index=True)
    profession_id: Mapped[int | None] = mapped_column(ForeignKey("profession_templates.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="available")
    rarity: Mapped[str] = mapped_column(String(30), nullable=False, default="common")
    hire_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    power: Mapped[int] = mapped_column(Integer, nullable=False)
    vitality: Mapped[int] = mapped_column(Integer, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False)
    luck: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="mercenaries")
    mercenary_class: Mapped[MercenaryClass] = relationship(back_populates="mercenaries")
    mission_run_members: Mapped[list["MissionRunMember"]] = relationship(back_populates="mercenary")
    dungeon_run_members: Mapped[list["DungeonRunMember"]] = relationship(back_populates="mercenary")
    equipment_instances: Mapped[list["GuildItemInstance"]] = relationship(back_populates="equipped_to_mercenary")
    class_change_runs: Mapped[list["ClassChangeRun"]] = relationship(back_populates="mercenary")
    skills: Mapped[list["MercenarySkill"]] = relationship(
        back_populates="mercenary",
        cascade="all, delete-orphan",
    )
    profession: Mapped["ProfessionTemplate | None"] = relationship(back_populates="mercenaries")
    profession_trainings: Mapped[list["ProfessionTraining"]] = relationship(back_populates="mercenary")
