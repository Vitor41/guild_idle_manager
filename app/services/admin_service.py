from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.building import BuildingTemplate
from app.models.dungeon import DungeonTemplate
from app.models.mission import MissionTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mercenary import MercenaryClass
from app.models.tavern import TavernConfig
from app.repositories.item_repository import (
    create_item_template,
    create_mission_drop,
    get_item_template,
    get_mission_drop,
    get_mission_drop_by_pair,
    list_active_item_templates,
    list_item_templates,
    list_mission_drops,
)
from app.repositories.dungeon_repository import (
    create_dungeon_drop,
    create_dungeon_template,
    get_dungeon_drop,
    get_dungeon_drop_by_pair,
    get_dungeon_template,
    get_dungeon_template_by_name,
    list_dungeon_drops,
    list_dungeon_templates,
)
from app.repositories.mission_repository import (
    create_mission_template,
    get_mission_template_by_name,
    get_mission_template_by_id,
    list_all_mission_templates,
    save_mission_template_order,
    update_mission_template,
)
from app.services.building_service import (
    BuildingError,
    get_admin_building,
    list_admin_buildings,
    save_admin_building,
)
from app.services.equipment_service import EQUIPMENT_SLOTS, normalize_equipment_slot
from app.repositories.tavern_repository import reset_all_special_checks
from app.services.tavern_service import get_or_create_tavern_config


class AdminMissionError(ValueError):
    pass


class AdminItemError(ValueError):
    pass


class AdminDropError(ValueError):
    pass


class AdminBuildingError(ValueError):
    pass


class AdminDungeonError(ValueError):
    pass


class AdminClassError(ValueError):
    pass


class AdminTavernError(ValueError):
    pass


MISSION_LEVEL_BANDS = ("1-20", "21-50", "51-100", "101-130", "131-200", "201-250", "251-300", "301-350")
MISSION_TYPES = (
    "standard", "combat", "patrol", "escort", "hunt", "exploration", "investigation",
    "defense", "rescue", "contract", "story", "elite", "gathering", "long_idle",
    "rare", "daily", "event",
)
MISSION_DIFFICULTIES = ("very_easy", "easy", "normal", "hard", "dangerous", "heroic", "legendary", "elite")
ITEM_RARITIES = ("common", "uncommon", "rare", "epic", "legendary", "mythic")


def list_admin_missions(db: Session) -> list[MissionTemplate]:
    return list_all_mission_templates(db)


def get_admin_mission(db: Session, mission_template_id: int) -> MissionTemplate | None:
    return get_mission_template_by_id(db, mission_template_id)


def save_admin_mission_order(db: Session, mission_ids: list[str]) -> None:
    try:
        parsed_ids = [int(mission_id) for mission_id in mission_ids]
    except ValueError as exc:
        raise AdminMissionError("Ordem de missões inválida.") from exc

    current_missions = list_all_mission_templates(db)
    current_by_id = {mission.id: mission for mission in current_missions}
    if len(parsed_ids) != len(set(parsed_ids)) or set(parsed_ids) != set(current_by_id):
        raise AdminMissionError("A lista de missões mudou. Atualize a página e tente novamente.")
    save_mission_template_order(db, [current_by_id[mission_id] for mission_id in parsed_ids])


def parse_duration_seconds(form: dict[str, str]) -> int:
    try:
        hours = int(form.get("duration_hours", "0") or "0")
        minutes = int(form.get("duration_minutes", "0") or "0")
        seconds = int(form.get("duration_seconds", "0") or "0")
    except ValueError as exc:
        raise AdminMissionError("Duracao invalida.") from exc

    if hours < 0 or minutes < 0 or seconds < 0:
        raise AdminMissionError("Duracao nao pode ter valores negativos.")
    if minutes > 59 or seconds > 59:
        raise AdminMissionError("Minutos e segundos devem ficar entre 0 e 59.")

    duration_seconds = hours * 3600 + minutes * 60 + seconds
    if duration_seconds <= 0:
        raise AdminMissionError("Duracao deve ser maior que zero.")
    return duration_seconds


