from math import ceil, floor

from app.models.mercenary import Mercenary


APPRENTICE_RARITY_CAPS = {
    "common": 7,
    "uncommon": 10,
}

SPECIAL_RARITY_CAPS = {
    "rare": 36,
    "epic": 48,
    "legendary": 66,
    "mythic": 92,
}

RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary", "mythic")

MERCENARY_POWER_RANGES = {
    "common": {"minimum": 1, "maximum": 18},
    "uncommon": {"minimum": 10, "maximum": 25},
    "rare": {"minimum": 45, "maximum": None},
    "epic": {"minimum": 60, "maximum": None},
    "legendary": {"minimum": 85, "maximum": None},
    "mythic": {"minimum": 115, "maximum": None},
}

RARITY_PROGRESSION_BONUS_PERCENT = {
    "common": 0,
    "uncommon": 1,
    "rare": 2,
    "epic": 3,
    "legendary": 4,
    "mythic": 5,
}

TAVERN_MANUAL_REFRESH_COST = 100

CLASS_PRIMARY_ATTRIBUTES = {
    "apprentice": ("power", "vitality", "agility", "intelligence", "luck"),
    "warrior": ("power", "vitality"),
    "knight": ("vitality", "armor"),
    "templar": ("vitality", "armor"),
    "blade": ("power", "agility"),
    "reaper": ("power", "agility"),
    "rogue": ("agility", "intelligence"),
    "assassin": ("agility", "luck"),
    "predator": ("agility", "luck", "power"),
    "ninja": ("agility", "intelligence"),
    "shinobi": ("agility", "intelligence", "luck"),
    "mage": ("intelligence", "luck"),
    "wizard": ("intelligence", "vitality"),
    "arcane": ("intelligence", "luck"),
    "mentalist": ("intelligence", "luck"),
    "warlock": ("intelligence", "luck"),
    "cleric": ("intelligence", "vitality"),
    "priest": ("intelligence", "vitality"),
    "high_priest": ("intelligence", "vitality"),
    "paladin": ("power", "vitality"),
    "sentinel": ("power", "vitality"),
    "archer": ("agility", "luck"),
    "ranger": ("agility", "vitality", "luck"),
    "patroller": ("agility", "vitality", "luck"),
    "shooter": ("agility", "luck"),
    "renegade": ("agility", "luck"),
}

CLASS_SUCCESS_BONUS = {
    "warrior": 1,
    "knight": 2,
    "templar": 3,
    "blade": 2,
    "reaper": 3,
    "rogue": 1,
    "assassin": 2,
    "predator": 3,
    "ninja": 2,
    "shinobi": 3,
    "mage": 1,
    "wizard": 2,
    "arcane": 3,
    "mentalist": 2,
    "warlock": 3,
    "cleric": 1,
    "priest": 2,
    "high_priest": 3,
    "paladin": 2,
    "sentinel": 3,
    "archer": 1,
    "ranger": 2,
    "patroller": 3,
    "shooter": 2,
    "renegade": 3,
}

ROLE_DESCRIPTIONS = {
    "balanced": "Base flexível para decidir a evolução depois do bônus inicial.",
    "frontline": "Linha de frente com bons ganhos de FOR e VIT.",
    "tank": "Defesa alta, ideal para conteúdos difíceis.",
    "duelist": "Ofensivo e ágil, indicado para arma secundária.",
    "skirmisher": "Rápido, bom com AGI e Sorte.",
    "caster": "Escala melhor com INT e efeitos mágicos.",
    "support": "Suporte com INT e VIT para reduzir riscos futuros.",
    "ranged": "Dano consistente à distância, com AGI e Sorte.",
}


def xp_required_for_level(level: int) -> int:
    return max(1, level) * 100


def calculate_power_score(attributes: dict[str, int]) -> int:
    return (
        attributes["power"]
        + floor(attributes["vitality"] / 2)
        + floor(attributes["agility"] / 2)
        + floor(attributes["intelligence"] / 2)
        + floor(attributes["luck"] / 3)
        + floor(attributes.get("armor", 0) / 2)
    )


def get_mercenary_power_range(rarity: str) -> tuple[int, int | None]:
    power_range = MERCENARY_POWER_RANGES.get(rarity, MERCENARY_POWER_RANGES["common"])
    return int(power_range["minimum"]), power_range["maximum"]


def rarity_progression_bonus_percent(rarity: str | None) -> int:
    return RARITY_PROGRESSION_BONUS_PERCENT.get(rarity or "common", 0)


def apply_rarity_progression_bonus(base_gain: int, rarity: str | None) -> int:
    if base_gain <= 0:
        return 0
    bonus_percent = rarity_progression_bonus_percent(rarity)
    if bonus_percent <= 0:
        return base_gain
    return base_gain + ceil(base_gain * bonus_percent / 100)


def levelup_gain_with_rarity(base_gain: int, rarity: str | None, new_level: int) -> int:
    if base_gain <= 0:
        return 0
    bonus_percent = rarity_progression_bonus_percent(rarity)
    if bonus_percent <= 0:
        return base_gain

    completed_levelups = max(1, new_level - 1)
    previous_levelups = completed_levelups - 1
    accumulated = floor(completed_levelups * base_gain * bonus_percent / 100)
    previous_accumulated = floor(previous_levelups * base_gain * bonus_percent / 100)
    return base_gain + accumulated - previous_accumulated


def class_code(mercenary: Mercenary) -> str:
    if mercenary.mercenary_class and mercenary.mercenary_class.code:
        return mercenary.mercenary_class.code
    return ""


def class_success_bonus(mercenary: Mercenary) -> int:
    return CLASS_SUCCESS_BONUS.get(class_code(mercenary), 0)


def party_class_success_bonus(mercenaries: list[Mercenary]) -> int:
    if not mercenaries:
        return 0
    role_types = {
        mercenary.mercenary_class.role_type
        for mercenary in mercenaries
        if mercenary.mercenary_class is not None
    }
    balanced_party_bonus = 2 if len(mercenaries) >= 3 and len(role_types) >= 3 else 0
    return min(8, sum(class_success_bonus(mercenary) for mercenary in mercenaries) + balanced_party_bonus)


def power_success_adjustment(power_score: int, recommended_power: int) -> int:
    if recommended_power <= 0:
        return min(15, floor(power_score / 20))
    ratio = power_score / recommended_power
    if ratio >= 1:
        return min(15, 3 + floor((ratio - 1) * 18))
    return -min(40, ceil((1 - ratio) * 45))


def rarity_success_bonus(mercenaries: list[Mercenary], recommended_level: int) -> int:
    if recommended_level < 51:
        return 0
    stage = min(4, 1 + max(0, recommended_level - 51) // 75)
    ranks = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4, "mythic": 5}
    if not mercenaries:
        return 0
    average_rank = sum(ranks.get(mercenary.rarity, 0) for mercenary in mercenaries) / len(mercenaries)
    return min(20, floor(average_rank * stage))
