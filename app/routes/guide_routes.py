from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.core.game_balance import OFFLINE_CAP_SECONDS, OFFLINE_MINIMUM_SECONDS
from app.models.user import User
from app.services.building_service import get_building_bonus_summary
from app.services.guild_service import get_current_guild_context
from app.services.offline_progress_service import get_passive_gold_rate


router = APIRouter(prefix="/guide")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def game_guide(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="guide/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "idle_rate": get_passive_gold_rate(db, guild),
            "offline_minimum_minutes": OFFLINE_MINIMUM_SECONDS // 60,
            "offline_cap_hours": OFFLINE_CAP_SECONDS // 3600,
            "building_bonuses": get_building_bonus_summary(db, guild.id),
        },
    )
