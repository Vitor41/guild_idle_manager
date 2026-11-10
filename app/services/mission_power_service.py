from __future__ import annotations

from functools import lru_cache
from itertools import product
from math import ceil
from types import SimpleNamespace

from app.services.balance_service import (
    APPRENTICE_RARITY_CAPS,
    calculate_power_score,
    get_mercenary_power_range,
)
from app.services.progression_service import apply_levelup_attributes


COMMON_APRENTICE_REFERENCE_MAX_LEVEL = 350
REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS = {
    "E": 0.70,
    "D": 0.80,
    "C": 0.95,
    "B": 1.15,
    "A": 1.45,
    "S": 1.80,
}


def _power(attributes: dict[str, int]) -> int:
    return calculate_power_score({**attributes, "armor": 0})


@lru_cache(maxsize=1)
def common_apprentice_max_initial_attributes() -> tuple[tuple[str, int], ...]:
    """Return the highest valid raw-stat Common Tavern roll, without role bonuses."""
    cap = APPRENTICE_RARITY_CAPS["common"]
    minimum_power, maximum_power = get_mercenary_power_range("common")
    names = ("power", "vitality", "agility", "intelligence", "luck")
    valid = []
    for values in product(range(1, cap + 1), repeat=len(names)):
        attributes = dict(zip(names, values))
        score = _power(attributes)
        if minimum_power <= score <= maximum_power:
            valid.append((sum(values), score, values))
    if not valid:
        raise RuntimeError("O catálogo não permite uma combinação válida de Aprendiz Comum.")
    _total, _score, values = max(valid)
    return tuple(zip(names, values))


@lru_cache(maxsize=8)
def common_apprentice_reference_curve(
    max_level: int = COMMON_APRENTICE_REFERENCE_MAX_LEVEL,
) -> tuple[dict[str, int], ...]:
    """Simulate the real Common Apprentice level-up service, including per-level rounding."""
    if not 1 <= max_level <= COMMON_APRENTICE_REFERENCE_MAX_LEVEL:
        raise ValueError(f"Nível de referência deve ficar entre 1 e {COMMON_APRENTICE_REFERENCE_MAX_LEVEL}.")

    attributes = dict(common_apprentice_max_initial_attributes())
    mercenary = SimpleNamespace(
        level=1,
        rarity="common",
        mercenary_class=SimpleNamespace(code="apprentice"),
        **attributes,
    )
    rows: list[dict[str, int]] = []
    for level in range(1, max_level + 1):
        mercenary.level = level
        attributes = {
            name: int(getattr(mercenary, name))
            for name in ("power", "vitality", "agility", "intelligence", "luck")
        }
        rows.append({"level": level, **attributes, "power_score": _power(attributes)})
        if level < max_level:
            mercenary.level = level + 1
            apply_levelup_attributes(mercenary)
    return tuple(rows)


def common_apprentice_reference_power(level: int) -> int:
    if not 1 <= int(level) <= COMMON_APRENTICE_REFERENCE_MAX_LEVEL:
        raise ValueError(f"Nível deve ficar entre 1 e {COMMON_APRENTICE_REFERENCE_MAX_LEVEL}.")
    return common_apprentice_reference_curve()[int(level) - 1]["power_score"]


def recommended_regional_contract_power(
    recommended_level: int,
    rank: str,
    max_party_size: int,
    *,
    fallback_power: int,
) -> int:
    """Snapshot calibrated power for a new regional combat contract."""
    level = int(recommended_level or 1)
    multiplier = REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS.get(str(rank).upper())
    if multiplier is None or not 1 <= level <= COMMON_APRENTICE_REFERENCE_MAX_LEVEL:
        return max(1, int(fallback_power or 1))
    group_size = max(1, int(max_party_size or 1))
    return max(1, ceil(common_apprentice_reference_power(level) * multiplier * group_size))
