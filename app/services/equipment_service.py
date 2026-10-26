from math import floor
from random import choice, randint

from sqlalchemy.orm import Session

from app.models.item import GuildItemInstance, ItemTemplate
from app.models.mercenary import Mercenary
from app.models.mission import MissionTemplate
from app.repositories.item_repository import (
    count_equipped_items_in_slot,
    create_item_instance,
    get_equipped_item_in_slot,
    get_item_instance_by_guild,
    list_available_item_instances_by_guild,
    list_equipment_for_mercenary,
)
from app.repositories.mercenary_repository import get_mercenary_by_guild
from app.services.balance_service import (
    calculate_power_score,
    class_success_bonus,
    party_class_success_bonus,
    power_success_adjustment,
    rarity_success_bonus,
)
from app.services.display_service import format_attribute_bonus


LEGACY_SLOT_MAP = {
    "weapon": "main_hand",
    "armor": "chest",
    "accessory": "ring",
}
EQUIPMENT_SLOTS = {
    "main_hand",
    "off_hand",
    "shield",
    "helmet",
    "chest",
    "gloves",
    "boots",
    "earring",
    "ring",
    "belt",
    "necklace",
}
EQUIPMENT_SLOT_LABELS = {
    "main_hand": "Arma principal",
    "off_hand": "Arma secundaria",
    "shield": "Escudo",
    "helmet": "Elmo",
    "chest": "Peito",
    "gloves": "Luvas",
    "boots": "Botas",
    "earring": "Brinco",
    "ring": "Anel",
    "belt": "Cinto",
    "necklace": "Colar",
}
EQUIPMENT_SLOT_CAPACITY = {
    "earring": 2,
    "ring": 2,
}
EQUIPMENT_RNG_ATTRIBUTES = ("power", "vitality", "agility", "intelligence", "luck", "armor")
EQUIPMENT_ATTRIBUTE_KEYS = (
    "power",
    "vitality",
    "agility",
    "intelligence",
    "luck",
    "armor",
)

CLASS_FAMILIES = {
    "warrior": {"warrior", "knight", "templar", "blade", "reaper"},
    "rogue": {"rogue", "assassin", "predator", "ninja", "shinobi"},
    "mage": {"mage", "wizard", "arcane", "mentalist", "warlock"},
    "cleric": {"cleric", "priest", "high_priest", "paladin", "sentinel"},
    "archer": {"archer", "ranger", "patroller", "shooter", "renegade"},
}
FAMILY_WEAPONS = {
    "warrior": {"sword", "axe", "mace"},
    "rogue": {"dagger", "sword"},
    "mage": {"staff", "wand", "book", "orb"},
    "cleric": {"mace", "book", "staff"},
    "archer": {"bow", "crossbow", "pistol"},
}
CLASS_FAMILY_LABELS = {
    "warrior": "Guerreiro", "rogue": "Ladino", "mage": "Mago",
    "cleric": "Clerigo", "archer": "Arqueiro", "apprentice": "Aprendiz",
}
ARMOR_WEIGHT_LABELS = {"heavy": "pesada", "light": "leve", "cloth": "de tecido", "generic": "versatil"}


class EquipmentError(ValueError):
    pass


def normalize_equipment_slot(slot: str | None) -> str:
    if not slot:
        return ""
    return LEGACY_SLOT_MAP.get(slot, slot)


def get_equipment_slot_label(slot: str) -> str:
    return EQUIPMENT_SLOT_LABELS.get(normalize_equipment_slot(slot), slot)


def get_slot_capacity(slot: str) -> int:
    return EQUIPMENT_SLOT_CAPACITY.get(normalize_equipment_slot(slot), 1)


def get_class_family(mercenary: Mercenary) -> str:
    code = (mercenary.mercenary_class.code or "").lower() if mercenary.mercenary_class else ""
    if code == "apprentice":
        return "apprentice"
    for family, codes in CLASS_FAMILIES.items():
        if code in codes:
            return family
    return "apprentice"


def _item_group(item_template: ItemTemplate) -> str:
    if item_template.icon_group:
        return item_template.icon_group.lower()
    name = item_template.name.lower()
    for group, tokens in {
        "sword": ("espada",), "axe": ("machado",), "mace": ("maca", "martelo"),
        "dagger": ("adaga", "punhal"), "staff": ("cajado",), "book": ("livro", "tomo"),
        "bow": ("arco",), "pistol": ("pistola",), "shield": ("escudo",),
    }.items():
        if any(token in name for token in tokens):
            return group
    return normalize_equipment_slot(item_template.equipment_slot)


