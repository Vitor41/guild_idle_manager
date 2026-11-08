from datetime import datetime, timedelta, timezone
from math import floor
from threading import Lock

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.guild import Guild, GuildResources
from app.models.market import MarketSale
from app.repositories.item_repository import (
    delete_item_instance,
    get_inventory_item,
    get_item_instance_by_guild,
    add_inventory_quantity,
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
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.economy_pricing_service import market_sale_unit_value
from app.services.achievement_service import record_guild_stat


RARITY_SECONDS = MARKET_RARITY_SECONDS
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


def _sale_duration_seconds(rarity: str, quantity: int, reduction: int) -> int:
    base = RARITY_SECONDS.get(rarity, 30) * max(1, quantity)
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
            "inventory_items": [],
            "equipment_items": [],
            "active_sales": [],
            "ready_sales_count": 0,
            "completed_sales": [],
            "now": now,
        }
    sales = list_market_sales_by_guild(db, guild.id)
    active_sales = [sale for sale in sales if sale.status == "in_progress"]
    inventory_items = get_inventory_for_guild(db, guild.id)
    slots_available = len(active_sales) < int(market["slots"])
    for item in inventory_items:
        item.market_max_quantity = int(item.quantity) if slots_available else 0
    for sale in active_sales:
        prepare_timer_context(sale, now)
        sale.cancelable = not sale.ready_for_loot
    completed_sales = [sale for sale in sales if sale.status in {"completed", "cancelled"}][:10]
    return {
        "market": market,
        "inventory_items": inventory_items,
        "equipment_items": [
            item for item in get_equipment_for_guild(db, guild.id)
            if item.equipped_to_mercenary_id is None and item.market_sale is None
        ],
        "active_sales": active_sales,
        "ready_sales_count": sum(1 for sale in active_sales if sale.ready_for_loot),
        "completed_sales": completed_sales,
        "rarity_seconds": RARITY_SECONDS,
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
    already_listed = item is not None and db.scalar(
        select(MarketSale.id).where(MarketSale.item_instance_id == item.id).limit(1)
    ) is not None
    if item is None or item.equipped_to_mercenary_id is not None or item.market_sale is not None or already_listed:
        raise MarketError("Equipamento indisponivel para venda.")
    return _start_sale(db, guild, item.item_template, 1, item_instance=item)


def _start_sale(db, guild, item_template, quantity, inventory_item=None, item_instance=None, commit=True):
    bonuses = get_market_bonuses(db, guild.id)
    if bonuses["level"] <= 0:
        raise MarketError("Construa o Mercado antes de anunciar itens.")
    if count_active_market_sales(db, guild.id) >= bonuses["slots"]:
        raise MarketError("Todos os espacos de venda estao ocupados.")

    started_at = utc_now()
    unit_value = _sale_unit_value(item_template.base_sell_value, bonuses["value_bonus_percent"])
    ends_at = started_at + timedelta(seconds=_sale_duration_seconds(
        item_template.rarity, quantity, bonuses["time_reduction_percent"]
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
    now: datetime | None = None,
) -> MarketSale:
    if resources is None:
        raise MarketError("Recursos da guilda indisponiveis.")
    sale = get_market_sale_by_guild(db, guild.id, sale_id)
    if sale is None or sale.status != "in_progress":
        raise MarketError("Venda nao encontrada ou ja coletada.")
    now = now or utc_now()
    now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    ends_at = sale.ends_at if sale.ends_at.tzinfo else sale.ends_at.replace(tzinfo=timezone.utc)
    if now < ends_at:
        raise MarketError("A venda ainda nao foi concluida.")

    claimed = db.execute(
        update(MarketSale)
        .where(
            MarketSale.id == sale_id,
            MarketSale.guild_id == guild.id,
            MarketSale.status == "in_progress",
            MarketSale.ends_at <= now,
        )
        .values(status="completed", collected_at=now)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        raise MarketError("Venda nao encontrada, cancelada ou ja coletada.")

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


def cancel_market_sale(
    db: Session,
    guild: Guild,
    sale_id: int,
    *,
    commit: bool = True,
    now: datetime | None = None,
) -> MarketSale:
    sale = get_market_sale_by_guild(db, guild.id, sale_id)
    if sale is None or sale.status != "in_progress":
        raise MarketError("Venda nao encontrada ou ja finalizada.")
    explicit_now = now is not None
    now = now or utc_now()
    now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    ends_at = sale.ends_at if sale.ends_at.tzinfo else sale.ends_at.replace(tzinfo=timezone.utc)
    if now >= ends_at:
        raise MarketError("O prazo terminou; esta venda esta pronta para coleta e nao pode ser cancelada.")

    item_instance = sale.item_instance
    if sale.item_template.item_type == "equipment" and item_instance is None:
        raise MarketError("A instancia do equipamento nao esta mais reservada; a venda nao foi alterada.")
    if sale.item_template.item_type == "material" and item_instance is not None:
        raise MarketError("A reserva do item esta inconsistente; a venda nao foi alterada.")
    if sale.item_template.item_type not in {"equipment", "material"}:
        raise MarketError("Este tipo de item nao pode ser cancelado pelo Mercado.")
    if item_instance is not None and item_instance.guild_id != guild.id:
        raise MarketError("Equipamento reservado invalido para esta guilda.")
    if item_instance is None:
        capacity = get_inventory_capacity(db, guild)
        used = get_inventory_usage(db, guild.id)
        if used + sale.quantity > capacity:
            raise MarketError(
                "Nao ha espaco suficiente no Armazem para devolver todos os itens; "
                "libere espaco e tente novamente."
            )

    transition_at = now if explicit_now else utc_now()
    if transition_at >= ends_at:
        raise MarketError("O prazo terminou; esta venda esta pronta para coleta e nao pode ser cancelada.")

    claimed = db.execute(
        update(MarketSale)
        .where(
            MarketSale.id == sale_id,
            MarketSale.guild_id == guild.id,
            MarketSale.status == "in_progress",
            MarketSale.ends_at > transition_at,
        )
        .values(status="cancelled", cancelled_at=transition_at)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        raise MarketError("A venda mudou de estado; confira o Mercado antes de tentar novamente.")

    if item_instance is None:
        add_inventory_quantity(db, guild.id, sale.item_template_id, sale.quantity)
    else:
        # Releasing the unique sale FK makes this exact instance available again.
        sale.item_instance_id = None
        db.flush()
    sale.status = "cancelled"
    sale.cancelled_at = transition_at
    db.add(sale)
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