def parse_mission_form(form: dict[str, str]) -> dict[str, object]:
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    difficulty = form.get("difficulty", "normal").strip()
    level_band = form.get("level_band", "1-20").strip()
    mission_type = form.get("mission_type", "standard").strip()
    try:
        base_gold_reward = int(form.get("base_gold_reward", ""))
        base_xp_reward = int(form.get("base_xp_reward", ""))
        base_success_chance = int(form.get("base_success_chance", ""))
        min_party_size = int(form.get("min_party_size", "1") or "1")
        max_party_size = int(form.get("max_party_size", "1") or "1")
        required_guild_level = int(form.get("required_guild_level", "1") or "1")
        required_min_mercenary_level = int(form.get("required_min_mercenary_level", "1") or "1")
        required_building_level = int(form.get("required_building_level", "0") or "0")
        recommended_level = int(form.get("recommended_level", "1") or "1")
        recommended_power = int(form.get("recommended_power", "10") or "10")
    except ValueError as exc:
        raise AdminMissionError("Valores numericos invalidos.") from exc

    if not name:
        raise AdminMissionError("Nome e obrigatorio.")
    if difficulty not in MISSION_DIFFICULTIES:
        raise AdminMissionError("Dificuldade invalida.")
    if level_band not in MISSION_LEVEL_BANDS:
        raise AdminMissionError("Faixa de nivel invalida.")
    if mission_type not in MISSION_TYPES:
        raise AdminMissionError("Tipo de missao invalido.")
    if base_gold_reward < 0:
        raise AdminMissionError("Recompensa de ouro deve ser maior ou igual a zero.")
    if base_xp_reward < 0:
        raise AdminMissionError("Recompensa de XP deve ser maior ou igual a zero.")
    if base_success_chance < 1 or base_success_chance > 100:
        raise AdminMissionError("Chance de sucesso deve ficar entre 1 e 100.")
    if min_party_size < 1:
        raise AdminMissionError("Grupo minimo deve ser pelo menos 1.")
    if max_party_size < min_party_size or max_party_size > 5:
        raise AdminMissionError("Grupo máximo deve ficar entre o mínimo e 5.")
    if required_guild_level < 1 or required_min_mercenary_level < 1:
        raise AdminMissionError("Niveis exigidos devem ser pelo menos 1.")
    if recommended_level < 1 or recommended_power < 0:
        raise AdminMissionError("Nível recomendado deve ser positivo e poder recomendado não pode ser negativo.")
    if required_building_level < 0:
        raise AdminMissionError("Nivel de construcao exigido nao pode ser negativo.")

    required_building_type = form.get("required_building_type", "").strip() or None
    if required_building_level > 0 and required_building_type is None:
        raise AdminMissionError("Informe a construção exigida quando o nível necessário for maior que zero.")
    data = {
        "name": name,
        "description": description,
        "difficulty": difficulty,
        "level_band": level_band,
        "mission_type": mission_type,
        "recommended_level": recommended_level,
        "recommended_power": recommended_power,
        "gathering_family": form.get("gathering_family", "").strip() or None,
        "profession_code": form.get("profession_code", "").strip() or None,
        "duration_seconds": parse_duration_seconds(form),
        "base_gold_reward": base_gold_reward,
        "base_xp_reward": base_xp_reward,
        "base_success_chance": base_success_chance,
        "min_party_size": min_party_size,
        "max_party_size": max_party_size,
        "required_guild_level": required_guild_level,
        "required_min_mercenary_level": required_min_mercenary_level,
        "required_building_type": required_building_type,
        "required_building_level": required_building_level,
        "is_active": form.get("is_active") == "on",
    }
    if mission_type == "long_idle":
        data["min_party_size"] = 1
        data["max_party_size"] = 5
        data["gathering_family"] = None
        data["profession_code"] = None
    return data


