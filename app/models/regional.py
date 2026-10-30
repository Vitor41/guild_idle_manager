from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RegionalWorldState(Base):
    __tablename__ = "regional_world_state"

    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), primary_key=True
    )
    last_materialized_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    last_completed_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False, default="vigilia-v3")
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class RegionalRegionState(Base):
    __tablename__ = "regional_region_state"
    __table_args__ = (UniqueConstraint("campaign_id", "region_code", name="uq_region_campaign_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    region_code: Mapped[str] = mapped_column(String(80), nullable=False)
    region_name: Mapped[str] = mapped_column(String(100), nullable=False)
    security: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    threat: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    influence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class RegionalGuildState(Base):
    __tablename__ = "regional_guild_state"
    __table_args__ = (
        UniqueConstraint("campaign_id", "region_code", "slot", name="uq_regional_guild_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    region_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    guild_id: Mapped[int | None] = mapped_column(
        ForeignKey("guilds.id"), nullable=True, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile: Mapped[str] = mapped_column(String(20), nullable=False)
    archetype: Mapped[str] = mapped_column(String(30), nullable=False)
    roster_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    power: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reputation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    influence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class RegionalCycle(Base):
    __tablename__ = "regional_cycles"
    __table_args__ = (
        UniqueConstraint("campaign_id", "cycle_number", name="uq_regional_campaign_cycle"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seed: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    player_level_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    player_power_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rank_weights_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    processed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RegionalCpuMercenary(Base):
    __tablename__ = "regional_cpu_mercenaries"
    __table_args__ = (
        UniqueConstraint("guild_state_id", "slot", name="uq_regional_cpu_mercenary_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    guild_state_id: Mapped[int] = mapped_column(
        ForeignKey("regional_guild_state.id"), nullable=False, index=True
    )
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    class_code: Mapped[str] = mapped_column(String(80), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rarity: Mapped[str] = mapped_column(String(30), nullable=False, default="common")
    profession_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    power: Mapped[int] = mapped_column(Integer, nullable=False)
    vitality: Mapped[int] = mapped_column(Integer, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False)
    luck: Mapped[int] = mapped_column(Integer, nullable=False)
    armor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    equipment_bonus_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class RegionalCpuResource(Base):
    __tablename__ = "regional_cpu_resources"
    __table_args__ = (
        UniqueConstraint("guild_state_id", "resource_code", name="uq_regional_cpu_resource_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    guild_state_id: Mapped[int] = mapped_column(
        ForeignKey("regional_guild_state.id"), nullable=False, index=True
    )
    resource_code: Mapped[str] = mapped_column(String(60), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class RegionalCpuCyclePlan(Base):
    __tablename__ = "regional_cpu_cycle_plans"
    __table_args__ = (
        UniqueConstraint("cycle_id", "guild_state_id", name="uq_regional_cpu_cycle_guild"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    cycle_id: Mapped[int] = mapped_column(ForeignKey("regional_cycles.id"), nullable=False, index=True)
    guild_state_id: Mapped[int] = mapped_column(
        ForeignKey("regional_guild_state.id"), nullable=False, index=True
    )
    seed: Mapped[str] = mapped_column(String(64), nullable=False)
    roster_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    resources_before_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    resources_after_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    decisions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    outcomes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gold_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RegionalCycleRegion(Base):
    __tablename__ = "regional_cycle_regions"
    __table_args__ = (
        UniqueConstraint("cycle_id", "region_code", name="uq_regional_cycle_region"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    cycle_id: Mapped[int] = mapped_column(ForeignKey("regional_cycles.id"), nullable=False, index=True)
    region_code: Mapped[str] = mapped_column(String(80), nullable=False)
    security_before: Mapped[float] = mapped_column(Float, nullable=False)
    threat_before: Mapped[float] = mapped_column(Float, nullable=False)
    influence_before: Mapped[int] = mapped_column(Integer, nullable=False)
    security_after: Mapped[float] = mapped_column(Float, nullable=False)
    threat_after: Mapped[float] = mapped_column(Float, nullable=False)
    influence_after: Mapped[int] = mapped_column(Integer, nullable=False)
    cpu_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cpu_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cpu_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cpu_gold_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cpu_xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RegionalOffer(Base):
    __tablename__ = "regional_offers"
    __table_args__ = (
        UniqueConstraint("cycle_id", "region_code", "offer_type", "slot", name="uq_regional_offer_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    cycle_id: Mapped[int] = mapped_column(ForeignKey("regional_cycles.id"), nullable=False, index=True)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    region_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    offer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_preparation_started_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supply_preparation_ends_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supply_prepared_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supply_preparation_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission_template_id: Mapped[int | None] = mapped_column(ForeignKey("mission_templates.id"), nullable=True)
    dungeon_template_id: Mapped[int | None] = mapped_column(ForeignKey("dungeon_templates.id"), nullable=True)
    reserved_by_guild_state_id: Mapped[int | None] = mapped_column(
        ForeignKey("regional_guild_state.id"), nullable=True, index=True
    )
    rank: Mapped[str] = mapped_column(String(2), nullable=False)
    name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    description_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    level_band_snapshot: Mapped[str] = mapped_column(String(20), nullable=False, default="1-20")
    recommended_level_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_power_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    min_party_size_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_party_size_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duration_seconds_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_reward_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_reward_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    success_chance_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    claimed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RegionalRunOutcome(Base):
    __tablename__ = "regional_run_outcomes"
    __table_args__ = (
        UniqueConstraint("campaign_id", "source_type", "source_run_id", name="uq_regional_run_outcome_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    guild_state_id: Mapped[int] = mapped_column(
        ForeignKey("regional_guild_state.id"), nullable=False, index=True
    )
    offer_id: Mapped[int] = mapped_column(ForeignKey("regional_offers.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[str] = mapped_column(String(2), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    contribution: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RegionalEvent(Base):
    """Campaign-scoped, replay-safe event trigger and lifecycle record."""

    __tablename__ = "regional_events"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "event_type", "trigger_cycle_number", "region_code",
            name="uq_regional_event_trigger",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaign_metadata.campaign_id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    region_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    trigger_cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    seed: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    dungeon_template_id: Mapped[int | None] = mapped_column(ForeignKey("dungeon_templates.id"), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    priority_ends_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cpu_started_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    player_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class RegionalEventParticipant(Base):
    __tablename__ = "regional_event_participants"
    __table_args__ = (
        UniqueConstraint("event_id", "guild_state_id", name="uq_regional_event_guild_participant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("regional_events.id"), nullable=False, index=True)
    guild_state_id: Mapped[int] = mapped_column(
        ForeignKey("regional_guild_state.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="invited")
    contribution: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    resolved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RegionalEventActivity(Base):
    __tablename__ = "regional_event_activities"
    __table_args__ = (
        UniqueConstraint("source_type", "source_run_id", name="uq_regional_event_activity_source_run"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("regional_events.id"), nullable=False, index=True)
    guild_state_id: Mapped[int] = mapped_column(
        ForeignKey("regional_guild_state.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="in_progress")
    successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contribution: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
