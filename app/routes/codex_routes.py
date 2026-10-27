from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.services.achievement_service import AchievementError, claim_achievement, get_codex_context
from app.services.guild_service import get_current_guild_context


router = APIRouter(prefix="/codex")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def codex_index(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    return templates.TemplateResponse(request=request, name="codex/index.html", context={
        "current_user": current_user, "guild": guild, "resources": resources,
        "message": request.query_params.get("message"), "error": request.query_params.get("error"),
        **get_codex_context(db, guild, True, request.query_params.get("category", "all")),
    })


@router.post("/achievements/{achievement_id}/claim")
def claim(achievement_id: int, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        reward = claim_achievement(db, guild, resources, achievement_id)
    except AchievementError as error:
        return RedirectResponse(f"/codex?error={quote(str(error))}", status_code=303)
    parts = []
    if reward["gold"]:
        parts.append(f"{reward['gold']} ouro")
    if reward["xp"]:
        parts.append(f"{reward['xp']} XP de guilda")
    return RedirectResponse(f"/codex?message={quote('Recompensa coletada: ' + ' e '.join(parts) + '.')}", status_code=303)
