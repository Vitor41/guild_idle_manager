from datetime import datetime, timezone
from math import ceil
from random import Random

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.time import prepare_timer_context

from app.core.game_balance import BLACKSMITH_REFINE_LEVEL, REFINE_BASE_GOLD_COST, REFINE_BASE_ORE_COST, REFINE_RARITY_CAPS
from app.models.crafting import CraftingRecipeMaterial
from app.models.dock import MerchantOfferTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import ItemTemplate
from app.repositories.crafting_repository import create_recipe, get_active_recipe, get_recipe_by_name, list_active_recipes
from app.repositories.item_repository import (
    get_inventory_item,
    get_item_instance_by_guild,
    get_item_template_by_name,
    list_item_instances_by_guild,
    remove_inventory_quantity,
    consume_inventory_resource,
    sync_inventory_resource_totals,
)
from app.services.building_service import get_building_level
from app.services.building_balance_service import docks_values
from app.services.economy_pricing_service import effective_crafting_gold_cost, effective_dock_unit_price
from app.services.salvage_service import _select_salvage_material
from app.services.equipment_service import create_equipment_instance_from_template, get_item_power_score
from app.services.guild_progression_service import add_guild_xp
from app.services.inventory_capacity_service import add_inventory_quantity_capped, get_inventory_capacity, get_inventory_usage
from app.services.achievement_service import record_guild_stat, unlock_codex_reference
from app.services.display_service import clean_generated_name


INITIAL_RECIPES = [
    ("Forjar Espada de Ferro", "Espada de Ferro", 1, 100, [("Fragmento de Minerio", 5), ("Madeira Rustica", 2)]),
    ("Forjar Armadura Reforcada", "Armadura Reforcada", 3, 180, [("Pele de Lobo", 8), ("Fragmento de Minerio", 6)]),
    ("Criar Amuleto do Cacador", "Amuleto do Cacador", 5, 250, [("Garra de Lobo", 3), ("Erva Medicinal", 2)]),
]

RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
RARITY_UNLOCK_LEVEL = {
    "common": 1,
    "uncommon": 5,
    "rare": 15,
    "epic": 25,
    "legendary": 40,
    "mythic": 50,
}
GENERATED_RECIPES_PER_RARITY = 12


class CraftingError(ValueError):
    pass


