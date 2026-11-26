"""Campaign-local event triggers with stable seeds and explicit deadlines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import combinations
import json
from threading import Lock
from types import SimpleNamespace

from sqlalchemy import event as sqlalchemy_event, or_, select
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import Session

from app.models.campaign import CampaignMetadata
from app.models.building import BuildingTemplate, GuildBuilding
from app.models.dungeon import DungeonTemplate
from app.models.guild import Guild
from app.models.item import ItemTemplate
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.regional import (
    RegionalCycle,
    RegionalCycleRegion,
    RegionalEvent,
    RegionalEventActivity,
    RegionalEventParticipant,
    RegionalCpuCyclePlan,
    RegionalCpuMercenary,
    RegionalCpuResource,
    RegionalGuildState,
    RegionalPortalSpawnState,
    RegionalRegionState,
)
from app.services.building_balance_service import scouts_values
from app.services.portal_spawn_rules import get_portal_spawn_rules
from app.services.regional_cycle_service import (
    CPU_INTERNAL_CONTRACT_RULES_VERSION,
    REGIONS,
    VIGILIA_RULES_VERSION,
    VIGILIA_V7_RULES_VERSION,
    VIGILIA_V9_RULES_VERSION,
    _cpu_offer_party,
    _rng,
    _seed_text,
    get_current_player_regional_guild,
    regional_outcome_impact,
)


V8_EVENT_RULES_VERSION = "regional-events-v5"
V9_EVENT_RULES_VERSION = "regional-events-v6"
EVENT_RULES_VERSION = V9_EVENT_RULES_VERSION
V7_EVENT_RULES_VERSION = "regional-events-v4"
LEGACY_EVENT_RULES_VERSION = "regional-events-v3"
PORTAL_LOOT_VERSION = "portal-loot-v1"
PORTAL_LOOT_CHANCE_BY_RARITY = {"rare": 20, "epic": 6, "legendary": 1}
PORTAL_BOSS_SNAPSHOT_VERSION = "portal-boss-v2"
LEGACY_REBELLION_CHANCE = 0.02
REBELLION_CHANCE = 0.05
REBELLION_REGION_ROLL_COOLDOWN_CYCLES = 0
LEGACY_REBELLION_REGION_ROLL_COOLDOWN_CYCLES = 5
PORTAL_TTL = timedelta(hours=3)
PORTAL_REGION_COOLDOWN_CYCLES = 24
REBELLION_PRIORITY = timedelta(hours=1)
REBELLION_TTL = timedelta(hours=12)
PORTAL_BASE_CHANCE = 0.05
PORTAL_MAX_CHANCE = 0.25
PORTAL_LOW_THREAT_CHANCE = 0.04
PORTAL_CHANCE_CAP = 0.30
PORTAL_MIN_THREAT = 70.0
PORTAL_CPU_PARTICIPATION_CHANCE = 0.25
REBELLION_MIN_THREAT = 85.0
REBELLION_MAX_SECURITY = 25.0

# Keep one small lock per observed campaign until process exit. Removing one
# while another thread is waiting can split callers across different locks.
_CAMPAIGN_EVENT_LOCKS: dict[str, Lock] = {}
_CAMPAIGN_EVENT_LOCKS_GUARD = Lock()
_SESSION_EVENT_LOCKS_KEY = "regional_event_campaign_locks"


def _hold_campaign_event_lock(db: Session, campaign_id: str) -> None:
    """Serialize event trigger checks through the caller's transaction end.

    The desktop app serves concurrent requests in one process. Holding the
    campaign lock until commit/rollback makes check-then-insert idempotent even
    when the first request has not committed when the next request arrives.
    """
    held_locks = db.info.setdefault(_SESSION_EVENT_LOCKS_KEY, {})
    if campaign_id in held_locks:
        return
    if not db.in_transaction():
        db.begin()
    with _CAMPAIGN_EVENT_LOCKS_GUARD:
        lock = _CAMPAIGN_EVENT_LOCKS.setdefault(campaign_id, Lock())
    lock.acquire()
    held_locks[campaign_id] = lock


@sqlalchemy_event.listens_for(SqlAlchemySession, "after_transaction_end")
def _release_campaign_event_locks(db: Session, transaction) -> None:
    if transaction.parent is not None:
        return
    held_locks = db.info.pop(_SESSION_EVENT_LOCKS_KEY, {})
    for lock in reversed(list(held_locks.values())):
        lock.release()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _event_rules_version_for_cycle(cycle: RegionalCycle) -> str:
    if cycle.rules_version == VIGILIA_RULES_VERSION:
        return EVENT_RULES_VERSION
    if cycle.rules_version == CPU_INTERNAL_CONTRACT_RULES_VERSION:
        return V8_EVENT_RULES_VERSION
    if cycle.rules_version == VIGILIA_V7_RULES_VERSION:
        return V7_EVENT_RULES_VERSION
    return LEGACY_EVENT_RULES_VERSION


def _portal_spawn_chance(threat: float, detection_bonus_pp: float = 0.0) -> float:
    if float(threat) < PORTAL_MIN_THREAT:
        base_chance = PORTAL_LOW_THREAT_CHANCE
    else:
        base_chance = PORTAL_BASE_CHANCE + (float(threat) - PORTAL_MIN_THREAT) * (0.20 / 30.0)
    return min(PORTAL_CHANCE_CAP, base_chance + float(detection_bonus_pp) / 100.0)


def _summary(event: RegionalEvent) -> dict[str, object]:
    try:
        parsed = json.loads(event.summary_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _save_summary(event: RegionalEvent, data: dict[str, object]) -> None:
    event.summary_json = json.dumps(data, ensure_ascii=False, sort_keys=True)


def _has_in_progress_activity(db: Session, event_id: int) -> bool:
    return db.scalar(select(RegionalEventActivity.id).where(
        RegionalEventActivity.event_id == event_id,
        RegionalEventActivity.status == "in_progress",
    ).limit(1)) is not None


def _mark_event_waiting_for_started_activities(db: Session, event: RegionalEvent) -> None:
    event.status = "in_progress"
    payload = _summary(event)
    payload.update({
        "reason": "deadline_elapsed_waiting_for_started_activities",
        "entry_window_closed_at_utc": _utc(event.expires_at_utc).isoformat(),
        "new_entries_after_expiry": False,
        "started_activities_may_finish": True,
    })
    _save_summary(event, payload)
    db.add(event)


def _finalize_portal_event(db: Session, event: RegionalEvent, now: datetime) -> None:
    activities = list(db.scalars(select(RegionalEventActivity).where(
        RegionalEventActivity.event_id == event.id,
        RegionalEventActivity.status == "resolved",
    ).order_by(RegionalEventActivity.guild_state_id, RegionalEventActivity.id)))
    participants = list(db.scalars(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == event.id,
    ).order_by(RegionalEventParticipant.guild_state_id)))
    results = [
        {
            "guild_state_id": participant.guild_state_id,
            "success": participant.success,
            "contribution": participant.contribution,
            "resolved_at_utc": (
                _utc(participant.resolved_at_utc).isoformat()
                if participant.resolved_at_utc is not None else None
            ),
        }
        for participant in participants
        if participant.status == "resolved"
    ]
    successes = sum(activity.successes for activity in activities)
    failures = sum(activity.failures for activity in activities)
    payload = _summary(event)
    payload.update({
        "reason": "deadline_elapsed_offline",
        "entry_window_closed_at_utc": _utc(event.expires_at_utc).isoformat(),
        "new_entries_after_expiry": False,
        "started_activities_may_finish": False,
        "started_activities_counted": True,
        "activities_completed_after_deadline": sum(
            1 for activity in activities
            if activity.resolved_at_utc is not None
            and _utc(activity.resolved_at_utc) > _utc(event.expires_at_utc)
        ),
        "participant_results": results,
        "aggregate": {"entries": len(results), "successes": successes, "failures": failures},
        "individual_run_rewards_already_claimed": True,
    })
    event.status = "resolved" if activities else "expired"
    event.resolved_at_utc = _utc(now)
    _save_summary(event, payload)
    db.add(event)


def _portal_has_pending_cpu_cycle(db: Session, event: RegionalEvent) -> bool:
    pending_cycle = db.scalar(select(RegionalCycle).where(
        RegionalCycle.campaign_id == event.campaign_id,
        RegionalCycle.cycle_number == event.trigger_cycle_number + 1,
        RegionalCycle.status == "open",
    ))
    if pending_cycle is None:
        return False
    cycle_start = _utc(pending_cycle.starts_at_utc)
    return _utc(event.created_at_utc) <= cycle_start < _utc(event.expires_at_utc)


def _portal_blocks_spawn_evaluation(
    db: Session,
    campaign_id: str,
    region_code: str,
    at: datetime,
) -> bool:
    """Match the portal generator's block after expired events are normalized."""
    current = _utc(at)
    blocker = db.scalar(select(RegionalEvent.id).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEvent.region_code == region_code,
        RegionalEvent.status.in_(("active", "in_progress")),
        RegionalEvent.created_at_utc <= current,
        or_(
            RegionalEvent.status == "in_progress",
            RegionalEvent.expires_at_utc > current,
        ),
    ).limit(1))
    return blocker is not None


def _finalize_portal_event_when_ready(db: Session, event: RegionalEvent, now: datetime) -> None:
    if _has_in_progress_activity(db, event.id):
        _mark_event_waiting_for_started_activities(db, event)
        return
    # A portal created at the close of cycle N remains eligible for the CPU
    # plan in cycle N+1. Every finalization path must wait for that open cycle.
    if _portal_has_pending_cpu_cycle(db, event):
        return
    _finalize_portal_event(db, event, now)


