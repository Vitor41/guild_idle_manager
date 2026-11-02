from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.services.guild_service import get_current_guild_context
from app.services.workshop_service import WorkshopError, craft_supply_kit, get_supply_workshop_context

router = APIRouter(prefix="/workshops")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def workshops_index(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    context = get_supply_workshop_context(db, guild)
    db.commit()
    return templates.TemplateResponse(request=request, name="workshops/index.html", context={
        "current_user": current_user, "guild": guild, **context,
        "message": request.query_params.get("message", ""), "error": request.query_params.get("error", ""),
    })


@router.post("/supply/craft")
def craft_supply_route(db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        craft_supply_kit(db, guild)
        db.commit()
    except WorkshopError as exc:
        db.rollback()
        return RedirectResponse(f"/workshops?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/workshops?message=Kit%20de%20Suprimentos%20fabricado.", status_code=303)
