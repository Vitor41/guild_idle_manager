from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.services.class_service import get_class_guide_context
from app.services.guild_service import get_current_guild_context


router = APIRouter(prefix="/classes")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def classes_index(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="classes/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            **get_class_guide_context(db),
        },
    )

