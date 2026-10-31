from pathlib import Path
import json
from datetime import datetime, timedelta, timezone
from math import floor
from types import SimpleNamespace
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.dependencies import DbSession, get_current_campaign, get_current_player
from app.core.forms import read_form_multi_fields
from app.models.campaign import CampaignMetadata
from app.models.guild import GuildResources
from app.models.dungeon import DungeonTemplate
from app.models.mission import MissionTemplate
from app.models.regional import RegionalEvent, RegionalEventParticipant, RegionalGuildState, RegionalOffer
from app.models.regional import RegionalCycle
from app.models.user import User
from app.services.dungeon_service import DungeonError, start_dungeon
from app.services.gathering_service import advance_all_assignments, list_assignments
from app.services.achievement_service import get_codex_context
from app.services.guild_service import get_current_guild_context
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.mission_service import MissionError, start_mission
from app.services.regional_cycle_service import get_current_player_regional_guild, get_regional_board
from app.services.regional_event_service import (
    attach_event_activity,
    event_history_summary,
    event_region_name,
    record_rebellion_decision,
    expire_due_events,
    build_portal_boss_snapshot,
)
from app.services.evolution_art_service import get_evolution_art_context
from app.services.supply_preparation_service import estimate_drop_sale_value, guild_gold, quote_supply
from app.repositories.item_repository import list_active_drops_for_mission
from app.repositories.dungeon_repository import list_active_drops_for_dungeon


router = APIRouter(prefix="/regional")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


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


