from pathlib import Path
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.dependencies import DbSession, get_current_campaign, get_current_player
from app.core.forms import read_form_multi_fields
from app.models.campaign import CampaignMetadata
from app.models.regional import RegionalOffer
from app.models.regional import RegionalCycle
from app.models.user import User
from app.services.dungeon_service import DungeonError, start_dungeon
from app.services.gathering_service import advance_all_assignments, list_assignments
from app.services.achievement_service import get_codex_context
from app.services.guild_service import get_current_guild_context
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.mission_service import MissionError, start_mission
from app.services.regional_cycle_service import get_current_player_regional_guild, get_regional_board
from app.services.evolution_art_service import get_evolution_art_context


router = APIRouter(prefix="/regional")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


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
    return templates.TemplateResponse(
        request=request,
        name="regional/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
            "assignments": assignments,
            "reports": reports,
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
        RegionalOffer.region_code == home_code,
        RegionalOffer.status == "available",
    ))
    if offer is None:
        return RedirectResponse("/regional?error=Oferta%20indispon%C3%ADvel", status_code=303)
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    if player_state is None:
        return RedirectResponse("/regional?error=Estado%20regional%20indispon%C3%ADvel", status_code=303)
    try:
        claim_result = db.execute(
            update(RegionalOffer)
            .where(
                RegionalOffer.id == offer.id,
                RegionalOffer.status == "available",
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
    form = await read_form_multi_fields(request)
    mercenary_ids = form.get("mercenary_ids", [])
    try:
        if offer.offer_type == "contract":
            run = start_mission(
                db, guild, str(offer.mission_template_id), mercenary_ids, commit=False,
                regional_duration_seconds=offer.duration_seconds_snapshot,
            )
            run.regional_offer_id = offer.id
            run.rank_snapshot = offer.rank
            source = "missions"
        else:
            run = start_dungeon(
                db, guild, str(offer.dungeon_template_id), mercenary_ids, commit=False,
                regional_duration_seconds=offer.duration_seconds_snapshot,
            )
            run.regional_offer_id = offer.id
            run.rank_snapshot = offer.rank
            source = "dungeons"
    except (MissionError, DungeonError) as error:
        db.rollback()
        return RedirectResponse(f"/regional?error={quote(str(error))}", status_code=303)
    offer.status = "in_progress"
    offer.claimed_at_utc = run.started_at
    db.add(offer)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        return RedirectResponse("/regional?error=Oferta%20j%C3%A1%20reservada", status_code=303)
    return RedirectResponse(f"/{source}?message=Contrato%20regional%20iniciado", status_code=303)
