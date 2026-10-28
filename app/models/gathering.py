from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.mercenary import Mercenary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GatheringAssignment(Base):
    __tablename__ = "gathering_assignments"
    __table_args__ = (
        UniqueConstraint("guild_id", "resource_family", name="uq_gathering_family_per_guild"),
        UniqueConstraint("mercenary_id", name="uq_gathering_mercenary"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    mercenary_id: Mapped[int] = mapped_column(ForeignKey("mercenaries.id"), nullable=False, index=True)
    resource_family: Mapped[str] = mapped_column(String(30), nullable=False)
    node_code: Mapped[str] = mapped_column(String(80), nullable=False)
    progress_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_chance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rng_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    checkpoint_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    guild: Mapped["Guild"] = relationship()
    mercenary: Mapped["Mercenary"] = relationship()