def _start_error_redirect(error: object, form: dict[str, list[str]], anchor: str = "") -> RedirectResponse:
    query: list[tuple[str, str]] = [("error", str(error))]
    query.extend(("selected_mercenary_id", value) for value in form.get("mercenary_ids", []))
    if (form.get("supply") or [""])[0] == "1":
        query.append(("selected_supply", "1"))
    return RedirectResponse(f"/regional?{urlencode(query, doseq=True)}{anchor}", status_code=303)


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
            validate_mission_requirements(db, guild, template)
        except ValueError as error:
            return {"available": False, "reason": str(error)}
        if not template.min_party_size <= len(members) <= template.max_party_size:
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
            validate_dungeon_requirements(db, guild, template)
            validate_advanced_party_requirements(db, guild, template, members)
        except ValueError as error:
            return {"available": False, "reason": str(error)}
        if not template.min_party_size <= len(members) <= template.max_party_size:
            return {"available": False, "reason": "O grupo não atende ao tamanho exigido pela masmorra."}
        details = get_party_chance_details(db, guild.id, offer.success_chance_snapshot, members,
                                           offer.recommended_power_snapshot, offer.recommended_level_snapshot,
                                           power_bonus=get_group_synergy_power_bonus(members, template))
        base_final = max(5, min(95, details["final_chance"] + skills.get("success_chance", 0)
                                + skills.get("dungeon_power", 0) // 10 + get_group_synergy_bonus(members, template)))
        base_final = min(95, base_final + scouts_values(get_building_level(db, guild.id, "scouts"))["success_bonus_percentage_points"])
        success_gold = floor(offer.gold_reward_snapshot * (100 + skills.get("gold_reward", 0)) / 100)
        drops = list_active_drops_for_dungeon(db, template.id)
    quote = quote_supply(
        rank=offer.rank, success_gold=success_gold,
        expected_drop_sale=estimate_drop_sale_value(db, guild.id, drops, 1),
        multiplier=1, available_gold=guild_gold(db, guild.id),
        applied_bonus_pp=min(5, max(0, 95 - base_final)),
    )
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
    return quote_supply(
        rank=offer.rank, success_gold=offer.gold_reward_snapshot,
        expected_drop_sale=estimate_drop_sale_value(db, guild.id, drops, 1),
        multiplier=1, available_gold=available_gold,
        applied_bonus_pp=5,
    )


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
        RegionalOffer.status.in_(("available", "supply_preparing")),
    ))
    if offer is None:
        return JSONResponse({"available": False, "reason": "Oferta indisponível."}, status_code=409)
    form = await read_form_multi_fields(request)
    return JSONResponse(_quote_offer_supply(db, guild, offer, form.get("mercenary_ids", [])))


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
    board = get_regional_board(db, campaign, guild)
    region_now = datetime.now(timezone.utc)
    for offer_list in board.get("offers", {}).values():
        for offer in offer_list:
            _annotate_supply_preparation(offer, region_now)
            try:
                saved_quote = json.loads(offer.supply_preparation_snapshot_json or "{}")
            except (TypeError, json.JSONDecodeError):
                saved_quote = {}
            offer.supply_quote = saved_quote or _initial_offer_supply_quote(db, guild, offer, resources.gold if resources else 0)
    advance_all_assignments(db, guild)
    db.commit()
    assignments = list_assignments(db, guild.id)
    achievement_context = get_codex_context(db, guild, True)
    reports = []
    for history_row in board["latest_history"]:
        cycle = db.get(RegionalCycle, history_row.cycle_id)
        reports.append({
            "row": history_row,
            "cycle_number": cycle.cycle_number if cycle else history_row.cycle_id,
            "summary": json.loads(history_row.summary_json or "{}"),
        })
    rebellion = board.get("rebellion_event")
    rebellion_participant = None
    rebellion_offers = []
    rebellion_region_name = None
    portal_cards = []
    event_history_cards = []
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    for event in board.get("portal_events", []):
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
        entered = db.scalar(select(RegionalEventParticipant.id).where(
            RegionalEventParticipant.event_id == event.id,
            RegionalEventParticipant.guild_state_id == player_state.id,
        )) if player_state is not None else None
        portal_cards.append({
            "event": event,
            "template": template,
            "entered": entered is not None,
            "expires_at_iso": _datetime_iso(event.expires_at_utc),
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
        rebellion_region_name = event_region_name(rebellion.region_code)
        if (rebellion.status == "active" and rebellion_participant is not None
                and rebellion_participant.status == "accepted"):
            rebellion_offers = list(db.scalars(select(RegionalOffer).where(
                RegionalOffer.cycle_id == board["cycle"].id,
                RegionalOffer.region_code == rebellion.region_code,
                RegionalOffer.status.in_(("available", "supply_preparing")),
            ).order_by(RegionalOffer.offer_type, RegionalOffer.slot)))
            for offer in rebellion_offers:
                _annotate_supply_preparation(offer, region_now)
                try:
                    saved_quote = json.loads(offer.supply_preparation_snapshot_json or "{}")
                except (TypeError, json.JSONDecodeError):
                    saved_quote = {}
                offer.supply_quote = saved_quote or _initial_offer_supply_quote(db, guild, offer, resources.gold if resources else 0)
    for event in board.get("event_history", []):
        summary = event_history_summary(event)
        raw_rows = summary.get("participant_results", []) if event.event_type == "portal" else summary.get("activities", [])
        state_ids = {int(row["guild_state_id"]) for row in raw_rows
                     if isinstance(row, dict) and row.get("guild_state_id") is not None}
        states = list(db.scalars(select(RegionalGuildState).where(RegionalGuildState.id.in_(state_ids)))) if state_ids else []
        state_names = {state.id: state.name for state in states}
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
    return templates.TemplateResponse(
        request=request,
        name="regional/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "error": request.query_params.get("error"),
            "selected_start_mercenary_ids": request.query_params.getlist("selected_mercenary_id"),
            "selected_start_supply": request.query_params.get("selected_supply") == "1",
            "message": request.query_params.get("message"),
            "assignments": assignments,
            "reports": reports,
            "rebellion_participant": rebellion_participant,
            "rebellion_priority_ends_at_iso": _datetime_iso(rebellion.priority_ends_at_utc) if rebellion else None,
            "rebellion_expires_at_iso": _datetime_iso(rebellion.expires_at_utc) if rebellion else None,
            "rebellion_offers": rebellion_offers,
            "rebellion_region_name": rebellion_region_name,
            "portal_cards": portal_cards,
            "event_history_cards": event_history_cards,
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
    from app.services.regional_cycle_service import REGIONS

    home_code = next((code for code, name in REGIONS if name == campaign.home_region), REGIONS[0][0])
    offer = db.scalar(select(RegionalOffer).where(
        RegionalOffer.id == offer_id,
        RegionalOffer.campaign_id == campaign.campaign_id,
        RegionalOffer.status.in_(("available", "supply_preparing")),
    ))
    if offer is None:
        return RedirectResponse("/regional?error=Oferta%20indispon%C3%ADvel", status_code=303)
    form = await read_form_multi_fields(request)
    if offer.supply_preparation_ends_at_utc is not None:
        prep_end = offer.supply_preparation_ends_at_utc
        prep_end = prep_end.replace(tzinfo=timezone.utc) if prep_end.tzinfo is None else prep_end.astimezone(timezone.utc)
        if datetime.now(timezone.utc) < prep_end:
            return _start_error_redirect("O suprimento ainda está sendo preparado.", form)
        if not offer.supply_prepared_at_utc:
            offer.supply_prepared_at_utc = prep_end
        try:
            supply_snapshot = json.loads(offer.supply_preparation_snapshot_json or "{}")
        except (TypeError, json.JSONDecodeError):
            supply_snapshot = {}
        if not supply_snapshot:
            return _start_error_redirect("A preparação não possui um snapshot válido. Inicie sem suprimento.", form)
        prepared_team = sorted(str(value) for value in supply_snapshot.get("mercenary_ids", []))
        submitted_team = sorted(set(str(value) for value in form.get("mercenary_ids", [])))
        if not prepared_team or submitted_team != prepared_team:
            return _start_error_redirect("Use a mesma equipe escolhida durante a preparação do suprimento.", form)
    else:
        supply_snapshot = None
        if (form.get("supply") or [""])[0] == "1":
            return _start_error_redirect("Prepare o suprimento antes de iniciar ou desmarque a opção.", form)
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if player_state is None:
        return RedirectResponse("/regional?error=Estado%20regional%20indispon%C3%ADvel", status_code=303)
    if offer.status == "supply_preparing" and offer.reserved_by_guild_state_id != player_state.id:
        return RedirectResponse("/regional?error=Oferta%20em%20prepara%C3%A7%C3%A3o%20por%20outra%20guilda", status_code=303)
    current_time = datetime.now(timezone.utc)
    rebellion = db.scalar(select(RegionalEvent).where(
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "rebellion",
        RegionalEvent.region_code == offer.region_code,
        RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc > current_time,
    ).order_by(RegionalEvent.id.desc()).limit(1))
    participant = db.scalar(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == rebellion.id,
        RegionalEventParticipant.guild_state_id == player_state.id,
        RegionalEventParticipant.status.in_(("accepted", "participating")),
    )) if rebellion is not None else None
    event_for_activity = rebellion if participant is not None else None
    if offer.region_code != home_code and event_for_activity is None:
        return RedirectResponse("/regional?error=Atividade%20fora%20da%20regi%C3%A3o%20natal%20indispon%C3%ADvel", status_code=303)
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
        return RedirectResponse("/regional?error=Oferta%20j%C3%A1%20reservada", status_code=303)
    if claim_result.rowcount != 1:
        db.rollback()
        return RedirectResponse("/regional?error=Oferta%20j%C3%A1%20reservada", status_code=303)
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
        return RedirectResponse("/regional?error=Oferta%20j%C3%A1%20reservada", status_code=303)
    return RedirectResponse(f"/{source}?message=Contrato%20regional%20iniciado", status_code=303)


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
    offer = db.scalar(select(RegionalOffer).where(
        RegionalOffer.id == offer_id,
        RegionalOffer.campaign_id == campaign.campaign_id,
        RegionalOffer.status == "available",
    ).with_for_update())
    if offer is None:
        return _start_error_redirect("Oferta indisponível para preparação.", form)
    if offer.supply_preparation_started_at_utc is not None:
        return _start_error_redirect("O suprimento já está em preparação ou foi preparado.", form)
    if (form.get("supply") or [""])[0] != "1":
        return _start_error_redirect("Marque o suprimento opcional para começar a preparação.", form)
    quote = _quote_offer_supply(db, guild, offer, form.get("mercenary_ids", []))
    if not quote.get("available"):
        return _start_error_redirect(quote.get("reason", "Suprimento indisponível."), form)
    cost = int(quote["cost_gold"])
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
    debit = db.execute(update(GuildResources).where(
        GuildResources.guild_id == guild.id,
        GuildResources.gold >= cost,
    ).values(gold=GuildResources.gold - cost))
    if debit.rowcount != 1:
        db.rollback()
        return _start_error_redirect("Saldo insuficiente para preparar o suprimento.", form)
    offer.status = "supply_preparing"
    offer.reserved_by_guild_state_id = player_state.id
    offer.supply_preparation_started_at_utc = now
    offer.supply_preparation_ends_at_utc = now + timedelta(seconds=prep_seconds)
    offer.supply_preparation_snapshot_json = preparation_snapshot
    db.add(offer)
    db.commit()
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
    event = db.scalar(select(RegionalEvent).where(
        RegionalEvent.id == event_id,
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "rebellion",
    ))
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if event is None or player_state is None:
        return RedirectResponse("/regional?error=Convite%20indispon%C3%ADvel", status_code=303)
    current_time = datetime.now(timezone.utc)
    expire_due_events(db, campaign.campaign_id, current_time)
    form = await read_form_multi_fields(request)
    decision = str((form.get("decision") or [""])[0]).strip().lower()
    try:
        record_rebellion_decision(db, event, player_state.id, decision, current_time)
        db.commit()
    except ValueError as error:
        db.rollback()
        return _start_error_redirect(error, form)
    label = "Convite%20aceito" if decision == "accept" else "Rebeli%C3%A3o%20delegada%20%C3%A0%20CPU"
    return RedirectResponse(f"/regional?message={label}#events-title", status_code=303)


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
    event = db.scalar(select(RegionalEvent).where(
        RegionalEvent.id == event_id, RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "portal", RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc > datetime.now(timezone.utc),
    ))
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if event is None or player_state is None or event.dungeon_template_id is None:
        return JSONResponse({"available": False, "reason": "Portal indisponível."}, status_code=409)
    if db.scalar(select(RegionalEventParticipant.id).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == player_state.id,
    )) is not None:
        return JSONResponse({"available": False, "reason": "Esta guilda já usou a entrada deste portal."}, status_code=409)
    form = await read_form_multi_fields(request)
    from app.repositories.mercenary_repository import list_available_mercenaries_by_ids
    from app.services.dungeon_service import (
        get_advanced_dungeon_chance, parse_dungeon_mercenary_ids,
        scouts_values, validate_advanced_party_requirements, validate_dungeon_requirements,
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
        validate_advanced_party_requirements(db, guild, template, members)
    except ValueError as error:
        return JSONResponse({"available": False, "reason": str(error)})
    if not template.min_party_size <= len(members) <= template.max_party_size:
        return JSONResponse({"available": False, "reason": "O grupo não atende ao tamanho exigido pelo chefe."})
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
    from app.services.regional_cycle_service import REGIONS

    home_code = next((code for code, name in REGIONS if name == campaign.home_region), REGIONS[0][0])
    now = datetime.now(timezone.utc)
    expire_due_events(db, campaign.campaign_id, now)
    event = db.scalar(select(RegionalEvent).where(
        RegionalEvent.id == event_id,
        RegionalEvent.campaign_id == campaign.campaign_id,
        RegionalEvent.event_type == "portal",
        RegionalEvent.region_code == home_code,
        RegionalEvent.status == "active",
        RegionalEvent.expires_at_utc > now,
    ))
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if event is None or player_state is None or event.dungeon_template_id is None:
        return RedirectResponse("/regional?error=Portal%20indispon%C3%ADvel", status_code=303)
    existing_entry = db.scalar(select(RegionalEventParticipant.id).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == player_state.id,
    ))
    if existing_entry is not None:
        return RedirectResponse("/regional?error=Esta%20guilda%20j%C3%A1%20usou%20sua%20entrada%20neste%20portal", status_code=303)
    template = db.get(DungeonTemplate, event.dungeon_template_id)
    if template is None:
        return RedirectResponse("/regional?error=Conte%C3%BAdo%20de%20portal%20indispon%C3%ADvel", status_code=303)
    try:
        event_summary = json.loads(event.summary_json or "{}")
    except (TypeError, json.JSONDecodeError):
        event_summary = {}
    boss_record = event_summary.get("portal_boss") if isinstance(event_summary, dict) else None
    boss_snapshot = boss_record.get("template") if isinstance(boss_record, dict) else None
    if not isinstance(boss_snapshot, dict) or int(boss_snapshot.get("id", -1)) != template.id:
        boss_snapshot = build_portal_boss_snapshot(template)
    form = await read_form_multi_fields(request)
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
        return _start_error_redirect(error, form, "#events-title")
    try:
        attach_event_activity(db, event, player_state, "dungeon", run.id)
    except ValueError as error:
        db.rollback()
        return _start_error_redirect(error, form, "#events-title")
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        return RedirectResponse("/regional?error=Entrada%20de%20portal%20j%C3%A1%20reservada", status_code=303)
    return RedirectResponse("/dungeons?message=Expedi%C3%A7%C3%A3o%20de%20portal%20iniciada", status_code=303)
