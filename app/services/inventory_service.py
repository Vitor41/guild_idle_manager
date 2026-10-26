from sqlalchemy.orm import Session

from app.models.item import GuildInventoryItem, GuildItemInstance
from app.repositories.item_repository import list_inventory_by_guild, list_item_instances_by_guild
from app.repositories.mercenary_repository import count_mercenaries_by_guild
from sqlalchemy import func, select
from app.models.item import GuildInventoryItem as InventoryModel
from app.models.mercenary import Mercenary


def get_inventory_for_guild(db: Session, guild_id: int) -> list[GuildInventoryItem]:
    return list_inventory_by_guild(db, guild_id)


def get_equipment_for_guild(db: Session, guild_id: int) -> list[GuildItemInstance]:
    return list_item_instances_by_guild(db, guild_id)


def get_inventory_summary(db: Session, guild_id: int) -> dict[str, int | str]:
    distinct_items = count_inventory_kinds(db, guild_id)
    total_quantity = total_inventory_quantity(db, guild_id)
    equipment_count = count_equipment_instances(db, guild_id)
    highest_level = db.scalar(
        select(func.max(Mercenary.level)).where(Mercenary.guild_id == guild_id)
    ) or 0
    return {
        "distinct_items": distinct_items,
        "total_quantity": total_quantity,
        "equipment_count": equipment_count,
        "highest_mercenary_level": highest_level,
    }


def count_inventory_kinds(db: Session, guild_id: int) -> int:
    return db.scalar(
        select(func.count(InventoryModel.id)).where(InventoryModel.guild_id == guild_id)
    ) or 0


def total_inventory_quantity(db: Session, guild_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(InventoryModel.quantity), 0)).where(
            InventoryModel.guild_id == guild_id
        )
    ) or 0


def count_equipment_instances(db: Session, guild_id: int) -> int:
    return db.scalar(
        select(func.count(GuildItemInstance.id)).where(GuildItemInstance.guild_id == guild_id)
    ) or 0
