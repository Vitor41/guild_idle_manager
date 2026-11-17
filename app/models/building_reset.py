from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuildBuildingResetState(Base):
    __tablename__ = "guild_building_reset_states"

    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), primary_key=True)
    free_reset_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_reset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    previous_paid_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class GuildBuildingReset(Base):
    __tablename__ = "guild_building_resets"
    __table_args__ = (
        UniqueConstraint("guild_id", "idempotency_key", name="uq_building_reset_idempotency"),
        Index("ix_guild_building_resets_guild_id", "guild_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    was_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    crystal_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    charge_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    refund_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    levels_before_json: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    has_estimated_refund: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class GuildBuildingInvestment(Base):
    __tablename__ = "guild_building_investments"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_building_investment_transaction"),
        UniqueConstraint("guild_building_id", "generation", "to_level", name="uq_building_investment_level"),
        Index("ix_guild_building_investments_guild_id", "guild_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False)
    guild_building_id: Mapped[int] = mapped_column(ForeignKey("guild_buildings.id"), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effect_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_level: Mapped[int] = mapped_column(Integer, nullable=False)
    to_level: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_debited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crystal_reserve_debited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    materials_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimate_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    refunded_by_reset_id: Mapped[int | None] = mapped_column(ForeignKey("guild_building_resets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
