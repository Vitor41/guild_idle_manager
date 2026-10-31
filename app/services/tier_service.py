from app.services.balance_service import (
    RARITY_ORDER,
    get_mercenary_power_range,
    rarity_progression_bonus_percent,
)
from app.services.display_service import rarity_label


RARITY_DESCRIPTIONS = {
    "common": "Base confiável, sem bônus adicional de progressão.",
    "uncommon": "Potencial inicial protegido e crescimento levemente superior.",
    "rare": "Mercenário especial com atributos fortes e evolução ampliada.",
    "epic": "Qualidade elevada para equipes de conteúdo avançado.",
    "legendary": "Poder excepcional e progressão de alto valor.",
    "mythic": "O ápice atual de raridade para mercenários e equipamentos.",
}

def get_tier_guide_context() -> dict[str, object]:
    rarity_cards: list[dict[str, object]] = []
    for rarity in RARITY_ORDER:
        minimum_power, maximum_power = get_mercenary_power_range(rarity)
        rarity_cards.append(
            {
                "code": rarity,
                "label": rarity_label(rarity),
                "description": RARITY_DESCRIPTIONS[rarity],
                "progression_bonus_percent": rarity_progression_bonus_percent(rarity),
                "minimum_power": minimum_power,
                "maximum_power": maximum_power,
            }
        )
    return {"rarity_cards": rarity_cards}
