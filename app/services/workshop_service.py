"""Small, data-driven workshop entry point; only supply production is active."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guild import Guild
from app.models.item import GuildInventoryItem, ItemTemplate
from app.repositories.item_repository import add_inventory_quantity, remove_inventory_quantity
from app.services.inventory_capacity_service import add_inventory_quantity_capped, get_inventory_capacity, get_inventory_usage


MEAT_PER_KIT = 3
HERBS_PER_KIT = 2
SUPPLY_KIT_FAMILY = "supply_kit"


class WorkshopError(ValueError):
    pass


def _materials(db: Session, family: str) -> list[ItemTemplate]:
    return list(db.scalars(select(ItemTemplate).where(
        ItemTemplate.item_type == "material", ItemTemplate.material_family == family,
        ItemTemplate.is_active.is_(True),
    ).order_by(ItemTemplate.item_level, ItemTemplate.tier, ItemTemplate.id)))


def _material_rows(db: Session, guild: Guild, family: str, *, lock: bool = False) -> list[GuildInventoryItem]:
    statement = (
        select(GuildInventoryItem)
        .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
        .where(
            GuildInventoryItem.guild_id == guild.id,
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family == family,
            ItemTemplate.is_active.is_(True),
        )
        .order_by(ItemTemplate.item_level, ItemTemplate.tier, ItemTemplate.id)
    )
    if lock:
        statement = statement.with_for_update()
    return list(db.scalars(statement))


def ensure_supply_kit(db: Session) -> ItemTemplate:
    item = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "supply_kit"))
    if item is None:
        item = ItemTemplate(
            slug="supply_kit", name="Kit de Suprimentos", description="Suprimentos preparados para fortalecer uma equipe regional.",
            item_type="material", rarity="common", item_level=1, level_band="1-20", tier=1,
            content_pack="workshops_v1", material_family=SUPPLY_KIT_FAMILY,
            base_sell_value=1, icon_group="resource-provisions", required_level=1, is_active=True,
        )
        db.add(item)
        db.flush()
    return item


def get_supply_workshop_context(db: Session, guild: Guild) -> dict[str, object]:
    kit = ensure_supply_kit(db)
    meats, herbs = _materials(db, "meat"), _materials(db, "herb")
    meat_rows, herb_rows = _material_rows(db, guild, "meat"), _material_rows(db, guild, "herb")
    kit_row = db.scalar(select(GuildInventoryItem).where(
        GuildInventoryItem.guild_id == guild.id, GuildInventoryItem.item_template_id == kit.id,
    ))
    stock = {
        "meat": sum(int(row.quantity) for row in meat_rows),
        "herb": sum(int(row.quantity) for row in herb_rows),
        "kit": int(kit_row.quantity) if kit_row else 0,
    }
    return {"meat_item": meats[0] if meats else None, "herb_item": herbs[0] if herbs else None,
            "kit_item": kit, "stock": stock,
            "can_craft": bool(meats and herbs) and stock["meat"] >= MEAT_PER_KIT
                         and stock["herb"] >= HERBS_PER_KIT
                         and get_inventory_usage(db, guild.id) - MEAT_PER_KIT - HERBS_PER_KIT + 1
                         <= get_inventory_capacity(db, guild)}


def craft_supply_kit(db: Session, guild: Guild) -> int:
    context = get_supply_workshop_context(db, guild)
    if context["meat_item"] is None or context["herb_item"] is None:
        raise WorkshopError("Os materiais da Oficina de Suprimentos ainda não estão disponíveis.")
    rows = {
        "meat": _material_rows(db, guild, "meat", lock=True),
        "herb": _material_rows(db, guild, "herb", lock=True),
    }
    totals = {key: sum(int(row.quantity) for row in stack_rows) for key, stack_rows in rows.items()}
    if totals["meat"] < MEAT_PER_KIT:
        raise WorkshopError(f"Faltam Carnes: receita exige {MEAT_PER_KIT}.")
    if totals["herb"] < HERBS_PER_KIT:
        raise WorkshopError(f"Faltam Ervas: receita exige {HERBS_PER_KIT}.")
    projected_usage = get_inventory_usage(db, guild.id) - MEAT_PER_KIT - HERBS_PER_KIT + 1
    if projected_usage > get_inventory_capacity(db, guild):
        raise WorkshopError("O resultado excederia a capacidade do Armazém.")
    kit = context["kit_item"]

    def consume_stacks(stack_rows: list[GuildInventoryItem], quantity: int) -> None:
        remaining = quantity
        for row in stack_rows:
            consumed = min(remaining, int(row.quantity))
            if consumed:
                remove_inventory_quantity(db, row, consumed)
                remaining -= consumed
            if remaining == 0:
                break

    consume_stacks(rows["meat"], MEAT_PER_KIT)
    consume_stacks(rows["herb"], HERBS_PER_KIT)
    add_inventory_quantity(db, guild.id, kit.id, 1)
    db.flush()
    stock = db.scalar(select(GuildInventoryItem.quantity).where(
        GuildInventoryItem.guild_id == guild.id, GuildInventoryItem.item_template_id == kit.id,
    ))
    return int(stock or 0)
