from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.models.building_reset import GuildBuildingReset
from app.services.building_service import (
    BuildingError,
    ensure_guild_buildings,
    get_effect_label,
    get_building_benefit,
    get_upgrade_cost,
    upgrade_guild_building,
)
from app.services.guild_service import get_current_guild_context
from app.services.building_reset_service import (
    BuildingResetError,
    get_building_reset_preview,
    perform_building_reset,
)
from app.services.icon_service import get_building_icon


router = APIRouter(prefix="/buildings")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
templates.env.globals.update(get_building_icon=get_building_icon)


@router.get("")
def buildings_index(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    reset_preview_requested = request.query_params.get("reset_preview") == "1"
    guild, resources = get_current_guild_context(
        db, current_user.id, sync_resources=not reset_preview_requested,
    )
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    reset_preview = None
    if reset_preview_requested:
        reset_preview = get_building_reset_preview(db, guild.id)
        buildings = reset_preview["buildings"]
    else:
        buildings = ensure_guild_buildings(db, guild.id)
    reset_id_raw = request.query_params.get("reset_id", "")
    try:
        reset_id = int(reset_id_raw)
    except (TypeError, ValueError):
        reset_id = None
    for building in buildings:
        building.view_icon = get_building_icon(building.building_template.effect_type)
        building.next_required_guild_level = max(
            building.building_template.required_guild_level,
            (building.level + 2) // 2,
        )
        building.benefit = get_building_benefit(building.building_template.effect_type, building.level)
    return templates.TemplateResponse(
        request=request,
        name="buildings/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "buildings": buildings,
            "get_effect_label": get_effect_label,
            "get_upgrade_cost": get_upgrade_cost,
            "get_building_icon": get_building_icon,
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
            "reset_preview": reset_preview,
            "reset_result": db.scalar(select(GuildBuildingReset).where(
                GuildBuildingReset.guild_id == guild.id,
                GuildBuildingReset.id == reset_id,
            )) if reset_id else None,
        },
    )


@router.post("/{building_id}/upgrade")
def upgrade(
    building_id: int,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    try:
        upgrade_guild_building(db, guild, resources, building_id)
    except BuildingError as error:
        return RedirectResponse(f"/buildings?error={quote(str(error))}", status_code=303)

    return RedirectResponse("/buildings?message=Construcao%20evoluida.", status_code=303)


@router.post("/reset")
def reset_buildings(
    db: DbSession,
    expected_fingerprint: str = Form(...),
    idempotency_key: str = Form(...),
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, _resources = get_current_guild_context(db, current_user.id, sync_resources=False)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    try:
        reset = perform_building_reset(
            db,
            guild.id,
            expected_fingerprint=expected_fingerprint,
            idempotency_key=idempotency_key,
        )
    except BuildingResetError as error:
        db.rollback()
        return RedirectResponse(
            f"/buildings?reset_preview=1&error={quote(str(error))}", status_code=303,
        )
    return RedirectResponse(f"/buildings?reset_id={reset.id}", status_code=303)
