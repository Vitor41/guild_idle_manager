from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.mercenary import Mercenary, MercenaryClass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClassTransitionOption(Base):
    __tablename__ = "class_transition_options"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    from_class_id: Mapped[int] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=False, index=True)
    to_class_id: Mapped[int] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=False, index=True)
    required_mercenary_level: Mapped[int] = mapped_column(Integer, nullable=False)
    required_guild_level: Mapped[int] = mapped_column(Integer, nullable=False)
    required_training_ground_level: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    from_class: Mapped["MercenaryClass"] = relationship(
        back_populates="next_transitions",
        foreign_keys=[from_class_id],
    )
    to_class: Mapped["MercenaryClass"] = relationship(foreign_keys=[to_class_id])


class ClassChangeRun(Base):
    __tablename__ = "class_change_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    mercenary_id: Mapped[int] = mapped_column(ForeignKey("mercenaries.id"), nullable=False, index=True)
    from_class_id: Mapped[int] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=False, index=True)
    to_class_id: Mapped[int] = mapped_column(ForeignKey("mercenary_classes.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="in_progress", index=True)
    gold_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="class_change_runs")
    mercenary: Mapped["Mercenary"] = relationship(back_populates="class_change_runs")
    to_class: Mapped["MercenaryClass"] = relationship(
        back_populates="class_change_targets",
        foreign_keys=[to_class_id],
    )
