from pathlib import Path
import json
from datetime import datetime, timedelta, timezone
from math import floor
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.dependencies import DbSession, get_current_campaign, get_current_player
from app.core.forms import read_form_multi_fields
from app.desktop.gameplay_diagnostics import log_gathering_advancement
from app.models.campaign import CampaignMetadata
from app.models.guild import GuildResources
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.item import ItemTemplate
from app.models.mission import MissionRun, MissionTemplate
from app.models.mercenary import Mercenary
from app.models.regional import (
    RegionalCpuCyclePlan, RegionalCpuMercenary, RegionalCpuResource, RegionalEvent, RegionalEventActivity,
    RegionalEventParticipant,
    RegionalGuildState, RegionalOffer, RegionalRegionState, RegionalRunOutcome,
)
from app.models.regional import RegionalCycle
from app.models.user import User
from app.services.dungeon_service import DungeonError, start_dungeon
from app.services.gathering_service import advance_all_assignments, list_assignments, FAMILY_LABELS, NODE_LABELS
from app.services.achievement_service import get_codex_context
from app.services.guild_service import get_current_guild_context
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.mission_service import MissionError, start_mission
from app.services.navigation_work_status_service import regional_events_review_token
from app.services.regional_cycle_service import (
    PUBLIC_REGIONAL_OFFER_TYPES,
    get_current_player_regional_guild,
    get_regional_board,
)
from app.services.regional_event_service import (
    attach_event_activity,
    event_history_summary,
    event_region_name,
    record_rebellion_decision,
    expire_due_events,
    build_portal_boss_snapshot,
    portal_spawn_status_for_region,
)
from app.services.evolution_art_service import get_evolution_art_context
from app.services.supply_preparation_service import estimate_drop_sale_value, guild_gold, quote_supply, regional_kit_quote
from app.services.display_service import clean_generated_name, rarity_label
from app.services.drop_preview_service import build_drop_preview
from app.services.icon_service import get_item_icon_path
from app.repositories.item_repository import list_active_drops_for_mission
from app.repositories.dungeon_repository import list_active_drops_for_dungeon


router = APIRouter(prefix="/regional")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _regional_home_code(campaign: CampaignMetadata) -> str:
    from app.services.regional_cycle_service import REGIONS

    return next((code for code, name in REGIONS if name == campaign.home_region), REGIONS[0][0])


def _portal_action_blocker(db, campaign, event, player_state, now: datetime) -> str | None:
    if event is None or event.campaign_id != campaign.campaign_id or event.event_type != "portal":
        return "Portal indisponível."
    if event.region_code != _regional_home_code(campaign):
        return "Portais só aceitam entrada na região natal. Rebeliões oferecem atividades próprias em outras regiões."
    expires_at = event.expires_at_utc
    expires_at = expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at.astimezone(timezone.utc)
    if event.status != "active" or expires_at <= now:
        return "O prazo deste portal terminou; novas entradas não são aceitas."
    if player_state is None:
        return "Estado regional da guilda indisponível."
    if db.scalar(select(RegionalEventParticipant.id).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == player_state.id,
    )) is not None:
        return "Esta guilda já usou a entrada deste portal."
    if event.dungeon_template_id is None or db.get(DungeonTemplate, event.dungeon_template_id) is None:
        return "O conteúdo do chefe do portal está indisponível."
    return None


def _regional_offer_rebellion_access(db, campaign, guild_id: int, offer: RegionalOffer, now: datetime):
    """Return (event, reason); home offers need no rebellion, external offers do."""
    from app.services.regional_cycle_service import get_current_player_regional_guild

    if offer.offer_type not in PUBLIC_REGIONAL_OFFER_TYPES:
        return None, "Oferta indisponível."
    is_home_offer = offer.region_code == _regional_home_code(campaign)
    current = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    expire_due_events(db, campaign.campaign_id, current)
    event = db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.region_code == offer.region_code,
        RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc > current,
    ).order_by(RegionalEvent.created_at_utc.desc(), RegionalEvent.id.desc()).limit(1))
    if event is None:
        if is_home_offer:
            return None, None
        in_progress = db.scalar(select(RegionalEvent.id).where(
            RegionalEvent.campaign_id == campaign.campaign_id,
            RegionalEvent.event_type == "rebellion",
            RegionalEvent.region_code == offer.region_code,
            RegionalEvent.status == "in_progress",
        ).order_by(RegionalEvent.created_at_utc.desc()).limit(1))
        if in_progress is not None:
            return None, "O prazo da rebelião terminou; novas atividades não podem começar."
        return None, "Atividade fora da região natal indisponível sem uma rebelião ativa."
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild_id)
    if player_state is None:
        return None, "Estado regional da guilda indisponível."
    participant = db.scalar(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == player_state.id,
    ))
    if participant is not None and participant.status in {"accepted", "participating"}:
        return event, None
    if is_home_offer:
        return None, None
    if participant is not None and participant.status == "declined":
        return None, "O convite foi delegado à CPU; esta guilda não pode iniciar atividades na região."
    return None, "Aceite o convite da rebelião antes de iniciar atividades nesta região."


def _regional_comparison_data(db, campaign, guild, region_code: str):
    from app.services.regional_cycle_service import REGIONS
    region_name = dict(REGIONS).get(region_code)
    if region_name is None:
        return None
    get_regional_board(db, campaign, guild)
    states = list(db.scalars(select(RegionalGuildState).where(
        RegionalGuildState.campaign_id == campaign.campaign_id,
        RegionalGuildState.region_code == region_code,
        RegionalGuildState.active.is_(True),
    ).order_by(RegionalGuildState.influence.desc(), RegionalGuildState.reputation.desc(), RegionalGuildState.name)))
    regions = list(db.scalars(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign.campaign_id,
    ).order_by(RegionalRegionState.region_name)))
    selected = next((row for row in regions if row.region_code == region_code), None)
    state_ids = [row.id for row in states]
    members = list(db.scalars(select(RegionalCpuMercenary).where(
        RegionalCpuMercenary.guild_state_id.in_(state_ids), RegionalCpuMercenary.active.is_(True),
    ))) if state_ids else []
    resources = list(db.scalars(select(RegionalCpuResource).where(
        RegionalCpuResource.guild_state_id.in_(state_ids),
    ))) if state_ids else []
    outcomes = list(db.execute(select(RegionalRunOutcome, RegionalOffer).join(
        RegionalOffer, RegionalOffer.id == RegionalRunOutcome.offer_id,
    ).where(
        RegionalRunOutcome.guild_state_id.in_(state_ids),
        RegionalRunOutcome.campaign_id == campaign.campaign_id,
        RegionalOffer.campaign_id == campaign.campaign_id,
        RegionalOffer.region_code == region_code,
        RegionalOffer.offer_type.in_(("contract", "dungeon", "boss")),
    ))) if state_ids else []
    rosters: dict[int, list] = {}
    wealth: dict[int, int] = {}
    results: dict[int, dict[str, int]] = {}
    for member in members:
        rosters.setdefault(member.guild_state_id, []).append(member)
    for resource in resources:
        if resource.resource_code in {"gold", "gold_coins"}:
            wealth[resource.guild_state_id] = resource.amount

    def result_counts(state_id: int):
        return results.setdefault(state_id, {"contracts": 0, "dungeons": 0, "bosses": 0, "successes": 0, "failures": 0})

    for outcome, offer in outcomes:
        key = {"contract": "contracts", "dungeon": "dungeons", "boss": "bosses"}.get(offer.offer_type)
        if key:
            counts = result_counts(outcome.guild_state_id)
            counts[key] += 1
            counts["successes" if outcome.success else "failures"] += 1

    cpu_plans = list(db.execute(select(RegionalCpuCyclePlan, RegionalGuildState).join(
        RegionalGuildState, RegionalGuildState.id == RegionalCpuCyclePlan.guild_state_id,
    ).where(
        RegionalCpuCyclePlan.campaign_id == campaign.campaign_id,
        RegionalCpuCyclePlan.guild_state_id.in_(state_ids),
        RegionalGuildState.campaign_id == campaign.campaign_id,
        RegionalGuildState.region_code == region_code,
        RegionalGuildState.guild_id.is_(None),
    ))) if state_ids else []
    for plan, state in cpu_plans:
        try:
            plan_outcomes = json.loads(plan.outcomes_json or "[]")
        except (TypeError, ValueError):
            plan_outcomes = []
        known = 0
        if isinstance(plan_outcomes, list):
            for item in plan_outcomes:
                if not isinstance(item, dict) or not isinstance(item.get("offer_id"), int):
                    continue
                offer = db.get(RegionalOffer, item["offer_id"])
                if (offer is None or offer.campaign_id != campaign.campaign_id or offer.region_code != region_code
                        or offer.offer_type not in {"contract", "dungeon", "boss"}):
                    continue
                counts = result_counts(state.id)
                counts[{"contract": "contracts", "dungeon": "dungeons", "boss": "bosses"}[offer.offer_type]] += 1
                counts["successes" if bool(item.get("success")) else "failures"] += 1
                known += 1
        if not known and not plan_outcomes:
            counts = result_counts(state.id)
            counts["successes"] += max(0, int(plan.successes or 0))
            counts["failures"] += max(0, int(plan.failures or 0))

    rows = []
    for state in states:
        roster = rosters.get(state.id, [])
        tiers: dict[str, int] = {}
        for member in roster:
            tiers[member.rarity] = tiers.get(member.rarity, 0) + 1
        current_wealth = wealth.get(state.id, 0)
        if state.guild_id == guild.id:
            roster = list(db.scalars(select(Mercenary).where(
                Mercenary.guild_id == guild.id, Mercenary.status != "dismissed",
            )))
            tiers = {}
            for member in roster:
                tiers[member.rarity] = tiers.get(member.rarity, 0) + 1
            resources_now = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild.id))
            current_wealth = resources_now.gold if resources_now else current_wealth
        rows.append({
            "state": state, "wealth": current_wealth, "roster": len(roster) or state.roster_size,
            "tier_counts": tiers,
            "results": results.get(state.id, {"contracts": 0, "dungeons": 0, "bosses": 0, "successes": 0, "failures": 0}),
        })
    return region_name, regions, selected, rows