def create_admin_mission(db: Session, form: dict[str, str]) -> MissionTemplate:
    data = parse_mission_form(form)
    existing_mission = get_mission_template_by_name(db, str(data["name"]))
    if existing_mission is not None:
        raise AdminMissionError("Ja existe uma missao com este nome.")

    mission_template = create_mission_template(db, data)
    db.commit()
    db.refresh(mission_template)
    return mission_template


def update_admin_mission(db: Session, mission_template_id: int, form: dict[str, str]) -> MissionTemplate:
    mission_template = get_mission_template_by_id(db, mission_template_id)
    if mission_template is None:
        raise AdminMissionError("Missao nao encontrada.")

    data = parse_mission_form(form)
    if mission_template.slug and mission_template.slug.startswith("long-idle-"):
        data["mission_type"] = "long_idle"
        data["min_party_size"] = 1
        data["max_party_size"] = 5
    existing_mission = get_mission_template_by_name(db, str(data["name"]))
    if existing_mission is not None and existing_mission.id != mission_template.id:
        raise AdminMissionError("Ja existe uma missao com este nome.")

    return update_mission_template(
        db,
        mission_template,
        data,
    )


def list_admin_items(db: Session) -> list[ItemTemplate]:
    return list_item_templates(db)


def list_active_admin_items(db: Session) -> list[ItemTemplate]:
    return list_active_item_templates(db)


def get_admin_item(db: Session, item_template_id: int) -> ItemTemplate | None:
    return get_item_template(db, item_template_id)


def save_admin_item(db: Session, form: dict[str, str], item_template: ItemTemplate | None = None) -> ItemTemplate:
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    item_type = form.get("item_type", "").strip()
    rarity = form.get("rarity", "").strip()
    icon_group = form.get("icon_group", "").strip() or None
    if not name:
        raise AdminItemError("Nome e obrigatorio.")
    if not item_type:
        raise AdminItemError("Tipo e obrigatorio.")
    if item_type not in {"material", "consumable", "misc", "equipment"}:
        raise AdminItemError("Tipo de item inválido.")
    if not rarity:
        raise AdminItemError("Raridade e obrigatoria.")
    if rarity not in ITEM_RARITIES:
        raise AdminItemError("Raridade inválida.")
    level_band = form.get("level_band", "1-20").strip()
    if level_band not in MISSION_LEVEL_BANDS:
        raise AdminItemError("Faixa de nível inválida.")
    try:
        item_level = int(form.get("item_level", "1") or "1")
        tier = int(form.get("tier", "1") or "1")
        base_sell_value = int(form.get("base_sell_value", "1") or "1")
        required_level = int(form.get("required_level", "1") or "1")
        bonus_power = int(form.get("bonus_power", "0") or "0")
        bonus_vitality = int(form.get("bonus_vitality", "0") or "0")
        bonus_agility = int(form.get("bonus_agility", "0") or "0")
        bonus_intelligence = int(form.get("bonus_intelligence", "0") or "0")
        bonus_luck = int(form.get("bonus_luck", "0") or "0")
        bonus_armor = int(form.get("bonus_armor", "0") or "0")
        rng_bonus_min = int(form.get("rng_bonus_min", "0") or "0")
        rng_bonus_max = int(form.get("rng_bonus_max", "0") or "0")
    except ValueError as exc:
        raise AdminItemError("Campos numericos de equipamento invalidos.") from exc

    equipment_slot = normalize_equipment_slot(form.get("equipment_slot", "").strip()) or None
    if item_type == "equipment":
        if equipment_slot not in EQUIPMENT_SLOTS:
            raise AdminItemError("Slot de equipamento invalido ou obrigatorio.")
        if required_level < 1:
            raise AdminItemError("Nivel minimo deve ser pelo menos 1 para equipamentos.")
    else:
        equipment_slot = None
        required_level = 1
        bonus_power = 0
        bonus_vitality = 0
        bonus_agility = 0
        bonus_intelligence = 0
        bonus_luck = 0
        bonus_armor = 0
        rng_bonus_min = 0
        rng_bonus_max = 0

    if item_level < 1:
        raise AdminItemError("Item level deve ser pelo menos 1.")
    if tier < 1 or tier > 8:
        raise AdminItemError("Tier deve ficar entre 1 e 8.")
    if base_sell_value < 1:
        raise AdminItemError("Valor de venda deve ser pelo menos 1.")
    bonuses = [bonus_power, bonus_vitality, bonus_agility, bonus_intelligence, bonus_luck, bonus_armor]
    if any(value < 0 for value in bonuses):
        raise AdminItemError("Bonus de equipamento devem ser maiores ou iguais a zero.")
    if rng_bonus_min < 0:
        raise AdminItemError("Bônus aleatório mínimo deve ser maior ou igual a zero.")
    if rng_bonus_max < rng_bonus_min:
        raise AdminItemError("Bônus aleatório máximo deve ser maior ou igual ao mínimo.")

    data = {
        "name": name,
        "description": description,
        "item_type": item_type,
        "rarity": rarity,
        "item_level": item_level,
        "level_band": level_band,
        "tier": tier,
        "material_family": form.get("material_family", "").strip() or None,
        "favored_class_code": form.get("favored_class_code", "").strip() or None,
        "favored_attribute": form.get("favored_attribute", "").strip() or None,
        "base_sell_value": base_sell_value,
        "equipment_slot": equipment_slot,
        "icon_group": icon_group,
        "required_level": required_level,
        "bonus_power": bonus_power,
        "bonus_vitality": bonus_vitality,
        "bonus_agility": bonus_agility,
        "bonus_intelligence": bonus_intelligence,
        "bonus_luck": bonus_luck,
        "bonus_armor": bonus_armor,
        "rng_bonus_min": rng_bonus_min,
        "rng_bonus_max": rng_bonus_max,
        "is_active": form.get("is_active") == "on",
    }
    if item_template is None:
        item_template = create_item_template(db, data)
    else:
        for key, value in data.items():
            setattr(item_template, key, value)
        db.add(item_template)
    db.commit()
    db.refresh(item_template)
    return item_template