def _finalize_rebellion_event(db: Session, event: RegionalEvent, now: datetime) -> None:
    event.status = "resolved"
    event.resolved_at_utc = _utc(now)
    payload = _summary(event)
    payload.update({
        "reason": "deadline_elapsed_offline",
        "entry_window_closed_at_utc": _utc(event.expires_at_utc).isoformat(),
        "new_entries_after_expiry": False,
        "started_activities_may_finish": False,
    })
    if event.player_decision is None:
        event.player_decision = "delegated_cpu"
    payload["player_decision"] = event.player_decision
    _resolve_rebellion_summary(db, event, payload)
    activities = list(db.scalars(select(RegionalEventActivity).where(
        RegionalEventActivity.event_id == event.id,
        RegionalEventActivity.status == "resolved",
    )))
    payload["activities_completed_after_deadline"] = sum(
        1 for activity in activities
        if activity.resolved_at_utc is not None
        and _utc(activity.resolved_at_utc) > _utc(event.expires_at_utc)
    )
    _save_summary(event, payload)
    db.add(event)


def build_portal_loot_snapshot(
    db: Session,
    template: DungeonTemplate,
    seed: str,
) -> dict[str, object]:
    """Choose a small, event-stable exclusive table of high-rarity equipment."""
    rng = _rng(seed, PORTAL_LOOT_VERSION, template.id)
    entries: list[dict[str, object]] = []
    for rarity, chance in PORTAL_LOOT_CHANCE_BY_RARITY.items():
        candidates = list(db.scalars(select(ItemTemplate).where(
            ItemTemplate.is_active.is_(True),
            ItemTemplate.item_type == "equipment",
            ItemTemplate.rarity == rarity,
            ItemTemplate.level_band == template.level_band,
        ).order_by(ItemTemplate.id)))
        if not candidates:
            continue
        item = candidates[rng.randrange(len(candidates))]
        entries.append({
            "item_template_id": item.id,
            "rarity": rarity,
            "chance_percent": chance,
            "quantity": 1,
            "item_snapshot": build_portal_item_snapshot(item),
        })
    return {
        "version": PORTAL_LOOT_VERSION,
        "roll_model": "one_100_point_roll;exclusive_rarity_bands;no_guaranteed_equipment",
        "entries": entries,
    }


def build_portal_item_snapshot(item: ItemTemplate) -> dict[str, object]:
    fields = (
        "id", "name", "description", "item_type", "rarity", "item_level", "level_band", "tier",
        "content_pack", "material_family", "favored_class_code", "favored_attribute", "base_sell_value",
        "equipment_slot", "icon_group", "required_level", "bonus_power", "bonus_vitality", "bonus_agility",
        "bonus_intelligence", "bonus_luck", "bonus_armor", "rng_bonus_min", "rng_bonus_max",
    )
    return {field: getattr(item, field) for field in fields}


def build_portal_boss_snapshot(template: DungeonTemplate) -> dict[str, object]:
    fields = (
        "id", "name", "description", "content_type", "content_pack", "level_band", "recommended_level",
        "biome", "difficulty", "duration_seconds", "base_gold_reward", "base_xp_reward", "base_success_chance",
        "min_party_size", "max_party_size", "required_guild_level", "required_min_mercenary_level",
        "required_building_type", "required_building_level", "required_total_power", "required_class_code",
        "required_tank_count", "required_support_count", "required_damage_count", "required_equipment_tier",
    )
    return {field: getattr(template, field) for field in fields}


def expire_due_events(db: Session, campaign_id: str, now: datetime) -> None:
    current = _utc(now)
    priority_due = list(db.scalars(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.status == "active",
        RegionalEvent.player_decision.is_(None),
        RegionalEvent.priority_ends_at_utc.is_not(None),
        RegionalEvent.priority_ends_at_utc <= current,
    )))
    for event in priority_due:
        event.player_decision = "delegated_cpu"
        event.cpu_started_at_utc = _utc(event.priority_ends_at_utc)
        event.expires_at_utc = _utc(event.priority_ends_at_utc) + REBELLION_TTL
        participant = db.scalar(select(RegionalEventParticipant).where(
            RegionalEventParticipant.event_id == event.id,
        ))
        if participant is not None and participant.status == "invited":
            participant.status = "declined"
            db.add(participant)
        payload = _summary(event)
        payload.update({
            "player_decision": "no_response_delegated_to_cpu",
            "priority_elapsed_offline": True,
            "cpu_started_at_utc": event.cpu_started_at_utc.isoformat(),
            "cpu_execution_expires_at_utc": event.expires_at_utc.isoformat(),
        })
        _save_summary(event, payload)
        db.add(event)
    due = list(db.scalars(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.status.in_(("active", "in_progress")),
        RegionalEvent.expires_at_utc <= current,
    )))
    for event in due:
        if event.event_type == "portal":
            _finalize_portal_event_when_ready(db, event, _utc(event.expires_at_utc))
        elif event.event_type == "rebellion":
            if _has_in_progress_activity(db, event.id):
                _mark_event_waiting_for_started_activities(db, event)
            else:
                _finalize_rebellion_event(db, event, _utc(event.expires_at_utc))
    if due or priority_due:
        db.flush()


def _resolve_rebellion_summary(
    db: Session,
    event: RegionalEvent,
    payload: dict[str, object],
) -> None:
    campaign = db.get(CampaignMetadata, event.campaign_id)
    if campaign is None:
        return
    deadline = _utc(event.expires_at_utc)
    activities = list(db.scalars(select(RegionalEventActivity).where(
        RegionalEventActivity.event_id == event.id,
        RegionalEventActivity.status == "resolved",
    )))
    successes = sum(activity.successes for activity in activities)
    failures = sum(activity.failures for activity in activities)
    cpu_successes = sum(activity.successes for activity in activities if activity.source_type == "cpu_cycle")
    cpu_failures = sum(activity.failures for activity in activities if activity.source_type == "cpu_cycle")
    player_successes = successes - cpu_successes
    player_failures = failures - cpu_failures
    won = successes > failures
    payload.update({
        "result": "success" if won else "failure",
        "aggregate": {
            "successes": successes,
            "failures": failures,
            "cpu_successes": cpu_successes,
            "cpu_failures": cpu_failures,
            "player_successes": player_successes,
            "player_failures": player_failures,
        },
        "activities": [
            {
                "guild_state_id": activity.guild_state_id,
                "source_type": activity.source_type,
                "source_run_id": activity.source_run_id,
                "successes": activity.successes,
                "failures": activity.failures,
                "contribution": activity.contribution,
                "resolved_at_utc": (
                    _utc(activity.resolved_at_utc).isoformat()
                    if activity.resolved_at_utc is not None else None
                ),
            }
            for activity in sorted(activities, key=lambda row: (row.source_type, row.source_run_id))
        ],
        "individual_run_rewards_already_claimed": True,
    })
    participants = list(db.scalars(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == event.id,
    )))
    activity_by_guild: dict[int, list[RegionalEventActivity]] = {}
    for activity in activities:
        activity_by_guild.setdefault(activity.guild_state_id, []).append(activity)
    for participant in participants:
        guild_activities = activity_by_guild.get(participant.guild_state_id, [])
        participant.contribution = sum(activity.contribution for activity in guild_activities)
        contributed = participant.contribution > 0
        participant.status = "resolved"
        participant.success = won and contributed
        participant.resolved_at_utc = deadline
        player_state = db.get(RegionalGuildState, participant.guild_state_id)
        if won and contributed and player_state is not None:
            player_state.event_wins += 1
            db.add(player_state)
        db.add(participant)


def create_cycle_portals(
    db: Session,
    campaign_id: str,
    cycle: RegionalCycle,
    regions: list[RegionalRegionState],
) -> None:
    """Evaluate portal odds once per closed cycle, at that cycle's end time."""
    _hold_campaign_event_lock(db, campaign_id)
    _create_cycle_portals_locked(db, campaign_id, cycle, regions)