@router.get("/regions/{region_code}")
def regional_region_detail(
    region_code: str,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return RedirectResponse("/login", status_code=303)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    from app.services.regional_cycle_service import REGIONS
    data = _regional_comparison_data(db, campaign, guild, region_code)
    if data is None:
        return RedirectResponse("/regional", status_code=303)
    region_name, region_snapshots, selected_region, rows = data
    return templates.TemplateResponse(request=request, name="regional/detail.html", context={
        "current_user": current_user, "guild": guild, "resources": _resources, "region_name": region_name,
        "region_code": region_code, "guild_rows": rows, "regions": region_snapshots,
        "selected_region": selected_region,
        "home_region_code": next((code for code, name in REGIONS if name == campaign.home_region), ""),
    })


@router.get("/regions/{region_code}/comparison")
def regional_region_comparison(
    region_code: str, request: Request, db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return JSONResponse({"detail": "Campanha indisponível."}, status_code=401)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return JSONResponse({"detail": "Guilda indisponível."}, status_code=404)
    data = _regional_comparison_data(db, campaign, guild, region_code)
    if data is None:
        return JSONResponse({"detail": "Região indisponível."}, status_code=404)
    _region_name, _regions, _selected, rows = data
    return JSONResponse({"guilds": {
        str(row["state"].id): {
            "wealth": row["wealth"], "roster": row["roster"], "tier_counts": row["tier_counts"],
            "results": row["results"], "event_wins": row["state"].event_wins,
        } for row in rows
    }})


def _datetime_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.isoformat()


templates.env.globals["utc_iso"] = _datetime_iso


def _annotate_supply_preparation(offer: RegionalOffer, now: datetime) -> None:
    started = offer.supply_preparation_started_at_utc
    ends = offer.supply_preparation_ends_at_utc
    offer.supply_preparation_ends_at_iso = _datetime_iso(ends)
    if started is None or ends is None:
        offer.supply_preparation_progress_percent = 0
        return
    started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started.astimezone(timezone.utc)
    ends = ends.replace(tzinfo=timezone.utc) if ends.tzinfo is None else ends.astimezone(timezone.utc)
    duration = max(1.0, (ends - started).total_seconds())
    elapsed = max(0.0, (now - started).total_seconds())
    offer.supply_preparation_progress_percent = max(0, min(100, int(elapsed * 100 / duration)))
    if now >= ends and offer.supply_prepared_at_utc is None:
        offer.supply_prepared_at_utc = ends


def _annotate_prepared_team(db, guild_id: int, offer: RegionalOffer) -> None:
    offer.prepared_mercenary_ids = []
    offer.unavailable_prepared_mercenaries = []
    offer.prepared_team_valid = True
    offer.prepared_team_available = True
    offer.prepared_team_can_start = True
    offer.prepared_team_issue = ""
    if offer.supply_preparation_started_at_utc is None:
        return

    try:
        snapshot = json.loads(offer.supply_preparation_snapshot_json or "{}")
    except (TypeError, json.JSONDecodeError):
        snapshot = None
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema") != 1
        or snapshot.get("supply") != "regional_group_supply"
        or snapshot.get("prepared_for_offer_id") != offer.id
        or not isinstance(snapshot.get("mercenary_ids"), list)
        or not snapshot["mercenary_ids"]
    ):
        offer.prepared_team_valid = False
        offer.prepared_team_available = False
        offer.prepared_team_can_start = False
        offer.prepared_team_issue = "Não foi possível confirmar a equipe do preparo. Atualize a Vigília antes de iniciar."
        return

    try:
        ids = [str(int(value)) for value in snapshot["mercenary_ids"]]
    except (TypeError, ValueError, OverflowError):
        ids = []
    if not ids or any(int(value) < 1 for value in ids) or len(ids) != len(set(ids)):
        offer.prepared_team_valid = False
        offer.prepared_team_available = False
        offer.prepared_team_can_start = False
        offer.prepared_team_issue = "Não foi possível confirmar a equipe do preparo. Atualize a Vigília antes de iniciar."
        return

    offer.prepared_mercenary_ids = sorted(ids, key=int)
    mercenaries = list(db.scalars(select(Mercenary).where(
        Mercenary.guild_id == guild_id,
        Mercenary.id.in_([int(value) for value in offer.prepared_mercenary_ids]),
    )))
    mercenaries_by_id = {str(mercenary.id): mercenary for mercenary in mercenaries}
    offer.unavailable_prepared_mercenaries = [
        {
            "id": mercenary_id,
            "name": getattr(mercenaries_by_id.get(mercenary_id), "name", "Integrante preparado"),
        }
        for mercenary_id in offer.prepared_mercenary_ids
        if (
            mercenary_id not in mercenaries_by_id
            or mercenaries_by_id[mercenary_id].status != "available"
        )
    ]
    offer.prepared_team_available = not offer.unavailable_prepared_mercenaries
    if offer.supply_preparation_ends_at_utc is None:
        offer.prepared_team_issue = "O prazo do preparo está indisponível. Atualize a Vigília antes de iniciar."
    elif offer.unavailable_prepared_mercenaries:
        offer.prepared_team_issue = "Libere os integrantes preparados indisponíveis antes de iniciar."
    offer.prepared_team_can_start = offer.prepared_team_available and not offer.prepared_team_issue


def _annotate_offer_drop_preview(db, offer: RegionalOffer) -> None:
    if offer.offer_type == "contract":
        template = db.get(MissionTemplate, offer.mission_template_id) if offer.mission_template_id else None
        active_entries = getattr(template, "item_drops", None) if template is not None else None
    else:
        template = db.get(DungeonTemplate, offer.dungeon_template_id) if offer.dungeon_template_id else None
        active_entries = getattr(template, "item_drops", None) if template is not None else None
    preview = build_drop_preview(active_entries)
    offer.drop_preview_available = preview["available"]
    offer.visible_drops = preview["drops"]
    offer.drop_chance_basis = preview["chance_basis"]


def _portal_drop_preview(db, summary: dict[str, object]) -> dict[str, object]:
    table = summary.get("portal_loot")
    if (
        not isinstance(table, dict)
        or table.get("roll_model") != "one_100_point_roll;exclusive_rarity_bands;no_guaranteed_equipment"
        or not isinstance(table.get("entries"), list)
        or not table["entries"]
    ):
        return {"drop_preview_available": False, "visible_drops": [], "drop_chance_basis": None}
    drops = []
    try:
        for entry in table["entries"]:
            if not isinstance(entry, dict):
                return {"drop_preview_available": False, "visible_drops": [], "drop_chance_basis": None}
            item_id = int(entry.get("item_template_id", 0))
            chance = int(entry.get("chance_percent", -1))
            quantity = int(entry.get("quantity", 0))
            item_data = entry.get("item_snapshot")
            if isinstance(item_data, dict) and int(item_data.get("id", -1)) == item_id:
                item = SimpleNamespace(**item_data)
            else:
                item = db.get(ItemTemplate, item_id)
            if (
                item is None or getattr(item, "item_type", None) != "equipment"
                or not getattr(item, "name", None) or not getattr(item, "rarity", None)
                or not 0 <= chance <= 100 or quantity < 1
            ):
                return {"drop_preview_available": False, "visible_drops": [], "drop_chance_basis": None}
            drops.append({
                "display_name": clean_generated_name(item.name),
                "rarity_class": str(item.rarity).lower(),
                "rarity_label": rarity_label(item.rarity),
                "icon_path": get_item_icon_path(item),
                "chance_percent": chance,
                "chance_label": "após sucesso",
                "min_quantity": quantity,
                "max_quantity": quantity,
                "quantity_unit": "instância(s)",
            })
    except (AttributeError, TypeError, ValueError):
        return {"drop_preview_available": False, "visible_drops": [], "drop_chance_basis": None}
    return {
        "drop_preview_available": True,
        "visible_drops": drops,
        "drop_chance_basis": "conditional",
    }


def _validated_regional_return_to(
    form: dict[str, list[str]],
    *,
    fallback: str = "/regional",
    fallback_anchor: str = "",
) -> str:
    raw = str((form.get("return_to") or [""])[0]).strip()
    if raw:
        parsed = urlsplit(raw)
        if not parsed.scheme and not parsed.netloc and parsed.path in {"/regional", "/regional/events"}:
            query = parse_qs(parsed.query, keep_blank_values=True)
            section_values = query.get("section", [])
            valid_query = set(query).issubset({"section"}) and len(section_values) <= 1
            valid_section = not section_values or section_values[0] in {"portals", "rebellions", "history"}
            valid_path_query = parsed.path == "/regional/events" or not section_values
            fragment = parsed.fragment
            valid_fragment = (
                not fragment
                or fragment in {"regional-board", "portals", "rebellions", "history"}
                or re.fullmatch(r"regional-event-\d+", fragment) is not None
            )
            if valid_query and valid_section and valid_path_query and valid_fragment:
                path = parsed.path
                if section_values:
                    path += "?" + urlencode({"section": section_values[0]})
                if fragment:
                    path += "#" + fragment
                return path
    target = fallback
    if fallback_anchor and re.fullmatch(r"#(?:regional-event-\d+|regional-board|portals|rebellions|history)", fallback_anchor):
        target += fallback_anchor
    return target


def _regional_redirect(
    form: dict[str, list[str]],
    *,
    fallback: str = "/regional",
    fallback_anchor: str = "",
    message: str | None = None,
    error: str | None = None,
    extra_query: list[tuple[str, str]] | None = None,
) -> RedirectResponse:
    target = _validated_regional_return_to(
        form, fallback=fallback, fallback_anchor=fallback_anchor,
    )
    path, fragment_sep, fragment = target.partition("#")
    base = urlsplit(path)
    query_items = [
        (key, value)
        for key, values in parse_qs(base.query, keep_blank_values=True).items()
        for value in values
    ]
    if message is not None:
        query_items.append(("message", message))
    if error is not None:
        query_items.append(("error", error))
    query_items.extend(extra_query or [])
    location = base.path
    if query_items:
        location += "?" + urlencode(query_items, doseq=True)
    if fragment_sep:
        location += "#" + fragment
    return RedirectResponse(location, status_code=303)


def _start_error_redirect(error: object, form: dict[str, list[str]], anchor: str = "") -> RedirectResponse:
    query: list[tuple[str, str]] = [
        ("selected_mercenary_id", value) for value in form.get("mercenary_ids", [])
    ]
    if (form.get("supply") or [""])[0] == "1":
        query.append(("selected_supply", "1"))
    return _regional_redirect(
        form, error=str(error), fallback_anchor=anchor, extra_query=query,
    )


def _quote_offer_supply(db, guild, offer: RegionalOffer, mercenary_ids: list[str]) -> dict[str, object]:
    from app.repositories.mercenary_repository import list_available_mercenaries_by_ids
    from app.services.building_service import get_building_level
    from app.services.equipment_service import get_party_chance_details
    from app.services.mission_service import mission_office_values, parse_mercenary_ids, validate_mission_requirements
    from app.services.skill_service import get_party_skill_effects

    try:
        ids = parse_mercenary_ids(mercenary_ids)
    except ValueError as error:
        return {"available": False, "reason": str(error)}
    members = list_available_mercenaries_by_ids(db, guild.id, ids)
    if not ids or len(members) != len(ids):
        return {"available": False, "reason": "Escolha um grupo de mercenários disponíveis."}
    skills = get_party_skill_effects(db, members)
    if offer.offer_type == "contract":
        template = db.get(MissionTemplate, offer.mission_template_id)
        if template is None:
            return {"available": False, "reason": "Contrato indisponível."}
        if template.mission_type in {"gathering", "long_idle"}:
            return {"available": False, "reason": "Suprimento indisponível nesta atividade."}
        try:
            validate_mission_requirements(db, guild, template, required_guild_level=offer.required_guild_level_snapshot)
        except ValueError as error:
            return {"available": False, "reason": str(error)}
        if not offer.min_party_size_snapshot <= len(members) <= offer.max_party_size_snapshot:
            return {"available": False, "reason": "O grupo não atende ao tamanho exigido pelo contrato."}
        details = get_party_chance_details(db, guild.id, offer.success_chance_snapshot, members,
                                           offer.recommended_power_snapshot, offer.recommended_level_snapshot)
        base_final = max(5, min(95, details["final_chance"] + skills.get("success_chance", 0)))
        office = mission_office_values(get_building_level(db, guild.id, "contract_office"))
        success_gold = floor(offer.gold_reward_snapshot * (100 + skills.get("gold_reward", 0) + office["reward_bonus_percent"]) / 100)
        drops = list_active_drops_for_mission(db, template.id)
    else:
        from app.services.dungeon_service import (
            get_group_synergy_bonus, get_group_synergy_power_bonus, scouts_values, validate_advanced_party_requirements,
            validate_dungeon_requirements,
        )
        from app.models.dungeon import DungeonTemplate

        template = db.get(DungeonTemplate, offer.dungeon_template_id)
        if template is None:
            return {"available": False, "reason": "Masmorra indisponível."}
        try:
            validate_dungeon_requirements(db, guild, template, required_guild_level=offer.required_guild_level_snapshot)
            validate_advanced_party_requirements(db, guild, template, members)
        except ValueError as error:
            return {"available": False, "reason": str(error)}
        if not offer.min_party_size_snapshot <= len(members) <= offer.max_party_size_snapshot:
            return {"available": False, "reason": "O grupo não atende ao tamanho exigido pela masmorra."}
        details = get_party_chance_details(db, guild.id, offer.success_chance_snapshot, members,
                                           offer.recommended_power_snapshot, offer.recommended_level_snapshot,
                                           power_bonus=get_group_synergy_power_bonus(members, template))
        base_final = max(5, min(95, details["final_chance"] + skills.get("success_chance", 0)
                                + skills.get("dungeon_power", 0) // 10 + get_group_synergy_bonus(members, template)))
        base_final = min(95, base_final + scouts_values(get_building_level(db, guild.id, "scouts"))["success_bonus_percentage_points"])
        success_gold = floor(offer.gold_reward_snapshot * (100 + skills.get("gold_reward", 0)) / 100)
        drops = list_active_drops_for_dungeon(db, template.id)
    quote = regional_kit_quote(db, guild.id, offer.rank, base_final)
    return {**quote, "base_final_chance": base_final,
            "final_chance": min(95, base_final + int(quote.get("chance_bonus_pp", 0)))}


def _initial_offer_supply_quote(db, guild, offer: RegionalOffer, available_gold: int) -> dict[str, object]:
    if offer.mission_template_id:
        template = db.get(MissionTemplate, offer.mission_template_id)
        if template is None or template.mission_type in {"gathering", "long_idle"}:
            return {"available": False, "reason": "Suprimento indisponível nesta atividade.", "chance_bonus_pp": 0}
        drops = list_active_drops_for_mission(db, template.id)
    else:
        drops = list_active_drops_for_dungeon(db, offer.dungeon_template_id)
    return regional_kit_quote(db, guild.id, offer.rank, offer.success_chance_snapshot)


@router.post("/offers/{offer_id}/supply-quote")
async def regional_supply_quote(
    offer_id: int, request: Request, db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return JSONResponse({"available": False, "reason": "Campanha indisponível."}, status_code=401)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return JSONResponse({"available": False, "reason": "Guilda indisponível."}, status_code=404)
    offer = db.scalar(select(RegionalOffer).where(
        RegionalOffer.id == offer_id,
        RegionalOffer.campaign_id == campaign.campaign_id,
        RegionalOffer.offer_type.in_(PUBLIC_REGIONAL_OFFER_TYPES),
        RegionalOffer.status.in_(("available", "supply_preparing")),
    ))
    if offer is None:
        return JSONResponse({"available": False, "reason": "Oferta indisponível."}, status_code=409)
    _event, access_error = _regional_offer_rebellion_access(
        db, campaign, guild.id, offer, datetime.now(timezone.utc),
    )
    if access_error:
        return JSONResponse({"available": False, "reason": access_error}, status_code=409)
    form = await read_form_multi_fields(request)
    return JSONResponse(_quote_offer_supply(db, guild, offer, form.get("mercenary_ids", [])))


@router.get("/events")
@router.get("")
def regional_index(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    central_events_view = request.url.path == "/regional/events"
    board = get_regional_board(db, campaign, guild)
    region_now = datetime.now(timezone.utc)
    if not central_events_view:
        for offer_list in board.get("offers", {}).values():
            for offer in offer_list:
                _annotate_supply_preparation(offer, region_now)
                _annotate_prepared_team(db, guild.id, offer)
                _annotate_offer_drop_preview(db, offer)
                try:
                    saved_quote = json.loads(offer.supply_preparation_snapshot_json or "{}")
                except (TypeError, json.JSONDecodeError):
                    saved_quote = {}
                offer.supply_quote = saved_quote or _initial_offer_supply_quote(db, guild, offer, resources.gold if resources else 0)
        advancement = advance_all_assignments(db, guild)
        log_gathering_advancement(
            route=request.url.path,
            diagnostic_id=getattr(request.state, "diagnostic_id", ""),
            advancement=advancement,
        )
        db.commit()
        assignments = list_assignments(db, guild.id)
        for assignment in assignments:
            assignment.catalog_unavailable = bool(
                advancement.get(assignment.resource_family, {}).get("catalog_missing")
            )
        achievement_context = get_codex_context(db, guild, True)
    else:
        assignments = []
        achievement_context = {"achievement_cards": []}
    reports = []
    for history_row in ([] if central_events_view else board["latest_history"]):
        cycle = db.get(RegionalCycle, history_row.cycle_id)
        cpu_plans = list(db.execute(select(RegionalCpuCyclePlan, RegionalGuildState).join(
            RegionalGuildState, RegionalGuildState.id == RegionalCpuCyclePlan.guild_state_id,
        ).where(RegionalCpuCyclePlan.cycle_id == history_row.cycle_id).order_by(RegionalGuildState.slot)))
        reports.append({
            "row": history_row,
            "cycle_number": cycle.cycle_number if cycle else history_row.cycle_id,
            "summary": json.loads(history_row.summary_json or "{}"),
            "cpu_activity_rows": [{"guild": state.name, "planned": plan.planned_actions,
                                   "eligible": plan.eligible_actions, "started": plan.started_actions,
                                   "resolved": plan.resolved_actions}
                                  for plan, state in cpu_plans],
            "has_unmeasured_cpu_activity": any(
                plan.planned_actions is None or plan.eligible_actions is None
                or plan.started_actions is None or plan.resolved_actions is None
                for plan, _state in cpu_plans
            ),
        })
    rebellion = board.get("rebellion_event")
    rebellion_priority_elapsed = False
    if rebellion is not None and rebellion.priority_ends_at_utc is not None:
        priority_deadline = rebellion.priority_ends_at_utc
        priority_deadline = (
            priority_deadline.replace(tzinfo=timezone.utc)
            if priority_deadline.tzinfo is None
            else priority_deadline.astimezone(timezone.utc)
        )
        rebellion_priority_elapsed = priority_deadline <= region_now
    rebellion_participant = None
    rebellion_invite_expired = False
    rebellion_offers = []
    rebellion_region_name = None
    portal_cards = []
    event_history_cards = []
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    home_code = _regional_home_code(campaign)
    portal_spawn_status = portal_spawn_status_for_region(
        db, campaign, board.get("cycle"), home_code, region_now,
    ) if central_events_view else None
    portal_events = list(board.get("portal_events", []))
    if central_events_view:
        portal_events = list(db.scalars(select(RegionalEvent).where(
            RegionalEvent.campaign_id == campaign.campaign_id,
            RegionalEvent.event_type == "portal",
            RegionalEvent.status.in_(("active", "in_progress")),
        ).order_by(RegionalEvent.expires_at_utc, RegionalEvent.id)))
    for event in portal_events:
        try:
            event_summary = json.loads(event.summary_json or "{}")
        except (TypeError, json.JSONDecodeError):
            event_summary = {}
        boss_record = event_summary.get("portal_boss") if isinstance(event_summary, dict) else None
        boss_snapshot = boss_record.get("template") if isinstance(boss_record, dict) else None
        template = (
            SimpleNamespace(**boss_snapshot)
            if isinstance(boss_snapshot, dict)
            else (db.get(DungeonTemplate, event.dungeon_template_id) if event.dungeon_template_id else None)
        )
        participant = db.scalar(select(RegionalEventParticipant).where(
            RegionalEventParticipant.event_id == event.id,
            RegionalEventParticipant.guild_state_id == player_state.id,
        )) if player_state is not None else None
        own_activity = db.scalar(select(RegionalEventActivity).where(
            RegionalEventActivity.event_id == event.id,
            RegionalEventActivity.guild_state_id == player_state.id,
            RegionalEventActivity.source_type == "dungeon",
        ).order_by(RegionalEventActivity.id.desc()).limit(1)) if player_state is not None else None
        own_run = (
            db.get(DungeonRun, own_activity.source_run_id)
            if own_activity is not None else None
        )
        run_due_at = own_run.ends_at if own_run is not None else None
        if run_due_at is not None:
            run_due_at = (
                run_due_at.replace(tzinfo=timezone.utc)
                if run_due_at.tzinfo is None else run_due_at.astimezone(timezone.utc)
            )
        activity_due = bool(
            own_activity is not None and own_activity.status == "in_progress"
            and own_run is not None and own_run.status == "in_progress"
            and run_due_at <= region_now
        )
        activity_collected = bool(
            own_activity is not None and own_activity.status == "resolved"
            and own_run is not None and own_run.status in {"completed", "failed"}
        )
        blocker = _portal_action_blocker(db, campaign, event, player_state, region_now)
        portal_deadline = event.expires_at_utc
        portal_deadline = (
            portal_deadline.replace(tzinfo=timezone.utc)
            if portal_deadline.tzinfo is None
            else portal_deadline.astimezone(timezone.utc)
        )
        entry_state = (
            "used" if participant is not None else
            "unavailable" if event.region_code != home_code else
            "unavailable_content" if template is None else
            "expired" if portal_deadline <= region_now else
            "unavailable" if blocker else
            "available"
        )
        entry_state_labels = {
            "used": "Entrada já utilizada",
            "unavailable_content": "Conteúdo indisponível",
            "expired": "Prazo de entrada encerrado",
            "unavailable": "Entrada indisponível",
            "available": "Entrada disponível",
        }
        entry_state_descriptions = {
            "used": (
                "O prazo de entrada também terminou." if portal_deadline <= region_now
                else "Sua única entrada já foi usada; não é possível enviar outra equipe."
            ),
            "unavailable_content": "O chefe deste portal não está disponível para iniciar uma atividade.",
            "expired": "Novas entradas não são aceitas; uma atividade iniciada no prazo ainda pode ser concluída.",
            "unavailable": blocker or "A entrada não está disponível para esta guilda.",
            "available": "Uma equipe enfrenta o chefe do bioma portal; a duração mínima é de 1 hora.",
        }
        entry_state_label = entry_state_labels[entry_state]
        entry_state_description = entry_state_descriptions[entry_state]
        if event.region_code != home_code:
            entry_state_label = (
                "Atividade em andamento · fora do alcance da guilda"
                if event.status == "in_progress" else
                "Prazo de entrada aberto · fora do alcance da guilda"
                if portal_deadline > region_now else
                "Prazo encerrado · fora do alcance da guilda"
            )
            entry_state_description = blocker or "Portais só aceitam entrada na região natal da guilda."
        portal_cards.append({
            "event": event,
            "template": template,
            "region_name": event_region_name(event.region_code),
            "participant": participant,
            "own_activity": own_activity,
            "own_run": own_run,
            "activity_due": activity_due,
            "activity_collected": activity_collected,
            "activity_due_iso": _datetime_iso(run_due_at),
            "entered": participant is not None,
            "action_blocker": blocker,
            "entry_window_closed": portal_deadline <= region_now,
            "entry_state": entry_state,
            "entry_state_label": entry_state_label,
            "entry_state_description": entry_state_description,
            "expires_at_iso": _datetime_iso(event.expires_at_utc),
            **_portal_drop_preview(db, event_summary),
            "supply_quote": quote_supply(
                rank=("E" if int(getattr(template, "recommended_level", 1)) <= 10 else "D" if int(getattr(template, "recommended_level", 1)) <= 20 else "C" if int(getattr(template, "recommended_level", 1)) <= 30 else "B" if int(getattr(template, "recommended_level", 1)) <= 40 else "A" if int(getattr(template, "recommended_level", 1)) <= 50 else "S"),
                success_gold=int(getattr(template, "base_gold_reward", 0)),
                expected_drop_sale=0,
                multiplier=1, available_gold=resources.gold if resources else 0,
                applied_bonus_pp=min(5, max(0, 95 - int(getattr(template, "base_success_chance", 0)))),
            ),
        })
    if rebellion is not None:
        if player_state is not None:
            rebellion_participant = db.scalar(select(RegionalEventParticipant).where(
                RegionalEventParticipant.event_id == rebellion.id,
                RegionalEventParticipant.guild_state_id == player_state.id,
            ))
        rebellion_invite_expired = bool(
            rebellion_participant is not None
            and rebellion_participant.status == "declined"
            and rebellion.player_decision == "delegated_cpu"
        )
        rebellion_region_name = event_region_name(rebellion.region_code)
        if (rebellion.status == "active" and rebellion_participant is not None
                and rebellion_participant.status in {"accepted", "participating"}):
            rebellion_offers = list(db.scalars(select(RegionalOffer).where(
                RegionalOffer.cycle_id == board["cycle"].id,
                RegionalOffer.region_code == rebellion.region_code,
                RegionalOffer.offer_type.in_(PUBLIC_REGIONAL_OFFER_TYPES),
                RegionalOffer.status.in_(("available", "supply_preparing")),
            ).order_by(RegionalOffer.offer_type, RegionalOffer.slot)))
            rebellion_offers = [
                offer for offer in rebellion_offers
                if _regional_offer_rebellion_access(
                    db, campaign, guild.id, offer, region_now,
                )[1] is None
            ]
            for offer in rebellion_offers:
                _annotate_supply_preparation(offer, region_now)
                _annotate_prepared_team(db, guild.id, offer)
                _annotate_offer_drop_preview(db, offer)
                try:
                    saved_quote = json.loads(offer.supply_preparation_snapshot_json or "{}")
                except (TypeError, json.JSONDecodeError):
                    saved_quote = {}
                offer.supply_quote = saved_quote or _initial_offer_supply_quote(db, guild, offer, resources.gold if resources else 0)
    current_event_ids = {card["event"].id for card in portal_cards}
    if rebellion is not None:
        current_event_ids.add(rebellion.id)
    for event in board.get("event_history", []):
        if event.id in current_event_ids:
            continue
        summary = event_history_summary(event)
        rows_key = "participant_results" if event.event_type == "portal" else "activities"
        saved_rows = summary.get(rows_key)
        history_data_registered = isinstance(saved_rows, list)
        raw_rows = saved_rows if history_data_registered else []
        state_ids = {int(row["guild_state_id"]) for row in raw_rows
                     if isinstance(row, dict) and row.get("guild_state_id") is not None}
        states = list(db.scalars(select(RegionalGuildState).where(RegionalGuildState.id.in_(state_ids)))) if state_ids else []
        state_names = {state.id: state.name for state in states}
        player_activity = db.scalar(select(RegionalEventActivity).where(
            RegionalEventActivity.event_id == event.id,
            RegionalEventActivity.guild_state_id == player_state.id,
        ).order_by(RegionalEventActivity.id.desc()).limit(1)) if player_state is not None else None
        player_run = None
        if player_activity is not None:
            if player_activity.source_type == "dungeon":
                player_run = db.get(DungeonRun, player_activity.source_run_id)
            elif player_activity.source_type == "mission":
                player_run = db.get(MissionRun, player_activity.source_run_id)
        player_run_due_at = player_run.ends_at if player_run is not None else None
        if player_run_due_at is not None:
            player_run_due_at = (
                player_run_due_at.replace(tzinfo=timezone.utc)
                if player_run_due_at.tzinfo is None else player_run_due_at.astimezone(timezone.utc)
            )
        player_activity_due = bool(
            player_activity is not None and player_activity.status == "in_progress"
            and player_run is not None and player_run.status == "in_progress"
            and player_run_due_at <= region_now
        )
        player_activity_active = bool(
            player_activity is not None and player_activity.status == "in_progress"
            and player_run is not None and player_run.status == "in_progress"
            and player_run_due_at > region_now
        )
        player_result_collected = bool(
            player_activity is not None and player_activity.status == "resolved"
            and player_run is not None and player_run.status in {"completed", "failed"}
        )
        contribution_rows = []
        if event.event_type == "portal":
            contribution_rows = [{
                "guild": state_names.get(int(row["guild_state_id"]), "Guilda participante"),
                "contribution": int(row.get("contribution", 0)),
                "successes": 1 if row.get("success") else 0,
                "failures": 0 if row.get("success") else 1,
            } for row in raw_rows if isinstance(row, dict) and row.get("guild_state_id") is not None]
        else:
            totals = {}
            for row in raw_rows:
                if not isinstance(row, dict) or row.get("guild_state_id") is None:
                    continue
                state_id = int(row["guild_state_id"])
                item = totals.setdefault(state_id, {"guild": state_names.get(state_id, "Guilda participante"),
                    "contribution": 0, "successes": 0, "failures": 0})
                item["contribution"] += int(row.get("contribution", 0))
                item["successes"] += int(row.get("successes", 0))
                item["failures"] += int(row.get("failures", 0))
            contribution_rows = list(totals.values())
        event_history_cards.append({
            "event": event,
            "region_name": event_region_name(event.region_code),
            "summary": summary,
            "contributions": contribution_rows,
            "history_data_registered": history_data_registered,
            "history_has_rows": bool(raw_rows),
            "player_result_collected": player_result_collected,
            "player_result_success": bool(player_run.success) if player_result_collected else None,
            "player_activity_due": player_activity_due,
            "player_activity_active": player_activity_active,
            "player_activity_due_iso": _datetime_iso(player_run_due_at),
            "player_run": player_run,
            "status_label": {
                "active": "Aberto", "in_progress": "Em andamento", "resolved": "Concluído",
                "expired": "Expirado", "suppressed": "Não ocorreu: outra rebelião estava ativa",
                "not_triggered": "Não ocorreu",
            }.get(event.status, "Registrado"),
            "reason_label": {
                "deadline_elapsed_offline": "O prazo de entrada terminou durante a ausência.",
                "deadline_elapsed_waiting_for_started_activities": "O prazo terminou; aguardando a conclusão das atividades iniciadas.",
            }.get(summary.get("reason"), "Encerramento registrado."),
            "decision_label": {
                "accept": "Aceita", "decline": "Delegada à CPU", "delegated_cpu": "Delegada à CPU",
            }.get(summary.get("player_decision"), "Registrada"),
        })
        if event.event_type == "portal" and event.region_code != home_code:
            event_deadline = event.expires_at_utc
            event_deadline = (
                event_deadline.replace(tzinfo=timezone.utc)
                if event_deadline.tzinfo is None
                else event_deadline.astimezone(timezone.utc)
            )
            if event_deadline <= region_now:
                event_history_cards[-1]["status_label"] = "Prazo encerrado · fora do alcance da guilda"
                event_history_cards[-1]["reason_label"] = (
                    "O prazo de entrada encerrou. Portais só aceitam entrada na região natal; a resolução continua consultável no histórico."
                )
            else:
                event_history_cards[-1]["status_label"] = "Prazo aberto · fora do alcance da guilda"
                event_history_cards[-1]["reason_label"] = (
                    "Portais só aceitam entrada na região natal. Rebeliões oferecem atividades próprias na região quando o convite é aceito."
                )
    if central_events_view:
        # This route advances the regional clock but intentionally skips the
        # gathering commit used by the main Vigília page.
        db.commit()
    review_token = regional_events_review_token(
        db, campaign.campaign_id, guild.id, now=region_now,
    ) if central_events_view else ""
    return templates.TemplateResponse(
        request=request,
        name="regional/events.html" if central_events_view else "regional/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "error": request.query_params.get("error"),
            "diagnostic_id": request.query_params.get("diagnostic"),
            "selected_start_mercenary_ids": request.query_params.getlist("selected_mercenary_id"),
            "selected_start_supply": request.query_params.get("selected_supply") == "1",
            "message": request.query_params.get("message"),
            "assignments": assignments,
            "family_labels": FAMILY_LABELS,
            "node_labels": NODE_LABELS,
            "reports": reports,
            "rebellion_participant": rebellion_participant,
            "rebellion_invite_expired": rebellion_invite_expired,
            "home_region_code": home_code,
            "rebellion_priority_ends_at_iso": _datetime_iso(rebellion.priority_ends_at_utc) if rebellion else None,
            "rebellion_priority_elapsed": rebellion_priority_elapsed,
            "rebellion_expires_at_iso": _datetime_iso(rebellion.expires_at_utc) if rebellion else None,
            "rebellion_offers": rebellion_offers,
            "rebellion_region_name": rebellion_region_name,
            "portal_cards": portal_cards,
            "event_history_cards": event_history_cards,
            "portal_spawn_status": portal_spawn_status,
            "regional_events_review_token": review_token,
            "central_events_view": central_events_view,
            "event_section": request.query_params.get("section")
            if request.query_params.get("section") in {"portals", "rebellions"}
            else "portals",
            "portal_history_cards": [card for card in event_history_cards
                                     if card["event"].event_type == "portal"],
            "rebellion_history_cards": [card for card in event_history_cards
                                        if card["event"].event_type == "rebellion"],
            "achievement_cards": achievement_context["achievement_cards"],
            "warehouse_used": get_inventory_usage(db, guild.id),
            "warehouse_capacity": get_inventory_capacity(db, guild),
            **get_evolution_art_context(),
            **board,
        },
    )


@router.post("/offers/{offer_id}/start")
async def start_offer(
    offer_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return RedirectResponse("/login", status_code=303)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_multi_fields(request)
    offer = db.scalar(select(RegionalOffer).where(
        RegionalOffer.id == offer_id,
        RegionalOffer.campaign_id == campaign.campaign_id,
        RegionalOffer.offer_type.in_(PUBLIC_REGIONAL_OFFER_TYPES),
        RegionalOffer.status.in_(("available", "supply_preparing")),
    ))
    if offer is None:
        return _start_error_redirect("Oferta indisponível.", form)
    requested_supply_mode = (form.get("supply_mode") or [""])[0]
    mode_was_explicit = bool(requested_supply_mode)
    has_preparation = (
        offer.status == "supply_preparing"
        or offer.supply_preparation_started_at_utc is not None
        or offer.supply_preparation_ends_at_utc is not None
        or bool(offer.supply_preparation_snapshot_json)
    )
    if requested_supply_mode not in {"", "none", "prepared"}:
        return _start_error_redirect("Escolha uma opção válida de suprimento.", form)
    if has_preparation and not mode_was_explicit:
        return _start_error_redirect("Escolha explicitamente iniciar com o suprimento preparado ou sem suprimento.", form)
    if not requested_supply_mode:
        requested_supply_mode = "none"
    current_time = datetime.now(timezone.utc)
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if player_state is None:
        return _start_error_redirect("Estado regional indisponível.", form)
    event_for_activity, access_error = _regional_offer_rebellion_access(
        db, campaign, guild.id, offer, current_time,
    )
    if access_error:
        return _start_error_redirect(access_error, form)
    required_guild_level = int(offer.required_guild_level_snapshot or 1)
    if guild.level < required_guild_level:
        return _start_error_redirect(
            f"Nível da guilda insuficiente para esta oferta. Nível mínimo: {required_guild_level}.",
            form,
        )
    if has_preparation:
        if offer.supply_preparation_started_at_utc is None or offer.supply_preparation_ends_at_utc is None:
            return _start_error_redirect("A preparação não possui um prazo válido. Atualize a página.", form)
        prep_end = offer.supply_preparation_ends_at_utc
        prep_end = prep_end.replace(tzinfo=timezone.utc) if prep_end.tzinfo is None else prep_end.astimezone(timezone.utc)
        try:
            supply_snapshot = json.loads(offer.supply_preparation_snapshot_json or "{}")
        except (TypeError, json.JSONDecodeError):
            supply_snapshot = {}
        if (
            not isinstance(supply_snapshot, dict)
            or supply_snapshot.get("schema") != 1
            or supply_snapshot.get("supply") != "regional_group_supply"
            or supply_snapshot.get("prepared_for_offer_id") != offer.id
            or not isinstance(supply_snapshot.get("mercenary_ids"), list)
        ):
            return _start_error_redirect("A preparação não possui um snapshot válido.", form)
        prepared_team = sorted(set(str(value) for value in supply_snapshot["mercenary_ids"]))
        if not prepared_team:
            return _start_error_redirect("A preparação não possui uma equipe válida.", form)
        submitted_team = sorted(set(str(value) for value in form.get("mercenary_ids", [])))
        if requested_supply_mode == "prepared":
            if current_time < prep_end:
                return _start_error_redirect("O suprimento ainda está sendo preparado.", form)
            if not offer.supply_prepared_at_utc:
                offer.supply_prepared_at_utc = prep_end
            if submitted_team != prepared_team:
                return _start_error_redirect("O bônus preparado exige exatamente a equipe escolhida no preparo.", form)
        else:
            if not set(prepared_team).issubset(submitted_team):
                return _start_error_redirect("Mantenha toda a equipe preparada para iniciar sem suprimento.", form)
            if current_time >= prep_end and not offer.supply_prepared_at_utc:
                offer.supply_prepared_at_utc = prep_end
            supply_snapshot = None
    else:
        supply_snapshot = None
        if not mode_was_explicit and (form.get("supply") or [""])[0] == "1":
            return _start_error_redirect("Prepare o suprimento antes de iniciar ou desmarque a opção.", form)
        if requested_supply_mode == "prepared":
            return _start_error_redirect("Esta oferta não possui suprimento preparado.", form)
    if offer.status == "supply_preparing" and offer.reserved_by_guild_state_id != player_state.id:
        return _start_error_redirect("Oferta em preparação por outra guilda.", form)
    try:
        claim_result = db.execute(
            update(RegionalOffer)
            .where(
                RegionalOffer.id == offer.id,
                RegionalOffer.status == offer.status,
                RegionalOffer.campaign_id == campaign.campaign_id,
            )
            .values(status="player_reserved", reserved_by_guild_state_id=player_state.id)
        )
    except OperationalError:
        db.rollback()
        return _start_error_redirect("Oferta já reservada.", form)
    if claim_result.rowcount != 1:
        db.rollback()
        return _start_error_redirect("Oferta já reservada.", form)
    offer.status = "player_reserved"
    offer.reserved_by_guild_state_id = player_state.id
    mercenary_ids = form.get("mercenary_ids", [])
    try:
        if offer.offer_type == "contract":
            run = start_mission(
                db, guild, str(offer.mission_template_id), mercenary_ids, commit=False,
                regional_duration_seconds=offer.duration_seconds_snapshot,
                supply_selected=False,
                supply_rank=offer.rank,
                regional_success_chance=offer.success_chance_snapshot,
                regional_recommended_power=offer.recommended_power_snapshot,
                regional_recommended_level=offer.recommended_level_snapshot,
                regional_party_bounds=(offer.min_party_size_snapshot, offer.max_party_size_snapshot),
                regional_required_guild_level=offer.required_guild_level_snapshot,
                allow_regional_supply=True,
                supply_snapshot_override=supply_snapshot,
            )
            run.regional_offer_id = offer.id
            run.rank_snapshot = offer.rank
            source = "missions"
        else:
            run = start_dungeon(
                db, guild, str(offer.dungeon_template_id), mercenary_ids, commit=False,
                regional_duration_seconds=offer.duration_seconds_snapshot,
                supply_selected=False,
                supply_rank=offer.rank,
                regional_success_chance=offer.success_chance_snapshot,
                regional_recommended_power=offer.recommended_power_snapshot,
                regional_recommended_level=offer.recommended_level_snapshot,
                regional_party_bounds=(offer.min_party_size_snapshot, offer.max_party_size_snapshot),
                regional_required_guild_level=offer.required_guild_level_snapshot,
                supply_snapshot_override=supply_snapshot,
            )
            run.regional_offer_id = offer.id
            run.rank_snapshot = offer.rank
            source = "dungeons"
    except (MissionError, DungeonError) as error:
        db.rollback()
        return _start_error_redirect(error, form)
    offer.status = "in_progress"
    offer.claimed_at_utc = run.started_at
    db.add(offer)
    if event_for_activity is not None:
        try:
            attach_event_activity(
                db,
                event_for_activity,
                player_state,
                "mission" if source == "missions" else "dungeon",
                run.id,
            )
        except ValueError as error:
            db.rollback()
            return _start_error_redirect(error, form)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        return _start_error_redirect("Oferta já reservada.", form)
    if _validated_regional_return_to(form, fallback="").startswith("/regional/events"):
        return _regional_redirect(form, message="Atividade regional iniciada")
    return RedirectResponse("/regional?message=Contrato%20regional%20iniciado", status_code=303)


@router.post("/offers/{offer_id}/prepare")
async def prepare_regional_offer_supply(
    offer_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None or resources is None:
        return RedirectResponse("/regional?error=Guilda%20indispon%C3%ADvel", status_code=303)
    form = await read_form_multi_fields(request)
    from app.services.building_reset_service import _lock_guild_for_building_mutation

    guild = _lock_guild_for_building_mutation(db, guild.id)
    if guild is None:
        return RedirectResponse("/regional?error=Guilda%20indispon%C3%ADvel", status_code=303)
    offer = db.scalar(select(RegionalOffer).where(
        RegionalOffer.id == offer_id,
        RegionalOffer.campaign_id == campaign.campaign_id,
        RegionalOffer.offer_type.in_(PUBLIC_REGIONAL_OFFER_TYPES),
        RegionalOffer.status == "available",
    ).with_for_update())
    if offer is None:
        return _start_error_redirect("Oferta indisponível para preparação.", form)
    _access_event, access_error = _regional_offer_rebellion_access(
        db, campaign, guild.id, offer, datetime.now(timezone.utc),
    )
    if access_error:
        return _start_error_redirect(access_error, form)
    if offer.supply_preparation_started_at_utc is not None:
        return _start_error_redirect("O suprimento já está em preparação ou foi preparado.", form)
    if (form.get("supply") or [""])[0] != "1":
        return _start_error_redirect("Marque o suprimento opcional para começar a preparação.", form)
    quote = _quote_offer_supply(db, guild, offer, form.get("mercenary_ids", []))
    if not quote.get("available"):
        return _start_error_redirect(quote.get("reason", "Suprimento indisponível."), form)
    cost = int(quote["cost_kits"])
    cycle = db.get(RegionalCycle, offer.cycle_id)
    now = datetime.now(timezone.utc)
    prep_seconds = max(1, int(offer.duration_seconds_snapshot * 0.015))
    cycle_end = cycle.ends_at_utc if cycle else now
    cycle_end = cycle_end.replace(tzinfo=timezone.utc) if cycle_end.tzinfo is None else cycle_end.astimezone(timezone.utc)
    if cycle is None or cycle.status != "open" or now + timedelta(seconds=prep_seconds) >= cycle_end:
        return _start_error_redirect("Não há tempo suficiente nesta Vigília para concluir a preparação.", form)
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if player_state is None:
        return _start_error_redirect("Estado regional indisponível.", form)
    preparation_snapshot = json.dumps({
        "schema": 1,
        "supply": "regional_group_supply",
        "prepared_for_offer_id": offer.id,
        "mercenary_ids": sorted(set(str(value) for value in form.get("mercenary_ids", []))),
        "base_final_chance": int(quote.get("base_final_chance", offer.success_chance_snapshot)),
        "preparation_seconds": prep_seconds,
        **quote,
    }, ensure_ascii=False, sort_keys=True)
    reserved = db.execute(update(RegionalOffer).where(
        RegionalOffer.id == offer.id,
        RegionalOffer.status == "available",
        RegionalOffer.supply_preparation_started_at_utc.is_(None),
    ).values(status="supply_preparing", reserved_by_guild_state_id=player_state.id))
    if reserved.rowcount != 1:
        db.rollback()
        return _start_error_redirect("Esta oferta já está sendo preparada.", form)
    from app.models.item import GuildInventoryItem, ItemTemplate
    kit_template = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "supply_kit"))
    debit = db.execute(update(GuildInventoryItem).where(
        GuildInventoryItem.guild_id == guild.id,
        GuildInventoryItem.item_template_id == (kit_template.id if kit_template else -1),
        GuildInventoryItem.quantity >= cost,
    ).values(quantity=GuildInventoryItem.quantity - cost))
    if debit.rowcount != 1:
        db.rollback()
        return _start_error_redirect("Os Kits de Suprimentos mudaram; confira o inventário e tente novamente.", form)
    offer.status = "supply_preparing"
    offer.reserved_by_guild_state_id = player_state.id
    offer.supply_preparation_started_at_utc = now
    offer.supply_preparation_ends_at_utc = now + timedelta(seconds=prep_seconds)
    offer.supply_preparation_snapshot_json = preparation_snapshot
    db.add(offer)
    db.commit()
    if _validated_regional_return_to(form, fallback="").startswith("/regional/events"):
        return _regional_redirect(form, message="Preparo de suprimento iniciado")
    return RedirectResponse("/regional?message=Preparo%20de%20suprimento%20iniciado", status_code=303)


@router.post("/events/{event_id}/decision")
async def decide_regional_event(
    event_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return RedirectResponse("/login", status_code=303)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_multi_fields(request)
    event = db.scalar(select(RegionalEvent).where(
        RegionalEvent.id == event_id,
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "rebellion",
    ))
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if event is None or player_state is None:
        return _start_error_redirect("Convite indisponível.", form, f"#regional-event-{event_id}")
    current_time = datetime.now(timezone.utc)
    expire_due_events(db, campaign.campaign_id, current_time)
    decision = str((form.get("decision") or [""])[0]).strip().lower()
    try:
        record_rebellion_decision(db, event, player_state.id, decision, current_time)
        db.commit()
    except ValueError as error:
        db.rollback()
        return _start_error_redirect(error, form)
    message = "Convite aceito" if decision == "accept" else "Rebelião delegada à CPU"
    return _regional_redirect(
        form,
        fallback_anchor=f"#regional-event-{event_id}",
        message=message,
    )


@router.post("/events/{event_id}/portals/supply-quote")
async def regional_portal_supply_quote(
    event_id: int, request: Request, db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return JSONResponse({"available": False, "reason": "Campanha indisponível."}, status_code=401)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return JSONResponse({"available": False, "reason": "Guilda indisponível."}, status_code=404)
    event = db.get(RegionalEvent, event_id)
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    blocker = _portal_action_blocker(db, campaign, event, player_state, datetime.now(timezone.utc))
    if blocker:
        return JSONResponse({"available": False, "reason": blocker}, status_code=409)
    form = await read_form_multi_fields(request)
    from app.repositories.mercenary_repository import list_available_mercenaries_by_ids
    from app.services.dungeon_service import (
        get_advanced_dungeon_chance, parse_dungeon_mercenary_ids,
        scouts_values, validate_dungeon_party_requirements, validate_dungeon_requirements,
    )
    from app.services.building_service import get_building_level
    from app.services.skill_service import get_party_skill_effects
    try:
        ids = parse_dungeon_mercenary_ids(form.get("mercenary_ids", []))
    except ValueError as error:
        return JSONResponse({"available": False, "reason": str(error)})
    members = list_available_mercenaries_by_ids(db, guild.id, ids)
    if not ids or len(members) != len(ids):
        return JSONResponse({"available": False, "reason": "Escolha um grupo de mercenários disponíveis."})
    db_template = db.get(DungeonTemplate, event.dungeon_template_id)
    try:
        event_summary = json.loads(event.summary_json or "{}")
    except (TypeError, json.JSONDecodeError):
        event_summary = {}
    boss_record = event_summary.get("portal_boss") if isinstance(event_summary, dict) else None
    boss_snapshot = boss_record.get("template") if isinstance(boss_record, dict) else None
    template = (SimpleNamespace(**boss_snapshot)
                if isinstance(boss_snapshot, dict) and int(boss_snapshot.get("id", -1)) == event.dungeon_template_id
                else db_template)
    if template is None:
        return JSONResponse({"available": False, "reason": "Conteúdo do chefe indisponível."}, status_code=409)
    try:
        validate_dungeon_requirements(db, guild, template)
        validate_dungeon_party_requirements(db, guild, template, members)
    except ValueError as error:
        return JSONResponse({"available": False, "reason": str(error)})
    chance = get_advanced_dungeon_chance(db, guild.id, template, members)["final_chance"]
    chance = min(95, chance + scouts_values(get_building_level(db, guild.id, "scouts"))["success_bonus_percentage_points"])
    skills = get_party_skill_effects(db, members)
    success_gold = floor(template.base_gold_reward * (100 + skills.get("gold_reward", 0)) / 100)
    level = max(1, int(template.recommended_level))
    rank = "E" if level <= 10 else "D" if level <= 20 else "C" if level <= 30 else "B" if level <= 40 else "A" if level <= 50 else "S"
    quote = quote_supply(
        rank=rank, success_gold=success_gold,
        expected_drop_sale=0,
        multiplier=1, available_gold=guild_gold(db, guild.id),
        applied_bonus_pp=min(5, max(0, 95 - chance)),
    )
    return JSONResponse({**quote, "base_final_chance": chance,
                         "final_chance": min(95, chance + int(quote.get("chance_bonus_pp", 0)))})


@router.post("/events/{event_id}/portals/start")
async def start_regional_portal(
    event_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
    campaign: CampaignMetadata | None = Depends(get_current_campaign),
):
    if current_user is None or campaign is None:
        return RedirectResponse("/login", status_code=303)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_multi_fields(request)
    now = datetime.now(timezone.utc)
    expire_due_events(db, campaign.campaign_id, now)
    event = db.get(RegionalEvent, event_id)
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    blocker = _portal_action_blocker(db, campaign, event, player_state, now)
    if blocker:
        return _start_error_redirect(blocker, form, f"#regional-event-{event_id}")
    template = db.get(DungeonTemplate, event.dungeon_template_id)
    try:
        event_summary = json.loads(event.summary_json or "{}")
    except (TypeError, json.JSONDecodeError):
        event_summary = {}
    boss_record = event_summary.get("portal_boss") if isinstance(event_summary, dict) else None
    boss_snapshot = boss_record.get("template") if isinstance(boss_record, dict) else None
    if not isinstance(boss_snapshot, dict) or int(boss_snapshot.get("id", -1)) != template.id:
        boss_snapshot = build_portal_boss_snapshot(template)
    try:
        run = start_dungeon(
            db, guild, str(template.id), form.get("mercenary_ids", []), commit=False,
            regional_duration_seconds=max(3600, int(boss_snapshot["duration_seconds"])),
            regional_min_duration_seconds=3600,
            template_snapshot=boss_snapshot,
            supply_selected=(form.get("supply") or [""])[0] == "1",
            supply_include_drops=False,
            supply_rank=("E" if int(boss_snapshot.get("recommended_level", 1)) <= 10 else "D" if int(boss_snapshot.get("recommended_level", 1)) <= 20 else "C" if int(boss_snapshot.get("recommended_level", 1)) <= 30 else "B" if int(boss_snapshot.get("recommended_level", 1)) <= 40 else "A" if int(boss_snapshot.get("recommended_level", 1)) <= 50 else "S"),
        )
    except DungeonError as error:
        db.rollback()
        return _start_error_redirect(error, form, f"#regional-event-{event_id}")
    try:
        attach_event_activity(db, event, player_state, "dungeon", run.id)
    except ValueError as error:
        db.rollback()
        return _start_error_redirect(error, form, f"#regional-event-{event_id}")
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        return _start_error_redirect("Entrada de portal já reservada.", form, f"#regional-event-{event_id}")
    if _validated_regional_return_to(form, fallback="").startswith("/regional/events"):
        return _regional_redirect(
            form,
            fallback_anchor=f"#regional-event-{event_id}",
            message="Expedição de portal iniciada",
        )
    return RedirectResponse("/dungeons?message=Expedi%C3%A7%C3%A3o%20de%20portal%20iniciada", status_code=303)
