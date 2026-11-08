from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_fields
from app.desktop.gameplay_diagnostics import log_gameplay_action, log_gathering_advancement
from app.models.mercenary import Mercenary
from app.models.user import User
from app.services.gathering_service import advance_all_assignments, assign_worker, get_inventory_quantity_by_family, list_assignments, preview_material_for_family, release_worker, FAMILY_LABELS, NODE_LABELS
from app.services.guild_service import get_current_guild_context
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage


router = APIRouter(prefix="/gathering")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/status")
def gathering_live_status(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return JSONResponse({"error": "session_expired"}, status_code=401)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return JSONResponse({"error": "guild_missing"}, status_code=409)

    advancement = advance_all_assignments(db, guild)
    log_gathering_advancement(
        route=request.url.path,
        diagnostic_id=getattr(request.state, "diagnostic_id", ""),
        advancement=advancement,
    )
    db.commit()
    assignments = list_assignments(db, guild.id)
    return JSONResponse({
        "warehouse": {
            "used": get_inventory_usage(db, guild.id),
            "capacity": get_inventory_capacity(db, guild),
        },
        "inventory_by_family": get_inventory_quantity_by_family(db, guild.id),
        "assignments": {
            assignment.resource_family: {
                "progress_seconds": assignment.progress_seconds,
                "capacity_paused": assignment.capacity_paused,
                "worker": assignment.mercenary.name,
                "target_item_template_id": assignment.target_item_template_id,
                "target_item_name": assignment.target_item_template.name if assignment.target_item_template else None,
                "target_item_rarity": assignment.target_item_template.rarity if assignment.target_item_template else None,
            }
            for assignment in assignments
        },
        "advanced": {
            family: {"cycles": result.get("cycles", 0), "stored": result.get("stored", 0)}
            for family, result in advancement.items()
        },
    })


def _log_gathering(request: Request, event: str, outcome: str, status_code: int = 200) -> None:
    log_gameplay_action(
        action="gathering.production",
        route=request.url.path,
        diagnostic_id=getattr(request.state, "diagnostic_id", ""),
        status_code=status_code,
        outcome=outcome,
        event=event,
    )


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
    advancement = advance_all_assignments(db, guild)
    log_gathering_advancement(
        route=request.url.path,
        diagnostic_id=getattr(request.state, "diagnostic_id", ""),
        advancement=advancement,
    )
    db.commit()
    assignments = list_assignments(db, guild.id)
    material_previews = {
        family: preview_material_for_family(db, family, guild.level)
        for family in FAMILY_LABELS
    }
    for material in material_previews.values():
        if material is not None:
            material.rarity_label = {
                "common": "Comum", "uncommon": "Incomum", "rare": "Raro",
                "epic": "Épico", "legendary": "Lendário", "mythic": "Mítico",
            }.get(material.rarity, material.rarity)
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
            "material_previews": material_previews,
            "workers": [worker for worker in workers if worker.id not in assigned_ids and worker.status == "available"],
            "family_labels": FAMILY_LABELS,
            "node_labels": NODE_LABELS,
            "capacity": get_inventory_capacity(db, guild),
            "used": get_inventory_usage(db, guild.id),
            "inventory_by_family": get_inventory_quantity_by_family(db, guild.id),
            "inventory_url": "/inventory",
            "error": request.query_params.get("error"),
            "diagnostic_id": request.query_params.get("diagnostic"),
            "message": request.query_params.get("message"),
            "catalog_errors": [FAMILY_LABELS[family] for family, result in advancement.items() if result.get("catalog_missing")],
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
        target_quantity = int(form["target_quantity"]) if form.get("target_quantity", "").strip() else None
        family = form.get("resource_family", "")
        assignment = assign_worker(db, guild, int(form.get("mercenary_id", "0")), family, target_quantity=target_quantity)
        db.commit()
        _log_gathering(request, "assignment", f"family={family} assignment_id={assignment.id} target={target_quantity or 'continuous'}")
    except (TypeError, ValueError) as exc:
        db.rollback()
        _log_gathering(request, "assignment_rejected", f"reason={exc}", 400)
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
        summary = release_worker(db, guild, assignment_id)
        db.commit()
        _log_gathering(
            request, "release",
            f"assignment_id={assignment_id} cycles={summary['cycles']} produced={summary['produced']} "
            f"stored={summary['stored']} discarded={summary['discarded']} "
            f"warehouse={summary['used']}/{summary['capacity']}",
        )
    except ValueError as exc:
        db.rollback()
        _log_gathering(request, "release_rejected", f"assignment_id={assignment_id} reason={exc}", 400)
        return RedirectResponse(f"/gathering?error={quote(str(exc))}", status_code=303)
    message = f"Trabalhador liberado. Coleta encerrada: {summary['stored']} unidade(s) armazenada(s)."
    return RedirectResponse(f"/gathering?message={quote(message)}", status_code=303)