def _create_cycle_portals_locked(
    db: Session,
    campaign_id: str,
    cycle: RegionalCycle,
    regions: list[RegionalRegionState],
) -> None:
    cycle_end = _utc(cycle.ends_at_utc)
    expire_due_events(db, campaign_id, cycle_end)
    if cycle.portal_spawn_rules_version is not None:
        _create_versioned_cycle_portals_locked(db, campaign_id, cycle, regions, cycle_end)
        return
    event_rules_version = _event_rules_version_for_cycle(cycle)
    stage_eligible = event_rules_version in {
        V7_EVENT_RULES_VERSION, V8_EVENT_RULES_VERSION, V9_EVENT_RULES_VERSION,
    }
    # New rules add the introductory boss and gate portal bosses by the
    # campaign stage. Older cycles retain their original portal-biome pool.
    boss_query = select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type == "boss",
    )
    if stage_eligible:
        stage_level = max(1, int(cycle.player_level_snapshot or 1))
        boss_query = boss_query.where(
            DungeonTemplate.required_guild_level <= stage_level,
            or_(
                DungeonTemplate.biome == "portal",
                (DungeonTemplate.level_band == "1-20") & (DungeonTemplate.recommended_level <= 1),
            ),
        )
    else:
        boss_query = boss_query.where(DungeonTemplate.biome == "portal")
    portal_bosses = list(db.scalars(boss_query.order_by(
        DungeonTemplate.recommended_level, DungeonTemplate.id,
    )))
    if not portal_bosses:
        return
    for region in sorted(regions, key=lambda row: row.region_code):
        if (region.threat < PORTAL_MIN_THREAT
                and event_rules_version not in {V8_EVENT_RULES_VERSION, V9_EVENT_RULES_VERSION}):
            continue
        active_id = db.scalar(select(RegionalEvent.id).where(
            RegionalEvent.campaign_id == campaign_id,
            RegionalEvent.event_type == "portal",
            RegionalEvent.region_code == region.region_code,
            RegionalEvent.status.in_(("active", "in_progress")),
            RegionalEvent.created_at_utc <= cycle_end,
            RegionalEvent.expires_at_utc > cycle_end,
        ).limit(1))
        if active_id is not None:
            continue
        most_recent_portal = db.scalar(select(RegionalEvent).where(
            RegionalEvent.campaign_id == campaign_id,
            RegionalEvent.event_type == "portal",
            RegionalEvent.region_code == region.region_code,
        ).order_by(RegionalEvent.trigger_cycle_number.desc()).limit(1))
        if (most_recent_portal is not None
                and cycle.cycle_number - most_recent_portal.trigger_cycle_number
                <= PORTAL_REGION_COOLDOWN_CYCLES):
            continue
        player_state = db.scalar(select(RegionalGuildState).where(
            RegionalGuildState.campaign_id == campaign_id,
            RegionalGuildState.region_code == region.region_code,
            RegionalGuildState.guild_id.is_not(None),
        ).limit(1))
        scouts_level = 0
        if player_state is not None and player_state.guild_id is not None:
            scouts_level = int(db.scalar(select(GuildBuilding.level).join(
                BuildingTemplate, BuildingTemplate.id == GuildBuilding.building_template_id,
            ).where(
                GuildBuilding.guild_id == player_state.guild_id,
                BuildingTemplate.effect_type == "scouts",
            )) or 0)
        detection_bonus_pp = scouts_values(scouts_level)["portal_detection_bonus_percentage_points"]
        chance = _portal_spawn_chance(region.threat, detection_bonus_pp)
        seed = _seed_text(
            campaign_id, cycle.cycle_number, region.region_code, event_rules_version, "portal",
        )
        rng = _rng(seed)
        if rng.random() >= chance:
            continue
        template = portal_bosses[rng.randrange(len(portal_bosses))]
        loot_snapshot = build_portal_loot_snapshot(db, template, seed)
        if not loot_snapshot["entries"]:
            continue
        db.add(RegionalEvent(
            campaign_id=campaign_id,
            event_type="portal",
            region_code=region.region_code,
            trigger_cycle_number=cycle.cycle_number,
            rules_version=event_rules_version,
            seed=seed,
            status="active",
            dungeon_template_id=template.id,
            created_at_utc=cycle_end,
            expires_at_utc=cycle_end + PORTAL_TTL,
            summary_json=json.dumps({
                "chance": round(chance, 6),
                "scouts_detection_bonus_pp": detection_bonus_pp,
                "threat_snapshot": round(region.threat, 4),
                "deadline_policy": "continues_offline",
                "region_cooldown_cycles": PORTAL_REGION_COOLDOWN_CYCLES,
                "content_policy": ("active_stage_eligible_portal_or_introductory_boss"
                                   if stage_eligible else "active_portal_biome_boss_template"),
                "progression_stage_level_snapshot": (
                    max(1, int(cycle.player_level_snapshot or 1)) if stage_eligible else None
                ),
                "portal_boss": {
                    "version": PORTAL_BOSS_SNAPSHOT_VERSION if stage_eligible else "portal-boss-v1",
                    "template": build_portal_boss_snapshot(template),
                },
                "portal_loot": loot_snapshot,
            }, ensure_ascii=False, sort_keys=True),
        ))
    db.flush()


def _versioned_portal_boss_pool(
    db: Session,
    cycle: RegionalCycle,
    *,
    stage_level: int | None = None,
) -> tuple[list[DungeonTemplate], bool]:
    """Return the exact active, stage-eligible bosses with at least one loot band."""
    event_rules_version = _event_rules_version_for_cycle(cycle)
    stage_eligible = event_rules_version in {
        V7_EVENT_RULES_VERSION, V8_EVENT_RULES_VERSION, V9_EVENT_RULES_VERSION,
    }
    boss_query = select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type == "boss",
    )
    if stage_eligible:
        stage_level = max(1, int(stage_level or cycle.player_level_snapshot or 1))
        boss_query = boss_query.where(
            DungeonTemplate.required_guild_level <= stage_level,
            or_(
                DungeonTemplate.biome == "portal",
                (DungeonTemplate.level_band == "1-20") & (DungeonTemplate.recommended_level <= 1),
            ),
        )
    else:
        boss_query = boss_query.where(DungeonTemplate.biome == "portal")
    portal_bosses = list(db.scalars(boss_query.order_by(
        DungeonTemplate.recommended_level, DungeonTemplate.id,
    )))

    # build_portal_loot_snapshot emits an entry exactly when this level band
    # has at least one active rare, epic, or legendary equipment template.
    valid_loot_bands = set(db.scalars(select(ItemTemplate.level_band).where(
        ItemTemplate.is_active.is_(True),
        ItemTemplate.item_type == "equipment",
        ItemTemplate.rarity.in_(tuple(PORTAL_LOOT_CHANCE_BY_RARITY)),
        ItemTemplate.level_band.is_not(None),
    ).distinct()))
    portal_bosses = [boss for boss in portal_bosses if boss.level_band in valid_loot_bands]
    return portal_bosses, stage_eligible


def _cpu_portal_candidate_offer(template: DungeonTemplate) -> SimpleNamespace:
    return SimpleNamespace(
        offer_type="portal",
        required_guild_level_snapshot=max(1, int(template.required_guild_level or 1)),
        min_party_size_snapshot=max(1, int(template.min_party_size or 1)),
        max_party_size_snapshot=max(1, int(template.max_party_size or 1)),
        required_min_mercenary_level_snapshot=max(1, int(template.required_min_mercenary_level or 1)),
        required_class_code_snapshot=template.required_class_code,
        required_total_power_snapshot=max(0, int(template.required_total_power or 0)),
        required_tank_count_snapshot=max(0, int(template.required_tank_count or 0)),
        required_support_count_snapshot=max(0, int(template.required_support_count or 0)),
        required_damage_count_snapshot=max(0, int(template.required_damage_count or 0)),
        required_equipment_tier_snapshot=max(0, int(template.required_equipment_tier or 0)),
        duration_seconds_snapshot=max(1, int(template.duration_seconds or 1)),
        recommended_power_snapshot=max(1, int(template.required_total_power or 0)),
        success_chance_snapshot=max(5, min(95, int(template.base_success_chance or 50))),
        cpu_failure_risk_snapshot=0,
    )


def _cpu_can_complete_portal_boss(
    state: RegionalGuildState,
    roster: list[RegionalCpuMercenary],
    class_roles: dict[str, str],
    template: DungeonTemplate,
    at: datetime,
) -> bool:
    if not state.active or state.guild_id is not None:
        return False
    offer = _cpu_portal_candidate_offer(template)
    available_at = {member.id: at for member in roster}
    return _cpu_offer_party(
        offer,
        state,
        roster,
        available_at,
        at + timedelta(days=365),
        class_roles,
        include_synergy_power=True,
        require_equipment_for_each_member=True,
        enforce_min_mercenary_level=True,
    ) is not None


def _player_can_complete_portal_boss(
    db: Session,
    guild: Guild,
    template: DungeonTemplate,
) -> bool:
    if max(1, int(guild.level or 1)) < max(1, int(template.required_guild_level or 1)):
        return False
    roster = list(db.scalars(select(Mercenary).where(
        Mercenary.guild_id == guild.id,
        Mercenary.status != "dismissed",
    ).order_by(Mercenary.id)))
    minimum = max(1, int(template.min_party_size or 1))
    maximum = max(minimum, int(template.max_party_size or minimum))
    if len(roster) < minimum:
        return False
    from app.services.dungeon_service import (
        validate_advanced_party_requirements,
        validate_dungeon_requirements,
    )

    try:
        validate_dungeon_requirements(db, guild, template)
    except ValueError:
        return False
    minimum_member_level = max(1, int(template.required_min_mercenary_level or 1))
    for size in range(minimum, min(maximum, len(roster)) + 1):
        for party in combinations(roster, size):
            if any(int(member.level or 1) < minimum_member_level for member in party):
                continue
            try:
                validate_advanced_party_requirements(db, guild, template, party)
            except ValueError:
                continue
            return True
    return False


def _region_portal_progression_level(
    db: Session,
    cycle: RegionalCycle,
    region_code: str,
    home_code: str,
) -> int:
    if region_code == home_code:
        return max(1, int(cycle.player_level_snapshot or 1))
    cpu_levels = list(db.scalars(select(RegionalGuildState.level).where(
        RegionalGuildState.campaign_id == cycle.campaign_id,
        RegionalGuildState.region_code == region_code,
        RegionalGuildState.guild_id.is_(None),
        RegionalGuildState.active.is_(True),
    )))
    return max([1, *(max(1, int(level or 1)) for level in cpu_levels)])