def list_admin_building_templates(db: Session) -> list[BuildingTemplate]:
    return list_admin_buildings(db)


def get_admin_building_template(db: Session, template_id: int) -> BuildingTemplate | None:
    return get_admin_building(db, template_id)


def save_admin_building_template(
    db: Session,
    form: dict[str, str],
    template: BuildingTemplate | None = None,
) -> BuildingTemplate:
    try:
        return save_admin_building(db, form, template)
    except BuildingError as exc:
        raise AdminBuildingError(str(exc)) from exc


def list_admin_dungeons(db: Session) -> list[DungeonTemplate]:
    return list_dungeon_templates(db)


def get_admin_dungeon(db: Session, dungeon_template_id: int) -> DungeonTemplate | None:
    return get_dungeon_template(db, dungeon_template_id)


def parse_dungeon_form(form: dict[str, str]) -> dict[str, object]:
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    content_type = form.get("content_type", "dungeon").strip()
    difficulty = form.get("difficulty", "normal").strip()
    level_band = form.get("level_band", "1-20").strip()
    try:
        duration_seconds = parse_duration_seconds(form)
        base_gold_reward = int(form.get("base_gold_reward", ""))
        base_xp_reward = int(form.get("base_xp_reward", ""))
        base_success_chance = int(form.get("base_success_chance", ""))
        min_party_size = int(form.get("min_party_size", "2") or "2")
        max_party_size = int(form.get("max_party_size", "3") or "3")
        required_guild_level = int(form.get("required_guild_level", "1") or "1")
        required_min_mercenary_level = int(form.get("required_min_mercenary_level", "1") or "1")
        required_building_level = int(form.get("required_building_level", "0") or "0")
        required_total_power = int(form.get("required_total_power", "0") or "0")
        required_tank_count = int(form.get("required_tank_count", "0") or "0")
        required_support_count = int(form.get("required_support_count", "0") or "0")
        required_damage_count = int(form.get("required_damage_count", "0") or "0")
        required_equipment_tier = int(form.get("required_equipment_tier", "0") or "0")
        recommended_level = int(form.get("recommended_level", "1") or "1")
    except ValueError as exc:
        raise AdminDungeonError("Valores numericos invalidos.") from exc

    if not name:
        raise AdminDungeonError("Nome e obrigatorio.")
    if content_type not in {"dungeon", "boss", "event"} or difficulty not in {"normal", "hard", "heroic", "legendary", "elite"}:
        raise AdminDungeonError("Tipo ou dificuldade invalida.")
    if level_band not in MISSION_LEVEL_BANDS:
        raise AdminDungeonError("Faixa de nível inválida.")
    if base_gold_reward < 0 or base_xp_reward < 0:
        raise AdminDungeonError("Recompensas devem ser maiores ou iguais a zero.")
    if base_success_chance < 1 or base_success_chance > 100:
        raise AdminDungeonError("Chance de sucesso deve ficar entre 1 e 100.")
    if min_party_size < 1 or max_party_size < min_party_size or max_party_size > 5:
        raise AdminDungeonError("Tamanho de grupo invalido.")
    if required_guild_level < 1 or required_min_mercenary_level < 1:
        raise AdminDungeonError("Niveis exigidos devem ser pelo menos 1.")
    if recommended_level < 1:
        raise AdminDungeonError("Nível recomendado deve ser pelo menos 1.")
    if required_equipment_tier > 8:
        raise AdminDungeonError("Tier mínimo de equipamento deve ficar entre 0 e 8.")
    if required_building_level < 0:
        raise AdminDungeonError("Nivel de construcao exigido nao pode ser negativo.")
    if min(required_total_power, required_tank_count, required_support_count, required_damage_count, required_equipment_tier) < 0:
        raise AdminDungeonError("Requisitos avancados nao podem ser negativos.")
    if required_tank_count + required_support_count + required_damage_count > max_party_size:
        raise AdminDungeonError("A soma dos papéis exigidos não pode superar o grupo máximo.")
    required_building_type = form.get("required_building_type", "").strip() or None
    if required_building_level > 0 and required_building_type is None:
        raise AdminDungeonError("Informe a construção exigida quando o nível necessário for maior que zero.")

    return {
        "name": name,
        "description": description,
        "content_type": content_type,
        "level_band": level_band,
        "recommended_level": recommended_level,
        "biome": form.get("biome", "").strip() or None,
        "difficulty": difficulty,
        "duration_seconds": duration_seconds,
        "base_gold_reward": base_gold_reward,
        "base_xp_reward": base_xp_reward,
        "base_success_chance": base_success_chance,
        "min_party_size": min_party_size,
        "max_party_size": max_party_size,
        "required_guild_level": required_guild_level,
        "required_min_mercenary_level": required_min_mercenary_level,
        "required_building_type": required_building_type,
        "required_building_level": required_building_level,
        "required_total_power": required_total_power,
        "required_class_code": form.get("required_class_code", "").strip() or None,
        "required_tank_count": required_tank_count,
        "required_support_count": required_support_count,
        "required_damage_count": required_damage_count,
        "required_equipment_tier": required_equipment_tier,
        "is_active": form.get("is_active") == "on",
    }


