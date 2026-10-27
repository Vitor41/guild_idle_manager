from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.dependencies import DbSession, get_current_user
from app.models.user import User
from app.services.guild_service import get_current_guild_context


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/")
def home(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    if current_user:
        guild, _ = get_current_guild_context(db, current_user.id)
        return RedirectResponse("/dashboard" if guild else "/guild/create", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "app_env": settings.app_env,
            "current_user": current_user,
            "desktop_mode": settings.app_mode == "desktop",
        },
    )