def _native_portal_boss_pool(
    db: Session,
    cycle: RegionalCycle,
    region_code: str,
    home_code: str,
    stage_level: int,
    candidates: list[DungeonTemplate],
) -> list[DungeonTemplate]:
    cpu_states = list(db.scalars(select(RegionalGuildState).where(
        RegionalGuildState.campaign_id == cycle.campaign_id,
        RegionalGuildState.region_code == region_code,
        RegionalGuildState.guild_id.is_(None),
        RegionalGuildState.active.is_(True),
    ).order_by(RegionalGuildState.slot)))
    roster_by_state = {
        state.id: list(db.scalars(select(RegionalCpuMercenary).where(
            RegionalCpuMercenary.guild_state_id == state.id,
            RegionalCpuMercenary.active.is_(True),
        ).order_by(RegionalCpuMercenary.slot)))
        for state in cpu_states
    }
    class_roles = {
        code: role for code, role in db.execute(select(
            MercenaryClass.code, MercenaryClass.role_type,
        ).where(MercenaryClass.code.is_not(None))) if code
    }
    player_guild = None
    if region_code == home_code:
        player_state = db.scalar(select(RegionalGuildState).where(
            RegionalGuildState.campaign_id == cycle.campaign_id,
            RegionalGuildState.region_code == region_code,
            RegionalGuildState.guild_id.is_not(None),
        ).limit(1))
        if player_state is not None and player_state.guild_id is not None:
            player_guild = db.get(Guild, player_state.guild_id)

    viable = []
    probe_at = _utc(cycle.ends_at_utc)
    for template in candidates:
        if player_guild is not None and _player_can_complete_portal_boss(db, player_guild, template):
            viable.append(template)
            continue
        if any(_cpu_can_complete_portal_boss(
            state, roster_by_state[state.id], class_roles, template, probe_at,
        ) for state in cpu_states):
            viable.append(template)
    return viable


def portal_spawn_status_for_region(
    db: Session,
    campaign: CampaignMetadata,
    cycle: RegionalCycle | None,
    region_code: str,
    now: datetime,
) -> dict[str, object]:
    """Read the authoritative next-roll inputs without evaluating or mutating them."""
    rules = get_portal_spawn_rules(
        getattr(cycle, "portal_spawn_rules_version", None) if cycle is not None else None,
    )
    if cycle is None or rules is None:
        return {
            "available": False,
            "unavailable_label": "Dados da próxima tentativa ainda não estão registrados.",
        }

    state = db.scalar(select(RegionalPortalSpawnState).where(
        RegionalPortalSpawnState.campaign_id == campaign.campaign_id,
        RegionalPortalSpawnState.region_code == region_code,
    ))
    if state is None:
        return {
            "available": False,
            "unavailable_label": "Dados da próxima tentativa ainda não estão registrados.",
        }

    current = _utc(now)
    home_code = next(
        (code for code, name in REGIONS if name == campaign.home_region), REGIONS[0][0],
    )
    event_rules_version = _event_rules_version_for_cycle(cycle)
    if event_rules_version == V9_EVENT_RULES_VERSION:
        stage_level = _region_portal_progression_level(db, cycle, region_code, home_code)
        candidates, _stage_eligible = _versioned_portal_boss_pool(
            db, cycle, stage_level=stage_level,
        )
        portal_bosses = _native_portal_boss_pool(
            db, cycle, region_code, home_code, stage_level, candidates,
        )
    else:
        portal_bosses, _stage_eligible = _versioned_portal_boss_pool(db, cycle)
    if not portal_bosses:
        return {
            "available": False,
            "reason_code": "no_eligible_content",
            "unavailable_label": "Sem conteúdo elegível para a próxima tentativa.",
        }

    active_portal = _portal_blocks_spawn_evaluation(
        db, campaign.campaign_id, region_code, current,
    )
    cooldown_until = _utc(state.cooldown_until_utc) if state.cooldown_until_utc else None
    cooldown_active = cooldown_until is not None and current < cooldown_until
    player_state = db.scalar(select(RegionalGuildState).where(
        RegionalGuildState.campaign_id == campaign.campaign_id,
        RegionalGuildState.region_code == region_code,
        RegionalGuildState.guild_id.is_not(None),
    ).limit(1))
    scouts_level = 0
    if player_state is not None and player_state.guild_id is not None:
        scouts_level = int(db.scalar(select(GuildBuilding.level).join(
            BuildingTemplate, BuildingTemplate.id == GuildBuilding.building_template_id,
        ).where(
            GuildBuilding.guild_id == player_state.guild_id,
            BuildingTemplate.effect_type == "scouts",
        )) or 0)
    explorer_bonus_pp = scouts_values(scouts_level)["portal_detection_bonus_percentage_points"]
    failure_stacks = min(rules.max_stack(), max(0, int(state.failure_stacks or 0)))
    base_chance_pp, explorer_bonus_pp, effective_chance_pp = rules.chance_percentages(
        failure_stacks, explorer_bonus_pp,
    )
    if active_portal:
        next_attempt_label = "Há um portal ativo; a próxima tentativa aguarda uma Vigília elegível."
    elif cooldown_active:
        next_attempt_label = "Nova tentativa após o cooldown, em uma Vigília elegível."
    else:
        next_attempt_label = "Chance calculada para a próxima Vigília elegível."

    return {
        "available": True,
        "reason_code": "active_portal" if active_portal else "cooldown" if cooldown_active else "eligible_next_cycle",
        "next_attempt_label": next_attempt_label,
        "failure_stacks": failure_stacks,
        "maximum_failure_stacks": rules.max_stack(),
        "failure_bonus_pp": max(0, base_chance_pp - rules.base_chance_pp),
        "base_chance_pp": rules.base_chance_pp,
        "base_chance_after_failures_pp": base_chance_pp,
        "explorer_bonus_pp": explorer_bonus_pp,
        "effective_chance_pp": effective_chance_pp,
        "failure_cap_reached": failure_stacks >= rules.max_stack(),
        "cooldown_until_iso": cooldown_until.isoformat() if cooldown_active else None,
        "cooldown_until_label": (
            cooldown_until.strftime("%d/%m/%Y às %H:%M UTC") if cooldown_active else None
        ),
        "last_evaluated_cycle_number": state.last_evaluated_cycle_number,
    }


