from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_fields
from app.models.mercenary import Mercenary
from app.models.user import User
from app.services.gathering_service import advance_all_assignments, assign_worker, list_assignments, release_worker, FAMILY_LABELS, NODE_LABELS
from app.services.guild_service import get_current_guild_context
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage


router = APIRouter(prefix="/gathering")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def gathering_index(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    advance_all_assignments(db, guild)
    db.commit()
    assignments = list_assignments(db, guild.id)
    assigned_ids = {entry.mercenary_id for entry in assignments}
    workers = list(db.scalars(
        select(Mercenary).where(Mercenary.guild_id == guild.id).order_by(Mercenary.name)
    ))
    return templates.TemplateResponse(
        request=request,
        name="gathering/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "assignments": assignments,
            "workers": [worker for worker in workers if worker.id not in assigned_ids and worker.status == "available"],
            "family_labels": FAMILY_LABELS,
            "node_labels": NODE_LABELS,
            "capacity": get_inventory_capacity(db, guild),
            "used": get_inventory_usage(db, guild.id),
            "inventory_url": "/inventory",
            "error": request.query_params.get("error"),
            "diagnostic_id": request.query_params.get("diagnostic"),
            "message": request.query_params.get("message"),
        },
    )


@router.post("/assign")
async def gathering_assign(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        assign_worker(db, guild, int(form.get("mercenary_id", "0")), form.get("resource_family", ""))
        db.commit()
    except (TypeError, ValueError) as exc:
        db.rollback()
        return RedirectResponse(f"/gathering?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/gathering?message=Designa%C3%A7%C3%A3o+iniciada.", status_code=303)


@router.post("/release/{assignment_id}")
def gathering_release(
    assignment_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        release_worker(db, guild, assignment_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/gathering?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/gathering?message=Trabalhador+liberado.", status_code=303)
