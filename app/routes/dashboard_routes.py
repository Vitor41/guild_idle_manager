from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.services.building_service import get_building_summary
from app.services.dungeon_service import get_dungeon_summary
from app.services.guild_service import get_current_guild_context
from app.services.inventory_service import get_inventory_summary
from app.services.mercenary_service import get_mercenary_summary
from app.services.mission_service import get_mission_summary
from app.services.tavern_service import tavern_summary


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/dashboard")
def dashboard(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    mercenary_summary = get_mercenary_summary(db, guild.id)
    mission_summary = get_mission_summary(db, guild.id)
    dungeon_summary = get_dungeon_summary(db, guild.id)
    inventory_summary = get_inventory_summary(db, guild.id)
    building_summary = get_building_summary(db, guild.id)
    tavern = tavern_summary(db, guild)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "mercenary_summary": mercenary_summary,
            "mission_summary": mission_summary,
            "dungeon_summary": dungeon_summary,
            "inventory_summary": inventory_summary,
            "building_summary": building_summary,
            "tavern_summary": tavern,
        },
    )
