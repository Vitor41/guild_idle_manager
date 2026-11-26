"""Read-only activity summaries for the shared navigation."""
import json
from hashlib import sha256
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import and_, case, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.models.campaign import CampaignMetadata
from app.models.class_change import ClassChangeRun
from app.models.content import ProfessionTraining
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.guild import Guild
from app.models.gathering import GatheringAssignment
from app.models.market import MarketSale
from app.models.mission import MissionRun
from app.models.regional import (
    RegionalCycle,
    RegionalEvent,
    RegionalEventActivity,
    RegionalEventParticipant,
    RegionalGuildState,
    RegionalOffer,
)
from app.services.regional_cycle_service import CYCLE_SECONDS, REGIONS
from app.models.salvage import GuildSalvageJob
from app.models.workshop import SupplyWorkshopJob


MENU_LABELS = {
    "missions": "Missões",
    "dungeons": "Masmorras",
    "gathering": "Coleta",
    "workshops": "Oficinas",
    "blacksmith": "Ferreiro",
    "market": "Mercado",
    "class_change": "Troca de Classe",
    "professions": "Profissões",
    "regional": "Vigília Regional",
    "regional_events": "Eventos Regionais",
}

READY_LABELS = {
    "missions": ("pronta para coletar", "prontas para coletar"),
    "dungeons": ("pronta para coletar", "prontas para coletar"),
    "workshops": ("produção pronta", "produções prontas"),
    "blacksmith": ("desmontagem pronta para coletar", "desmontagens prontas para coletar"),
    "market": ("venda pronta para coletar", "vendas prontas para coletar"),
    "class_change": ("troca pronta para concluir", "trocas prontas para concluir"),
    "professions": ("treinamento pronto para concluir", "treinamentos prontos para concluir"),
    "regional": ("preparação pronta para iniciar", "preparações prontas para iniciar"),
    "regional_events": ("evento pronto para ação", "eventos prontos para ação"),
}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _regional_events_review_token(
    db: Session,
    campaign_id: str,
    guild_id: int,
    *,
    now: datetime | None = None,
) -> str:
    """Fingerprint only the campaign/event state visible in the central events view.

    The token changes at stored event/run milestones and each six-hour campaign
    cycle boundary. It is read-only and deliberately excludes the current clock
    value so routine polling does not force a refresh every time.
    """
    timestamp = _utc(now or datetime.now(timezone.utc))
    campaign = db.get(CampaignMetadata, campaign_id)
    if campaign is None:
        return ""
    elapsed = max(0.0, (timestamp - _utc(campaign.created_at_utc)).total_seconds())
    target_cycle = int(elapsed // CYCLE_SECONDS)
    cycle = db.scalar(select(RegionalCycle).where(
        RegionalCycle.campaign_id == campaign_id,
    ).order_by(RegionalCycle.cycle_number.desc()).limit(1))
    cycle_state = {
        "target_cycle": target_cycle,
        "materialized_cycle": cycle.cycle_number if cycle else None,
        "cycle_status": cycle.status if cycle else None,
        "cycle_ends_at": _utc(cycle.ends_at_utc).isoformat() if cycle else None,
        "cycle_elapsed": bool(cycle and timestamp >= _utc(cycle.ends_at_utc)),
    }
    recent_history_ids = select(RegionalEvent.id).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.status.not_in(("not_triggered", "suppressed")),
    ).order_by(RegionalEvent.created_at_utc.desc(), RegionalEvent.id.desc()).limit(12)
    events = list(db.scalars(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        or_(
            RegionalEvent.status.in_(("active", "in_progress")),
            RegionalEvent.id.in_(recent_history_ids),
        ),
    ).order_by(RegionalEvent.event_type, RegionalEvent.created_at_utc, RegionalEvent.id)))
    event_ids = [event.id for event in events]
    player_state_id = db.scalar(select(RegionalGuildState.id).where(
        RegionalGuildState.campaign_id == campaign_id,
        RegionalGuildState.guild_id == guild_id,
    ))
    participants_by_event: dict[int, list[dict[str, object]]] = {}
    activities_by_event: dict[int, list[dict[str, object]]] = {}
    if player_state_id is not None and event_ids:
        participant_rows = db.execute(select(
            RegionalEventParticipant.event_id,
            RegionalEventParticipant.status,
            RegionalEventParticipant.contribution,
            RegionalEventParticipant.success,
            RegionalEventParticipant.resolved_at_utc,
        ).where(
            RegionalEventParticipant.event_id.in_(event_ids),
            RegionalEventParticipant.guild_state_id == player_state_id,
        ).order_by(RegionalEventParticipant.event_id))
        for event_id, status, contribution, success, resolved_at in participant_rows:
            participants_by_event.setdefault(event_id, []).append({
                "status": status,
                "contribution": contribution,
                "success": success,
                "resolved_at": _utc(resolved_at).isoformat() if resolved_at else None,
            })

        activity = RegionalEventActivity
        activity_rows = db.execute(select(
            activity.event_id,
            activity.source_type,
            activity.status,
            activity.successes,
            activity.failures,
            activity.contribution,
            activity.due_at_utc,
            activity.resolved_at_utc,
            DungeonRun.status,
            DungeonRun.ends_at,
            MissionRun.status,
            MissionRun.ends_at,
        ).outerjoin(
            DungeonRun,
            and_(activity.source_type == "dungeon", DungeonRun.id == activity.source_run_id,
                 DungeonRun.guild_id == guild_id),
        ).outerjoin(
            MissionRun,
            and_(activity.source_type == "mission", MissionRun.id == activity.source_run_id,
                 MissionRun.guild_id == guild_id),
        ).where(
            activity.event_id.in_(event_ids),
            activity.guild_state_id == player_state_id,
        ).order_by(activity.event_id, activity.id))
        for (event_id, source_type, status, successes, failures, contribution, due_at,
             resolved_at, dungeon_status, dungeon_ends_at, mission_status, mission_ends_at) in activity_rows:
            run_status, run_ends_at = (
                (dungeon_status, dungeon_ends_at) if source_type == "dungeon"
                else (mission_status, mission_ends_at) if source_type == "mission"
                else (None, None)
            )
            milestone = due_at or run_ends_at
            activities_by_event.setdefault(event_id, []).append({
                "source_type": source_type,
                "status": status,
                "successes": successes,
                "failures": failures,
                "contribution": contribution,
                "due_at": _utc(milestone).isoformat() if milestone else None,
                "due_elapsed": bool(milestone and timestamp >= _utc(milestone)),
                "run_status": run_status,
                "run_ends_at": _utc(run_ends_at).isoformat() if run_ends_at else None,
                "resolved_at": _utc(resolved_at).isoformat() if resolved_at else None,
            })

    event_state = []
    for event in events:
        expires_at = _utc(event.expires_at_utc)
        priority_ends_at = _utc(event.priority_ends_at_utc) if event.priority_ends_at_utc else None
        event_state.append({
            "id": event.id,
            "type": event.event_type,
            "region": event.region_code,
            "status": event.status,
            "created_at": _utc(event.created_at_utc).isoformat(),
            "expires_at": expires_at.isoformat(),
            "expired": timestamp >= expires_at,
            "priority_ends_at": priority_ends_at.isoformat() if priority_ends_at else None,
            "priority_elapsed": bool(priority_ends_at and timestamp >= priority_ends_at),
            "cpu_started_at": _utc(event.cpu_started_at_utc).isoformat() if event.cpu_started_at_utc else None,
            "summary_digest": sha256((event.summary_json or "{}").encode("utf-8")).hexdigest(),
            "participants": participants_by_event.get(event.id, []),
            "activities": activities_by_event.get(event.id, []),
        })
    material = json.dumps(
        {"cycle": cycle_state, "events": event_state},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return sha256(material.encode("utf-8")).hexdigest()


def regional_events_review_token(
    db: Session,
    campaign_id: str,
    guild_id: int,
    *,
    now: datetime | None = None,
) -> str:
    """Read the current central-event revision without flushing pending ORM state."""
    with db.no_autoflush:
        return _regional_events_review_token(db, campaign_id, guild_id, now=now)


def _count_row(menu: str, model, guild_id: int, now: datetime, *, ready_action: bool = True):
    active = model.status == "in_progress" if hasattr(model, "status") else literal(True)
    if hasattr(model, "ends_at"):
        is_ready = model.ends_at <= now
        active = active & (model.ends_at > now)
    elif hasattr(model, "supply_preparation_ends_at_utc"):
        is_ready = model.supply_prepared_at_utc.is_not(None) | (model.supply_preparation_ends_at_utc <= now)
        active = active & model.supply_preparation_ends_at_utc.is_not(None) & (model.supply_preparation_ends_at_utc > now)
    else:
        is_ready = literal(False)
    ready = ((model.status == "in_progress") & is_ready) if ready_action else literal(False)
    query = select(
        literal(menu).label("menu"),
        func.coalesce(func.sum(case((active, 1), else_=0)), 0).label("active"),
        func.coalesce(func.sum(case((ready, 1), else_=0)), 0).label("ready"),
    ).where(model.guild_id == guild_id)
    if model is GatheringAssignment:
        # Capacity-paused collectors have no production in progress. Their
        # assignment remains persisted and resumes after inventory space frees.
        query = query.where(GatheringAssignment.capacity_paused.is_(False))
    return query


def _regional_preparation_row(campaign_id: str, guild_id: int, now: datetime):
    state_id = select(RegionalGuildState.id).where(
        RegionalGuildState.campaign_id == campaign_id,
        RegionalGuildState.guild_id == guild_id,
    ).scalar_subquery()
    offer = RegionalOffer
    active = (
        (offer.status == "supply_preparing")
        & offer.reserved_by_guild_state_id.is_not(None)
        & (offer.supply_preparation_ends_at_utc > now)
        & (offer.supply_prepared_at_utc.is_(None))
    )
    ready = (
        (offer.status == "supply_preparing")
        & offer.reserved_by_guild_state_id.is_not(None)
        & (
            offer.supply_prepared_at_utc.is_not(None)
            | (offer.supply_preparation_ends_at_utc <= now)
        )
    )
    return select(
        literal("regional").label("menu"),
        func.coalesce(func.sum(case((active, 1), else_=0)), 0).label("active"),
        func.coalesce(func.sum(case((ready, 1), else_=0)), 0).label("ready"),
    ).where(
        offer.campaign_id == campaign_id,
        offer.reserved_by_guild_state_id == state_id,
    )


def _regional_event_row(campaign_id: str, guild_id: int, now: datetime, ready_portal_count: int):
    home_code = case(
        *[(CampaignMetadata.home_region == name, code) for code, name in REGIONS],
        else_=REGIONS[0][0],
    )
    player_state_id = select(RegionalGuildState.id).where(
        RegionalGuildState.campaign_id == CampaignMetadata.campaign_id,
        RegionalGuildState.guild_id == guild_id,
    ).scalar_subquery()
    ready_rebellions = select(func.count(RegionalEvent.id)).join(
        RegionalEventParticipant,
        RegionalEventParticipant.event_id == RegionalEvent.id,
    ).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc > now,
        RegionalEventParticipant.guild_state_id == player_state_id,
        RegionalEventParticipant.status.in_(("invited", "accepted", "participating")),
    ).scalar_subquery()
    dungeon_ready = select(DungeonRun.id).where(
        DungeonRun.id == RegionalEventActivity.source_run_id,
        DungeonRun.guild_id == guild_id,
        DungeonRun.status == "in_progress",
        DungeonRun.ends_at <= now,
    ).exists()
    mission_ready = select(MissionRun.id).where(
        MissionRun.id == RegionalEventActivity.source_run_id,
        MissionRun.guild_id == guild_id,
        MissionRun.status == "in_progress",
        MissionRun.ends_at <= now,
    ).exists()
    dungeon_active = select(DungeonRun.id).where(
        DungeonRun.id == RegionalEventActivity.source_run_id,
        DungeonRun.guild_id == guild_id,
        DungeonRun.status == "in_progress",
        DungeonRun.ends_at > now,
    ).exists()
    mission_active = select(MissionRun.id).where(
        MissionRun.id == RegionalEventActivity.source_run_id,
        MissionRun.guild_id == guild_id,
        MissionRun.status == "in_progress",
        MissionRun.ends_at > now,
    ).exists()
    ready_activities = select(func.count(func.distinct(RegionalEventActivity.event_id))).join(
        RegionalEvent,
        RegionalEvent.id == RegionalEventActivity.event_id,
    ).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEventActivity.guild_state_id == player_state_id,
        RegionalEventActivity.status == "in_progress",
        RegionalEvent.status.in_(("active", "in_progress")),
        or_(
            and_(RegionalEventActivity.source_type == "dungeon", dungeon_ready),
            and_(RegionalEventActivity.source_type == "mission", mission_ready),
        ),
    ).scalar_subquery()
    active_events = select(func.count(func.distinct(RegionalEventActivity.event_id))).join(
        RegionalEvent,
        RegionalEvent.id == RegionalEventActivity.event_id,
    ).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEventActivity.guild_state_id == player_state_id,
        RegionalEventActivity.status == "in_progress",
        RegionalEvent.status.in_(("active", "in_progress")),
        or_(
            and_(RegionalEventActivity.source_type == "dungeon", dungeon_active),
            and_(RegionalEventActivity.source_type == "mission", mission_active),
        ),
    ).scalar_subquery()
    ready = literal(ready_portal_count) + ready_rebellions + ready_activities
    return select(
        literal("regional_events").label("menu"),
        func.coalesce(active_events, 0).label("active"),
        func.coalesce(ready, 0).label("ready"),
    ).select_from(CampaignMetadata).where(
        CampaignMetadata.campaign_id == campaign_id,
    )


