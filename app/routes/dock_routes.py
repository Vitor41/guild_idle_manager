from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.dock_service import DockError, buy_dock_offer, get_docks_context
from app.services.guild_service import get_current_guild_context
from app.services.display_service import clean_generated_name, rarity_label


MERCHANT_TYPE_LABELS = {
    "wood": "Madeiras", "ore": "Minérios", "herb": "Ervas", "gem": "Gemas",
    "leather": "Couros", "cloth": "Tecidos", "relic": "Relíquias", "essence": "Essências",
    "forge": "Forja", "armor": "Armaduras", "rare": "Colecionáveis raros",
    "smuggler": "Contrabando", "guild": "Emissário de guilda",
}


router = APIRouter(prefix="/docks")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def docks_index(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        dock_context = get_docks_context(db, guild)
        error = request.query_params.get("error")
    except DockError as exc:
        dock_context = {"dock_level": 0, "rotation": None, "offer_slots": 0, "now": None}
        error = str(exc)
    return templates.TemplateResponse(request=request, name="docks/index.html", context={
        "current_user": current_user, "guild": guild, "resources": resources,
        "message": request.query_params.get("message"), "error": error,
        "merchant_type_labels": MERCHANT_TYPE_LABELS, "rarity_label": rarity_label,
        "clean_generated_name": clean_generated_name, **dock_context,
    })


@router.post("/offers/{offer_id}/buy")
async def buy(offer_id: int, request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None or resources is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        buy_dock_offer(db, guild, resources, offer_id, int(form.get("quantity", "1")))
    except (ValueError, DockError) as error:
        return RedirectResponse(f"/docks?error={quote(str(error))}", status_code=303)
    return RedirectResponse("/docks?message=Compra%20concluida.", status_code=303)
