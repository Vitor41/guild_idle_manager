from pathlib import Path
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.core.forms import read_form_fields
from app.models.user import User
from app.models.campaign import CampaignMetadata
from app.services.guild_service import get_current_guild_context
from app.services.tavern_service import (
    TavernError,
    generate_apprentice_preview,
    get_tavern_page_context,
    hire_apprentice,
    hire_apprentices_bulk,
    hire_special_offer,
    is_valid_apprentice_preview,
    manually_refresh_special_offer,
)


router = APIRouter(prefix="/tavern")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _get_apprentice_preview(request: Request, db: DbSession, current_user, config, tavern_level):
    if request.app.state.app_mode == "desktop":
        metadata = db.get(CampaignMetadata, current_user.id)
        try:
            preview = json.loads(metadata.apprentice_preview) if metadata and metadata.apprentice_preview else None
        except json.JSONDecodeError:
            preview = None
    else:
        preview = request.session.get("apprentice_preview")
    if not is_valid_apprentice_preview(preview, config, tavern_level) or "progression_bonus_percent" not in preview:
        preview = generate_apprentice_preview(config, tavern_level)
        _set_apprentice_preview(request, db, current_user, preview)
    return preview


def _set_apprentice_preview(request: Request, db: DbSession, current_user, preview) -> None:
    if request.app.state.app_mode == "desktop":
        metadata = db.get(CampaignMetadata, current_user.id)
        if metadata is not None:
            metadata.apprentice_preview = json.dumps(preview, separators=(",", ":")) if preview else None
            db.commit()
    elif preview is None:
        request.session.pop("apprentice_preview", None)
    else:
        request.session["apprentice_preview"] = preview


def build_tavern_page_context(request: Request, db: DbSession, guild, resources, current_user) -> dict[str, object]:
    context = get_tavern_page_context(db, guild, resources)
    if context["tavern_level"] < 1:
        return context
    preview = _get_apprentice_preview(request, db, current_user, context["config"], context["tavern_level"])
    context["apprentice_preview"] = preview
    return context


@router.get("")
def tavern_index(
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
        name="tavern/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
            **build_tavern_page_context(request, db, guild, resources, current_user),
        },
    )


@router.post("/hire-apprentice")
async def hire_apprentice_submit(
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
        tavern_context = get_tavern_page_context(db, guild, resources)
        preview = _get_apprentice_preview(
            request, db, current_user, tavern_context["config"], tavern_context["tavern_level"]
        )
        hire_apprentice(
            db,
            guild,
            resources,
            form.get("name", ""),
            preview,
        )
    except TavernError as error:
        context = build_tavern_page_context(request, db, guild, resources, current_user)
        return templates.TemplateResponse(
            request=request,
            name="tavern/index.html",
            context={
                "current_user": current_user,
                "guild": guild,
                "error": str(error),
                "message": None,
                **context,
            },
            status_code=400,
        )
    _set_apprentice_preview(request, db, current_user, None)
    return RedirectResponse("/tavern?message=Aprendiz contratado.", status_code=303)


@router.post("/hire-apprentices-bulk")
async def hire_apprentices_bulk_submit(
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
        hire_apprentices_bulk(db, guild, resources, 10)
    except TavernError as error:
        context = build_tavern_page_context(request, db, guild, resources, current_user)
        return templates.TemplateResponse(
            request=request,
            name="tavern/index.html",
            context={
                "current_user": current_user,
                "guild": guild,
                "error": str(error),
                "message": None,
                **context,
            },
            status_code=400,
        )
    return RedirectResponse("/tavern?message=10 Aprendizes contratados.", status_code=303)


@router.post("/refresh-special")
def refresh_special_submit(
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
        offer = manually_refresh_special_offer(db, guild, resources)
    except TavernError as error:
        context = build_tavern_page_context(request, db, guild, resources)
        return templates.TemplateResponse(
            request=request,
            name="tavern/index.html",
            context={
                "current_user": current_user,
                "guild": guild,
                "error": str(error),
                "message": None,
                **context,
            },
            status_code=400,
        )
    message = "Novo visitante especial encontrado." if offer else "A renovação não encontrou visitante especial."
    return RedirectResponse(f"/tavern?message={quote(message)}", status_code=303)


@router.post("/hire-special")
async def hire_special_submit(
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
        hire_special_offer(db, guild, resources, form.get("offer_id", ""))
    except TavernError as error:
        context = build_tavern_page_context(request, db, guild, resources)
        return templates.TemplateResponse(
            request=request,
            name="tavern/index.html",
            context={
                "current_user": current_user,
                "guild": guild,
                "error": str(error),
                "message": None,
                **context,
            },
            status_code=400,
        )
    return RedirectResponse("/tavern?message=Mercenario especial contratado.", status_code=303)
