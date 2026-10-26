from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.class_change_service import (
    ClassChangeError,
    claim_class_change,
    get_class_change_page_context,
    start_class_change,
)
from app.services.guild_service import get_current_guild_context


router = APIRouter(prefix="/class-change")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def class_change_index(
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
        name="class_change/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
            **get_class_change_page_context(db, guild),
        },
    )


@router.post("/start")
async def start_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        start_class_change(db, guild, resources, form.get("mercenary_id", ""), form.get("to_class_id", ""))
    except ClassChangeError as error:
        context = get_class_change_page_context(db, guild)
        return templates.TemplateResponse(
            request=request,
            name="class_change/index.html",
            context={
                "current_user": current_user,
                "guild": guild,
                "resources": resources,
                "error": str(error),
                "message": None,
                **context,
            },
            status_code=400,
        )
    return RedirectResponse("/class-change?message=Troca de classe iniciada.", status_code=303)


@router.post("/{run_id}/claim")
def claim_submit(
    run_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        claim_class_change(db, guild, run_id)
    except ClassChangeError as error:
        context = get_class_change_page_context(db, guild)
        return templates.TemplateResponse(
            request=request,
            name="class_change/index.html",
            context={
                "current_user": current_user,
                "guild": guild,
                "resources": resources,
                "error": str(error),
                "message": None,
                **context,
            },
            status_code=400,
        )
    return RedirectResponse("/class-change?message=Classe alterada.", status_code=303)
