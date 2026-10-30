from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.models.user import User
from app.services.guild_service import get_current_guild_context
from app.services.equipment_service import get_equipment_slot_label
from app.services.icon_service import get_item_icon, get_item_icon_path
from app.services.display_service import BONUS_ATTRIBUTE_LABELS, clean_generated_name, item_type_label, rarity_label
from app.services.inventory_service import get_equipment_for_guild, get_inventory_for_guild
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage


router = APIRouter(prefix="/inventory")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def inventory_index(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    inventory_items = get_inventory_for_guild(db, guild.id)
    for inventory_item in inventory_items:
        inventory_item.display_name = clean_generated_name(inventory_item.item_template.name)
        inventory_item.view_icon = get_item_icon(inventory_item)
        inventory_item.icon_path = get_item_icon_path(inventory_item)
        inventory_item.rarity_label = rarity_label(inventory_item.item_template.rarity)
        inventory_item.item_type_label = item_type_label(inventory_item.item_template.item_type)
    equipment_items = get_equipment_for_guild(db, guild.id)
    equipment_count = len(equipment_items)
    for item in equipment_items:
        item.display_name = clean_generated_name(item.item_template.name)
        item.view_icon = get_item_icon(item)
        item.icon_path = get_item_icon_path(item)
        item.slot_label = get_equipment_slot_label(item.equipment_slot)
        item.rarity_label = rarity_label(item.item_template.rarity)

    selected_category = request.query_params.get("category", "all")
    selected_rarity = request.query_params.get("rarity", "all")
    selected_max_level = request.query_params.get("max_level", "")
    if selected_rarity != "all":
        inventory_items = [item for item in inventory_items if item.item_template.rarity == selected_rarity]
        equipment_items = [item for item in equipment_items if item.item_template.rarity == selected_rarity]
    if selected_max_level:
        try:
            max_level = max(1, int(selected_max_level))
        except ValueError:
            max_level = 0
        inventory_items = [item for item in inventory_items if item.item_template.item_level <= max_level]
        equipment_items = [item for item in equipment_items if item.required_level <= max_level]
    if selected_category in {"weapons", "armor", "accessories"}:
        inventory_items = []
        slot_groups = {
            "weapons": {"main_hand", "off_hand", "shield", "weapon"},
            "armor": {"helmet", "chest", "gloves", "boots", "armor"},
            "accessories": {"earring", "ring", "belt", "necklace", "accessory"},
        }
        equipment_items = [item for item in equipment_items if item.equipment_slot in slot_groups[selected_category]]
    elif selected_category == "materials":
        inventory_items = [item for item in inventory_items if item.item_template.item_type == "material"]
        equipment_items = []

    return templates.TemplateResponse(
        request=request,
        name="inventory/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "inventory_items": inventory_items,
            "equipment_items": equipment_items,
            "warehouse_capacity": get_inventory_capacity(db, guild),
            "warehouse_used": get_inventory_usage(db, guild.id),
            "equipment_count": equipment_count,
            "get_item_icon": get_item_icon,
            "get_equipment_slot_label": get_equipment_slot_label,
            "selected_category": selected_category,
            "selected_rarity": selected_rarity,
            "selected_max_level": selected_max_level,
            "bonus_attribute_labels": BONUS_ATTRIBUTE_LABELS,
        },
    )
