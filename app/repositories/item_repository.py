from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.item import DungeonTemplateItemDrop, GuildInventoryItem, GuildItemInstance, ItemTemplate, MissionTemplateItemDrop
from app.models.guild import GuildResources
from app.models.market import MarketSale


RESOURCE_MATERIAL_FAMILIES = {
    "wood": ("wood",),
    "ore": ("ore", "stone"),
    "crystals": ("gem", "essence", "crystal"),
}


def get_inventory_resource_totals(db: Session, guild_id: int) -> dict[str, int]:
    totals: dict[str, int] = {}
    for resource_name, families in RESOURCE_MATERIAL_FAMILIES.items():
        totals[resource_name] = db.scalar(
            select(func.coalesce(func.sum(GuildInventoryItem.quantity), 0))
            .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
            .where(
                GuildInventoryItem.guild_id == guild_id,
                ItemTemplate.item_type == "material",
                ItemTemplate.material_family.in_(families),
            )
        ) or 0
    return totals


def sync_inventory_resource_totals(db: Session, resources: GuildResources) -> bool:
    totals = get_inventory_resource_totals(db, resources.guild_id)
    totals["crystals"] += max(0, int(resources.crystal_reserve or 0))
    changed = False
    for resource_name, total in totals.items():
        if getattr(resources, resource_name) != total:
            setattr(resources, resource_name, total)
            changed = True
    if changed:
        db.add(resources)
    return changed


def _resource_name_for_item(db: Session, item_template_id: int) -> str | None:
    item_template = db.get(ItemTemplate, item_template_id)
    if item_template is None or item_template.item_type != "material":
        return None
    for resource_name, families in RESOURCE_MATERIAL_FAMILIES.items():
        if item_template.material_family in families:
            return resource_name
    return None


def _adjust_resource_total(db: Session, guild_id: int, item_template_id: int, delta: int) -> None:
    resource_name = _resource_name_for_item(db, item_template_id)
    if resource_name is None or delta == 0:
        return
    resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))
    if resources is not None:
        setattr(resources, resource_name, max(0, getattr(resources, resource_name) + delta))
        db.add(resources)


def count_item_templates(db: Session) -> int:
    return db.scalar(select(func.count(ItemTemplate.id))) or 0


def count_mission_drops(db: Session) -> int:
    return db.scalar(select(func.count(MissionTemplateItemDrop.id))) or 0


def list_item_templates(db: Session) -> list[ItemTemplate]:
    return list(db.scalars(select(ItemTemplate).order_by(ItemTemplate.id)))


def list_active_item_templates(db: Session) -> list[ItemTemplate]:
    return list(
        db.scalars(
            select(ItemTemplate)
            .where(ItemTemplate.is_active.is_(True))
            .order_by(ItemTemplate.name)
        )
    )


def get_item_template(db: Session, item_template_id: int) -> ItemTemplate | None:
    return db.get(ItemTemplate, item_template_id)


def get_item_template_by_name(db: Session, name: str) -> ItemTemplate | None:
    return db.scalar(select(ItemTemplate).where(ItemTemplate.name == name))


def create_item_template(db: Session, data: dict[str, object]) -> ItemTemplate:
    payload = dict(data)
    if "base_sell_value" not in payload:
        tier = int(payload.get("tier", 1))
        payload["base_sell_value"] = max(10, tier * 20) if payload.get("item_type") == "equipment" else max(1, tier * 2)
    item_template = ItemTemplate(**payload)
    db.add(item_template)
    return item_template


def list_inventory_by_guild(db: Session, guild_id: int) -> list[GuildInventoryItem]:
    return list(
        db.scalars(
            select(GuildInventoryItem)
            .options(joinedload(GuildInventoryItem.item_template))
            .where(GuildInventoryItem.guild_id == guild_id)
            .order_by(GuildInventoryItem.id)
        )
    )


def get_inventory_item(
    db: Session,
    guild_id: int,
    item_template_id: int,
) -> GuildInventoryItem | None:
    return db.scalar(
        select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == guild_id,
            GuildInventoryItem.item_template_id == item_template_id,
        )
    )


