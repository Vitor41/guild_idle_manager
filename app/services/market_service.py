from datetime import datetime, timedelta, timezone
from math import floor
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guild import Guild, GuildResources
from app.models.market import MarketSale
from app.models.item import ItemTemplate
from app.repositories.item_repository import (
    delete_item_instance,
    get_inventory_item,
    get_item_instance_by_guild,
    remove_inventory_quantity,
)
from app.repositories.market_repository import (
    count_active_market_sales,
    create_market_sale,
    get_market_sale_by_guild,
    list_market_sales_by_guild,
)
from app.services.building_service import ensure_guild_buildings, get_building_level
from app.services.guild_progression_service import add_guild_xp
from app.services.inventory_service import get_equipment_for_guild, get_inventory_for_guild
from app.core.game_balance import MARKET_RARITY_SECONDS
from app.core.time import prepare_timer_context
from app.services.building_balance_service import market_values
from app.services.economy_pricing_service import market_sale_unit_value
from app.services.achievement_service import record_guild_stat


RARITY_SECONDS = MARKET_RARITY_SECONDS
MATERIAL_BASE_UNITS_PER_24H: int | None = 25
MATERIAL_SALE_WINDOW = timedelta(hours=24)
_MATERIAL_SALE_LOCKS: dict[int, Lock] = {}
_MATERIAL_SALE_LOCKS_GUARD = Lock()


class MarketError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _material_sale_lock(guild_id: int) -> Lock:
    with _MATERIAL_SALE_LOCKS_GUARD:
        return _MATERIAL_SALE_LOCKS.setdefault(int(guild_id), Lock())


def get_market_bonuses(db: Session, guild_id: int) -> dict[str, int]:
    level = get_building_level(db, guild_id, "market")
    return {"level": level, **market_values(level)}


