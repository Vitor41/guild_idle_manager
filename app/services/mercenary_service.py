from math import floor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guild import Guild, GuildResources
from app.models.mercenary import Mercenary
from app.repositories.mercenary_repository import (
    count_mercenaries_by_guild,
    count_mercenaries_by_status,
    create_mercenary,
    create_mercenary_class,
    get_active_mercenary_class,
    get_mercenary_by_guild,
    get_mercenary_class_by_name,
    list_active_mercenary_classes,
    list_mercenaries_by_guild,
    spend_gold,
)
from app.services.building_service import ensure_guild_buildings, get_mercenary_limit
from app.services.equipment_service import (
    EquipmentError,
    equip_item,
    get_available_equipment_for_mercenary,
    get_mercenary_attribute_summary,
    get_equipment_slot_label,
    unequip_item,
)
from app.services.icon_service import get_item_icon, get_item_icon_path, get_slot_icon
from app.services.class_service import get_weapon_profile_label
from app.services.profession_service import PROFESSION_FAMILY_LABELS
from app.services.display_service import (
    ATTRIBUTE_TOOLTIPS,
    BONUS_ATTRIBUTE_LABELS,
    annotate_mercenary_display,
    clean_generated_name,
    rarity_label,
)
from app.services.skill_service import effect_label, effect_suffix, ensure_mercenary_skills


RECRUITMENT_COST_GOLD = 50

INITIAL_MERCENARY_CLASSES = [
    {
        "name": "Guerreiro",
        "description": "Combatente resistente para a linha de frente.",
        "base_power": 8,
        "base_vitality": 8,
        "base_agility": 4,
        "base_intelligence": 2,
        "base_luck": 3,
        "is_active": True,
    },
    {
        "name": "Arqueiro",
        "description": "Atirador agil com bom alcance e precisao.",
        "base_power": 6,
        "base_vitality": 4,
        "base_agility": 8,
        "base_intelligence": 3,
        "base_luck": 4,
        "is_active": True,
    },
    {
        "name": "Ladino",
        "description": "Especialista veloz em risco, sorte e oportunidades.",
        "base_power": 5,
        "base_vitality": 4,
        "base_agility": 9,
        "base_intelligence": 3,
        "base_luck": 6,
        "is_active": True,
    },
    {
        "name": "Mago",
        "description": "Conjurador de alto intelecto e poder arcano.",
        "base_power": 7,
        "base_vitality": 3,
        "base_agility": 3,
        "base_intelligence": 9,
        "base_luck": 4,
        "is_active": True,
    },
    {
        "name": "Clerigo",
        "description": "Devoto equilibrado com foco em suporte e sabedoria.",
        "base_power": 4,
        "base_vitality": 5,
        "base_agility": 3,
        "base_intelligence": 8,
        "base_luck": 5,
        "is_active": True,
    },
]


class MercenaryRecruitmentError(ValueError):
    pass


class MercenaryEquipmentError(ValueError):
    pass


class MercenaryDismissalError(ValueError):
    pass


def seed_initial_mercenary_classes(db: Session) -> None:
    created_any = False
    for class_data in INITIAL_MERCENARY_CLASSES:
        if get_mercenary_class_by_name(db, str(class_data["name"])):
            continue
        create_mercenary_class(db, class_data)
        created_any = True

    if created_any:
        db.commit()


