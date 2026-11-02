from math import ceil, floor

from app.services.building_balance_service import market_values


EQUIPMENT_COMMON_BASE_BY_SLOT = {
    "main_hand": 24, "shield": 23, "chest": 30, "helmet": 22,
    "gloves": 18, "boots": 18, "ring": 16, "necklace": 17,
    "earring": 15, "belt": 16,
}
EQUIPMENT_RARITY_PREMIUM_PERCENT = {
    "common": 0, "uncommon": 15, "rare": 35, "epic": 60,
    "legendary": 90, "mythic": 125,
}


def equipment_base_sell_value(slot: str | None, rarity: str) -> int:
    """Type-based common price with strictly increasing rarity premiums."""
    common_value = EQUIPMENT_COMMON_BASE_BY_SLOT.get(str(slot or ""), 18)
    premium = EQUIPMENT_RARITY_PREMIUM_PERCENT.get(str(rarity or "common").lower(), 0)
    return common_value + ceil(common_value * premium / 100)


def market_sale_unit_value(base_sell_value: int, value_bonus_percent: int) -> int:
    return max(1, floor(max(1, int(base_sell_value)) * (100 + max(0, int(value_bonus_percent))) / 100))


def dock_no_arbitrage_price_floor(base_sell_value: int) -> int:
    """Keep a purchased item one gold above its best possible market resale value."""
    maximum_bonus = market_values(100)["value_bonus_percent"]
    return market_sale_unit_value(base_sell_value, maximum_bonus) + 1


def effective_dock_unit_price(configured_price: int, base_sell_value: int) -> int:
    return max(max(1, int(configured_price)), dock_no_arbitrage_price_floor(base_sell_value))


def effective_crafting_gold_cost(
    configured_gold_cost: int,
    output_base_sell_value: int,
    output_quantity: int,
    dock_material_cost: int | float,
) -> int:
    """Keep the crafting-to-Market conversion from returning positive gold."""
    market_value = market_sale_unit_value(
        output_base_sell_value, market_values(100)["value_bonus_percent"]
    ) * max(1, int(output_quantity))
    break_even_guard = ceil(market_value - max(0, float(dock_material_cost)) + 1)
    return max(max(0, int(configured_gold_cost)), break_even_guard)
