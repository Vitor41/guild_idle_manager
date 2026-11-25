"""Read-only activity summaries for the shared navigation."""
from datetime import datetime, timezone

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
from app.models.mercenary import Mercenary
from app.models.regional import (
    RegionalEvent,
    RegionalEventActivity,
    RegionalEventParticipant,
    RegionalGuildState,
    RegionalOffer,
)
from app.services.regional_cycle_service import REGIONS
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


def _regional_event_row(campaign_id: str, guild_id: int, now: datetime):
    home_code = case(
        *[(CampaignMetadata.home_region == name, code) for code, name in REGIONS],
        else_=REGIONS[0][0],
    )
    player_state_id = select(RegionalGuildState.id).where(
        RegionalGuildState.campaign_id == CampaignMetadata.campaign_id,
        RegionalGuildState.guild_id == guild_id,
    ).scalar_subquery()
    available_count = select(func.count(Mercenary.id)).where(
        Mercenary.guild_id == guild_id,
        Mercenary.status == "available",
    ).scalar_subquery()
    guild_level = select(Guild.level).where(Guild.id == guild_id).scalar_subquery()
    eligible_portal_template = select(DungeonTemplate.id).where(
        DungeonTemplate.id == RegionalEvent.dungeon_template_id,
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.min_party_size <= available_count,
        DungeonTemplate.max_party_size >= DungeonTemplate.min_party_size,
        DungeonTemplate.required_guild_level <= guild_level,
    ).exists()
    ready_portals = select(func.count(RegionalEvent.id)).where(
        RegionalEvent.campaign_id == campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEvent.region_code == home_code,
        RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc > now,
        RegionalEvent.dungeon_template_id.is_not(None),
        eligible_portal_template,
        ~select(RegionalEventParticipant.id).where(
            RegionalEventParticipant.event_id == RegionalEvent.id,
            RegionalEventParticipant.guild_state_id == player_state_id,
        ).exists(),
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
    ready = ready_portals + ready_rebellions + ready_activities
    return select(
        literal("regional_events").label("menu"),
        func.coalesce(active_events, 0).label("active"),
        func.coalesce(ready, 0).label("ready"),
    ).select_from(CampaignMetadata).where(
        CampaignMetadata.campaign_id == campaign_id,
    )


def _accessible_status(menu: str, active_count: int, ready_count: int) -> str:
    name = MENU_LABELS[menu]
    parts: list[str] = []
    if ready_count:
        singular, plural = READY_LABELS[menu]
        parts.append(f"{ready_count} {singular if ready_count == 1 else plural}")
    if active_count:
        parts.append(f"{active_count} em andamento")
    return f"{name}: " + "; ".join(parts)


def get_navigation_work_status(
    db: Session,
    guild_id: int,
    *,
    campaign_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, int | str]]:
    """Aggregate persisted tasks in one SELECT without progressing any game state."""
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
        rows.append(_regional_event_row(campaign_id, guild_id, timestamp))

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
    return result
