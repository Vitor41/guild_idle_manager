from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.guild_service import get_current_guild_context
from app.services.equipment_service import get_equipment_slot_label
from app.services.icon_service import get_item_icon, get_slot_icon
from app.services.mercenary_service import (
    MercenaryDismissalError,
    MercenaryEquipmentError,
    dismiss_mercenary,
    equip_mercenary_item,
    get_mercenary_detail_context,
    get_mercenaries_page_context,
    unequip_mercenary_item,
)


router = APIRouter(prefix="/mercenaries")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
templates.env.globals.update(
    get_equipment_slot_label=get_equipment_slot_label,
    get_item_icon=get_item_icon,
    get_slot_icon=get_slot_icon,
)


@router.get("")
def mercenaries_index(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    context = get_mercenaries_page_context(
        db,
        guild,
        resources,
        request.query_params.get("sort", "power"),
    )
    return templates.TemplateResponse(
        request=request,
        name="mercenaries/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "error": None,
            "message": request.query_params.get("message"),
            "form": {},
            **context,
        },
    )


@router.post("/recruit")
async def recruit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    return RedirectResponse("/tavern", status_code=303)


@router.get("/{mercenary_id}")
def mercenary_detail(
    mercenary_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    context = get_mercenary_detail_context(db, guild, mercenary_id)
    if context is None:
        return RedirectResponse("/mercenaries", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="mercenaries/detail.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
            **context,
        },
    )


@router.post("/{mercenary_id}/equip")
async def equip(
    mercenary_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    form = await read_form_fields(request)
    try:
        equip_mercenary_item(db, guild, mercenary_id, form.get("item_instance_id", ""))
    except MercenaryEquipmentError as error:
        context = get_mercenary_detail_context(db, guild, mercenary_id)
        if context is None:
            return RedirectResponse("/mercenaries", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="mercenaries/detail.html",
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

    return RedirectResponse(f"/mercenaries/{mercenary_id}?message=Equipamento equipado.", status_code=303)


@router.post("/{mercenary_id}/unequip")
async def unequip(
    mercenary_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    form = await read_form_fields(request)
    try:
        unequip_mercenary_item(db, guild, mercenary_id, form.get("item_instance_id", ""))
    except MercenaryEquipmentError as error:
        context = get_mercenary_detail_context(db, guild, mercenary_id)
        if context is None:
            return RedirectResponse("/mercenaries", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="mercenaries/detail.html",
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

    return RedirectResponse(f"/mercenaries/{mercenary_id}?message=Equipamento removido.", status_code=303)


@router.post("/{mercenary_id}/dismiss")
def dismiss(
    mercenary_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    try:
        refund = dismiss_mercenary(db, guild, resources, mercenary_id)
    except MercenaryDismissalError as error:
        context = get_mercenary_detail_context(db, guild, mercenary_id)
        if context is None:
            return RedirectResponse("/mercenaries", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="mercenaries/detail.html",
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

    return RedirectResponse(f"/mercenaries?message=Mercenario demitido. Reembolso: {refund} ouro.", status_code=303)
