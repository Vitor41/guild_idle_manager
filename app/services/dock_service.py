from datetime import datetime, timedelta, timezone
from random import choices, randint, sample

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.dock import DockOffer, DockRotation, DockRotationMerchant, MerchantOfferTemplate, MerchantTemplate
from app.models.guild import Guild, GuildResources
from app.repositories.item_repository import add_inventory_quantity
from app.services.building_service import ensure_guild_buildings, get_building_level
from app.services.equipment_service import create_equipment_instance_from_template
from app.services.building_balance_service import docks_values
from app.services.achievement_service import record_guild_stat


class DockError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _rotation_duration(level: int) -> int:
    return docks_values(level)["rotation_seconds"]


def _merchant_count(level: int) -> int:
    return docks_values(level)["merchants"]


def _offer_count(level: int) -> int:
    return docks_values(level)["offers"]


def _load_rotation(db: Session, rotation_id: int) -> DockRotation:
    return db.scalars(select(DockRotation).options(
        joinedload(DockRotation.merchants).joinedload(DockRotationMerchant.merchant),
        joinedload(DockRotation.merchants).joinedload(DockRotationMerchant.offers).joinedload(DockOffer.item_template),
    ).where(DockRotation.id == rotation_id)).unique().one()


def create_dock_rotation(db: Session, guild: Guild, dock_level: int) -> DockRotation:
    now = utc_now()
    active = db.scalar(select(DockRotation).where(DockRotation.guild_id == guild.id, DockRotation.status == "active"))
    if active is not None:
        active.status = "expired"
        db.add(active)
    catalog_level = docks_values(dock_level)["catalog_level"]
    candidates = list(db.scalars(select(MerchantTemplate).where(MerchantTemplate.is_active.is_(True), MerchantTemplate.min_dock_level <= catalog_level)))
    if not candidates:
        raise DockError("Nenhum mercante está disponível para este nível das Docas.")
    selected = sample(candidates, min(_merchant_count(dock_level), len(candidates)))
    rotation = DockRotation(guild_id=guild.id, status="active", starts_at=now, ends_at=now + timedelta(seconds=_rotation_duration(dock_level)))
    db.add(rotation)
    db.flush()
    slots_total = _offer_count(dock_level)
    used_item_ids: set[int] = set()
    global_pool = list(db.scalars(select(MerchantOfferTemplate).options(joinedload(MerchantOfferTemplate.item_template)).where(
        MerchantOfferTemplate.is_active.is_(True), MerchantOfferTemplate.min_dock_level <= catalog_level)))
    for slot, merchant in enumerate(selected, start=1):
        rotation_merchant = DockRotationMerchant(dock_rotation_id=rotation.id, merchant_template_id=merchant.id, slot=slot)
        db.add(rotation_merchant)
        db.flush()
        pool = [offer for offer in global_pool if offer.item_template_id not in used_item_ids]
        amount = max(1, slots_total // len(selected) + (1 if slot <= slots_total % len(selected) else 0))
        if pool:
            selected_offers = []
            available = list(pool)
            for _ in range(min(amount, len(available))):
                offer = choices(available, weights=[max(1, candidate.weight) for candidate in available], k=1)[0]
                selected_offers.append(offer)
                available = [candidate for candidate in available if candidate.item_template_id != offer.item_template_id]
            for offer in selected_offers:
                used_item_ids.add(offer.item_template_id)
                stock = randint(offer.min_stock, offer.max_stock)
                db.add(DockOffer(dock_rotation_merchant_id=rotation_merchant.id, item_template_id=offer.item_template_id,
                    unit_price=offer.base_price, initial_stock=stock, remaining_stock=stock))
    db.commit()
    return _load_rotation(db, rotation.id)


def get_docks_context(db: Session, guild: Guild) -> dict[str, object]:
    ensure_guild_buildings(db, guild.id)
    level = get_building_level(db, guild.id, "docks")
    rotation = None
    if level > 0:
        rotation = db.scalar(select(DockRotation).where(DockRotation.guild_id == guild.id, DockRotation.status == "active").order_by(DockRotation.id.desc()))
        if rotation is None or rotation.ends_at <= utc_now():
            rotation = create_dock_rotation(db, guild, level)
        else:
            rotation = _load_rotation(db, rotation.id)
    return {"dock_level": level, "rotation": rotation, "now": utc_now(), "offer_slots": _offer_count(level) if level else 0}


def buy_dock_offer(db: Session, guild: Guild, resources: GuildResources, offer_id: int, quantity: int) -> None:
    if get_building_level(db, guild.id, "docks") < 1:
        raise DockError("Evolua as Docas para o nível 1 antes de comprar ofertas.")
    if quantity < 1:
        raise DockError("Informe uma quantidade válida.")
    offer = db.scalar(select(DockOffer).options(joinedload(DockOffer.item_template), joinedload(DockOffer.rotation_merchant).joinedload(DockRotationMerchant.rotation)).where(DockOffer.id == offer_id))
    if offer is None or offer.rotation_merchant.rotation.guild_id != guild.id:
        raise DockError("Oferta indisponível.")
    rotation = offer.rotation_merchant.rotation
    if rotation.status != "active" or rotation.ends_at <= utc_now():
        raise DockError("Esta rotação já terminou.")
    if offer.item_template.item_type == "equipment" and quantity != 1:
        raise DockError("Equipamentos são comprados uma unidade por vez.")
    if quantity > offer.remaining_stock:
        raise DockError("Estoque insuficiente.")
    total = offer.unit_price * quantity
    if resources.gold < total:
        raise DockError("Ouro insuficiente para esta compra.")
    resources.gold -= total
    offer.remaining_stock -= quantity
    if offer.item_template.item_type == "equipment":
        create_equipment_instance_from_template(db, guild.id, offer.item_template)
    else:
        add_inventory_quantity(db, guild.id, offer.item_template_id, quantity)
    db.add_all([resources, offer])
    record_guild_stat(db, guild.id, "dock_purchases", 1)
    db.commit()
