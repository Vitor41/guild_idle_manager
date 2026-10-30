"""Campaign-local event triggers with stable seeds and explicit deadlines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from threading import Lock

from sqlalchemy import event as sqlalchemy_event, select
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import Session

from app.models.campaign import CampaignMetadata
from app.models.dungeon import DungeonTemplate
from app.models.item import ItemTemplate
from app.models.regional import (
    RegionalCycle,
    RegionalEvent,
    RegionalEventActivity,
    RegionalEventParticipant,
    RegionalGuildState,
    RegionalRegionState,
)
from app.services.regional_cycle_service import (
    REGIONS,
    _rng,
    _seed_text,
    get_current_player_regional_guild,
    regional_outcome_impact,
)


EVENT_RULES_VERSION = "regional-events-v3"
PORTAL_LOOT_VERSION = "portal-loot-v1"
PORTAL_LOOT_CHANCE_BY_RARITY = {"rare": 20, "epic": 6, "legendary": 1}
PORTAL_BOSS_SNAPSHOT_VERSION = "portal-boss-v1"
REBELLION_CHANCE = 0.02
PORTAL_TTL = timedelta(hours=3)
REBELLION_PRIORITY = timedelta(hours=1)
REBELLION_TTL = timedelta(hours=12)
PORTAL_BASE_CHANCE = 0.05
PORTAL_MAX_CHANCE = 0.25
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
        RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc <= current,
    )))
    for event in due:
        if _has_in_progress_activity(db, event.id):
            _mark_event_waiting_for_started_activities(db, event)
            continue
        if event.event_type == "portal":
            _finalize_portal_event(db, event, _utc(event.expires_at_utc))
        elif event.event_type == "rebellion":
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
    portal_bosses = list(db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type == "boss",
        DungeonTemplate.biome == "portal",
    ).order_by(DungeonTemplate.recommended_level, DungeonTemplate.id)))
    if not portal_bosses:
        return
    for region in sorted(regions, key=lambda row: row.region_code):
        if region.threat < PORTAL_MIN_THREAT:
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
        chance = min(
            PORTAL_MAX_CHANCE,
            PORTAL_BASE_CHANCE + (float(region.threat) - PORTAL_MIN_THREAT) * (0.20 / 30.0),
        )
        seed = _seed_text(
            campaign_id, cycle.cycle_number, region.region_code, EVENT_RULES_VERSION, "portal",
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
            rules_version=EVENT_RULES_VERSION,
            seed=seed,
            status="active",
            dungeon_template_id=template.id,
            created_at_utc=cycle_end,
            expires_at_utc=cycle_end + PORTAL_TTL,
            summary_json=json.dumps({
                "chance": round(chance, 6),
                "threat_snapshot": round(region.threat, 4),
                "deadline_policy": "continues_offline",
                "content_policy": "active_portal_biome_boss_template",
                "portal_boss": {
                    "version": PORTAL_BOSS_SNAPSHOT_VERSION,
                    "template": build_portal_boss_snapshot(template),
                },
                "portal_loot": loot_snapshot,
            }, ensure_ascii=False, sort_keys=True),
        ))
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
    rolled: list[tuple[RegionalRegionState, str]] = []
    seeds: dict[str, str] = {}
    for region in regions:
        seed = _seed_text(
            campaign.campaign_id, cycle.cycle_number, region.region_code, EVENT_RULES_VERSION, "rebellion",
        )
        seeds[region.region_code] = seed
        if region.region_code in eligible and _rng(seed).random() < REBELLION_CHANCE:
            rolled.append((region, seed))
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
            rules_version=EVENT_RULES_VERSION,
            seed=seeds[region.region_code],
            status="active" if chosen else ("suppressed" if candidate else "not_triggered"),
            created_at_utc=current,
            priority_ends_at_utc=current + REBELLION_PRIORITY if chosen else None,
                expires_at_utc=(current + REBELLION_PRIORITY + REBELLION_TTL) if chosen else current,
            summary_json=json.dumps({
                "eligible": region.region_code in eligible,
                "chance_per_eligible_region_cycle": REBELLION_CHANCE if region.region_code in eligible else 0,
                "threat_snapshot": round(region.threat, 4),
                "security_snapshot": round(region.security, 4),
                "generated_while_campaign_open": chosen,
                "suppressed_by_global_limit": candidate and not chosen,
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
    if plan.actions <= 0:
        return 0.0, 0.0
    portal_security_delta = 0.0
    portal_threat_delta = 0.0
    cycle_end = _utc(cycle.ends_at_utc)
    cycle_start = _utc(cycle.starts_at_utc)
    portal = db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEvent.region_code == region_code,
        RegionalEvent.status == "active",
        RegionalEvent.created_at_utc <= cycle_start,
        RegionalEvent.expires_at_utc > cycle_start,
    ).order_by(RegionalEvent.id.desc()).limit(1))
    if portal is not None:
        participant_exists = db.scalar(select(RegionalEventParticipant.id).where(
            RegionalEventParticipant.event_id == portal.id,
            RegionalEventParticipant.guild_state_id == plan.guild_state_id,
        ))
        if participant_exists is None:
            rng = _rng(portal.seed, plan.seed, "cpu-portal-entry")
            resolved_at = cycle_start + timedelta(hours=2)
            if (rng.random() < PORTAL_CPU_PARTICIPATION_CHANCE
                    and resolved_at <= _utc(portal.expires_at_utc)):
                success = rng.random() < (plan.successes / max(1, plan.actions))
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

    event = db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.region_code == region_code,
        RegionalEvent.status == "active",
        RegionalEvent.created_at_utc <= _utc(cycle.starts_at_utc),
        RegionalEvent.cpu_started_at_utc <= _utc(cycle.starts_at_utc),
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
        successes=plan.successes,
        failures=plan.failures,
        contribution=plan.actions,
        resolved_at_utc=cycle_end,
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
        if _has_in_progress_activity(db, event.id):
            _mark_event_waiting_for_started_activities(db, event)
        else:
            _finalize_portal_event(db, event, current)
    db.flush()


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