def _create_versioned_cycle_portals_locked(
    db: Session,
    campaign_id: str,
    cycle: RegionalCycle,
    regions: list[RegionalRegionState],
    cycle_end: datetime,
) -> None:
    """Evaluate the versioned portal policy, leaving unmarked cycles legacy."""
    rules = get_portal_spawn_rules(cycle.portal_spawn_rules_version)
    if rules is None:
        return
    event_rules_version = _event_rules_version_for_cycle(cycle)
    campaign = db.get(CampaignMetadata, campaign_id)
    home_code = (
        next((code for code, name in REGIONS if campaign and name == campaign.home_region), REGIONS[0][0])
    )
    legacy_portal_bosses, legacy_stage_eligible = (
        _versioned_portal_boss_pool(db, cycle)
        if event_rules_version != V9_EVENT_RULES_VERSION else ([], True)
    )

    for region in sorted(regions, key=lambda row: row.region_code):
        stage_level = (
            _region_portal_progression_level(db, cycle, region.region_code, home_code)
            if event_rules_version == V9_EVENT_RULES_VERSION
            else max(1, int(cycle.player_level_snapshot or 1))
        )
        if event_rules_version == V9_EVENT_RULES_VERSION:
            region_candidates, stage_eligible = _versioned_portal_boss_pool(
                db, cycle, stage_level=stage_level,
            )
            portal_bosses = _native_portal_boss_pool(
                db, cycle, region.region_code, home_code, stage_level, region_candidates,
            )
        else:
            portal_bosses, stage_eligible = legacy_portal_bosses, legacy_stage_eligible
        state = db.scalar(select(RegionalPortalSpawnState).where(
            RegionalPortalSpawnState.campaign_id == campaign_id,
            RegionalPortalSpawnState.region_code == region.region_code,
        ))
        if state is None:
            previous_portal = db.scalar(select(RegionalEvent).where(
                RegionalEvent.campaign_id == campaign_id,
                RegionalEvent.event_type == "portal",
                RegionalEvent.region_code == region.region_code,
                RegionalEvent.created_at_utc <= cycle_end,
            ).order_by(RegionalEvent.created_at_utc.desc(), RegionalEvent.id.desc()).limit(1))
            previous_origin = (
                _utc(previous_portal.created_at_utc) if previous_portal is not None else None
            )
            state = RegionalPortalSpawnState(
                campaign_id=campaign_id,
                region_code=region.region_code,
                failure_stacks=0,
                last_portal_spawned_at_utc=previous_origin,
                cooldown_until_utc=(
                    previous_origin + timedelta(seconds=rules.cooldown_seconds)
                    if previous_origin is not None else None
                ),
                rules_version=rules.version,
                created_at_utc=cycle_end,
                updated_at_utc=cycle_end,
            )
            db.add(state)
        elif state.rules_version != rules.version:
            state.failure_stacks = min(max(0, int(state.failure_stacks)), rules.max_stack())
            state.rules_version = rules.version

        if (state.last_evaluated_cycle_number is not None
                and state.last_evaluated_cycle_number >= cycle.cycle_number):
            continue

        same_cycle_event = db.scalar(select(RegionalEvent.id).where(
            RegionalEvent.campaign_id == campaign_id,
            RegionalEvent.event_type == "portal",
            RegionalEvent.region_code == region.region_code,
            RegionalEvent.trigger_cycle_number == cycle.cycle_number,
        ).limit(1))
        if same_cycle_event is not None:
            state.last_evaluated_cycle_number = cycle.cycle_number
            state.last_result = "event_already_exists"
            state.updated_at_utc = cycle_end
            continue

        if _portal_blocks_spawn_evaluation(
            db, campaign_id, region.region_code, cycle_end,
        ):
            result = "active_portal"
        elif state.cooldown_until_utc is not None and cycle_end < _utc(state.cooldown_until_utc):
            result = "cooldown"
        elif not portal_bosses:
            result = (
                "no_eligible_content"
                if event_rules_version == V9_EVENT_RULES_VERSION
                else "content_unavailable"
            )
        else:
            player_state = db.scalar(select(RegionalGuildState).where(
                RegionalGuildState.campaign_id == campaign_id,
                RegionalGuildState.region_code == region.region_code,
                RegionalGuildState.guild_id.is_not(None),
            ).limit(1))
            scouts_level = 0
            if player_state is not None and player_state.guild_id is not None:
                scouts_level = int(db.scalar(select(GuildBuilding.level).join(
                    BuildingTemplate, BuildingTemplate.id == GuildBuilding.building_template_id,
                ).where(
                    GuildBuilding.guild_id == player_state.guild_id,
                    BuildingTemplate.effect_type == "scouts",
                )) or 0)
            detection_bonus_pp = int(
                scouts_values(scouts_level)["portal_detection_bonus_percentage_points"]
            )
            base_chance_pp, explorer_bonus_pp, chance_pp = rules.chance_percentages(
                state.failure_stacks, detection_bonus_pp,
            )
            seed = _seed_text(
                campaign_id, cycle.cycle_number, region.region_code, rules.version, "portal",
            )
            if _rng(seed, "chance").random() * 100.0 >= chance_pp:
                state.failure_stacks = min(rules.max_stack(), int(state.failure_stacks) + 1)
                result = "rolled_failure"
            else:
                template = portal_bosses[_rng(seed, "boss").randrange(len(portal_bosses))]
                loot_snapshot = build_portal_loot_snapshot(
                    db,
                    template,
                    _seed_text(seed, "loot", template.id),
                )
                if not loot_snapshot["entries"]:
                    # Content may be edited concurrently by an administrator.
                    # Do not turn an invalidated pool into a failure or success.
                    result = "content_unavailable"
                else:
                    db.add(RegionalEvent(
                        campaign_id=campaign_id,
                        event_type="portal",
                        region_code=region.region_code,
                        trigger_cycle_number=cycle.cycle_number,
                        rules_version=event_rules_version,
                        seed=seed,
                        status="active",
                        dungeon_template_id=template.id,
                        created_at_utc=cycle_end,
                        expires_at_utc=cycle_end + timedelta(hours=rules.entry_window_hours),
                        summary_json=json.dumps({
                            "portal_spawn_rules_version": rules.version,
                            "chance_percent": chance_pp,
                            "base_chance_percent": base_chance_pp,
                            "explorer_detection_bonus_pp": explorer_bonus_pp,
                            "failure_stacks_before_roll": int(state.failure_stacks),
                            "failure_stacks_after_roll": 0,
                            "cooldown_hours": rules.cooldown_hours,
                            "entry_window_hours": rules.entry_window_hours,
                            "deadline_policy": "continues_offline",
                            "threat_snapshot": round(region.threat, 4),
                            "content_policy": (
                                "active_stage_eligible_portal_or_introductory_boss"
                                if stage_eligible else "active_portal_biome_boss_template"
                            ),
                            "progression_stage_level_snapshot": (
                                stage_level if stage_eligible else None
                            ),
                            "content_eligibility_version": (
                                "native-party-v1" if event_rules_version == V9_EVENT_RULES_VERSION else None
                            ),
                            "portal_boss": {
                                "version": PORTAL_BOSS_SNAPSHOT_VERSION if stage_eligible else "portal-boss-v1",
                                "template": build_portal_boss_snapshot(template),
                            },
                            "portal_loot": loot_snapshot,
                        }, ensure_ascii=False, sort_keys=True),
                    ))
                    state.failure_stacks = 0
                    state.last_portal_spawned_at_utc = cycle_end
                    state.cooldown_until_utc = cycle_end + timedelta(seconds=rules.cooldown_seconds)
                    result = "spawned"

        state.last_evaluated_cycle_number = cycle.cycle_number
        state.last_result = result
        state.updated_at_utc = cycle_end
        db.add(state)
    db.flush()


def evaluate_open_rebellion(
    db: Session,
    campaign: CampaignMetadata,
    cycle: RegionalCycle,
    guild_id: int,
    now: datetime,
) -> RegionalEvent | None:
    """Roll once for this cycle, and only when the campaign is open."""
    _hold_campaign_event_lock(db, campaign.campaign_id)
    return _evaluate_open_rebellion_locked(db, campaign, cycle, guild_id, now)


def _evaluate_open_rebellion_locked(
    db: Session,
    campaign: CampaignMetadata,
    cycle: RegionalCycle,
    guild_id: int,
    now: datetime,
) -> RegionalEvent | None:
    current = _utc(now)
    expire_due_events(db, campaign.campaign_id, current)
    event_rules_version = _event_rules_version_for_cycle(cycle)
    current_rebellion_rules = event_rules_version in {
        V7_EVENT_RULES_VERSION, V8_EVENT_RULES_VERSION, V9_EVENT_RULES_VERSION,
    }
    rebellion_cooldown = (
        REBELLION_REGION_ROLL_COOLDOWN_CYCLES if current_rebellion_rules
        else LEGACY_REBELLION_REGION_ROLL_COOLDOWN_CYCLES
    )
    rebellion_chance = (
        REBELLION_CHANCE if event_rules_version in {V8_EVENT_RULES_VERSION, V9_EVENT_RULES_VERSION}
        else LEGACY_REBELLION_CHANCE
    )
    active = db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.status.in_(("active", "in_progress")),
    ).order_by(RegionalEvent.id).limit(1))
    if active is not None:
        return active
    attempted = list(db.scalars(select(RegionalEvent.id).where(
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.trigger_cycle_number == cycle.cycle_number,
    )))
    if attempted:
        return None

    regions = list(db.scalars(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign.campaign_id,
    ).order_by(RegionalRegionState.region_code)))
    eligible = {
        region.region_code: region
        for region in regions
        if region.threat >= REBELLION_MIN_THREAT and region.security <= REBELLION_MAX_SECURITY
    }
    seeds: dict[str, str] = {}
    for region in regions:
        seed = _seed_text(
            campaign.campaign_id, cycle.cycle_number, region.region_code, event_rules_version, "rebellion",
        )
        seeds[region.region_code] = seed
    prior_rolls = list(db.scalars(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.trigger_cycle_number < cycle.cycle_number,
    )))
    last_targeted: dict[str, int] = {}
    for event in prior_rolls:
        if (_summary(event).get("roll_selected")
                or event.status not in {"not_triggered", "suppressed"}):
            last_targeted[event.region_code] = max(
                event.trigger_cycle_number, last_targeted.get(event.region_code, -1),
            )
    roll_target = None
    available = [
        region for region in eligible.values()
        if region.region_code not in last_targeted
        or cycle.cycle_number - last_targeted[region.region_code] > rebellion_cooldown
    ]
    if available:
        roll_target = min(
            available,
            key=lambda region: (
                last_targeted.get(region.region_code, -1),
                -float(region.threat + 100.0 - region.security),
                region.region_code,
            ),
        )
    rolled: list[tuple[RegionalRegionState, str]] = []
    if roll_target is not None:
        target_seed = seeds[roll_target.region_code]
        if _rng(target_seed).random() < rebellion_chance:
            rolled.append((roll_target, target_seed))
    winner = rolled[0] if rolled else None
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild_id)
    result: RegionalEvent | None = None
    for region in regions:
        chosen = bool(winner and winner[0].region_code == region.region_code)
        candidate = any(row.region_code == region.region_code for row, _seed in rolled)
        event = RegionalEvent(
            campaign_id=campaign.campaign_id,
            event_type="rebellion",
            region_code=region.region_code,
            trigger_cycle_number=cycle.cycle_number,
            rules_version=event_rules_version,
            seed=seeds[region.region_code],
            status="active" if chosen else ("suppressed" if candidate else "not_triggered"),
            created_at_utc=current,
            priority_ends_at_utc=current + REBELLION_PRIORITY if chosen else None,
                expires_at_utc=(current + REBELLION_PRIORITY + REBELLION_TTL) if chosen else current,
            summary_json=json.dumps({
                "eligible": region.region_code == (roll_target.region_code if roll_target else None),
                "threshold_eligible": region.region_code in eligible,
                "roll_selected": region.region_code == (roll_target.region_code if roll_target else None),
                "chance_per_eligible_region_cycle": (
                    rebellion_chance
                    if region.region_code == (roll_target.region_code if roll_target else None)
                    else 0
                ),
                "threat_snapshot": round(region.threat, 4),
                "security_snapshot": round(region.security, 4),
                "generated_while_campaign_open": chosen,
                "suppressed_by_global_limit": False,
                "region_roll_cooldown_cycles": rebellion_cooldown,
                "simultaneous_candidates": len(rolled),
            }, ensure_ascii=False, sort_keys=True),
        )
        db.add(event)
        db.flush()
        if chosen:
            result = event
            if player_state is not None:
                db.add(RegionalEventParticipant(
                    event_id=event.id,
                    guild_state_id=player_state.id,
                    status="invited",
                ))
    db.flush()
    return result


