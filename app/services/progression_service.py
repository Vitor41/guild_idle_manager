from app.models.mercenary import Mercenary, MercenaryClass
from app.services.balance_service import (
    CLASS_PRIMARY_ATTRIBUTES,
    apply_rarity_progression_bonus,
    levelup_gain_with_rarity,
    xp_required_for_level,
)


def add_xp_and_apply_levelups(mercenary: Mercenary, xp_gain: int) -> list[str]:
    level_up_messages: list[str] = []
    mercenary.xp += xp_gain

    while mercenary.xp >= xp_required_for_level(mercenary.level):
        required_xp = xp_required_for_level(mercenary.level)
        mercenary.xp -= required_xp
        mercenary.level += 1
        apply_levelup_attributes(mercenary)
        level_up_messages.append(f"{mercenary.name} subiu para o nível {mercenary.level}.")

    return level_up_messages


def apply_levelup_attributes(mercenary: Mercenary) -> None:
    class_code = mercenary.mercenary_class.code if mercenary.mercenary_class else ""
    gains = {"power": 1, "vitality": 1}
    for primary_attribute in CLASS_PRIMARY_ATTRIBUTES.get(class_code or "", ("power",)):
        if primary_attribute == "armor":
            continue
        gains[primary_attribute] = gains.get(primary_attribute, 0) + 1

    for attribute, base_gain in gains.items():
        gain = levelup_gain_with_rarity(base_gain, mercenary.rarity, mercenary.level)
        setattr(mercenary, attribute, getattr(mercenary, attribute) + gain)


def apply_class_evolution_attributes(
    mercenary: Mercenary,
    from_class: MercenaryClass,
    to_class: MercenaryClass,
) -> dict[str, int]:
    gains: dict[str, int] = {}
    for attribute in ("power", "vitality", "agility", "intelligence", "luck"):
        base_gain = max(
            0,
            int(getattr(to_class, f"base_{attribute}")) - int(getattr(from_class, f"base_{attribute}")),
        )
        gain = apply_rarity_progression_bonus(base_gain, mercenary.rarity)
        if gain:
            setattr(mercenary, attribute, getattr(mercenary, attribute) + gain)
            gains[attribute] = gain
    return gains