def _armor_weight(item_template: ItemTemplate) -> str:
    text = f"{item_template.name} {item_template.description} {item_template.icon_group or ''}".lower()
    if any(token in text for token in ("pesad", "ferro", "aco", "cota", "placa", "reforcad")):
        return "heavy"
    if any(token in text for token in ("robe", "manto", "veste", "tunica", "tecido")):
        return "cloth"
    if any(token in text for token in ("leve", "couro", "viajante")):
        return "light"
    return "generic"


def can_class_equip_item(mercenary: Mercenary, item_template: ItemTemplate) -> tuple[bool, str]:
    family = get_class_family(mercenary)
    family_label = CLASS_FAMILY_LABELS.get(family, family)
    if family == "apprentice":
        return True, "Aprendiz: equipamento livre"
    slot = normalize_equipment_slot(item_template.equipment_slot)
    group = _item_group(item_template)
    if slot in {"main_hand", "off_hand", "shield"}:
        if group == "shield":
            allowed = family in {"warrior", "cleric"}
        else:
            allowed = group in FAMILY_WEAPONS.get(family, set())
        return allowed, f"Uso por {family_label}"
    if slot in {"helmet", "chest", "gloves", "boots"}:
        weight = _armor_weight(item_template)
        allowed_weights = {
            "warrior": {"heavy", "light", "generic"},
            "rogue": {"light", "generic"},
            "mage": {"cloth", "generic"},
            "cleric": {"cloth", "heavy", "generic"},
            "archer": {"light", "generic"},
        }
        return weight in allowed_weights.get(family, {"generic"}), f"Armadura {ARMOR_WEIGHT_LABELS[weight]} para {family_label}"
    return True, f"Acessorio livre para {family_label}"


def get_item_power_score(item: GuildItemInstance) -> int:
    attributes = {key: getattr(item, f"bonus_{key}") for key in EQUIPMENT_ATTRIBUTE_KEYS}
    if item.rng_bonus_attribute in attributes:
        attributes[item.rng_bonus_attribute] += item.rng_bonus_value
    return calculate_power_score(attributes)


def can_use_off_hand_weapon(mercenary: Mercenary) -> bool:
    profile = (mercenary.mercenary_class.allowed_weapon_profile or "").lower() if mercenary.mercenary_class else ""
    code = (mercenary.mercenary_class.code or "").lower() if mercenary.mercenary_class else ""
    return (
        "dual" in profile
        or code in {"rogue", "assassin", "ninja", "shinobi", "blade", "reaper", "shooter"}
    )


def can_use_shield(mercenary: Mercenary) -> bool:
    profile = (mercenary.mercenary_class.allowed_weapon_profile or "").lower() if mercenary.mercenary_class else ""
    code = (mercenary.mercenary_class.code or "").lower() if mercenary.mercenary_class else ""
    blocked = {"bow", "rifle", "dual", "wand_only", "staff"}
    if any(token in profile for token in blocked):
        return False
    return code not in {"archer", "ranger", "patroller", "shooter", "renegade", "wizard", "arcane"}


def create_equipment_instance_from_template(
    db: Session,
    guild_id: int,
    item_template: ItemTemplate,
) -> GuildItemInstance:
    if item_template.item_type != "equipment" or not item_template.equipment_slot:
        raise EquipmentError("Item nao e equipamento.")

    rng_bonus_attribute = None
    rng_bonus_value = 0
    if item_template.rng_bonus_max > 0:
        rng_bonus_attribute = choice(EQUIPMENT_RNG_ATTRIBUTES)
        rng_bonus_value = randint(item_template.rng_bonus_min, item_template.rng_bonus_max)

    return create_item_instance(
        db,
        {
            "guild_id": guild_id,
            "item_template_id": item_template.id,
            "equipment_slot": normalize_equipment_slot(item_template.equipment_slot),
            "required_level": item_template.required_level,
            "bonus_power": item_template.bonus_power,
            "bonus_vitality": item_template.bonus_vitality,
            "bonus_agility": item_template.bonus_agility,
            "bonus_intelligence": item_template.bonus_intelligence,
            "bonus_luck": item_template.bonus_luck,
            "bonus_armor": item_template.bonus_armor,
            "rng_bonus_attribute": rng_bonus_attribute,
            "rng_bonus_value": rng_bonus_value,
        },
    )


def format_equipment_bonus(item_instance: GuildItemInstance) -> str:
    base_parts = []
    for attribute in EQUIPMENT_ATTRIBUTE_KEYS:
        value = getattr(item_instance, f"bonus_{attribute}")
        if value:
            base_parts.append(format_attribute_bonus(attribute, value))
    rng_text = ""
    if item_instance.rng_bonus_attribute and item_instance.rng_bonus_value:
        rng_text = f" | {format_attribute_bonus(item_instance.rng_bonus_attribute, item_instance.rng_bonus_value, generated=True)}"
    return f"{', '.join(base_parts) if base_parts else 'Sem bônus base'}{rng_text}"


