from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.guild_service import (
    GuildCreationError,
    create_initial_guild,
    get_current_guild_context,
)


router = APIRouter(prefix="/guild")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/create")
def create_guild_form(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _ = get_current_guild_context(db, current_user.id)
    if guild:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="guild/create.html",
        context={"current_user": current_user, "error": None, "guild_name": ""},
    )


@router.post("/create")
async def create_guild_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, _ = get_current_guild_context(db, current_user.id)
    if guild:
        return RedirectResponse("/dashboard", status_code=303)

    form = await read_form_fields(request)
    guild_name = str(form.get("name", ""))
    try:
        create_initial_guild(db=db, user_id=current_user.id, guild_name=guild_name)
    except GuildCreationError as error:
        return templates.TemplateResponse(
            request=request,
            name="guild/create.html",
            context={"current_user": current_user, "error": str(error), "guild_name": guild_name},
            status_code=400,
        )
    return RedirectResponse("/dashboard", status_code=303)
