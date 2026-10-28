from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.guild import Guild
from app.models.item import GuildInventoryItem
from app.services.building_service import get_building_level
from app.repositories.item_repository import add_inventory_quantity


BASE_WAREHOUSE_CAPACITY = 1500
WAREHOUSE_CAPACITY_PER_MILESTONE = 250
GUILD_CAPACITY_PER_LEVEL = 10


def get_inventory_capacity(db: Session, guild: Guild) -> int:
    warehouse_level = get_building_level(db, guild.id, "warehouse")
    return (
        BASE_WAREHOUSE_CAPACITY
        + (warehouse_level // 5) * WAREHOUSE_CAPACITY_PER_MILESTONE
        + max(0, guild.level - 1) * GUILD_CAPACITY_PER_LEVEL
    )


def get_inventory_usage(db: Session, guild_id: int) -> int:
    return int(db.scalar(
        select(func.coalesce(func.sum(GuildInventoryItem.quantity), 0)).where(
            GuildInventoryItem.guild_id == guild_id,
        )
    ) or 0)


def add_inventory_quantity_capped(
    db: Session,
    guild: Guild,
    item_template_id: int,
    quantity: int,
) -> tuple[int, int]:
    requested = max(0, int(quantity))
    capacity_left = max(0, get_inventory_capacity(db, guild) - get_inventory_usage(db, guild.id))
    accepted = min(requested, capacity_left)
    if accepted:
        add_inventory_quantity(db, guild.id, item_template_id, accepted)
        db.flush()
    return accepted, requested - accepted
