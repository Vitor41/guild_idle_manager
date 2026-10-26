from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.mercenary import Mercenary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProfessionTemplate(Base):
    __tablename__ = "profession_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    material_family: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    bonus_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    training_gold_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=250)
    training_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mercenaries: Mapped[list["Mercenary"]] = relationship(back_populates="profession")


class ProfessionTraining(Base):
    __tablename__ = "profession_trainings"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    mercenary_id: Mapped[int] = mapped_column(ForeignKey("mercenaries.id"), nullable=False, index=True)
    profession_id: Mapped[int] = mapped_column(ForeignKey("profession_templates.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mercenary: Mapped["Mercenary"] = relationship(back_populates="profession_trainings")
    profession: Mapped[ProfessionTemplate] = relationship()


class ContentSeedRun(Base):
    __tablename__ = "content_seed_runs"
    __table_args__ = (UniqueConstraint("pack_key", "version", name="uq_content_seed_pack_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pack_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