def save_admin_dungeon(
    db: Session,
    form: dict[str, str],
    dungeon_template: DungeonTemplate | None = None,
) -> DungeonTemplate:
    data = parse_dungeon_form(form)
    existing = get_dungeon_template_by_name(db, str(data["name"]))
    if existing is not None and (dungeon_template is None or existing.id != dungeon_template.id):
        raise AdminDungeonError("Já existe uma masmorra com este nome.")
    if dungeon_template is None:
        dungeon_template = create_dungeon_template(db, data)
    else:
        for key, value in data.items():
            setattr(dungeon_template, key, value)
        db.add(dungeon_template)
    db.commit()
    db.refresh(dungeon_template)
    return dungeon_template


def list_admin_dungeon_drops(db: Session) -> list[DungeonTemplateItemDrop]:
    return list_dungeon_drops(db)


def get_admin_dungeon_drop(db: Session, drop_id: int) -> DungeonTemplateItemDrop | None:
    return get_dungeon_drop(db, drop_id)


def save_admin_dungeon_drop(
    db: Session,
    form: dict[str, str],
    drop: DungeonTemplateItemDrop | None = None,
) -> DungeonTemplateItemDrop:
    try:
        dungeon_template_id = int(form.get("dungeon_template_id", ""))
        item_template_id = int(form.get("item_template_id", ""))
        drop_chance = int(form.get("drop_chance", ""))
        min_quantity = int(form.get("min_quantity", ""))
        max_quantity = int(form.get("max_quantity", ""))
    except ValueError as exc:
        raise AdminDropError("Valores numericos invalidos.") from exc

    if get_dungeon_template(db, dungeon_template_id) is None:
        raise AdminDropError("Masmorra inválida.")
    if get_item_template(db, item_template_id) is None:
        raise AdminDropError("Item invalido.")
    if drop_chance < 0 or drop_chance > 100:
        raise AdminDropError("Chance de drop deve ficar entre 0 e 100.")
    if min_quantity < 1:
        raise AdminDropError("Quantidade minima deve ser pelo menos 1.")
    if max_quantity < min_quantity:
        raise AdminDropError("Quantidade maxima deve ser maior ou igual a minima.")
    existing_pair = get_dungeon_drop_by_pair(db, dungeon_template_id, item_template_id)
    if existing_pair is not None and (drop is None or existing_pair.id != drop.id):
        raise AdminDropError("Este item já está configurado como drop deste desafio.")

    data = {
        "dungeon_template_id": dungeon_template_id,
        "item_template_id": item_template_id,
        "drop_chance": drop_chance,
        "min_quantity": min_quantity,
        "max_quantity": max_quantity,
        "is_active": form.get("is_active") == "on",
    }
    if drop is None:
        drop = create_dungeon_drop(db, data)
    else:
        for key, value in data.items():
            setattr(drop, key, value)
        db.add(drop)
    db.commit()
    db.refresh(drop)
    return drop