def get_equipment_bonus_totals(equipment_items: list[GuildItemInstance]) -> dict[str, int]:
    totals = {attribute: 0 for attribute in EQUIPMENT_ATTRIBUTE_KEYS}
    for item_instance in equipment_items:
        for attribute in EQUIPMENT_ATTRIBUTE_KEYS:
            totals[attribute] += getattr(item_instance, f"bonus_{attribute}")
        if item_instance.rng_bonus_attribute in totals:
            totals[item_instance.rng_bonus_attribute] += item_instance.rng_bonus_value
    return totals


def get_mercenary_attribute_summary(
    db: Session,
    guild_id: int,
    mercenary: Mercenary,
) -> dict[str, object]:
    equipment_items = list_equipment_for_mercenary(db, guild_id, mercenary.id)
    bonus = get_equipment_bonus_totals(equipment_items)
    base = {
        "power": mercenary.power,
        "vitality": mercenary.vitality,
        "agility": mercenary.agility,
        "intelligence": mercenary.intelligence,
        "luck": mercenary.luck,
        "armor": 0,
    }
    total = {attribute: base[attribute] + bonus[attribute] for attribute in EQUIPMENT_ATTRIBUTE_KEYS}
    total_power_score = calculate_total_power_score(total)
    return {
        "base": base,
        "bonus": bonus,
        "total": total,
        "total_power_score": total_power_score,
        "equipment_items": equipment_items,
        "equipment_by_slot": build_equipment_slots(equipment_items),
    }


def build_equipment_slots(equipment_items: list[GuildItemInstance]) -> dict[str, list[GuildItemInstance | None]]:
    slots: dict[str, list[GuildItemInstance | None]] = {
        "helmet": [None],
        "chest": [None],
        "gloves": [None],
        "boots": [None],
        "main_hand": [None],
        "off_hand": [None],
        "necklace": [None],
        "earring": [None, None],
        "belt": [None],
        "ring": [None, None],
    }
    for item in equipment_items:
        slot = normalize_equipment_slot(item.equipment_slot)
        if slot == "shield":
            slot = "off_hand"
        if slot not in slots:
            continue
        for index, current in enumerate(slots[slot]):
            if current is None:
                slots[slot][index] = item
                break
    return slots


def calculate_total_power_score(attributes: dict[str, int]) -> int:
    return calculate_power_score(attributes)


