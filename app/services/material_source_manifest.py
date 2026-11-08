"""Live, deterministic material-source audit for the workshop and Wiki."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crafting import CraftingRecipe, CraftingRecipeMaterial
from app.models.dock import DockOffer, DockRotation, DockRotationMerchant, MerchantOfferTemplate, MerchantTemplate
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.services.display_service import clean_generated_name
from app.services.economy_pricing_service import effective_dock_unit_price
from app.services.gathering_service import preview_material_for_family
from app.services.salvage_service import _select_salvage_material, salvage_material_family

MAX_GATHERING_GUILD_LEVEL = 350


def build_material_source_manifest(db: Session, guild_level: int | None = None, guild_id: int | None = None) -> dict:
    """Describe configured sources without treating config weights as probabilities.

    ``guild_level`` scopes deterministic gathering visibility. ``guild_id`` adds only
    that guild's current Dock rotation snapshot; it is never emitted in the result.
    """
    materials = list(db.scalars(select(ItemTemplate).where(
        ItemTemplate.item_type == "material"
    ).order_by(ItemTemplate.id)))
    equipment = list(db.scalars(select(ItemTemplate).where(
        ItemTemplate.item_type == "equipment"
    ).order_by(ItemTemplate.id)))
    all_items = materials + equipment
    rows = {item.id: {"item": {"id": item.id, "slug": item.slug, "name": clean_generated_name(item.name),
        "item_type": item.item_type, "rarity": item.rarity, "icon_group": item.icon_group,
        "level_band": item.level_band, "equipment_slot": item.equipment_slot,
        "family": item.material_family, "tier": item.tier, "item_level": item.item_level,
        "required_level": item.required_level, "active": bool(item.is_active)},
        "required_by": [], "dependencies": [], "sources": []} for item in materials}
    for item in equipment:
        rows[item.id] = {"item": {"id": item.id, "slug": item.slug, "name": clean_generated_name(item.name),
            "item_type": item.item_type, "rarity": item.rarity, "icon_group": item.icon_group,
            "level_band": item.level_band, "equipment_slot": item.equipment_slot, "family": item.material_family, "tier": item.tier,
            "item_level": item.item_level, "required_level": item.required_level,
            "active": bool(item.is_active)}, "required_by": [], "dependencies": [], "sources": []}
    for recipe, ingredient, item in db.execute(
        select(CraftingRecipe, CraftingRecipeMaterial, ItemTemplate)
        .join(CraftingRecipeMaterial, CraftingRecipeMaterial.recipe_id == CraftingRecipe.id)
        .join(ItemTemplate, ItemTemplate.id == CraftingRecipeMaterial.item_template_id)
        .where(CraftingRecipe.is_active.is_(True))
    ):
        if item.id in rows:
            rows[item.id]["required_by"].append({"type": "crafting_recipe", "name": clean_generated_name(recipe.name),
                "quantity": ingredient.quantity, "recipe_active": bool(recipe.is_active)})
    for recipe, item in db.execute(select(CraftingRecipe, ItemTemplate)
        .join(ItemTemplate, ItemTemplate.id == CraftingRecipe.output_item_template_id)
        .where(CraftingRecipe.is_active.is_(True))):
        if item.id in rows:
            rows[item.id]["sources"].append({"type": "crafting_output", "recipe": clean_generated_name(recipe.name),
                "quantity": recipe.output_quantity, "gold_cost": recipe.gold_cost,
                "required_blacksmith_level": recipe.required_blacksmith_level,
                "condition": "receita ativa do Ferreiro; exige os ingredientes listados na receita",
                "provenance": "live CraftingRecipe + CraftingRecipeMaterial"})
    for drop, mission in db.execute(select(MissionTemplateItemDrop, MissionTemplate)
        .join(MissionTemplate, MissionTemplate.id == MissionTemplateItemDrop.mission_template_id)
        .where(MissionTemplateItemDrop.is_active.is_(True), MissionTemplate.is_active.is_(True))):
        if (drop.item_template_id in rows and drop.drop_chance > 0
                and drop.min_quantity >= 1 and drop.max_quantity >= drop.min_quantity):
            rows[drop.item_template_id]["sources"].append({"type": "mission", "name": clean_generated_name(mission.name),
                "configured_base_chance_percent": drop.drop_chance,
                "quantity_range": [drop.min_quantity, drop.max_quantity],
                "min_guild_level": mission.required_guild_level,
                "required_building": [mission.required_building_type, mission.required_building_level],
                "min_mercenary_level": mission.required_min_mercenary_level,
                "condition": "atividade concluída com sucesso; chance pode receber modificadores",
                "provenance": "live MissionTemplateItemDrop + MissionTemplate"})
    for drop, dungeon in db.execute(select(DungeonTemplateItemDrop, DungeonTemplate)
        .join(DungeonTemplate, DungeonTemplate.id == DungeonTemplateItemDrop.dungeon_template_id)
        .where(DungeonTemplateItemDrop.is_active.is_(True), DungeonTemplate.is_active.is_(True))):
        if (drop.item_template_id in rows and drop.drop_chance > 0
                and drop.min_quantity >= 1 and drop.max_quantity >= drop.min_quantity):
            rows[drop.item_template_id]["sources"].append({"type": "dungeon_or_boss", "name": clean_generated_name(dungeon.name),
                "content_type": dungeon.content_type, "configured_base_chance_percent": drop.drop_chance,
                "quantity_range": [drop.min_quantity, drop.max_quantity],
                "min_guild_level": dungeon.required_guild_level,
                "required_building": [dungeon.required_building_type, dungeon.required_building_level],
                "min_mercenary_level": dungeon.required_min_mercenary_level,
                "condition": "atividade concluída com sucesso; chance pode receber modificadores",
                "provenance": "live DungeonTemplateItemDrop + DungeonTemplate"})
    for offer, merchant, item_template in db.execute(select(MerchantOfferTemplate, MerchantTemplate, ItemTemplate)
        .join(MerchantTemplate, MerchantTemplate.id == MerchantOfferTemplate.merchant_template_id)
        .join(ItemTemplate, ItemTemplate.id == MerchantOfferTemplate.item_template_id)
        .where(MerchantOfferTemplate.is_active.is_(True), MerchantTemplate.is_active.is_(True))):
        if (offer.item_template_id in rows and offer.min_stock >= 1
                and offer.max_stock >= offer.min_stock and offer.base_price > 0):
            rows[offer.item_template_id]["sources"].append({"type": "docks_possible_offer",
                "merchant": clean_generated_name(merchant.name), "base_price": offer.base_price,
                "effective_unit_price": effective_dock_unit_price(offer.base_price, item_template.base_sell_value),
                "stock_range": [offer.min_stock, offer.max_stock],
                "weight": offer.weight, "min_dock_level": max(offer.min_dock_level, merchant.min_dock_level),
                "condition": "oferta possível conforme rotação e nível do cais; peso não é probabilidade",
                "provenance": "live MerchantOfferTemplate + MerchantTemplate"})
    if guild_id is not None:
        for offer, rotation, merchant in db.execute(select(DockOffer, DockRotation, DockRotationMerchant)
            .join(DockRotationMerchant, DockRotationMerchant.id == DockOffer.dock_rotation_merchant_id)
            .join(DockRotation, DockRotation.id == DockRotationMerchant.dock_rotation_id)
            .where(DockRotation.guild_id == guild_id, DockRotation.status == "active")):
            if offer.item_template_id in rows:
                rows[offer.item_template_id]["sources"].append({"type": "docks_current_snapshot",
                    "remaining_stock": offer.remaining_stock, "unit_price": offer.unit_price,
                    "rotation_ends_at": rotation.ends_at.isoformat(),
                    "provenance": "campaign DockOffer snapshot; scoped to requested guild"})
    families = {item.material_family for item in materials if item.is_active and item.material_family}
    for family in families:
        if guild_level is not None:
            selected = preview_material_for_family(db, family, max(1, int(guild_level)))
            if selected:
                rows[selected.id]["sources"].append({"type": "gathering", "family": family,
                    "guild_level": int(guild_level), "guild_level_range": [int(guild_level), int(guild_level)],
                    "condition": "seleção determinística por família e nível; sem chance de drop",
                    "provenance": "preview_material_for_family live rule"})
            continue
        thresholds = {1, MAX_GATHERING_GUILD_LEVEL}
        for item in materials:
            if item.is_active and item.material_family == family:
                unlock = max(1, int(item.required_level), int(item.item_level))
                if unlock <= MAX_GATHERING_GUILD_LEVEL:
                    thresholds.add(unlock)
        ordered = sorted(thresholds)
        for index, start_level in enumerate(ordered):
            end_level = min(MAX_GATHERING_GUILD_LEVEL,
                ordered[index + 1] - 1 if index + 1 < len(ordered) else MAX_GATHERING_GUILD_LEVEL)
            selected = preview_material_for_family(db, family, start_level)
            if selected:
                rows[selected.id]["sources"].append({"type": "gathering", "family": family,
                    "guild_level_range": [start_level, end_level],
                    "condition": "seleção determinística por família e nível; sem chance de drop",
                    "provenance": "preview_material_for_family live rule"})
    active_equipment = [gear for gear in equipment if gear.is_active]
    for gear in active_equipment:
        try:
            material = _select_salvage_material(db, gear)
        except Exception:
            continue
        if material.id in rows:
            rows[material.id]["sources"].append({"type": "salvage", "equipment": gear.name,
                "family_rule": salvage_material_family(gear), "quantity_range": [1, 3],
                "condition": "resultado selecionado por regra do equipamento; quantidade uniforme 1–3",
                "provenance": "live salvage selector + SystemRandom.randint(1, 3)"})
    for item in materials:
        if item.material_family in {"meat", "herb"} and item.is_active:
            rows[item.id]["dependencies"].append({"type": "workshop_input", "recipe": "Kit de Suprimentos",
                "quantity_per_kit": 3 if item.material_family == "meat" else 2,
                "condition": "qualquer variante ativa da família; produção em lote",
                "provenance": "workshop recipe constants"})
        if item.material_family == "supply_kit" and item.is_active:
            rows[item.id]["sources"].append({"type": "workshop_output", "quantity": 1,
                "condition": "3 Carnes + 2 Ervas; 5 segundos por unidade",
                "provenance": "workshop service constants"})
    material_rows = list(rows.values())
    for row in material_rows:
        row["sources"].sort(key=lambda source: (source["type"], source.get("name", ""), source.get("guild_level", 0)))
        row["dependencies"].sort(key=lambda dependency: dependency["type"])
    return {"schema_version": 1, "scope": {"guild_level": guild_level,
            "gathering_level_range": [guild_level, guild_level] if guild_level is not None else [1, MAX_GATHERING_GUILD_LEVEL],
            "includes_current_dock_snapshot": guild_id is not None},
        "materials": material_rows,
        "equipment": [rows[item.id] for item in equipment],
        "gaps": [row["item"] for row in material_rows if row["item"]["active"] and not row["sources"]]}