def list_admin_drops(db: Session) -> list[MissionTemplateItemDrop]:
    return list_mission_drops(db)


def get_admin_drop(db: Session, drop_id: int) -> MissionTemplateItemDrop | None:
    return get_mission_drop(db, drop_id)


def save_admin_drop(
    db: Session,
    form: dict[str, str],
    drop: MissionTemplateItemDrop | None = None,
) -> MissionTemplateItemDrop:
    try:
        mission_template_id = int(form.get("mission_template_id", ""))
        item_template_id = int(form.get("item_template_id", ""))
        drop_chance = int(form.get("drop_chance", ""))
        min_quantity = int(form.get("min_quantity", ""))
        max_quantity = int(form.get("max_quantity", ""))
    except ValueError as exc:
        raise AdminDropError("Valores numericos invalidos.") from exc

    if get_mission_template_by_id(db, mission_template_id) is None:
        raise AdminDropError("Missao invalida.")
    if get_item_template(db, item_template_id) is None:
        raise AdminDropError("Item invalido.")
    if drop_chance < 0 or drop_chance > 100:
        raise AdminDropError("Chance de drop deve ficar entre 0 e 100.")
    if min_quantity < 1:
        raise AdminDropError("Quantidade minima deve ser pelo menos 1.")
    if max_quantity < min_quantity:
        raise AdminDropError("Quantidade maxima deve ser maior ou igual a minima.")
    existing_pair = get_mission_drop_by_pair(db, mission_template_id, item_template_id)
    if existing_pair is not None and (drop is None or existing_pair.id != drop.id):
        raise AdminDropError("Este item já está configurado como drop desta missão.")

    data = {
        "mission_template_id": mission_template_id,
        "item_template_id": item_template_id,
        "drop_chance": drop_chance,
        "min_quantity": min_quantity,
        "max_quantity": max_quantity,
        "is_active": form.get("is_active") == "on",
    }
    if drop is None:
        drop = create_mission_drop(db, data)
    else:
        for key, value in data.items():
            setattr(drop, key, value)
        db.add(drop)
    db.commit()
    db.refresh(drop)
    return drop