def record_rebellion_decision(
    db: Session,
    event: RegionalEvent,
    guild_state_id: int,
    decision: str,
    now: datetime,
) -> None:
    if decision not in {"accept", "decline"}:
        raise ValueError("Decisão de evento inválida.")
    current = _utc(now)
    if event.event_type != "rebellion" or event.status != "active":
        raise ValueError("Convite indisponível.")
    if event.priority_ends_at_utc is None or current >= _utc(event.priority_ends_at_utc):
        raise ValueError("A prioridade do convite terminou.")
    participant = db.scalar(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == guild_state_id,
    ))
    if participant is None or participant.status != "invited":
        raise ValueError("Convite já respondido ou indisponível.")
    participant.status = "accepted" if decision == "accept" else "declined"
    event.player_decision = decision
    if decision == "accept":
        event.cpu_started_at_utc = _utc(event.priority_ends_at_utc)
        # Acceptance preserves the full 12-hour activity window after the
        # one-hour invitation priority ends.
        event.expires_at_utc = _utc(event.priority_ends_at_utc) + REBELLION_TTL
    else:
        event.cpu_started_at_utc = current
        event.expires_at_utc = current + REBELLION_TTL
    payload = _summary(event)
    payload["player_decision"] = decision
    payload["player_decision_at_utc"] = current.isoformat()
    payload["cpu_started_at_utc"] = event.cpu_started_at_utc.isoformat()
    payload["cpu_execution_expires_at_utc"] = event.expires_at_utc.isoformat()
    _save_summary(event, payload)
    db.add_all([event, participant])
    db.flush()


def attach_event_activity(
    db: Session,
    event: RegionalEvent,
    guild_state: RegionalGuildState,
    source_type: str,
    source_run_id: int,
) -> RegionalEventActivity:
    if event.status != "active":
        raise ValueError("O evento já foi encerrado.")
    if event.event_type == "rebellion" and event.player_decision != "accept":
        raise ValueError("A guilda precisa aceitar o convite antes de participar.")
    existing_activity = db.scalar(select(RegionalEventActivity).where(
        RegionalEventActivity.source_type == source_type,
        RegionalEventActivity.source_run_id == source_run_id,
    ))
    if existing_activity is not None:
        if existing_activity.event_id == event.id and existing_activity.guild_state_id == guild_state.id:
            return existing_activity
        raise ValueError("Esta atividade já está vinculada a outro evento.")
    participant = db.scalar(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == guild_state.id,
    ))
    if event.event_type == "portal" and participant is not None:
        raise ValueError("Esta guilda já usou sua entrada neste portal.")
    if participant is None:
        participant = RegionalEventParticipant(
            event_id=event.id,
            guild_state_id=guild_state.id,
            status="participating",
        )
        db.add(participant)
        db.flush()
    elif participant.status not in {"accepted", "participating"}:
        raise ValueError("A guilda não está habilitada para esta atividade do evento.")
    participant.status = "participating"
    activity = RegionalEventActivity(
        event_id=event.id,
        guild_state_id=guild_state.id,
        source_type=source_type,
        source_run_id=source_run_id,
        status="in_progress",
    )
    db.add_all([participant, activity])
    db.flush()
    return activity


def record_event_activity_result(
    db: Session,
    source_type: str,
    source_run_id: int,
    success: bool,
    now: datetime,
) -> RegionalEventActivity | None:
    activity = db.scalar(select(RegionalEventActivity).where(
        RegionalEventActivity.source_type == source_type,
        RegionalEventActivity.source_run_id == source_run_id,
        RegionalEventActivity.status == "in_progress",
    ))
    if activity is None:
        return None
    activity.status = "resolved"
    activity.successes = 1 if success else 0
    activity.failures = 0 if success else 1
    activity.contribution = max(1, activity.contribution)
    activity.resolved_at_utc = _utc(now)
    db.add(activity)
    db.flush()
    event = db.get(RegionalEvent, activity.event_id)
    if (event is not None and event.event_type == "rebellion"
            and _utc(now) >= _utc(event.expires_at_utc)):
        if _has_in_progress_activity(db, event.id):
            _mark_event_waiting_for_started_activities(db, event)
        else:
            _finalize_rebellion_event(db, event, _utc(now))
        db.flush()
    return activity