def get_mission_chance_details(
    db: Session,
    guild_id: int,
    mission_template: MissionTemplate,
    mercenary: Mercenary,
) -> dict[str, int]:
    summary = get_mercenary_attribute_summary(db, guild_id, mercenary)
    power_score = int(summary["total_power_score"])
    recommended_power = getattr(mission_template, "recommended_power", 0)
    if not recommended_power:
        party_power = getattr(mission_template, "required_total_power", 0)
        recommended_power = max(1, party_power // max(1, getattr(mission_template, "min_party_size", 1)))
    bonus_chance = power_success_adjustment(power_score, recommended_power)
    class_bonus = class_success_bonus(mercenary)
    from app.services.skill_service import get_mercenary_skill_effects
    skill_bonus = get_mercenary_skill_effects(db, mercenary).get("success_chance", 0)
    rarity_bonus = rarity_success_bonus([mercenary], mission_template.recommended_level)
    final_chance = max(5, min(95, mission_template.base_success_chance + bonus_chance + class_bonus + skill_bonus + rarity_bonus))
    return {
        "base_chance": mission_template.base_success_chance,
        "bonus_chance": bonus_chance,
        "class_bonus_chance": class_bonus,
        "skill_bonus_chance": skill_bonus,
        "rarity_bonus_chance": rarity_bonus,
        "final_chance": final_chance,
        "total_power_score": power_score,
    }


def get_party_power_score(db: Session, guild_id: int, mercenaries: list[Mercenary]) -> int:
    return sum(
        int(get_mercenary_attribute_summary(db, guild_id, mercenary)["total_power_score"])
        for mercenary in mercenaries
    )


def get_party_chance_details(
    db: Session,
    guild_id: int,
    base_success_chance: int,
    mercenaries: list[Mercenary],
    recommended_power: int = 0,
    recommended_level: int = 1,
) -> dict[str, int]:
    power_score = get_party_power_score(db, guild_id, mercenaries)
    bonus_chance = power_success_adjustment(power_score, recommended_power)
    class_bonus = party_class_success_bonus(mercenaries)
    rarity_bonus = rarity_success_bonus(mercenaries, recommended_level)
    final_chance = max(5, min(95, base_success_chance + bonus_chance + class_bonus + rarity_bonus))
    return {
        "base_chance": base_success_chance,
        "bonus_chance": bonus_chance,
        "class_bonus_chance": class_bonus,
        "rarity_bonus_chance": rarity_bonus,
        "final_chance": final_chance,
        "total_power_score": power_score,
    }


def get_available_equipment_for_mercenary(
    db: Session,
    guild_id: int,
    mercenary: Mercenary,
) -> list[GuildItemInstance]:
    equipped_items = list_equipment_for_mercenary(db, guild_id, mercenary.id)
    available: list[GuildItemInstance] = []
    for item in list_available_item_instances_by_guild(db, guild_id):
        compatible, restriction_label = can_class_equip_item(mercenary, item.item_template)
        if item.required_level > mercenary.level or not compatible:
            continue
        item.class_restriction_label = restriction_label
        item.equipment_power_score = get_item_power_score(item)
        slot = normalize_equipment_slot(item.equipment_slot)
        comparable_slots = {"off_hand", "shield"} if slot in {"off_hand", "shield"} else {slot}
        current = [equipped for equipped in equipped_items if normalize_equipment_slot(equipped.equipment_slot) in comparable_slots]
        current_item = min(current, key=get_item_power_score) if len(current) >= get_slot_capacity(slot) else None
        current_score = get_item_power_score(current_item) if current_item else 0
        item.comparison_delta = item.equipment_power_score - current_score
        item.comparison_current_name = current_item.item_template.name if current_item else None
        available.append(item)
    return available


def equip_item(
    db: Session,
    guild_id: int,
    mercenary_id: int,
    item_instance_id: int,
) -> GuildItemInstance:
    mercenary = get_mercenary_by_guild(db, guild_id, mercenary_id)
    if mercenary is None:
        raise EquipmentError("Mercenario nao encontrado.")
    if mercenary.status != "available":
        raise EquipmentError("Mercenario ocupado nao pode trocar equipamentos.")

    item_instance = get_item_instance_by_guild(db, guild_id, item_instance_id)
    if item_instance is None:
        raise EquipmentError("Equipamento nao encontrado.")
    if item_instance.item_template.item_type != "equipment":
        raise EquipmentError("Item nao e equipamento.")
    if item_instance.equipped_to_mercenary_id is not None:
        raise EquipmentError("Equipamento ja esta em uso.")
    item_instance.equipment_slot = normalize_equipment_slot(item_instance.equipment_slot)
    if mercenary.level < item_instance.required_level:
        raise EquipmentError("Mercenario nao possui nivel suficiente para equipar este item.")
    compatible, _ = can_class_equip_item(mercenary, item_instance.item_template)
    if not compatible:
        raise EquipmentError("A classe deste mercenario nao pode usar este equipamento.")
    if item_instance.equipment_slot == "off_hand" and not can_use_off_hand_weapon(mercenary):
        raise EquipmentError("Esta classe nao pode usar arma secundaria.")
    if item_instance.equipment_slot == "shield" and not can_use_shield(mercenary):
        raise EquipmentError("Esta classe nao pode usar escudo.")
    if item_instance.equipment_slot in {"off_hand", "shield"}:
        occupied_off_hand = count_equipped_items_in_slot(
            db,
            guild_id,
            mercenary.id,
            "off_hand",
        ) + count_equipped_items_in_slot(db, guild_id, mercenary.id, "shield")
        if occupied_off_hand >= 1:
            raise EquipmentError("A mao secundaria ja possui um equipamento.")
    elif count_equipped_items_in_slot(db, guild_id, mercenary.id, item_instance.equipment_slot) >= get_slot_capacity(item_instance.equipment_slot):
        raise EquipmentError("Este slot ja possui um equipamento. Desequipe o item atual antes de equipar outro.")

    item_instance.equipped_to_mercenary_id = mercenary.id
    db.add(item_instance)
    db.commit()
    db.refresh(item_instance)
    return item_instance


def unequip_item(
    db: Session,
    guild_id: int,
    mercenary_id: int,
    item_instance_id: int,
) -> GuildItemInstance:
    mercenary = get_mercenary_by_guild(db, guild_id, mercenary_id)
    if mercenary is None:
        raise EquipmentError("Mercenario nao encontrado.")
    if mercenary.status != "available":
        raise EquipmentError("Mercenario ocupado nao pode trocar equipamentos.")

    item_instance = get_item_instance_by_guild(db, guild_id, item_instance_id)
    if item_instance is None or item_instance.equipped_to_mercenary_id != mercenary.id:
        raise EquipmentError("Equipamento nao encontrado neste mercenario.")

    item_instance.equipped_to_mercenary_id = None
    db.add(item_instance)
    db.commit()
    db.refresh(item_instance)
    return item_instance