def list_admin_classes(db: Session) -> list[MercenaryClass]:
    return list(db.scalars(select(MercenaryClass).order_by(MercenaryClass.tier, MercenaryClass.name)))


def get_admin_class(db: Session, class_id: int) -> MercenaryClass | None:
    return db.get(MercenaryClass, class_id)


def save_admin_class(
    db: Session,
    form: dict[str, str],
    mercenary_class: MercenaryClass,
) -> MercenaryClass:
    name = form.get("name", "").strip()
    display_name = form.get("display_name", "").strip()
    description = form.get("description", "").strip()
    allowed_weapon_profile = form.get("allowed_weapon_profile", "").strip() or "any"
    role_type = form.get("role_type", "").strip() or "balanced"
    try:
        tier = int(form.get("tier", "0") or "0")
        required_level = int(form.get("required_level", "1") or "1")
        base_power = int(form.get("base_power", str(mercenary_class.base_power)) or "0")
        base_vitality = int(form.get("base_vitality", str(mercenary_class.base_vitality)) or "0")
        base_agility = int(form.get("base_agility", str(mercenary_class.base_agility)) or "0")
        base_intelligence = int(form.get("base_intelligence", str(mercenary_class.base_intelligence)) or "0")
        base_luck = int(form.get("base_luck", str(mercenary_class.base_luck)) or "0")
        parent_class_id = int(form["parent_class_id"]) if form.get("parent_class_id", "").strip() else None
    except ValueError as exc:
        raise AdminClassError("Valores numericos invalidos.") from exc
    if not name:
        raise AdminClassError("Nome e obrigatorio.")
    if tier < 0:
        raise AdminClassError("Tier nao pode ser negativo.")
    if required_level < 1:
        raise AdminClassError("Nivel requerido deve ser pelo menos 1.")
    if allowed_weapon_profile not in {"any", "melee", "light", "ranged", "arcane", "holy"}:
        raise AdminClassError("Perfil de arma inválido.")
    if role_type not in {"balanced", "tank", "frontline", "support", "caster", "ranged", "duelist", "skirmisher"}:
        raise AdminClassError("Papel de classe inválido.")
    if min(base_power, base_vitality, base_agility, base_intelligence, base_luck) < 0:
        raise AdminClassError("Atributos base não podem ser negativos.")
    existing_name = db.scalar(select(MercenaryClass).where(
        MercenaryClass.name == name,
        MercenaryClass.id != mercenary_class.id,
    ))
    if existing_name is not None:
        raise AdminClassError("Já existe uma classe com este nome interno.")
    if parent_class_id == mercenary_class.id:
        raise AdminClassError("Uma classe não pode ser sua própria classe de origem.")
    if parent_class_id is not None and db.get(MercenaryClass, parent_class_id) is None:
        raise AdminClassError("Classe de origem inválida.")

    mercenary_class.name = name
    mercenary_class.display_name = display_name or name
    mercenary_class.description = description
    mercenary_class.tier = tier
    mercenary_class.required_level = required_level
    mercenary_class.parent_class_id = parent_class_id
    mercenary_class.allowed_weapon_profile = allowed_weapon_profile
    mercenary_class.role_type = role_type
    mercenary_class.base_power = base_power
    mercenary_class.base_vitality = base_vitality
    mercenary_class.base_agility = base_agility
    mercenary_class.base_intelligence = base_intelligence
    mercenary_class.base_luck = base_luck
    mercenary_class.is_active = form.get("is_active") == "on"
    db.add(mercenary_class)
    db.commit()
    db.refresh(mercenary_class)
    return mercenary_class