def _startable_portal_count(db: Session, campaign_id: str, guild_id: int, now: datetime) -> int:
    campaign = db.get(CampaignMetadata, campaign_id)
    guild = db.get(Guild, guild_id)
    if campaign is None or guild is None:
        return 0
    home_code = next((code for code, name in REGIONS if name == campaign.home_region), REGIONS[0][0])
    player_state_id = db.scalar(select(RegionalGuildState.id).where(
        RegionalGuildState.campaign_id == campaign_id,
        RegionalGuildState.guild_id == guild_id,
    ))
    if player_state_id is None:
        return 0

    from app.services.dungeon_service import has_startable_dungeon_party

    unentered = ~select(RegionalEventParticipant.id).where(
        RegionalEventParticipant.event_id == RegionalEvent.id,
        RegionalEventParticipant.guild_state_id == player_state_id,
    ).exists()
    portals = db.scalars(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEvent.region_code == home_code,
        RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc > now,
        RegionalEvent.dungeon_template_id.is_not(None),
        unentered,
    ).order_by(RegionalEvent.id))

    ready = 0
    for portal in portals:
        template_record = db.get(DungeonTemplate, portal.dungeon_template_id)
        if template_record is None:
            continue
        try:
            summary = json.loads(portal.summary_json or "{}")
        except (TypeError, json.JSONDecodeError):
            summary = {}
        boss = summary.get("portal_boss") if isinstance(summary, dict) else None
        snapshot = boss.get("template") if isinstance(boss, dict) else None
        template = (
            SimpleNamespace(**snapshot)
            if isinstance(snapshot, dict) and int(snapshot.get("id", -1)) == portal.dungeon_template_id
            else template_record
        )
        if has_startable_dungeon_party(db, guild, template):
            ready += 1
    return ready