def get_mercenaries_page_context(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    sort_by: str = "power",
) -> dict[str, object]:
    ensure_guild_buildings(db, guild.id)
    mercenaries = list_mercenaries_by_guild(db, guild.id)
    summaries = {
        mercenary.id: get_mercenary_attribute_summary(db, guild.id, mercenary)
        for mercenary in mercenaries
    }
    for mercenary in mercenaries:
        annotate_mercenary_display(mercenary)
    sorters = {
        "power": lambda mercenary: int(summaries[mercenary.id]["total_power_score"]),
        "level": lambda mercenary: mercenary.level,
        "rarity": lambda mercenary: {
            "common": 1,
            "uncommon": 2,
            "rare": 3,
            "epic": 4,
            "legendary": 5,
            "mythic": 6,
        }.get(mercenary.rarity, 0),
        "name": lambda mercenary: mercenary.name.lower(),
        "strength": lambda mercenary: mercenary.power,
        "agility": lambda mercenary: mercenary.agility,
        "intelligence": lambda mercenary: mercenary.intelligence,
        "vitality": lambda mercenary: mercenary.vitality,
    }
    selected_sort = sort_by if sort_by in sorters else "power"
    reverse = selected_sort != "name"
    mercenaries.sort(key=sorters[selected_sort], reverse=reverse)
    return {
        "mercenaries": mercenaries,
        "attribute_summaries": summaries,
        "resources": resources,
        "mercenary_limit": get_mercenary_limit(db, guild.id),
        "selected_sort": selected_sort,
        "attribute_tooltips": ATTRIBUTE_TOOLTIPS,
    }


def get_mercenary_detail_context(
    db: Session,
    guild: Guild,
    mercenary_id: int,
) -> dict[str, object] | None:
    mercenary = get_mercenary_by_guild(db, guild.id, mercenary_id)
    if mercenary is None:
        return None
    annotate_mercenary_display(mercenary)
    summary = get_mercenary_attribute_summary(db, guild.id, mercenary)
    for item in summary.get("equipment_items", []):
        item.display_name = clean_generated_name(item.item_template.name)
        item.rarity_label = rarity_label(item.item_template.rarity)
        item.view_icon = get_item_icon(item)
        item.icon_path = get_item_icon_path(item)
        item.slot_label = get_equipment_slot_label(item.equipment_slot)
    available_equipment = get_available_equipment_for_mercenary(db, guild.id, mercenary)
    skills = ensure_mercenary_skills(db, mercenary)
    for item in available_equipment:
        item.display_name = clean_generated_name(item.item_template.name)
        item.rarity_label = rarity_label(item.item_template.rarity)
        item.view_icon = get_item_icon(item)
        item.icon_path = get_item_icon_path(item)
        item.slot_label = get_equipment_slot_label(item.equipment_slot)
    return {
        "mercenary": mercenary,
        "attribute_summary": summary,
        "available_equipment": available_equipment,
        "skills": skills,
        "skill_effect_label": effect_label,
        "skill_effect_suffix": effect_suffix,
        "attribute_tooltips": ATTRIBUTE_TOOLTIPS,
        "bonus_attribute_labels": BONUS_ATTRIBUTE_LABELS,
        "get_item_icon": get_item_icon,
        "get_slot_icon": get_slot_icon,
        "get_equipment_slot_label": get_equipment_slot_label,
        "weapon_profile_label": get_weapon_profile_label(mercenary.mercenary_class),
        "profession_family_label": PROFESSION_FAMILY_LABELS.get(mercenary.profession.material_family, mercenary.profession.material_family) if mercenary.profession else None,
    }


def equip_mercenary_item(
    db: Session,
    guild: Guild,
    mercenary_id: int,
    item_instance_id: str,
) -> None:
    try:
        parsed_item_id = int(item_instance_id)
    except ValueError as exc:
        raise MercenaryEquipmentError("Equipamento invalido.") from exc
    try:
        equip_item(db, guild.id, mercenary_id, parsed_item_id)
    except EquipmentError as exc:
        raise MercenaryEquipmentError(str(exc)) from exc


def unequip_mercenary_item(
    db: Session,
    guild: Guild,
    mercenary_id: int,
    item_instance_id: str,
) -> None:
    try:
        parsed_item_id = int(item_instance_id)
    except ValueError as exc:
        raise MercenaryEquipmentError("Equipamento invalido.") from exc
    try:
        unequip_item(db, guild.id, mercenary_id, parsed_item_id)
    except EquipmentError as exc:
        raise MercenaryEquipmentError(str(exc)) from exc


