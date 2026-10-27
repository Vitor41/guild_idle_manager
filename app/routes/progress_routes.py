from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.services.building_service import ensure_guild_buildings, get_building_bonus_summary, get_building_summary
from app.services.guild_progression_service import GUILD_MAX_LEVEL, guild_xp_required_for_level
from app.services.guild_service import get_current_guild_context


router = APIRouter(prefix="/guild/progress")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def guild_progress(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    buildings = ensure_guild_buildings(db, guild.id)
    return templates.TemplateResponse(request=request, name="guild/progress.html", context={
        "current_user": current_user, "guild": guild, "resources": resources, "buildings": buildings,
        "building_summary": get_building_summary(db, guild.id),
        "bonuses": get_building_bonus_summary(db, guild.id),
        "xp_required": guild_xp_required_for_level(guild.level), "guild_max_level": GUILD_MAX_LEVEL,
    })
