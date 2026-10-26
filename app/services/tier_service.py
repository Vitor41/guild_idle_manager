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

ITEM_TIER_GUIDE = [
    {"tier": 1, "label": "Inicial", "description": "Equipamentos básicos e requisitos baixos."},
    {"tier": 2, "label": "Aprimorado", "description": "Base de atributos superior para progressão intermediária."},
    {"tier": 3, "label": "Avançado", "description": "Itens voltados a missões e masmorras mais exigentes."},
    {"tier": 4, "label": "Superior", "description": "Faixas de bônus altas e requisitos avançados."},
    {"tier": 5, "label": "Excepcional", "description": "Referência preparada para equipamentos de fim de jogo."},
    {"tier": 6, "label": "Heroico", "description": "Equipamentos de regiões perigosas e desafios heroicos."},
    {"tier": 7, "label": "Lendário", "description": "Poder elevado para expedições de elite e chefes."},
    {"tier": 8, "label": "Primordial", "description": "O patamar máximo atual para conteúdos de nível 301 a 350."},
]


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
    return {"rarity_cards": rarity_cards, "item_tiers": ITEM_TIER_GUIDE}