def record_cpu_event_activity(
    db: Session,
    campaign_id: str,
    cycle: RegionalCycle,
    region_code: str,
    plan,
) -> tuple[float, float]:
    portal_security_delta = 0.0
    portal_threat_delta = 0.0
    cycle_end = _utc(cycle.ends_at_utc)
    cycle_start = _utc(cycle.starts_at_utc)
    if cycle.rules_version == VIGILIA_V9_RULES_VERSION:
        # Acquire before the first read so concurrent schedulers cannot both
        # observe an unused guild/event entry from an older database snapshot.
        _hold_campaign_event_lock(db, campaign_id)
    portal = db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEvent.region_code == region_code,
        RegionalEvent.status.in_(("active", "in_progress")),
        RegionalEvent.created_at_utc <= cycle_start,
        RegionalEvent.expires_at_utc > cycle_start,
    ).order_by(RegionalEvent.id.desc()).limit(1))
    new_cpu_portal_rules = bool(
        portal is not None
        and cycle.rules_version == VIGILIA_V9_RULES_VERSION
        and portal.rules_version == V9_EVENT_RULES_VERSION
    )
    if portal is not None and new_cpu_portal_rules:
        _hold_campaign_event_lock(db, campaign_id)
        existing_activity = db.scalar(select(RegionalEventActivity).where(
            RegionalEventActivity.source_type == "cpu_portal",
            RegionalEventActivity.source_run_id == plan.id,
        ))
        if existing_activity is None:
            try:
                decisions = json.loads(plan.decisions_json or "[]")
                diagnostics = json.loads(plan.event_diagnostics_json or "{}")
            except (TypeError, json.JSONDecodeError):
                decisions, diagnostics = [], {}
            if not isinstance(decisions, list):
                decisions = []
            if not isinstance(diagnostics, dict):
                diagnostics = {}
            portal_run = next((row for row in decisions if (
                isinstance(row, dict)
                and row.get("offer_type") == "portal"
                and row.get("event_id") == portal.id
                and row.get("pending_cpu_resolution") is True
            )), None)
            participant = db.scalar(select(RegionalEventParticipant).where(
                RegionalEventParticipant.event_id == portal.id,
                RegionalEventParticipant.guild_state_id == plan.guild_state_id,
            ))
            if (portal_run is not None and participant is None
                    and portal_run.get("started_at_utc") and portal_run.get("resolved_at_utc")
                    and isinstance(portal_run.get("result_success_snapshot"), bool)):
                started_at = _utc(datetime.fromisoformat(portal_run["started_at_utc"]))
                due_at = _utc(datetime.fromisoformat(portal_run["resolved_at_utc"]))
                if started_at >= _utc(portal.expires_at_utc):
                    reason_code = "entry_window_closed_before_start"
                    reason_detail = "A equipe ficou disponível depois do prazo de entrada do portal."
                else:
                    participant = RegionalEventParticipant(
                        event_id=portal.id,
                        guild_state_id=plan.guild_state_id,
                        status="participating",
                    )
                    planner_effects = portal_run.get("planner_effects_snapshot")
                    snapshot = {
                        "version": (
                            "cpu-portal-resolution-v2"
                            if isinstance(planner_effects, dict)
                            else "cpu-portal-resolution-v1"
                        ),
                        "cycle_rules_version": cycle.rules_version,
                        "event_rules_version": portal.rules_version,
                        "seed": plan.seed,
                        "event_seed": portal.seed,
                        "success": portal_run["result_success_snapshot"],
                        "success_chance": int(portal_run.get("success_chance") or 0),
                        "mercenary_ids": [int(value) for value in portal_run.get("mercenary_ids", [])],
                        "party": portal_run.get("party_snapshot", []),
                        "planner_effects": planner_effects,
                        "portal_boss": _summary(portal).get("portal_boss", {}),
                        "started_at_utc": started_at.isoformat(),
                        "due_at_utc": due_at.isoformat(),
                    }
                    activity = RegionalEventActivity(
                        event_id=portal.id,
                        guild_state_id=plan.guild_state_id,
                        source_type="cpu_portal",
                        source_run_id=plan.id,
                        status="in_progress",
                        contribution=0,
                        started_at_utc=started_at,
                        due_at_utc=due_at,
                        snapshot_json=json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                    )
                    db.add_all([participant, activity])
                    db.flush()
                    reason_code = None
                    reason_detail = None
            elif participant is not None:
                reason_code = "entry_already_used"
                reason_detail = "Esta guilda já registrou uma entrada neste portal."
            elif portal_run is not None:
                reason_code = "invalid_start_snapshot"
                reason_detail = "O plano não contém um snapshot completo da equipe e do prazo."
            else:
                reason_code = str(diagnostics.get("reason_code") or "no_eligible_portal_action")
                reason_detail = str(diagnostics.get("detail") or "Nenhuma equipe iniciou o portal dentro do prazo.")

            if reason_code:
                db.add(RegionalEventActivity(
                    event_id=portal.id,
                    guild_state_id=plan.guild_state_id,
                    source_type="cpu_portal",
                    source_run_id=plan.id,
                    status="not_started",
                    reason_code=reason_code[:40],
                    reason_detail=reason_detail[:255],
                ))
                db.flush()
    elif portal is not None and plan.actions > 0:
        participant_exists = db.scalar(select(RegionalEventParticipant.id).where(
            RegionalEventParticipant.event_id == portal.id,
            RegionalEventParticipant.guild_state_id == plan.guild_state_id,
        ))
        if participant_exists is None:
            rng = _rng(portal.seed, plan.seed, "cpu-portal-entry")
            if cycle.rules_version in {
                "vigilia-v5", "vigilia-v6", VIGILIA_V7_RULES_VERSION,
                CPU_INTERNAL_CONTRACT_RULES_VERSION, VIGILIA_RULES_VERSION,
            }:
                decisions = json.loads(plan.decisions_json or "[]")
                outcomes = json.loads(plan.outcomes_json or "[]")
                outcome_by_offer = {item.get("offer_id"): item for item in outcomes}
                portal_runs = [decision for decision in decisions if (
                    decision.get("offer_type") == "portal"
                    and decision.get("event_id") == portal.id
                    and decision.get("started_at_utc")
                    and _utc(datetime.fromisoformat(decision["started_at_utc"])) < _utc(portal.expires_at_utc)
                )]
                portal_run = min(portal_runs, key=lambda item: (item["started_at_utc"], item["offer_id"])) if portal_runs else None
                resolved_at = (
                    _utc(datetime.fromisoformat(portal_run["resolved_at_utc"]))
                    if portal_run and portal_run.get("resolved_at_utc") else None
                )
                eligible_portal_action = portal_run is not None and resolved_at is not None
                success = bool(outcome_by_offer.get(portal_run["offer_id"], {}).get("success")) if eligible_portal_action else False
                # The entry window gates the start time. An eligible run may
                # finish after the portal closes and still count in its result.
                participate = eligible_portal_action
            else:
                # Legacy CPU rules assigned a fixed two-hour, independent portal roll.
                resolved_at = cycle_start + timedelta(hours=2)
                participate = rng.random() < PORTAL_CPU_PARTICIPATION_CHANCE
                if participate:
                    success = rng.random() < (plan.successes / max(1, plan.actions))
            if participate:
                db.add(RegionalEventParticipant(
                    event_id=portal.id,
                    guild_state_id=plan.guild_state_id,
                    status="resolved",
                    success=success,
                    contribution=3 if success else 1,
                    resolved_at_utc=resolved_at,
                ))
                db.add(RegionalEventActivity(
                    event_id=portal.id,
                    guild_state_id=plan.guild_state_id,
                    source_type="cpu_portal",
                    source_run_id=plan.id,
                    status="resolved",
                    successes=1 if success else 0,
                    failures=0 if success else 1,
                    contribution=3 if success else 1,
                    resolved_at_utc=resolved_at,
                ))
                impact = regional_outcome_impact("C")
                portal_security_delta = impact if success else -impact
                portal_threat_delta = -impact if success else impact
                db.flush()

    if plan.actions <= 0:
        return portal_security_delta, portal_threat_delta

    event = db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.region_code == region_code,
        RegionalEvent.status == "active",
        RegionalEvent.created_at_utc <= _utc(cycle.starts_at_utc),
        RegionalEvent.expires_at_utc > cycle_start,
    ).order_by(RegionalEvent.id.desc()).limit(1))
    if event is None:
        return portal_security_delta, portal_threat_delta
    db.flush()
    existing = db.scalar(select(RegionalEventActivity.id).where(
        RegionalEventActivity.event_id == event.id,
        RegionalEventActivity.source_type == "cpu_cycle",
        RegionalEventActivity.source_run_id == plan.id,
    ))
    if existing is not None:
        return portal_security_delta, portal_threat_delta
    try:
        decisions = json.loads(getattr(plan, "decisions_json", "[]") or "[]")
        outcomes = json.loads(getattr(plan, "outcomes_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        decisions, outcomes = [], []
    cpu_start = event.cpu_started_at_utc or event.priority_ends_at_utc or event.created_at_utc
    cpu_start = _utc(cpu_start)
    event_deadline = _utc(event.expires_at_utc)
    if decisions:
        eligible_decisions = []
        for decision in decisions:
            if not isinstance(decision, dict) or decision.get("internal_contract"):
                continue
            started_value = decision.get("started_at_utc")
            if not started_value:
                continue
            started_at = _utc(datetime.fromisoformat(started_value))
            if cpu_start <= started_at < event_deadline:
                eligible_decisions.append(decision)
        if not eligible_decisions:
            return portal_security_delta, portal_threat_delta
        eligible_offer_ids = {str(row.get("offer_id")) for row in eligible_decisions}
        eligible_outcomes = [
            row for row in outcomes
            if isinstance(row, dict) and str(row.get("offer_id")) in eligible_offer_ids
        ]
        successes = sum(bool(row.get("success")) for row in eligible_outcomes)
        failures = len(eligible_outcomes) - successes
        contribution = len(eligible_outcomes)
        resolved_values = [
            row.get("resolved_at_utc") for row in eligible_decisions
            if row.get("resolved_at_utc")
        ]
        resolved_at = max(
            (_utc(datetime.fromisoformat(value)) for value in resolved_values),
            default=cycle_end,
        )
    elif cpu_start <= cycle_start:
        # Legacy plans don't carry per-action timestamps; keep their original
        # whole-cycle accounting when the CPU window had already opened.
        successes = int(plan.successes or 0)
        failures = int(plan.failures or 0)
        contribution = int(plan.actions or 0)
        resolved_at = cycle_end
        if contribution <= 0:
            return portal_security_delta, portal_threat_delta
    else:
        return portal_security_delta, portal_threat_delta
    participant = db.scalar(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == plan.guild_state_id,
    ))
    if participant is None:
        participant = RegionalEventParticipant(
            event_id=event.id,
            guild_state_id=plan.guild_state_id,
            status="participating",
        )
        db.add(participant)
    else:
        participant.status = "participating"
        db.add(participant)
    db.add(RegionalEventActivity(
        event_id=event.id,
        guild_state_id=plan.guild_state_id,
        source_type="cpu_cycle",
        source_run_id=plan.id,
        status="resolved",
        successes=successes,
        failures=failures,
        contribution=contribution,
        resolved_at_utc=resolved_at,
    ))
    db.flush()
    return portal_security_delta, portal_threat_delta


def resolve_portal_participant(
    db: Session,
    activity: RegionalEventActivity,
    success: bool,
    now: datetime,
) -> None:
    event = db.get(RegionalEvent, activity.event_id)
    participant = db.scalar(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == activity.event_id,
        RegionalEventParticipant.guild_state_id == activity.guild_state_id,
    ))
    if event is None or participant is None or event.event_type != "portal":
        return
    region = db.scalar(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == event.campaign_id,
        RegionalRegionState.region_code == event.region_code,
    ))
    if region is None:
        return
    impact = regional_outcome_impact("C")
    if success:
        region.security = round(min(100.0, region.security + impact), 4)
        region.threat = round(max(0.0, region.threat - impact), 4)
    else:
        region.security = round(max(0.0, region.security - impact), 4)
        region.threat = round(min(100.0, region.threat + impact), 4)
    region.last_updated_cycle = event.trigger_cycle_number
    participant.status = "resolved"
    participant.success = success
    participant.contribution = 3 if success else 1
    participant.resolved_at_utc = _utc(now)
    db.add_all([region, participant])
    current = _utc(now)
    if event.status == "in_progress" or current >= _utc(event.expires_at_utc):
        _finalize_portal_event_when_ready(db, event, current)
    db.flush()