def get_material_sale_quota(
    db: Session,
    guild_id: int,
    *,
    now: datetime | None = None,
) -> dict[str, int | None]:
    """Return material throughput in the rolling 24h window, including active listings."""
    timestamp = now or utc_now()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    cutoff = timestamp - MATERIAL_SALE_WINDOW
    market = get_market_bonuses(db, guild_id)
    market_level = int(market["level"])
    limit = (
        None if MATERIAL_BASE_UNITS_PER_24H is None else
        0 if market_level < 1 else
        MATERIAL_BASE_UNITS_PER_24H + 5 * (market_level // 5)
    )
    recent_sales = list(db.execute(
        select(MarketSale.started_at, MarketSale.quantity)
        .join(ItemTemplate, ItemTemplate.id == MarketSale.item_template_id)
        .where(
            MarketSale.guild_id == guild_id,
            ItemTemplate.item_type == "material",
            MarketSale.started_at > cutoff,
            MarketSale.started_at <= timestamp,
        )
        .order_by(MarketSale.started_at, MarketSale.id)
    ))
    used = sum(int(row.quantity) for row in recent_sales)
    # Report the first expiry that frees at least one unit of the active quota,
    # rather than implying that the entire daily allowance returns at once.
    next_release_at = None
    if recent_sales and limit is not None and used > 0:
        units_to_release = max(1, used - limit + 1)
        released = 0
        for row in recent_sales:
            released += int(row.quantity)
            if released >= units_to_release:
                started_at = row.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                next_release_at = started_at + MATERIAL_SALE_WINDOW
                break
    remaining = 2_147_483_647 if limit is None else max(0, limit - used)
    return {"limit": limit, "used": used, "remaining": remaining,
            "next_release_at": next_release_at}


def _sale_duration_seconds(rarity: str, tier: int, quantity: int, reduction: int) -> int:
    base = RARITY_SECONDS.get(rarity, 30) * max(1, tier) * max(1, quantity)
    return max(5, floor(base * (100 - reduction) / 100))


def _sale_unit_value(base_value: int, bonus_percent: int) -> int:
    return market_sale_unit_value(base_value, bonus_percent)


def get_market_page_context(db: Session, guild: Guild) -> dict[str, object]:
    ensure_guild_buildings(db, guild.id)
    now = utc_now()
    market = get_market_bonuses(db, guild.id)
    if market["level"] < 1:
        return {
            "market": market,
            "material_sale_quota": get_material_sale_quota(db, guild.id),
            "inventory_items": [],
            "equipment_items": [],
            "active_sales": [],
            "ready_sales_count": 0,
            "completed_sales": [],
            "now": now,
        }
    sales = list_market_sales_by_guild(db, guild.id)
    active_sales = [sale for sale in sales if sale.status == "in_progress"]
    for sale in active_sales:
        prepare_timer_context(sale, now)
    completed_sales = [sale for sale in sales if sale.status == "completed"][:10]
    return {
        "market": market,
        "material_sale_quota": get_material_sale_quota(db, guild.id, now=now),
        "inventory_items": get_inventory_for_guild(db, guild.id),
        "equipment_items": [
            item for item in get_equipment_for_guild(db, guild.id)
            if item.equipped_to_mercenary_id is None and item.market_sale is None
        ],
        "active_sales": active_sales,
        "ready_sales_count": sum(1 for sale in active_sales if sale.ready_for_loot),
        "completed_sales": completed_sales,
        "now": now,
    }


def start_material_sale(
    db: Session,
    guild: Guild,
    item_template_id: str,
    quantity: str,
    *,
    commit: bool = True,
) -> MarketSale:
    if get_building_level(db, guild.id, "market") < 1:
        raise MarketError("Evolua o Mercado para o nível 1 antes de anunciar itens.")
    try:
        parsed_item_id = int(item_template_id)
        parsed_quantity = int(quantity)
    except ValueError as exc:
        raise MarketError("Item ou quantidade invalida.") from exc
    if parsed_quantity < 1:
        raise MarketError("Quantidade deve ser pelo menos 1.")

    with _material_sale_lock(guild.id):
        inventory_item = get_inventory_item(db, guild.id, parsed_item_id)
        if inventory_item is not None:
            db.refresh(inventory_item)
        if inventory_item is None or inventory_item.quantity < parsed_quantity:
            raise MarketError("Quantidade indisponivel no inventario.")
        return _start_sale(db, guild, inventory_item.item_template, parsed_quantity,
                           inventory_item=inventory_item, commit=commit)


def start_equipment_sale(db: Session, guild: Guild, item_instance_id: str) -> MarketSale:
    if get_building_level(db, guild.id, "market") < 1:
        raise MarketError("Evolua o Mercado para o nível 1 antes de anunciar itens.")
    try:
        parsed_item_id = int(item_instance_id)
    except ValueError as exc:
        raise MarketError("Equipamento invalido.") from exc
    item = get_item_instance_by_guild(db, guild.id, parsed_item_id)
    if item is None or item.equipped_to_mercenary_id is not None or item.market_sale is not None:
        raise MarketError("Equipamento indisponivel para venda.")
    return _start_sale(db, guild, item.item_template, 1, item_instance=item)


def _start_sale(db, guild, item_template, quantity, inventory_item=None, item_instance=None, commit=True):
    bonuses = get_market_bonuses(db, guild.id)
    if bonuses["level"] <= 0:
        raise MarketError("Construa o Mercado antes de anunciar itens.")
    if count_active_market_sales(db, guild.id) >= bonuses["slots"]:
        raise MarketError("Todos os espacos de venda estao ocupados.")

    started_at = utc_now()
    if inventory_item is not None and item_template.item_type == "material":
        quota = get_material_sale_quota(db, guild.id, now=started_at)
        if quota["limit"] is not None and int(quantity) > quota["remaining"]:
            raise MarketError(
                f"Limite de materiais nas últimas 24h: restam {quota['remaining']} de {quota['limit']} unidades."
            )

    unit_value = _sale_unit_value(item_template.base_sell_value, bonuses["value_bonus_percent"])
    ends_at = started_at + timedelta(seconds=_sale_duration_seconds(
        item_template.rarity, item_template.tier, quantity, bonuses["time_reduction_percent"]
    ))
    sale = create_market_sale(db, {
        "guild_id": guild.id,
        "item_template_id": item_template.id,
        "item_instance_id": item_instance.id if item_instance else None,
        "quantity": quantity,
        "unit_value": unit_value,
        "total_value": unit_value * quantity,
        "status": "in_progress",
        "started_at": started_at,
        "ends_at": ends_at,
    })
    if inventory_item is not None:
        remove_inventory_quantity(db, inventory_item, quantity)
    if commit:
        db.commit()
        db.refresh(sale)
    else:
        db.flush()
    return sale


def collect_market_sale(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    sale_id: int,
    *,
    commit: bool = True,
) -> MarketSale:
    if resources is None:
        raise MarketError("Recursos da guilda indisponiveis.")
    sale = get_market_sale_by_guild(db, guild.id, sale_id)
    if sale is None or sale.status != "in_progress":
        raise MarketError("Venda nao encontrada ou ja coletada.")
    now = utc_now()
    ends_at = sale.ends_at if sale.ends_at.tzinfo else sale.ends_at.replace(tzinfo=timezone.utc)
    if now < ends_at:
        raise MarketError("A venda ainda nao foi concluida.")

    resources.gold += sale.total_value
    add_guild_xp(guild, 2 if sale.total_value >= 100 else 1)
    if sale.item_instance is not None:
        item_instance = sale.item_instance
        sale.item_instance = None
        db.flush()
        delete_item_instance(db, item_instance)
    sale.status = "completed"
    sale.collected_at = now
    db.add(sale)
    db.add(resources)
    db.add(guild)
    record_guild_stat(db, guild.id, "market_sales", 1)
    if commit:
        db.commit()
        db.refresh(sale)
    else:
        db.flush()
    return sale


def collect_all_ready_market_sales(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
) -> dict[str, int]:
    now = utc_now()
    ready_sales = [
        sale for sale in list_market_sales_by_guild(db, guild.id)
        if sale.status == "in_progress"
        and now >= (sale.ends_at if sale.ends_at.tzinfo else sale.ends_at.replace(tzinfo=timezone.utc))
    ]
    if not ready_sales:
        raise MarketError("Nenhuma venda está pronta para coleta.")
    total = 0
    for sale in ready_sales:
        total += sale.total_value
        collect_market_sale(db, guild, resources, sale.id)
    return {"count": len(ready_sales), "gold": total}
