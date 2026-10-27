from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm.attributes import set_committed_value

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.display_service import clean_generated_name, rarity_label
from app.services.guild_service import get_current_guild_context
from app.services.icon_service import get_item_icon_path
from app.services.market_service import (
    MarketError,
    collect_all_ready_market_sales,
    collect_market_sale,
    get_market_page_context,
    start_equipment_sale,
    start_material_sale,
)


router = APIRouter(prefix="/market")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def market_index(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    context = get_market_page_context(db, guild)
    for item in [*context["inventory_items"], *context["equipment_items"]]:
        item.icon_path = get_item_icon_path(item)
        item.rarity_label = rarity_label(item.item_template.rarity)
        set_committed_value(item.item_template, "name", clean_generated_name(item.item_template.name))
    for sale in [*context["active_sales"], *context["completed_sales"]]:
        set_committed_value(sale.item_template, "name", clean_generated_name(sale.item_template.name))
    return templates.TemplateResponse(request=request, name="market/index.html", context={
        "current_user": current_user, "guild": guild, "resources": resources,
        "message": request.query_params.get("message"), "error": request.query_params.get("error"), **context,
    })


@router.post("/sell/material")
async def sell_material(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        start_material_sale(db, guild, form.get("item_template_id", ""), form.get("quantity", "1"))
    except MarketError as error:
        return RedirectResponse(f"/market?error={quote(str(error))}", status_code=303)
    return RedirectResponse("/market?message=Item%20anunciado.", status_code=303)


@router.post("/sell/equipment")
async def sell_equipment(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        start_equipment_sale(db, guild, form.get("item_instance_id", ""))
    except MarketError as error:
        return RedirectResponse(f"/market?error={quote(str(error))}", status_code=303)
    return RedirectResponse("/market?message=Equipamento%20anunciado.", status_code=303)


@router.post("/collect-all")
def collect_all(db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        result = collect_all_ready_market_sales(db, guild, resources)
    except MarketError as error:
        return RedirectResponse(f"/market?error={quote(str(error))}", status_code=303)
    message = quote(f"{result['count']} vendas coletadas: {result['gold']} ouro.")
    return RedirectResponse(f"/market?message={message}", status_code=303)


@router.post("/{sale_id}/collect")
def collect(sale_id: int, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        sale = collect_market_sale(db, guild, resources, sale_id)
    except MarketError as error:
        return RedirectResponse(f"/market?error={quote(str(error))}", status_code=303)
    return RedirectResponse(f"/market?message=Venda%20coletada:%20{sale.total_value}%20ouro.", status_code=303)
