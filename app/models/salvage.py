from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.item import ItemTemplate


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuildSalvageJob(Base):
    __tablename__ = "guild_salvage_jobs"
    __table_args__ = (
        Index(
            "uq_guild_salvage_active_slot",
            "guild_id",
            "slot_number",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False)
    material_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    gold_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    result_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    guild: Mapped["Guild"] = relationship(back_populates="salvage_jobs")
    item_template: Mapped["ItemTemplate"] = relationship(foreign_keys=[item_template_id])
    material_template: Mapped["ItemTemplate"] = relationship(foreign_keys=[material_template_id])
