from math import ceil, floor

from app.services.building_balance_service import market_values


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
