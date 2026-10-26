from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.crafting_service import CraftingError, craft_recipe, get_blacksmith_context, refine_equipment
from app.services.guild_service import get_current_guild_context
from app.services.icon_service import get_item_icon_path
from app.services.display_service import clean_generated_name, rarity_label
from app.services.salvage_service import SalvageError, collect_salvage, get_salvage_context, start_salvage


router = APIRouter(prefix="/blacksmith")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def blacksmith_index(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    context = get_blacksmith_context(db, guild)
    salvage_context = get_salvage_context(db, guild, context["blacksmith_level"])
    for recipe in context["recipes"]:
        recipe.icon_path = get_item_icon_path(recipe.output_item_template)
    for item in context["equipment_items"]:
        item.icon_path = get_item_icon_path(item)
        item.display_name = clean_generated_name(item.item_template.name)
    for group in salvage_context["salvage_equipment_groups"]:
        group["icon_path"] = get_item_icon_path(group["item_template"])
    for slot in salvage_context["salvage_slots"]:
        job = slot["job"]
        if job:
            job.icon_path = get_item_icon_path(job.item_template)
            job.item_display_name = clean_generated_name(job.item_template.name)
            job.material_display_name = clean_generated_name(job.material_template.name)
    for job in salvage_context["salvage_history"]:
        job.item_display_name = clean_generated_name(job.item_template.name)
        job.material_display_name = clean_generated_name(job.material_template.name)
    return templates.TemplateResponse(request=request, name="blacksmith/index.html", context={
        "current_user": current_user, "guild": guild, "resources": resources,
        "message": request.query_params.get("message"), "error": request.query_params.get("error"),
        "rarity_label": rarity_label, **context, **salvage_context,
    })


@router.post("/craft")
async def craft(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        message = craft_recipe(db, guild, resources, form.get("recipe_id", ""))
    except CraftingError as error:
        return RedirectResponse(f"/blacksmith?error={quote(str(error))}", status_code=303)
    return RedirectResponse(f"/blacksmith?message={quote(message)}", status_code=303)


@router.post("/salvage/start")
async def salvage_start(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        job = start_salvage(
            db, guild, resources,
            form.get("slot_number", ""),
            form.get("item_template_id", ""),
            form.get("quantity", ""),
        )
    except SalvageError as error:
        return RedirectResponse(f"/blacksmith?error={quote(str(error))}#salvage", status_code=303)
    message = f"Desmontagem iniciada no espaço {job.slot_number}."
    return RedirectResponse(f"/blacksmith?message={quote(message)}#salvage", status_code=303)


@router.post("/salvage/collect")
async def salvage_collect_route(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        job = collect_salvage(db, guild, form.get("job_id", ""))
    except SalvageError as error:
        return RedirectResponse(f"/blacksmith?error={quote(str(error))}#salvage", status_code=303)
    material_name = clean_generated_name(job.material_template.name)
    message = f"Desmontagem concluída: {job.result_quantity}x {material_name}."
    return RedirectResponse(f"/blacksmith?message={quote(message)}#salvage", status_code=303)


@router.post("/refine")
async def refine(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        result = refine_equipment(db, guild, resources, form.get("item_instance_id", ""))
    except CraftingError as error:
        return RedirectResponse(f"/blacksmith?error={quote(str(error))}", status_code=303)
    message = f"{result['name']} refinado para +{result['level']}. Poder {result['before']} -> {result['after']}."
    return RedirectResponse(f"/blacksmith?message={quote(message)}", status_code=303)
