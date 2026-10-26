from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.mercenary import Mercenary, MercenaryClass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SkillTemplate(Base):
    __tablename__ = "skill_templates"
    __table_args__ = (UniqueConstraint("class_id", "name", name="uq_skill_class_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    effect_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    effect_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_level: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    mercenary_class: Mapped["MercenaryClass"] = relationship(back_populates="skill_templates")
    mercenary_skills: Mapped[list["MercenarySkill"]] = relationship(back_populates="skill_template")


class MercenarySkill(Base):
    __tablename__ = "mercenary_skills"
    __table_args__ = (UniqueConstraint("mercenary_id", "skill_template_id", name="uq_mercenary_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    mercenary_id: Mapped[int] = mapped_column(ForeignKey("mercenaries.id"), nullable=False, index=True)
    skill_template_id: Mapped[int] = mapped_column(ForeignKey("skill_templates.id"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    mercenary: Mapped["Mercenary"] = relationship(back_populates="skills")
    skill_template: Mapped[SkillTemplate] = relationship(back_populates="mercenary_skills")