def get_admin_tavern_config(db: Session) -> TavernConfig:
    return get_or_create_tavern_config(db)


def save_admin_tavern_config(db: Session, form: dict[str, str]) -> TavernConfig:
    config = get_or_create_tavern_config(db)
    previous_special_settings = (
        config.special_spawn_cooldown_hours,
        config.special_offer_duration_hours,
        config.special_spawn_chance,
    )
    integer_fields = [
        "base_apprentice_cost",
        "apprentice_cost_threshold",
        "apprentice_growth_before_threshold_percent",
        "apprentice_growth_after_threshold_percent",
        "common_apprentice_chance",
        "uncommon_apprentice_chance",
        "special_spawn_cooldown_hours",
        "special_offer_duration_hours",
        "special_spawn_chance",
        "special_rare_chance",
        "special_epic_chance",
        "special_legendary_chance",
        "special_mythic_chance",
        "special_rare_cost",
        "special_epic_cost",
        "special_legendary_cost",
        "special_mythic_cost",
    ]
    try:
        parsed = {field: int(form.get(field, "0") or "0") for field in integer_fields}
    except ValueError as exc:
        raise AdminTavernError("Valores numericos invalidos.") from exc
    if parsed["base_apprentice_cost"] < 1:
        raise AdminTavernError("Custo inicial deve ser maior que zero.")
    if parsed["apprentice_cost_threshold"] < parsed["base_apprentice_cost"]:
        raise AdminTavernError("Limite de custo deve ser maior ou igual ao custo inicial.")
    chance_fields = [
        "common_apprentice_chance",
        "uncommon_apprentice_chance",
        "special_spawn_chance",
        "special_rare_chance",
        "special_epic_chance",
        "special_legendary_chance",
        "special_mythic_chance",
    ]
    if any(parsed[field] < 0 or parsed[field] > 100 for field in chance_fields):
        raise AdminTavernError("Chances devem ficar entre 0 e 100.")
    if parsed["common_apprentice_chance"] + parsed["uncommon_apprentice_chance"] != 100:
        raise AdminTavernError("As chances de Aprendiz Comum e Incomum devem somar 100%.")
    if sum(parsed[field] for field in (
        "special_rare_chance", "special_epic_chance", "special_legendary_chance", "special_mythic_chance",
    )) != 100:
        raise AdminTavernError("As chances de raridade da oferta especial devem somar 100%.")
    if parsed["apprentice_growth_before_threshold_percent"] < 0 or parsed["apprentice_growth_after_threshold_percent"] < 0:
        raise AdminTavernError("Percentuais de crescimento não podem ser negativos.")
    if any(parsed[field] < 0 for field in (
        "special_rare_cost", "special_epic_cost", "special_legendary_cost", "special_mythic_cost",
    )):
        raise AdminTavernError("Custos de ofertas especiais não podem ser negativos.")
    if parsed["special_spawn_cooldown_hours"] < 1 or parsed["special_offer_duration_hours"] < 1:
        raise AdminTavernError("Tempos da oferta devem ser de pelo menos 1 hora.")

    for field, value in parsed.items():
        setattr(config, field, value)
    config.is_active = form.get("is_active") == "on"
    current_special_settings = (
        config.special_spawn_cooldown_hours,
        config.special_offer_duration_hours,
        config.special_spawn_chance,
    )
    if current_special_settings != previous_special_settings:
        reset_all_special_checks(db, datetime.now(timezone.utc))
    db.add(config)
    db.commit()
    db.refresh(config)
    return config