def add_inventory_quantity(
    db: Session,
    guild_id: int,
    item_template_id: int,
    quantity: int,
) -> GuildInventoryItem:
    inventory_item = get_inventory_item(db, guild_id, item_template_id)
    if inventory_item is None:
        inventory_item = GuildInventoryItem(
            guild_id=guild_id,
            item_template_id=item_template_id,
            quantity=quantity,
        )
        db.add(inventory_item)
    else:
        inventory_item.quantity += quantity
        db.add(inventory_item)
    _adjust_resource_total(db, guild_id, item_template_id, quantity)
    return inventory_item


def list_item_instances_by_guild(db: Session, guild_id: int) -> list[GuildItemInstance]:
    return list(
        db.scalars(
            select(GuildItemInstance)
            .options(
                joinedload(GuildItemInstance.item_template),
                joinedload(GuildItemInstance.equipped_to_mercenary),
                joinedload(GuildItemInstance.market_sale),
            )
            .where(GuildItemInstance.guild_id == guild_id)
            .order_by(GuildItemInstance.id)
        )
    )


def list_available_item_instances_by_guild(db: Session, guild_id: int) -> list[GuildItemInstance]:
    return list(
        db.scalars(
            select(GuildItemInstance)
            .options(joinedload(GuildItemInstance.item_template))
            .where(
                GuildItemInstance.guild_id == guild_id,
                GuildItemInstance.equipped_to_mercenary_id.is_(None),
                ~select(MarketSale.id).where(
                    MarketSale.item_instance_id == GuildItemInstance.id,
                    MarketSale.status == "in_progress",
                ).exists(),
            )
            .order_by(GuildItemInstance.id)
        )
    )


def list_available_item_instances_for_template(
    db: Session,
    guild_id: int,
    item_template_id: int,
    *,
    lock: bool = False,
) -> list[GuildItemInstance]:
    statement = (
        select(GuildItemInstance)
        .options(joinedload(GuildItemInstance.item_template))
        .where(
            GuildItemInstance.guild_id == guild_id,
            GuildItemInstance.item_template_id == item_template_id,
            GuildItemInstance.equipped_to_mercenary_id.is_(None),
            ~select(MarketSale.id).where(
                MarketSale.item_instance_id == GuildItemInstance.id,
                MarketSale.status == "in_progress",
            ).exists(),
        )
        .order_by(GuildItemInstance.id)
    )
    if lock:
        statement = statement.with_for_update(of=GuildItemInstance)
    return list(db.scalars(statement))


def list_equipment_for_mercenary(
    db: Session,
    guild_id: int,
    mercenary_id: int,
) -> list[GuildItemInstance]:
    return list(
        db.scalars(
            select(GuildItemInstance)
            .options(joinedload(GuildItemInstance.item_template))
            .where(
                GuildItemInstance.guild_id == guild_id,
                GuildItemInstance.equipped_to_mercenary_id == mercenary_id,
            )
            .order_by(GuildItemInstance.equipment_slot)
        )
    )


def get_item_instance_by_guild(
    db: Session,
    guild_id: int,
    item_instance_id: int,
) -> GuildItemInstance | None:
    return db.scalar(
        select(GuildItemInstance)
        .options(joinedload(GuildItemInstance.item_template))
        .where(
            GuildItemInstance.id == item_instance_id,
            GuildItemInstance.guild_id == guild_id,
        )
    )


def get_equipped_item_in_slot(
    db: Session,
    guild_id: int,
    mercenary_id: int,
    equipment_slot: str,
) -> GuildItemInstance | None:
    return db.scalar(
        select(GuildItemInstance).where(
            GuildItemInstance.guild_id == guild_id,
            GuildItemInstance.equipped_to_mercenary_id == mercenary_id,
            GuildItemInstance.equipment_slot == equipment_slot,
        )
    )