def _accessible_status(menu: str, active_count: int, ready_count: int) -> str:
    name = MENU_LABELS[menu]
    parts: list[str] = []
    if ready_count:
        singular, plural = READY_LABELS[menu]
        parts.append(f"{ready_count} {singular if ready_count == 1 else plural}")
    if active_count:
        parts.append(f"{active_count} em andamento")
    return f"{name}: " + "; ".join(parts)


def _get_navigation_work_status(
    db: Session,
    guild_id: int,
    *,
    campaign_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, int | str]]:
    """Aggregate persisted tasks without progressing any game state."""
    timestamp = now or datetime.now(timezone.utc)
    rows = [
        _count_row("missions", MissionRun, guild_id, timestamp),
        _count_row("dungeons", DungeonRun, guild_id, timestamp),
        _count_row("gathering", GatheringAssignment, guild_id, timestamp, ready_action=False),
        _count_row("workshops", SupplyWorkshopJob, guild_id, timestamp),
        _count_row("blacksmith", GuildSalvageJob, guild_id, timestamp),
        _count_row("market", MarketSale, guild_id, timestamp),
        _count_row("class_change", ClassChangeRun, guild_id, timestamp),
        _count_row("professions", ProfessionTraining, guild_id, timestamp),
    ]
    if campaign_id:
        rows.append(_regional_preparation_row(campaign_id, guild_id, timestamp))
        rows.append(_regional_event_row(
            campaign_id, guild_id, timestamp,
            _startable_portal_count(db, campaign_id, guild_id, timestamp),
        ))

    work = union_all(*rows).subquery()
    result: dict[str, dict[str, int | str]] = {}
    for menu, active_value, ready_value in db.execute(select(work.c.menu, work.c.active, work.c.ready)):
        active_count, ready_count = int(active_value or 0), int(ready_value or 0)
        result[menu] = {
            "active": active_count,
            "ready": ready_count,
            "state": "ready" if ready_count else "active" if active_count else "none",
            "label": _accessible_status(menu, active_count, ready_count),
        }
    if campaign_id and "regional_events" in result:
        result["regional_events"]["review_token"] = regional_events_review_token(
            db, campaign_id, guild_id, now=timestamp,
        )
    return result


def get_navigation_work_status(
    db: Session,
    guild_id: int,
    *,
    campaign_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, int | str]]:
    """Read navigation status without flushing or progressing pending game state."""
    with db.no_autoflush:
        return _get_navigation_work_status(
            db, guild_id, campaign_id=campaign_id, now=now,
        )