def _apply_cpu_portal_planner_effects(
    db: Session,
    guild_state_id: int,
    region_code: str,
    planner_effects: dict[str, object],
) -> tuple[int, int]:
    """Apply the frozen non-event effects of one completed CPU portal run."""
    state = db.get(RegionalGuildState, guild_state_id)
    if state is None:
        raise ValueError("A guilda CPU do portal não existe mais.")

    success = planner_effects.get("success")
    rank_value = planner_effects.get("rank_value")
    int_fields = (
        "gold_earned", "xp_earned", "gold_resource_delta", "xp_resource_delta",
        "profession_resource_delta",
    )
    if (not isinstance(success, bool)
            or type(rank_value) is not int or not 1 <= rank_value <= 6
            or any(type(planner_effects.get(key)) is not int or planner_effects[key] < 0
                   for key in int_fields)):
        raise ValueError("O snapshot dos efeitos do planejador CPU está inválido.")
    profession_code = planner_effects.get("profession_resource_code")
    profession_delta = int(planner_effects["profession_resource_delta"])
    if profession_delta and (not isinstance(profession_code, str) or not profession_code):
        raise ValueError("O snapshot da recompensa de profissão está inválido.")

    if success:
        state.influence = min(100, int(state.influence or 0) + rank_value)
        state.reputation = min(100, int(state.reputation or 0) + rank_value)
    else:
        state.influence = min(100, int(state.influence or 0) + 1)
        state.reputation = max(0, int(state.reputation or 0) - max(1, rank_value // 2))
    db.add(state)

    resource_deltas = {
        "gold": int(planner_effects["gold_resource_delta"]),
        "xp": int(planner_effects["xp_resource_delta"]),
    }
    if profession_delta:
        resource_deltas[str(profession_code)] = profession_delta
    for resource_code, delta in resource_deltas.items():
        if not delta:
            continue
        resource = db.scalar(select(RegionalCpuResource).where(
            RegionalCpuResource.guild_state_id == guild_state_id,
            RegionalCpuResource.resource_code == resource_code,
        ))
        if resource is None:
            raise ValueError("Uma recompensa congelada perdeu seu recurso CPU.")
        resource.amount = min(int(resource.capacity), int(resource.amount) + delta)
        db.add(resource)

    region = db.scalar(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == state.campaign_id,
        RegionalRegionState.region_code == region_code,
    ))
    if region is None:
        raise ValueError("A região do portal CPU não existe mais.")
    guild_influences = list(db.scalars(select(RegionalGuildState.influence).where(
        RegionalGuildState.campaign_id == state.campaign_id,
        RegionalGuildState.region_code == region_code,
    )))
    region.influence = max(0, min(100, round(sum(guild_influences) / max(1, len(guild_influences)))))
    db.add(region)
    db.flush()
    return int(planner_effects["gold_earned"]), int(planner_effects["xp_earned"])


def resolve_due_cpu_portal_activities(
    db: Session,
    campaign_id: str,
    now: datetime,
    *,
    region_code: str | None = None,
) -> dict[str, tuple[float, float]]:
    """Resolve frozen CPU portal runs due by ``now`` once, in timestamp order."""
    current = _utc(now)
    _hold_campaign_event_lock(db, campaign_id)
    query = select(RegionalEventActivity).join(
        RegionalEvent, RegionalEvent.id == RegionalEventActivity.event_id,
    ).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEventActivity.source_type == "cpu_portal",
        RegionalEventActivity.status == "in_progress",
        RegionalEventActivity.due_at_utc.is_not(None),
        RegionalEventActivity.due_at_utc <= current,
    )
    if region_code is not None:
        query = query.where(RegionalEvent.region_code == region_code)
    activities = list(db.scalars(query.order_by(
        RegionalEventActivity.due_at_utc, RegionalEventActivity.id,
    )))
    if not activities:
        return {}
    effects: dict[str, tuple[float, float]] = {}
    for activity in activities:
        if activity.status != "in_progress":
            continue
        event = db.get(RegionalEvent, activity.event_id)
        participant = db.scalar(select(RegionalEventParticipant).where(
            RegionalEventParticipant.event_id == activity.event_id,
            RegionalEventParticipant.guild_state_id == activity.guild_state_id,
        ))
        region = db.scalar(select(RegionalRegionState).where(
            RegionalRegionState.campaign_id == campaign_id,
            RegionalRegionState.region_code == (event.region_code if event else ""),
        ))
        if event is None or participant is None or region is None:
            raise ValueError("A atividade CPU pendente perdeu seu evento, participante ou região.")
        try:
            snapshot = json.loads(activity.snapshot_json or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("O snapshot da atividade CPU pendente está inválido.") from exc
        snapshot_version = snapshot.get("version") if isinstance(snapshot, dict) else None
        planner_effects = snapshot.get("planner_effects") if isinstance(snapshot, dict) else None
        if (not isinstance(snapshot, dict)
                or snapshot_version not in {"cpu-portal-resolution-v1", "cpu-portal-resolution-v2"}
                or snapshot.get("event_rules_version") != V9_EVENT_RULES_VERSION
                or snapshot.get("cycle_rules_version") != VIGILIA_V9_RULES_VERSION
                or not isinstance(snapshot.get("success"), bool)):
            raise ValueError("O snapshot da atividade CPU pendente não corresponde às regras v9.")
        if (snapshot_version == "cpu-portal-resolution-v2"
                and (not isinstance(planner_effects, dict)
                     or planner_effects.get("success") is not snapshot["success"])):
            raise ValueError("O snapshot dos efeitos do planejador CPU está inválido.")

        due_at = _utc(activity.due_at_utc)
        success = bool(snapshot["success"])
        activity.status = "resolved"
        activity.successes = 1 if success else 0
        activity.failures = 0 if success else 1
        activity.contribution = 3 if success else 1
        activity.resolved_at_utc = due_at
        db.add(activity)
        db.flush()

        if participant.status != "resolved":
            before_security, before_threat = float(region.security), float(region.threat)
            if snapshot_version == "cpu-portal-resolution-v1":
                # The old candidate applied planner effects eagerly. Preserve
                # those persisted values and finish only its event ledger.
                participant.status = "resolved"
                participant.success = success
                participant.contribution = 3 if success else 1
                participant.resolved_at_utc = due_at
                db.add(participant)
                if event.status == "in_progress" or due_at >= _utc(event.expires_at_utc):
                    _finalize_portal_event_when_ready(db, event, due_at)
                db.flush()
            else:
                resolve_portal_participant(db, activity, success, due_at)
                _apply_cpu_portal_planner_effects(
                    db, activity.guild_state_id, event.region_code, planner_effects,
                )
            delta = (
                round(float(region.security) - before_security, 4),
                round(float(region.threat) - before_threat, 4),
            )
            old = effects.get(event.region_code, (0.0, 0.0))
            effects[event.region_code] = (old[0] + delta[0], old[1] + delta[1])
        plan = db.get(RegionalCpuCyclePlan, activity.source_run_id)
        if plan is not None and plan.guild_state_id == activity.guild_state_id:
            try:
                decisions = json.loads(plan.decisions_json or "[]")
                outcomes = json.loads(plan.outcomes_json or "[]")
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("O plano da atividade CPU pendente está inválido.") from exc
            portal_decision = next((row for row in decisions if (
                isinstance(row, dict)
                and row.get("event_id") == event.id
                and row.get("pending_cpu_resolution") is True
            )), None) if isinstance(decisions, list) else None
            if portal_decision is None or not isinstance(outcomes, list):
                raise ValueError("O plano da atividade CPU pendente perdeu sua decisão congelada.")
            offer_id = portal_decision.get("offer_id")
            if not any(
                isinstance(row, dict)
                and row.get("offer_id") == offer_id
                and row.get("event_id") == event.id
                for row in outcomes
            ):
                if snapshot_version == "cpu-portal-resolution-v2":
                    gold_earned = int(planner_effects.get("gold_earned", 0))
                    xp_earned = int(planner_effects.get("xp_earned", 0))
                    contribution = int(planner_effects.get("rank_value", 3))
                else:
                    gold_earned = xp_earned = 0
                    contribution = 3 if success else 1
                outcomes.append({
                    "offer_id": offer_id,
                    "event_id": event.id,
                    "rank": "C",
                    "success": success,
                    "gold": gold_earned,
                    "xp": xp_earned,
                    "contribution": contribution,
                })
                plan.outcomes_json = json.dumps(outcomes, ensure_ascii=False, sort_keys=True)
                if snapshot_version == "cpu-portal-resolution-v2":
                    plan.successes = int(plan.successes or 0) + int(success)
                    plan.failures = int(plan.failures or 0) + int(not success)
                    plan.gold_earned = int(plan.gold_earned or 0) + gold_earned
                    plan.xp_earned = int(plan.xp_earned or 0) + xp_earned
                resolved_before = max(0, int(plan.resolved_actions or 0))
                resolved_limit = max(0, int(plan.started_actions or plan.actions or 0))
                if resolved_before >= resolved_limit:
                    raise ValueError("O plano da atividade CPU não tem uma entrada pendente para resolver.")
                plan.resolved_actions = min(resolved_limit, resolved_before + 1)
                db.add(plan)

                cycle_summary = db.scalar(select(RegionalCycleRegion).where(
                    RegionalCycleRegion.cycle_id == plan.cycle_id,
                    RegionalCycleRegion.region_code == event.region_code,
                ))
                if cycle_summary is not None:
                    try:
                        summary = json.loads(cycle_summary.summary_json or "{}")
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise ValueError("O resumo regional do ciclo está inválido.") from exc
                    cpu_activity = summary.get("cpu_activity") if isinstance(summary, dict) else None
                    if not isinstance(cpu_activity, dict):
                        raise ValueError("O resumo regional perdeu as métricas de atividade CPU.")
                    started = max(0, int(cpu_activity.get("started", 0)))
                    resolved = max(0, int(cpu_activity.get("resolved", 0)))
                    pending = int(cpu_activity.get("pending", started - resolved))
                    if pending <= 0 or resolved >= started:
                        raise ValueError("O resumo regional não contém a atividade CPU pendente.")
                    cpu_activity["resolved"] = resolved + 1
                    cpu_activity["pending"] = pending - 1
                    if snapshot_version == "cpu-portal-resolution-v2":
                        summary["successes"] = int(summary.get("successes", 0)) + int(success)
                        summary["failures"] = int(summary.get("failures", 0)) + int(not success)
                        cycle_summary.cpu_successes = int(cycle_summary.cpu_successes or 0) + int(success)
                        cycle_summary.cpu_failures = int(cycle_summary.cpu_failures or 0) + int(not success)
                        cycle_summary.cpu_gold_earned = (
                            int(cycle_summary.cpu_gold_earned or 0) + gold_earned
                        )
                        cycle_summary.cpu_xp_earned = int(cycle_summary.cpu_xp_earned or 0) + xp_earned
                    cycle_summary.summary_json = json.dumps(
                        summary, ensure_ascii=False, sort_keys=True,
                    )
                    db.add(cycle_summary)
                db.flush()
        elif participant.success is not None:
            # Repair a partially completed legacy transaction without applying
            # its regional effect a second time.
            activity.successes = 1 if participant.success else 0
            activity.failures = 0 if participant.success else 1
            activity.contribution = participant.contribution
            activity.resolved_at_utc = participant.resolved_at_utc or due_at
            db.add(activity)
            db.flush()
    return effects


def event_history_for_campaign(db: Session, campaign_id: str, limit: int = 12) -> list[RegionalEvent]:
    return list(db.scalars(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.status.not_in(("not_triggered", "suppressed")),
    ).order_by(RegionalEvent.created_at_utc.desc(), RegionalEvent.id.desc()).limit(limit)))


def active_portals_for_region(db: Session, campaign_id: str, region_code: str) -> list[RegionalEvent]:
    return list(db.scalars(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEvent.region_code == region_code,
        RegionalEvent.status == "active",
    ).order_by(RegionalEvent.expires_at_utc)))


def active_rebellion(db: Session, campaign_id: str) -> RegionalEvent | None:
    return db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.status.in_(("active", "in_progress")),
    ).order_by(RegionalEvent.created_at_utc.desc()).limit(1))


def event_history_summary(event: RegionalEvent) -> dict[str, object]:
    return _summary(event)


def event_region_name(region_code: str) -> str:
    return next((name for code, name in REGIONS if code == region_code), region_code)
