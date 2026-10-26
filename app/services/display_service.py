import re

from app.models.mercenary import Mercenary, MercenaryClass
from app.services.balance_service import rarity_progression_bonus_percent
from app.services.icon_service import get_class_icon_path


RARITY_LABELS = {
    "common": "Comum",
    "uncommon": "Incomum",
    "rare": "Raro",
    "epic": "Épico",
    "legendary": "Lendário",
    "mythic": "Mítico",
}

STATUS_LABELS = {
    "available": "Disponível",
    "busy": "Ocupado",
    "in_progress": "Em andamento",
    "completed": "Concluído",
    "failed": "Falhou",
    "active": "Ativa",
    "expired": "Expirada",
    "hired": "Contratado",
    "dismissed": "Demitido",
}

ITEM_TYPE_LABELS = {
    "material": "Material",
    "consumable": "Consumível",
    "misc": "Diversos",
    "equipment": "Equipamento",
}

ATTRIBUTE_LABELS = {
    "power": "FOR",
    "vitality": "VIT",
    "agility": "AGI",
    "intelligence": "INT",
    "luck": "SOR",
    "armor": "ARM",
}

ATTRIBUTE_TOOLTIPS = {
    "power": "Força aumenta o impacto físico e contribui para o Poder Total.",
    "vitality": "Vitalidade melhora resistência e contribui para o Poder Total.",
    "agility": "Agilidade favorece classes rápidas e contribui para o Poder Total.",
    "intelligence": "Inteligência favorece magia, suporte e contribui para o Poder Total.",
    "luck": "Sorte ajuda recompensas futuras e contribui levemente para o Poder Total.",
    "armor": "Armadura vem de equipamentos e ajuda na sobrevivência.",
}

CLASS_LABELS = {
    "apprentice": "Aprendiz",
    "warrior": "Guerreiro",
    "rogue": "Ladino",
    "mage": "Mago",
    "cleric": "Clérigo",
    "archer": "Arqueiro",
    "knight": "Cavaleiro",
    "blade": "Duelista",
    "templar": "Templário",
    "reaper": "Retalhador",
    "assassin": "Assassino",
    "ninja": "Ninja",
    "predator": "Predador",
    "shinobi": "Shinobi",
    "wizard": "Sábio",
    "mentalist": "Mentalista",
    "arcane": "Arcano",
    "warlock": "Bruxo",
    "priest": "Padre",
    "paladin": "Paladino",
    "high_priest": "Sacerdote",
    "sentinel": "Sentinela",
    "ranger": "Ranger",
    "shooter": "Pistoleiro",
    "patroller": "Patrulheiro",
    "renegade": "Renegado",
}


def rarity_label(rarity: str | None) -> str:
    return RARITY_LABELS.get(rarity or "", rarity or "-")


def clean_generated_name(name: str) -> str:
    return re.sub(r"\s+\d+-\d{2,4}(?=\s*(?:\(|x\d+|$))", "", name).strip()


BONUS_ATTRIBUTE_LABELS = {
    "power": "Força", "vitality": "Vitalidade", "agility": "Agilidade",
    "intelligence": "Inteligência", "luck": "Sorte", "armor": "Armadura",
}


def attribute_label(attribute_key: str | None, *, compact: bool = False) -> str:
    key = (attribute_key or "").lower()
    return ATTRIBUTE_LABELS.get(key, key.upper() or "-") if compact else BONUS_ATTRIBUTE_LABELS.get(key, key.title() or "-")


def format_attribute_bonus(attribute_key: str | None, value: int, *, generated: bool = False) -> str:
    prefix = "Bônus " if generated else ""
    return f"{prefix}+{value} {attribute_label(attribute_key)}"


def localize_bonus_text(text: str) -> str:
    """Translate legacy equipment bonus fragments without mutating stored history."""
    localized = str(text)
    for key, label in BONUS_ATTRIBUTE_LABELS.items():
        localized = re.sub(
            rf"\bRNG\s*\+(\d+)\s+{key}\b",
            rf"Bônus +\1 {label}",
            localized,
            flags=re.IGNORECASE,
        )
        localized = re.sub(
            rf"(?<![\w])\+(\d+)\s+{key}\b",
            rf"+\1 {label}",
            localized,
            flags=re.IGNORECASE,
        )
    return localized.replace("RNG", "Bônus")


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "-")


def item_type_label(item_type: str | None) -> str:
    return ITEM_TYPE_LABELS.get(item_type or "", item_type or "-")


def class_label(mercenary_class: MercenaryClass | None) -> str:
    if mercenary_class is None:
        return "Sem classe"
    if mercenary_class.code in CLASS_LABELS:
        return CLASS_LABELS[mercenary_class.code]
    return mercenary_class.display_name or mercenary_class.name


def annotate_mercenary_display(mercenary: Mercenary) -> Mercenary:
    mercenary.rarity_label = rarity_label(mercenary.rarity)
    mercenary.status_label = status_label(mercenary.status)
    mercenary.class_label = class_label(mercenary.mercenary_class)
    mercenary.class_icon_path = get_class_icon_path(mercenary.mercenary_class)
    mercenary.progression_bonus_percent = rarity_progression_bonus_percent(mercenary.rarity)
    return mercenary
