"""Small, data-driven workshop entry point; only supply production is active."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guild import Guild
from app.models.item import GuildInventoryItem, ItemTemplate
from app.services.inventory_capacity_service import add_inventory_quantity_capped, get_inventory_capacity, get_inventory_usage


MEAT_PER_KIT = 3
HERBS_PER_KIT = 2
SUPPLY_KIT_FAMILY = "supply_kit"


class WorkshopError(ValueError):
    pass


def _material(db: Session, guild: Guild, family: str) -> ItemTemplate | None:
    return db.scalar(select(ItemTemplate).where(
        ItemTemplate.item_type == "material", ItemTemplate.material_family == family,
        ItemTemplate.is_active.is_(True), ItemTemplate.item_level <= max(1, guild.level),
    ).order_by(ItemTemplate.item_level.desc(), ItemTemplate.tier.desc(), ItemTemplate.id)) or db.scalar(
        select(ItemTemplate).where(ItemTemplate.item_type == "material", ItemTemplate.material_family == family,
                                   ItemTemplate.is_active.is_(True)).order_by(ItemTemplate.item_level, ItemTemplate.id)
    )


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
    meat, herbs = _material(db, guild, "meat"), _material(db, guild, "herb")
    stock = {}
    for key, item in (("meat", meat), ("herb", herbs), ("kit", kit)):
        row = db.scalar(select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == guild.id, GuildInventoryItem.item_template_id == item.id,
        )) if item else None
        stock[key] = int(row.quantity) if row else 0
    return {"meat_item": meat, "herb_item": herbs, "kit_item": kit, "stock": stock,
            "can_craft": meat is not None and herbs is not None and stock["meat"] >= MEAT_PER_KIT and stock["herb"] >= HERBS_PER_KIT
                         and get_inventory_usage(db, guild.id) < get_inventory_capacity(db, guild)}


def craft_supply_kit(db: Session, guild: Guild) -> int:
    context = get_supply_workshop_context(db, guild)
    if context["meat_item"] is None or context["herb_item"] is None:
        raise WorkshopError("Os materiais da Oficina de Suprimentos ainda não estão disponíveis.")
    if get_inventory_usage(db, guild.id) >= get_inventory_capacity(db, guild):
        raise WorkshopError("Armazém cheio: libere espaço antes de fabricar.")
    rows = {}
    for key, item in (("meat", context["meat_item"]), ("herb", context["herb_item"])):
        rows[key] = db.scalar(select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == guild.id, GuildInventoryItem.item_template_id == item.id,
        ).with_for_update())
    if rows["meat"] is None or rows["meat"].quantity < MEAT_PER_KIT:
        raise WorkshopError(f"Faltam Carnes: receita exige {MEAT_PER_KIT}.")
    if rows["herb"] is None or rows["herb"].quantity < HERBS_PER_KIT:
        raise WorkshopError(f"Faltam Ervas: receita exige {HERBS_PER_KIT}.")
    kit = context["kit_item"]
    target = db.scalar(select(GuildInventoryItem).where(
        GuildInventoryItem.guild_id == guild.id, GuildInventoryItem.item_template_id == kit.id,
    ).with_for_update())
    if target is None:
        target = GuildInventoryItem(guild_id=guild.id, item_template_id=kit.id, quantity=0)
        db.add(target)
        db.flush()
    rows["meat"].quantity -= MEAT_PER_KIT
    rows["herb"].quantity -= HERBS_PER_KIT
    target.quantity += 1
    db.add_all([rows["meat"], rows["herb"], target])
    db.flush()
    return int(target.quantity)
