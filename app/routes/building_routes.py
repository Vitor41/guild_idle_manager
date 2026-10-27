from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.services.building_service import (
    BuildingError,
    ensure_guild_buildings,
    get_effect_label,
    get_building_benefit,
    get_upgrade_cost,
    upgrade_guild_building,
)
from app.services.guild_service import get_current_guild_context
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

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    buildings = ensure_guild_buildings(db, guild.id)
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
