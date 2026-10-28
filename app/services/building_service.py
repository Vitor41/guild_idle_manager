from math import ceil, floor

from sqlalchemy.orm import Session

from app.models.building import BuildingTemplate, GuildBuilding
from app.models.guild import Guild, GuildResources
from app.repositories.building_repository import (
    create_building_template,
    create_guild_building,
    get_building_template,
    get_building_template_by_name,
    get_guild_building,
    get_guild_building_by_effect,
    get_guild_building_by_template,
    list_active_building_templates,
    list_building_templates,
    list_guild_buildings,
)
from app.services.guild_progression_service import add_guild_xp
from app.repositories.item_repository import consume_inventory_resource, sync_inventory_resource_totals
from app.services.building_balance_service import (
    BUILDING_MAX_LEVEL,
    blacksmith_drop_bonus,
    building_cost_factor,
    get_building_benefit,
    housing_capacity,
    market_values,
    mission_office_values,
    required_guild_level_for_upgrade,
    scouts_values,
    training_xp_bonus,
    warehouse_material_bonus,
)


INITIAL_BUILDING_TEMPLATES = [
    {
        "name": "Alojamento",
        "description": "Aumenta o limite de mercenarios da guilda.",
        "effect_type": "housing",
        "base_upgrade_gold_cost": 100,
        "base_upgrade_wood_cost": 20,
        "base_upgrade_ore_cost": 0,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
    {
        "name": "Campo de Treino",
        "description": "Aumenta o XP ganho em missões e masmorras.",
        "effect_type": "training_ground",
        "base_upgrade_gold_cost": 120,
        "base_upgrade_wood_cost": 10,
        "base_upgrade_ore_cost": 10,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
    {
        "name": "Ferreiro",
        "description": "Aumenta a chance de encontrar equipamentos.",
        "effect_type": "blacksmith",
        "base_upgrade_gold_cost": 150,
        "base_upgrade_wood_cost": 0,
        "base_upgrade_ore_cost": 25,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
    {
        "name": "Armazem",
        "description": "Aumenta a quantidade de materiais obtidos.",
        "effect_type": "warehouse",
        "base_upgrade_gold_cost": 90,
        "base_upgrade_wood_cost": 30,
        "base_upgrade_ore_cost": 0,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
    {
        "name": "Escritório de Missões",
        "description": "Permite aceitar missões com grupos maiores.",
        "effect_type": "contract_office",
        "base_upgrade_gold_cost": 180,
        "base_upgrade_wood_cost": 20,
        "base_upgrade_ore_cost": 20,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
    {
        "name": "Exploradores",
        "description": "Libera o acesso a masmorras e explorações perigosas.",
        "effect_type": "scouts",
        "base_upgrade_gold_cost": 160,
        "base_upgrade_wood_cost": 20,
        "base_upgrade_ore_cost": 10,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
    {
        "name": "Taverna",
        "description": "Central de contratacao de Aprendizes e mercenarios especiais.",
        "effect_type": "tavern",
        "base_upgrade_gold_cost": 140,
        "base_upgrade_wood_cost": 25,
        "base_upgrade_ore_cost": 5,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
    {
        "name": "Mercado",
        "description": "Libera espacos de venda e melhora o comercio da guilda.",
        "effect_type": "market",
        "base_upgrade_gold_cost": 130,
        "base_upgrade_wood_cost": 20,
        "base_upgrade_ore_cost": 5,
        "base_upgrade_crystals_cost": 0,
        "max_level": BUILDING_MAX_LEVEL,
        "is_active": True,
    },
]


class BuildingError(ValueError):
    pass


EFFECT_LABELS = {
    "housing": "Alojamento",
    "training_ground": "Campo de Treino",
    "blacksmith": "Ferreiro",
    "warehouse": "Armazem",
    "contract_office": "Escritório de Missões",
    "scouts": "Exploradores",
    "tavern": "Taverna",
    "market": "Mercado",
}


def get_effect_label(effect_type: str) -> str:
    return EFFECT_LABELS.get(effect_type, effect_type)


def seed_initial_building_templates(db: Session) -> None:
    created_any = False
    for data in INITIAL_BUILDING_TEMPLATES:
        existing = get_building_template_by_name(db, str(data["name"]))
        if existing:
            if existing.max_level > BUILDING_MAX_LEVEL:
                existing.max_level = BUILDING_MAX_LEVEL
                db.add(existing)
                created_any = True
            continue
        create_building_template(db, data)
        created_any = True
    if created_any:
        db.commit()


def ensure_guild_buildings(db: Session, guild_id: int) -> list[GuildBuilding]:
    created_any = False
    for template in list_active_building_templates(db):
        if get_guild_building_by_template(db, guild_id, template.id):
            continue
        create_guild_building(db, guild_id, template.id)
        created_any = True
    if created_any:
        db.commit()
    return list_guild_buildings(db, guild_id)


def list_admin_buildings(db: Session) -> list[BuildingTemplate]:
    return list_building_templates(db)


def get_admin_building(db: Session, template_id: int) -> BuildingTemplate | None:
    return get_building_template(db, template_id)


def parse_building_template_form(form: dict[str, str]) -> dict[str, object]:
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    effect_type = form.get("effect_type", "").strip()
    try:
        base_upgrade_gold_cost = int(form.get("base_upgrade_gold_cost", "0") or "0")
        base_upgrade_wood_cost = int(form.get("base_upgrade_wood_cost", "0") or "0")
        base_upgrade_ore_cost = int(form.get("base_upgrade_ore_cost", "0") or "0")
        base_upgrade_crystals_cost = int(form.get("base_upgrade_crystals_cost", "0") or "0")
        max_level = int(form.get("max_level", "1") or "1")
        required_guild_level = int(form.get("required_guild_level", "1") or "1")
    except ValueError as exc:
        raise BuildingError("Valores numericos invalidos.") from exc

    if not name:
        raise BuildingError("Nome e obrigatorio.")
    if not effect_type:
        raise BuildingError("Tipo de efeito e obrigatorio.")
    if min(base_upgrade_gold_cost, base_upgrade_wood_cost, base_upgrade_ore_cost, base_upgrade_crystals_cost) < 0:
        raise BuildingError("Custos nao podem ser negativos.")
    if max_level < 1 or max_level > BUILDING_MAX_LEVEL:
        raise BuildingError(f"Nivel maximo deve ficar entre 1 e {BUILDING_MAX_LEVEL}.")
    if required_guild_level < 1:
        raise BuildingError("Nivel de guilda exigido deve ser pelo menos 1.")

    return {
        "name": name,
        "description": description,
        "effect_type": effect_type,
        "base_upgrade_gold_cost": base_upgrade_gold_cost,
        "base_upgrade_wood_cost": base_upgrade_wood_cost,
        "base_upgrade_ore_cost": base_upgrade_ore_cost,
        "base_upgrade_crystals_cost": base_upgrade_crystals_cost,
        "max_level": max_level,
        "required_guild_level": required_guild_level,
        "is_active": form.get("is_active") == "on",
    }


def save_admin_building(
    db: Session,
    form: dict[str, str],
    template: BuildingTemplate | None = None,
) -> BuildingTemplate:
    data = parse_building_template_form(form)
    existing = get_building_template_by_name(db, str(data["name"]))
    if existing is not None and (template is None or existing.id != template.id):
        raise BuildingError("Ja existe uma construcao com este nome.")

    if template is None:
        template = create_building_template(db, data)
    else:
        for key, value in data.items():
            setattr(template, key, value)
        db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_upgrade_cost(building: GuildBuilding) -> dict[str, int]:
    template = building.building_template
    if template.effect_type in {"housing", "tavern"} and building.level == 0:
        return {"gold": 10, "wood": 0, "ore": 0, "crystals": 0}
    multiplier = building_cost_factor(building.level + 1)
    return {
        "gold": ceil(template.base_upgrade_gold_cost * multiplier),
        "wood": ceil(template.base_upgrade_wood_cost * multiplier),
        "ore": ceil(template.base_upgrade_ore_cost * multiplier),
        "crystals": ceil(template.base_upgrade_crystals_cost * multiplier),
    }


def can_pay(resources: GuildResources, cost: dict[str, int]) -> bool:
    return (
        resources.gold >= cost["gold"]
        and resources.wood >= cost["wood"]
        and resources.ore >= cost["ore"]
        and resources.crystals >= cost["crystals"]
    )


def upgrade_guild_building(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    building_id: int,
) -> GuildBuilding:
    if resources is None:
        raise BuildingError("Recursos da guilda indisponiveis.")

    building = get_guild_building(db, guild.id, building_id)
    if building is None:
        raise BuildingError("Construcao nao encontrada.")
    if building.level >= building.building_template.max_level:
        raise BuildingError("Construcao ja esta no nivel maximo.")
    required_level = required_guild_level_for_upgrade(
        building.level + 1,
        building.building_template.required_guild_level,
    )
    if guild.level < required_level:
        raise BuildingError(f"A guilda precisa estar no nivel {required_level} para esta melhoria.")

    sync_inventory_resource_totals(db, resources)
    cost = get_upgrade_cost(building)
    if not can_pay(resources, cost):
        raise BuildingError("Recursos insuficientes para evoluir esta construcao.")

    resources.gold -= cost["gold"]
    for resource_name in ("wood", "ore", "crystals"):
        if not consume_inventory_resource(db, resources, resource_name, cost[resource_name]):
            raise BuildingError("Materiais insuficientes para evoluir esta construcao.")
    building.level += 1
    add_guild_xp(guild, 10)
    db.add(resources)
    db.add(building)
    db.add(guild)
    db.commit()
    db.refresh(building)
    return building


def get_building_level(db: Session, guild_id: int, effect_type: str) -> int:
    building = get_guild_building_by_effect(db, guild_id, effect_type)
    return building.level if building else 0


def get_mercenary_limit(db: Session, guild_id: int) -> int:
    return housing_capacity(get_building_level(db, guild_id, "housing"))


def get_training_xp_bonus_percent(db: Session, guild_id: int) -> int:
    return training_xp_bonus(get_building_level(db, guild_id, "training_ground"))


def apply_xp_bonus(base_xp: int, db: Session, guild_id: int) -> int:
    percent = get_training_xp_bonus_percent(db, guild_id)
    return base_xp + floor(base_xp * percent / 100)


def get_equipment_drop_bonus_percent(db: Session, guild_id: int) -> int:
    return blacksmith_drop_bonus(get_building_level(db, guild_id, "blacksmith"))


def get_material_quantity_bonus(db: Session, guild_id: int) -> int:
    return warehouse_material_bonus(get_building_level(db, guild_id, "warehouse"))


def apply_material_quantity_bonus(quantity: int, db: Session, guild_id: int, *, is_primary: bool = True) -> int:
    return max(quantity, quantity + (get_material_quantity_bonus(db, guild_id) if is_primary else 0))


def get_max_allowed_mission_party_size(db: Session, guild_id: int) -> int:
    return mission_office_values(get_building_level(db, guild_id, "contract_office"))["party_size"]


def are_dungeons_available(db: Session, guild_id: int) -> bool:
    return get_building_level(db, guild_id, "scouts") >= 1


def get_max_run_multiplier(db: Session, guild_id: int) -> int:
    return scouts_values(get_building_level(db, guild_id, "scouts"))["max_multiplier"]


def get_building_bonus_summary(db: Session, guild_id: int) -> dict[str, int]:
    return {
        "xp_bonus_percent": get_training_xp_bonus_percent(db, guild_id),
        "equipment_drop_bonus_percent": get_equipment_drop_bonus_percent(db, guild_id),
        "material_quantity_bonus": get_material_quantity_bonus(db, guild_id),
        "max_mission_party_size": get_max_allowed_mission_party_size(db, guild_id),
        "max_run_multiplier": get_max_run_multiplier(db, guild_id),
        "tavern_quality_bonus_percent": min(30, (get_building_level(db, guild_id, "tavern") // 5) * 2),
        "offline_bonus_percent": get_building_level(db, guild_id, "warehouse") // 5,
        "market_slots": market_values(get_building_level(db, guild_id, "market"))["slots"],
    }


def get_building_summary(db: Session, guild_id: int) -> dict[str, int]:
    buildings = ensure_guild_buildings(db, guild_id)
    return {
        "total": len(buildings),
        "owned": sum(1 for building in buildings if building.level > 0),
        "level_sum": sum(building.level for building in buildings),
        "mercenary_limit": get_mercenary_limit(db, guild_id),
        "max_mission_party_size": get_max_allowed_mission_party_size(db, guild_id),
        "max_run_multiplier": get_max_run_multiplier(db, guild_id),
    }