def count_equipped_items_in_slot(
    db: Session,
    guild_id: int,
    mercenary_id: int,
    equipment_slot: str,
) -> int:
    return (
        db.scalar(
            select(func.count(GuildItemInstance.id)).where(
                GuildItemInstance.guild_id == guild_id,
                GuildItemInstance.equipped_to_mercenary_id == mercenary_id,
                GuildItemInstance.equipment_slot == equipment_slot,
            )
        )
        or 0
    )


def create_item_instance(
    db: Session,
    data: dict[str, object],
) -> GuildItemInstance:
    item_instance = GuildItemInstance(**data)
    db.add(item_instance)
    return item_instance


def remove_inventory_quantity(
    db: Session,
    inventory_item: GuildInventoryItem,
    quantity: int,
) -> None:
    removed_quantity = min(max(0, quantity), inventory_item.quantity)
    inventory_item.quantity -= removed_quantity
    _adjust_resource_total(
        db,
        inventory_item.guild_id,
        inventory_item.item_template_id,
        -removed_quantity,
    )
    if inventory_item.quantity <= 0:
        db.delete(inventory_item)
    else:
        db.add(inventory_item)


def consume_inventory_resource(
    db: Session,
    resources: GuildResources,
    resource_name: str,
    quantity: int,
) -> bool:
    if quantity <= 0:
        return True
    families = RESOURCE_MATERIAL_FAMILIES.get(resource_name)
    if families is None:
        return False
    sync_inventory_resource_totals(db, resources)
    if getattr(resources, resource_name) < quantity:
        return False
    stacks = list(db.scalars(
        select(GuildInventoryItem)
        .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
        .where(
            GuildInventoryItem.guild_id == resources.guild_id,
            GuildInventoryItem.quantity > 0,
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family.in_(families),
        )
        .order_by(GuildInventoryItem.quantity.desc(), GuildInventoryItem.id)
    ))
    remaining = quantity
    for stack in stacks:
        consumed = min(stack.quantity, remaining)
        remove_inventory_quantity(db, stack, consumed)
        remaining -= consumed
        if remaining == 0:
            break
    if remaining and resource_name == "crystals":
        from_reserve = min(max(0, int(resources.crystal_reserve or 0)), remaining)
        resources.crystal_reserve -= from_reserve
        resources.crystals -= from_reserve
        remaining -= from_reserve
        db.add(resources)
    return remaining == 0


def delete_item_instance(db: Session, item_instance: GuildItemInstance) -> None:
    db.delete(item_instance)


def list_mission_drops(db: Session) -> list[MissionTemplateItemDrop]:
    return list(
        db.scalars(
            select(MissionTemplateItemDrop)
            .options(
                joinedload(MissionTemplateItemDrop.mission_template),
                joinedload(MissionTemplateItemDrop.item_template),
            )
            .order_by(MissionTemplateItemDrop.id)
        )
    )


def list_active_drops_for_mission(db: Session, mission_template_id: int) -> list[MissionTemplateItemDrop]:
    return list(
        db.scalars(
            select(MissionTemplateItemDrop)
            .options(joinedload(MissionTemplateItemDrop.item_template))
            .where(
                MissionTemplateItemDrop.mission_template_id == mission_template_id,
                MissionTemplateItemDrop.is_active.is_(True),
            )
            .order_by(MissionTemplateItemDrop.id)
        )
    )


def get_mission_drop(db: Session, drop_id: int) -> MissionTemplateItemDrop | None:
    return db.get(MissionTemplateItemDrop, drop_id)


def get_mission_drop_by_pair(
    db: Session,
    mission_template_id: int,
    item_template_id: int,
) -> MissionTemplateItemDrop | None:
    return db.scalar(
        select(MissionTemplateItemDrop).where(
            MissionTemplateItemDrop.mission_template_id == mission_template_id,
            MissionTemplateItemDrop.item_template_id == item_template_id,
        )
    )


def create_mission_drop(db: Session, data: dict[str, object]) -> MissionTemplateItemDrop:
    drop = MissionTemplateItemDrop(**data)
    db.add(drop)
    return drop
