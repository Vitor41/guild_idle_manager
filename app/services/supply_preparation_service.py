"""Economic quote and immutable snapshot for the optional regional supply."""

from __future__ import annotations

import json
from math import floor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guild import GuildResources
from app.services.economy_pricing_service import market_sale_unit_value


SUPPLY_CHANCE_BONUS_PP = 5
SUPPLY_RANK_COST_CAP = {"E": 1, "D": 2, "C": 3, "B": 4, "A": 5, "S": 6}


def estimate_drop_sale_value(db: Session, guild_id: int, drops: list[object], multiplier: int) -> float:
    """Conservative expected resale value; ignores positive drop/quantity bonuses."""
    expected = 0.0
    from app.services.market_service import get_market_bonuses

    market = get_market_bonuses(db, guild_id)
    for drop in drops:
        item = getattr(drop, "item_template", None)
        if item is None:
            continue
        chance = max(0.0, min(100.0, float(getattr(drop, "drop_chance", 0)))) / 100
        quantity = (int(getattr(drop, "min_quantity", 1)) + int(getattr(drop, "max_quantity", 1))) / 2
        if market["level"] < 1:
            continue
        expected += chance * quantity * market_sale_unit_value(item.base_sell_value, market["value_bonus_percent"]) * max(1, multiplier)
    return expected


def quote_supply(
    *, rank: str, success_gold: int, expected_drop_sale: float = 0.0,
    multiplier: int = 1, available_gold: int = 0, applied_bonus_pp: int = SUPPLY_CHANCE_BONUS_PP,
) -> dict[str, object]:
    """Charge at most both the 5pp incremental expected value and rank cap.

    XP is deliberately excluded: it has no stable gold denomination in the economy.
    """
    normalized_rank = str(rank or "E").upper()
    rank_unit_cap = SUPPLY_RANK_COST_CAP.get(normalized_rank)
    if rank_unit_cap is None:
        return {"available": False, "reason": "Rank de suprimento inválido.", "rank": normalized_rank}
    cap = rank_unit_cap * max(1, int(multiplier))
    base_win_value = max(0, int(success_gold)) + max(0.0, float(expected_drop_sale))
    applied_bonus_pp = max(0, min(SUPPLY_CHANCE_BONUS_PP, int(applied_bonus_pp)))
    incremental_ev = base_win_value * applied_bonus_pp / 100
    gold_only_incremental_ev = max(0, int(success_gold)) * applied_bonus_pp / 100
    # Charge against gold-only EV. Drop sale value is reported, but cannot make a
    # supply charge unsafe when storage is full or a player chooses not to sell.
    cost = min(cap, floor(incremental_ev + 1e-9), floor(gold_only_incremental_ev + 1e-9))
    if cost < 1:
        return {
            "available": False, "reason": "O retorno esperado do bônus ainda não cobre 1 ouro.",
            "rank": normalized_rank, "cost_gold": 0, "incremental_ev_gold": round(incremental_ev, 2),
            "rank_cost_cap_gold": cap,
            "gold_only_incremental_ev_gold": round(gold_only_incremental_ev, 2),
            "victory_value_gold": round(base_win_value, 2), "chance_bonus_pp": applied_bonus_pp,
        }
    if int(available_gold) < cost:
        return {
            "available": False, "reason": f"Saldo insuficiente: custo {cost} ouro; saldo {int(available_gold)}.",
            "rank": normalized_rank, "cost_gold": cost, "incremental_ev_gold": round(incremental_ev, 2),
            "rank_cost_cap_gold": cap,
            "gold_only_incremental_ev_gold": round(gold_only_incremental_ev, 2),
            "victory_value_gold": round(base_win_value, 2), "chance_bonus_pp": applied_bonus_pp,
        }
    return {
        "available": True, "reason": "", "rank": normalized_rank, "cost_gold": cost,
        "incremental_ev_gold": round(incremental_ev, 2), "victory_value_gold": round(base_win_value, 2),
        "rank_cost_cap_gold": cap,
        "gold_only_incremental_ev_gold": round(gold_only_incremental_ev, 2),
        "chance_bonus_pp": applied_bonus_pp, "multiplier": max(1, int(multiplier)),
    }


def guild_gold(db: Session, guild_id: int) -> int:
    resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))
    return int(resources.gold) if resources is not None else 0


def prepare_supply_snapshot(db: Session, guild_id: int, rank: str, success_gold: int,
                            drops: list[object], multiplier: int, selected: bool,
                            base_final_chance: int = 5) -> tuple[dict[str, object] | None, int]:
    if not selected:
        return None, 0
    quote = quote_supply(rank=rank, success_gold=success_gold,
                         expected_drop_sale=estimate_drop_sale_value(db, guild_id, drops, multiplier),
                         multiplier=multiplier, available_gold=guild_gold(db, guild_id),
                         applied_bonus_pp=max(0, min(SUPPLY_CHANCE_BONUS_PP, 95 - int(base_final_chance))))
    if not quote["available"]:
        raise ValueError(str(quote["reason"]))
    snapshot = {"schema": 1, "supply": "regional_group_supply", "base_final_chance": int(base_final_chance), **quote}
    return snapshot, int(quote["cost_gold"])


def encode_supply_snapshot(snapshot: dict[str, object] | None) -> str | None:
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True) if snapshot else None


def supply_bonus_from_snapshot(snapshot_json: str | None) -> int:
    if not snapshot_json:
        return 0
    try:
        snapshot = json.loads(snapshot_json)
    except (TypeError, json.JSONDecodeError):
        return 0
    if not isinstance(snapshot, dict) or snapshot.get("schema") != 1 or snapshot.get("supply") != "regional_group_supply":
        return 0
    try:
        return max(0, min(SUPPLY_CHANCE_BONUS_PP, int(snapshot.get("chance_bonus_pp", 0))))
    except (TypeError, ValueError):
        return 0