def seed_crafting_recipes(db: Session) -> None:
    changed = False
    for name, output_name, blacksmith_level, gold_cost, materials in INITIAL_RECIPES:
        if get_recipe_by_name(db, name):
            continue
        output = get_item_template_by_name(db, output_name)
        material_templates = [(get_item_template_by_name(db, item_name), quantity) for item_name, quantity in materials]
        if output is None or any(item is None for item, _ in material_templates):
            continue
        recipe = create_recipe(db, {
            "name": name,
            "description": f"Produz {output_name} usando materiais da guilda.",
            "output_item_template_id": output.id,
            "output_quantity": 1,
            "gold_cost": gold_cost,
            "required_blacksmith_level": blacksmith_level,
            "is_active": True,
        })
        db.flush()
        for item, quantity in material_templates:
            db.add(CraftingRecipeMaterial(recipe_id=recipe.id, item_template_id=item.id, quantity=quantity))
        changed = True
    equipment_by_rarity = {
        rarity: list(db.scalars(
            select(ItemTemplate).where(
                ItemTemplate.item_type == "equipment",
                ItemTemplate.rarity == rarity,
                ItemTemplate.is_active.is_(True),
            ).order_by(ItemTemplate.item_level, ItemTemplate.tier, ItemTemplate.id)
        ))
        for rarity in RARITY_ORDER
    }
    materials = list(db.scalars(
        select(ItemTemplate).where(
            ItemTemplate.item_type == "material",
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.tier, ItemTemplate.id)
    ))
    existing_output_ids = {
        recipe.output_item_template_id for recipe in list_active_recipes(db)
    }
    for rarity_index, rarity in enumerate(RARITY_ORDER):
        candidates = equipment_by_rarity[rarity]
        if not candidates or not materials:
            continue
        step = max(1, len(candidates) // GENERATED_RECIPES_PER_RARITY)
        selected: list[ItemTemplate] = []
        used_names: set[str] = set()
        for candidate in candidates[::step]:
            display_name = clean_generated_name(candidate.name)
            if candidate.id in existing_output_ids or display_name in used_names:
                continue
            selected.append(candidate)
            used_names.add(display_name)
            if len(selected) >= GENERATED_RECIPES_PER_RARITY:
                break
        for index, output in enumerate(selected):
            recipe_name = f"Forjar {clean_generated_name(output.name)}"[:120]
            if get_recipe_by_name(db, recipe_name):
                continue
            required_level = max(
                RARITY_UNLOCK_LEVEL[rarity],
                min(50, ceil(max(1, output.item_level) / 7)),
            )
            if rarity == "common" and index < 3:
                required_level = 1
            recipe = create_recipe(db, {
                "name": recipe_name,
                "description": f"Produz {clean_generated_name(output.name)} na oficina da guilda.",
                "output_item_template_id": output.id,
                "output_quantity": 1,
                "gold_cost": max(80, 55 * max(1, output.tier) * (rarity_index + 1)),
                "required_blacksmith_level": required_level,
                "is_active": True,
            })
            db.flush()
            material_pool = [material for material in materials if material.tier <= max(1, output.tier)] or materials
            first = material_pool[(output.id + index) % len(material_pool)]
            second = material_pool[(output.id + index + max(1, len(material_pool) // 3)) % len(material_pool)]
            if second.id == first.id and len(material_pool) > 1:
                second = material_pool[(material_pool.index(first) + 1) % len(material_pool)]
            quantity_base = max(2, output.tier + rarity_index + 1)
            db.add(CraftingRecipeMaterial(recipe_id=recipe.id, item_template_id=first.id, quantity=quantity_base))
            if second.id != first.id:
                db.add(CraftingRecipeMaterial(recipe_id=recipe.id, item_template_id=second.id, quantity=max(1, quantity_base // 2)))
            existing_output_ids.add(output.id)
            changed = True
    if changed:
        db.commit()


def get_blacksmith_rotation_rules(level: int, now: datetime | None = None) -> dict[str, object]:
    now = now or datetime.now(timezone.utc)
    if level < 1:
        return {
            "slots": 0,
            "duration_hours": 0,
            "max_rarity": "common",
            "ends_at": None,
        }
    if level >= 50:
        duration_hours = 4
    elif level >= 45:
        duration_hours = 6
    elif level >= 35:
        duration_hours = 8
    elif level >= 25:
        duration_hours = 12
    elif level >= 15:
        duration_hours = 18
    else:
        duration_hours = 24
    max_rarity = max(
        (rarity for rarity in RARITY_ORDER if level >= RARITY_UNLOCK_LEVEL[rarity]),
        key=RARITY_ORDER.index,
    )
    duration_seconds = duration_hours * 3600
    bucket = int(now.timestamp()) // duration_seconds
    ends_at = datetime.fromtimestamp((bucket + 1) * duration_seconds, tz=timezone.utc)
    return {
        "slots": min(8, 3 + level // 10),
        "duration_hours": duration_hours,
        "max_rarity": max_rarity,
        "ends_at": ends_at,
        "bucket": bucket,
    }


def list_rotating_recipes(
    db: Session,
    guild: Guild,
    blacksmith_level: int,
    now: datetime | None = None,
) -> tuple[list, dict[str, object]]:
    rules = get_blacksmith_rotation_rules(blacksmith_level, now)
    if blacksmith_level < 1:
        return [], rules
    maximum_rarity_index = RARITY_ORDER.index(str(rules["max_rarity"]))
    eligible = [
        recipe for recipe in list_active_recipes(db)
        if recipe.required_blacksmith_level <= blacksmith_level
        and RARITY_ORDER.index(recipe.output_item_template.rarity) <= maximum_rarity_index
    ]
    randomizer = Random(f"blacksmith:{guild.id}:{rules['bucket']}:{blacksmith_level}")
    highest_rarity = str(rules["max_rarity"])
    featured = [
        recipe for recipe in eligible
        if recipe.output_item_template.rarity == highest_rarity
    ]
    randomizer.shuffle(featured)
    randomizer.shuffle(eligible)
    selected = featured[:1]
    selected.extend(
        recipe for recipe in eligible
        if recipe.id not in {selected_recipe.id for selected_recipe in selected}
    )
    return selected[:int(rules["slots"])], rules


def get_blacksmith_context(db: Session, guild: Guild) -> dict[str, object]:
    blacksmith_level = get_building_level(db, guild.id, "blacksmith")
    recipes, rotation = list_rotating_recipes(db, guild, blacksmith_level)
    docks_level = get_building_level(db, guild.id, "docks")
    for recipe in recipes:
        recipe.effective_gold_cost = _effective_recipe_gold_cost(db, recipe, docks_level)
    if rotation is not None and rotation.get("ends_at") is not None:
        prepare_timer_context(rotation, datetime.now(timezone.utc))
    for recipe in recipes:
        recipe.material_status = []
        for material in recipe.materials:
            owned = get_inventory_item(db, guild.id, material.item_template_id)
            recipe.material_status.append({
                "material": material,
                "display_name": clean_generated_name(material.item_template.name),
                "owned": owned.quantity if owned else 0,
            })
    equipment = [] if blacksmith_level < BLACKSMITH_REFINE_LEVEL else [
        item for item in list_item_instances_by_guild(db, guild.id) if item.market_sale is None
    ]
    for item in equipment:
        item.current_power = get_item_power_score(item)
        item.refine_cap = REFINE_RARITY_CAPS.get(item.item_template.rarity, 3)
        item.refine_gold_cost = REFINE_BASE_GOLD_COST * (item.upgrade_level + 1) * max(1, item.item_template.tier)
        item.refine_ore_cost = REFINE_BASE_ORE_COST * (item.upgrade_level + 1)
        item.next_power = item.current_power + max(1, sum(1 for key in ("power", "vitality", "agility", "intelligence", "luck", "armor") if getattr(item, f"bonus_{key}") > 0))
    return {
        "recipes": recipes,
        "equipment_items": equipment,
        "blacksmith_level": blacksmith_level,
        "rotation": rotation,
        "refine_unlock_level": BLACKSMITH_REFINE_LEVEL,
    }


def craft_recipe(db: Session, guild: Guild, resources: GuildResources | None, recipe_id: str) -> str:
    if resources is None:
        raise CraftingError("Recursos da guilda indisponiveis.")
    try:
        parsed_id = int(recipe_id)
    except ValueError as exc:
        raise CraftingError("Receita invalida.") from exc
    recipe = get_active_recipe(db, parsed_id)
    if recipe is None:
        raise CraftingError("Receita indisponivel.")
    blacksmith_level = get_building_level(db, guild.id, "blacksmith")
    if blacksmith_level < 1:
        raise CraftingError("Construa o Ferreiro no nível 1 antes de fabricar equipamentos.")
    rotating_recipes, _ = list_rotating_recipes(db, guild, blacksmith_level)
    if recipe.id not in {active_recipe.id for active_recipe in rotating_recipes}:
        raise CraftingError("Esta receita não faz mais parte da rotação atual.")
    if blacksmith_level < recipe.required_blacksmith_level:
        raise CraftingError("Nivel do Ferreiro insuficiente para esta receita.")
    gold_cost = _effective_recipe_gold_cost(db, recipe, get_building_level(db, guild.id, "docks"))
    if resources.gold < gold_cost:
        raise CraftingError("Ouro insuficiente para fabricar este item.")
    owned_materials = []
    for material in recipe.materials:
        owned = get_inventory_item(db, guild.id, material.item_template_id)
        if owned is None or owned.quantity < material.quantity:
            raise CraftingError(f"Material insuficiente: {material.item_template.name}.")
        owned_materials.append((owned, material.quantity))
    resources.gold -= gold_cost
    for owned, quantity in owned_materials:
        remove_inventory_quantity(db, owned, quantity)
    db.flush()
    output = recipe.output_item_template
    if output.item_type == "equipment":
        for _ in range(recipe.output_quantity):
            create_equipment_instance_from_template(db, guild.id, output)
    else:
        capacity_left = max(0, get_inventory_capacity(db, guild) - get_inventory_usage(db, guild.id))
        if recipe.output_quantity > capacity_left:
            raise CraftingError("Espaço insuficiente no Armazém para guardar o resultado.")
        add_inventory_quantity_capped(db, guild, output.id, recipe.output_quantity)
    add_guild_xp(guild, 5)
    record_guild_stat(db, guild.id, "crafted_count", recipe.output_quantity)
    unlock_codex_reference(db, guild.id, "item", output.id)
    db.add(resources)
    db.add(guild)
    db.commit()
    return f"{output.name} criado com sucesso."


def _effective_recipe_gold_cost(db: Session, recipe, docks_level: int) -> int:
    """Prevent a crafting → Market loop from minting gold, including zero-input recipes."""
    if not recipe.materials:
        return effective_crafting_gold_cost(
            recipe.gold_cost, recipe.output_item_template.base_sell_value,
            recipe.output_quantity, 0,
        )
    if docks_level < 1:
        return int(recipe.gold_cost)
    cache = db.info.setdefault("_closed_loop_crafting_material_costs", {})
    if docks_level not in cache:
        catalog_level = docks_values(docks_level)["catalog_level"]
        offers = db.scalars(select(MerchantOfferTemplate).options(
            joinedload(MerchantOfferTemplate.item_template),
        ).where(
            MerchantOfferTemplate.is_active.is_(True),
            MerchantOfferTemplate.min_dock_level <= catalog_level,
        )).unique().all()
        lowest_price: dict[int, int | float] = {}
        cheapest_equipment: dict[int, tuple[int, ItemTemplate]] = {}
        for offer in offers:
            template = offer.item_template
            if template.item_type == "material":
                effective = effective_dock_unit_price(offer.base_price, template.base_sell_value)
                lowest_price[template.id] = min(effective, lowest_price.get(template.id, effective))
            elif template.item_type == "equipment":
                effective = effective_dock_unit_price(offer.base_price, template.base_sell_value)
                previous = cheapest_equipment.get(template.id)
                if previous is None or effective < previous[0]:
                    cheapest_equipment[template.id] = (effective, template)
        # One bought equipment plus the minimum 50g fee yields 1–3 units,
        # exactly 2 in expectation. This is a long-run EV unit cost.
        for dock_cost, equipment_template in cheapest_equipment.values():
            material = _select_salvage_material(db, equipment_template)
            expected_cost = (dock_cost + 50) / 2
            lowest_price[material.id] = min(
                expected_cost, lowest_price.get(material.id, expected_cost)
            )
        cache[docks_level] = lowest_price
    lowest_price = cache[docks_level]
    material_ids = {int(material.item_template_id) for material in recipe.materials}
    if material_ids - lowest_price.keys():
        return int(recipe.gold_cost)
    input_cost = sum(lowest_price[int(material.item_template_id)] * int(material.quantity)
                     for material in recipe.materials)
    return effective_crafting_gold_cost(
        recipe.gold_cost, recipe.output_item_template.base_sell_value,
        recipe.output_quantity, input_cost,
    )


def refine_equipment(db: Session, guild: Guild, resources: GuildResources | None, item_instance_id: str) -> dict[str, int | str]:
    if resources is None:
        raise CraftingError("Recursos da guilda indisponiveis.")
    try:
        parsed_id = int(item_instance_id)
    except ValueError as exc:
        raise CraftingError("Equipamento invalido.") from exc
    item = get_item_instance_by_guild(db, guild.id, parsed_id)
    if item is None or item.market_sale is not None:
        raise CraftingError("Equipamento indisponivel para refino.")
    if get_building_level(db, guild.id, "blacksmith") < BLACKSMITH_REFINE_LEVEL:
        raise CraftingError(f"O refino de equipamentos exige Ferreiro nível {BLACKSMITH_REFINE_LEVEL}.")
    cap = REFINE_RARITY_CAPS.get(item.item_template.rarity, 3)
    if item.upgrade_level >= cap:
        raise CraftingError("Este equipamento atingiu o limite de refino da raridade.")
    gold_cost = REFINE_BASE_GOLD_COST * (item.upgrade_level + 1) * max(1, item.item_template.tier)
    ore_cost = REFINE_BASE_ORE_COST * (item.upgrade_level + 1)
    sync_inventory_resource_totals(db, resources)
    if resources.gold < gold_cost or resources.ore < ore_cost:
        raise CraftingError("Gold ou minerio insuficiente para o refino.")
    before = get_item_power_score(item)
    resources.gold -= gold_cost
    if not consume_inventory_resource(db, resources, "ore", ore_cost):
        raise CraftingError("Minério insuficiente para o refino.")
    improved = False
    for attribute in ("power", "vitality", "agility", "intelligence", "luck", "armor"):
        key = f"bonus_{attribute}"
        if getattr(item, key) > 0:
            setattr(item, key, getattr(item, key) + 1)
            improved = True
    if not improved:
        item.bonus_power += 1
    item.upgrade_level += 1
    after = get_item_power_score(item)
    add_guild_xp(guild, 3)
    record_guild_stat(db, guild.id, "refined_count", 1)
    if item.upgrade_level == 10:
        record_guild_stat(db, guild.id, f"refined_distinct_to_10:{item.id}", 1)
    db.add(item)
    db.add(resources)
    db.add(guild)
    db.commit()
    return {"name": item.item_template.name, "level": item.upgrade_level, "before": before, "after": after}