def dismiss_mercenary(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    mercenary_id: int,
) -> int:
    if resources is None:
        raise MercenaryDismissalError("Recursos da guilda indisponiveis.")
    mercenary = get_mercenary_by_guild(db, guild.id, mercenary_id)
    if mercenary is None:
        raise MercenaryDismissalError("Mercenario nao encontrado.")
    if mercenary.status != "available":
        raise MercenaryDismissalError("Apenas mercenarios disponiveis podem ser demitidos.")

    refund = floor((mercenary.hire_cost or 0) * 0.3)
    for item in mercenary.equipment_instances:
        item.equipped_to_mercenary_id = None
        db.add(item)
    resources.gold += refund
    from app.models.class_change import ClassChangeRun
    from app.models.content import ProfessionTraining
    from app.models.dungeon import DungeonRunMember
    from app.models.mission import MissionRunMember

    has_history = any(db.scalar(select(model.id).where(column == mercenary.id).limit(1)) is not None for model, column in (
        (MissionRunMember, MissionRunMember.mercenary_id),
        (DungeonRunMember, DungeonRunMember.mercenary_id),
        (ClassChangeRun, ClassChangeRun.mercenary_id),
        (ProfessionTraining, ProfessionTraining.mercenary_id),
    ))
    if has_history:
        mercenary.status = "dismissed"
        db.add(mercenary)
    else:
        db.delete(mercenary)
    db.add(resources)
    db.commit()
    return refund


def cleanup_orphaned_dismissed_mercenaries(db: Session) -> int:
    from app.models.class_change import ClassChangeRun
    from app.models.content import ProfessionTraining
    from app.models.dungeon import DungeonRunMember
    from app.models.item import GuildItemInstance
    from app.models.mission import MissionRunMember

    dismissed = list(db.scalars(select(Mercenary).where(Mercenary.status == "dismissed")))
    removed = 0
    for mercenary in dismissed:
        linked = any(db.scalar(select(model.id).where(column == mercenary.id).limit(1)) is not None for model, column in (
            (MissionRunMember, MissionRunMember.mercenary_id),
            (DungeonRunMember, DungeonRunMember.mercenary_id),
            (ClassChangeRun, ClassChangeRun.mercenary_id),
            (ProfessionTraining, ProfessionTraining.mercenary_id),
            (GuildItemInstance, GuildItemInstance.equipped_to_mercenary_id),
        ))
        if not linked:
            db.delete(mercenary)
            removed += 1
    if removed:
        db.commit()
    return removed


def recruit_mercenary(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    name: str,
    class_id: str,
) -> Mercenary:
    raise MercenaryRecruitmentError("Recrutamento direto foi movido para a Taverna.")
    name = name.strip()
    if not name:
        raise MercenaryRecruitmentError("Nome do mercenario e obrigatorio.")
    if not class_id:
        raise MercenaryRecruitmentError("Classe e obrigatoria.")

    try:
        parsed_class_id = int(class_id)
    except ValueError as exc:
        raise MercenaryRecruitmentError("Classe invalida.") from exc

    mercenary_class = get_active_mercenary_class(db, parsed_class_id)
    if mercenary_class is None:
        raise MercenaryRecruitmentError("Classe invalida ou indisponivel.")
    if resources is None:
        raise MercenaryRecruitmentError("Recursos da guilda indisponiveis.")
    if resources.gold < RECRUITMENT_COST_GOLD:
        raise MercenaryRecruitmentError("Ouro insuficiente para recrutar.")
    if count_mercenaries_by_guild(db, guild.id) >= get_mercenary_limit(db, guild.id):
        raise MercenaryRecruitmentError("Limite de mercenarios da guilda atingido. Evolua o Alojamento.")

    spend_gold(resources, RECRUITMENT_COST_GOLD)
    mercenary = create_mercenary(db, guild_id=guild.id, mercenary_class=mercenary_class, name=name)
    db.commit()
    db.refresh(mercenary)
    return mercenary


def get_mercenary_summary(db: Session, guild_id: int) -> dict[str, int]:
    busy = count_mercenaries_by_status(db, guild_id, "busy")
    gathering = count_mercenaries_by_status(db, guild_id, "gathering")
    return {
        "total": count_mercenaries_by_guild(db, guild_id),
        "available": count_mercenaries_by_status(db, guild_id, "available"),
        "busy": busy + gathering,
        "gathering": gathering,
    }
