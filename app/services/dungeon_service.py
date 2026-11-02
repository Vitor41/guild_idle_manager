from datetime import datetime, timedelta, timezone
from math import floor
from random import Random, randint
import json
from types import SimpleNamespace
from urllib.parse import urlencode

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.core.time import as_utc, prepare_timer_context
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import ItemTemplate
from app.repositories.dungeon_repository import (
    count_awaiting_dungeon_loot,
    count_dungeon_runs_by_status,
    create_dungeon_drop,
    create_dungeon_run,
    create_dungeon_template,
    get_active_dungeon_template,
    get_dungeon_drop_by_pair,
    get_dungeon_template_by_name,
    get_active_dungeon_run_for_template,
    list_active_drops_for_dungeon,
    list_active_dungeon_templates_for_band,
    list_dungeon_runs_by_guild,
)
from app.repositories.item_repository import get_item_template_by_name
from app.repositories.mercenary_repository import list_available_mercenaries_by_ids
from app.repositories.mission_repository import list_available_mercenaries_by_guild
from app.services.building_service import (
    apply_material_quantity_bonus,
    apply_xp_bonus,
    are_dungeons_available,
    get_building_bonus_summary,
    get_building_level,
    get_equipment_drop_bonus_percent,
    get_max_run_multiplier,
)
from app.services.equipment_service import (
    create_equipment_instance_from_template,
    format_equipment_bonus,
    get_mission_chance_details,
    get_party_chance_details,
)
from app.services.guild_progression_service import add_guild_xp_from_mercenary_xp
from app.services.inventory_capacity_service import add_inventory_quantity_capped
from app.services.mission_service import format_duration_seconds
from app.services.progression_service import add_xp_and_apply_levelups
from app.services.result_detail_service import parse_result_details, serialize_result_details
from app.services.skill_service import get_party_skill_effects
from app.services.achievement_service import record_guild_stat, unlock_codex_reference
from app.services.display_service import annotate_mercenary_display, clean_generated_name, rarity_label
from app.services.building_balance_service import scouts_values
from app.services.icon_service import get_item_icon_path
from app.services.equipment_service import get_party_power_score
from app.repositories.item_repository import list_equipment_for_mercenary
from app.services.prd3_dungeon_balance_service import dungeon_identity, maximum_drop_rarity
from app.services.supply_preparation_service import (
    encode_supply_snapshot, estimate_drop_sale_value, guild_gold, prepare_supply_snapshot,
    quote_supply, supply_bonus_from_snapshot,
)


INITIAL_DUNGEON_TEMPLATES = [
    {
        "name": "Covil dos Lobos",
        "description": "Uma toca ocupada por lobos alfa e criaturas agressivas.",
        "duration_seconds": 1800,
        "base_gold_reward": 150,
        "base_xp_reward": 80,
        "base_success_chance": 60,
        "min_party_size": 2,
        "max_party_size": 3,
        "required_guild_level": 1,
        "required_min_mercenary_level": 2,
        "required_building_type": "scouts",
        "required_building_level": 1,
        "is_active": True,
    },
    {
        "name": "Fortaleza do Ogro",
        "description": "Uma fortaleza brutal que exige um grupo equilibrado e bem equipado.",
        "content_type": "dungeon",
        "difficulty": "hard",
        "duration_seconds": 3600,
        "base_gold_reward": 450,
        "base_xp_reward": 220,
        "base_success_chance": 45,
        "min_party_size": 3,
        "max_party_size": 5,
        "required_guild_level": 10,
        "required_min_mercenary_level": 20,
        "required_building_type": "scouts",
        "required_building_level": 10,
        "required_total_power": 150,
        "required_tank_count": 1,
        "required_support_count": 1,
        "required_damage_count": 1,
        "required_equipment_tier": 1,
        "is_active": True,
    },
    {
        "name": "Dragao das Cinzas",
        "description": "Chefe ancestral com recompensas raras e exigências de alto nível.",
        "content_type": "boss",
        "difficulty": "elite",
        "duration_seconds": 7200,
        "base_gold_reward": 1200,
        "base_xp_reward": 600,
        "base_success_chance": 30,
        "min_party_size": 5,
        "max_party_size": 5,
        "required_guild_level": 25,
        "required_min_mercenary_level": 50,
        "required_building_type": "scouts",
        "required_building_level": 25,
        "required_total_power": 400,
        "required_tank_count": 1,
        "required_support_count": 1,
        "required_damage_count": 2,
        "required_equipment_tier": 2,
        "is_active": True,
    },
]

INITIAL_DUNGEON_DROPS = [
    ("Covil dos Lobos", "Espada de Ferro", 25, 1, 1),
    ("Covil dos Lobos", "Armadura Reforcada", 25, 1, 1),
    ("Covil dos Lobos", "Amuleto do Cacador", 20, 1, 1),
    ("Covil dos Lobos", "Pele de Lobo", 70, 2, 4),
    ("Fortaleza do Ogro", "Armadura Reforcada", 35, 1, 1),
    ("Fortaleza do Ogro", "Fragmento de Minerio", 80, 6, 12),
    ("Dragao das Cinzas", "Amuleto do Cacador", 20, 1, 1),
    ("Dragao das Cinzas", "Fragmento de Minerio", 100, 15, 25),
]


class DungeonError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seed_initial_dungeon_templates(db: Session) -> None:
    created_any = False
    for data in INITIAL_DUNGEON_TEMPLATES:
        if get_dungeon_template_by_name(db, str(data["name"])):
            continue
        create_dungeon_template(db, data)
        created_any = True
    if created_any:
        db.commit()


def seed_initial_dungeon_drops(db: Session) -> None:
    created_any = False
    for dungeon_name, item_name, chance, min_quantity, max_quantity in INITIAL_DUNGEON_DROPS:
        dungeon = get_dungeon_template_by_name(db, dungeon_name)
        item = get_item_template_by_name(db, item_name)
        if dungeon is None or item is None:
            continue
        if get_dungeon_drop_by_pair(db, dungeon.id, item.id):
            continue
        create_dungeon_drop(
            db,
            {
                "dungeon_template_id": dungeon.id,
                "item_template_id": item.id,
                "drop_chance": chance,
                "min_quantity": min_quantity,
                "max_quantity": max_quantity,
                "is_active": True,
            },
        )
        created_any = True
    if created_any:
        db.commit()


def validate_dungeon_requirements(
    db: Session,
    guild: Guild,
    dungeon_template: DungeonTemplate,
    *,
    required_guild_level: int | None = None,
) -> None:
    minimum_level = dungeon_template.required_guild_level if required_guild_level is None else required_guild_level
    if guild.level < minimum_level:
        raise DungeonError("Nível da guilda insuficiente para esta masmorra.")


def _party_roles(mercenaries) -> dict[str, int]:
    roles = {"tank": 0, "support": 0, "damage": 0}
    for mercenary in mercenaries:
        role = (mercenary.mercenary_class.role_type or "").lower()
        if role == "tank":
            roles["tank"] += 1
        elif role == "support":
            roles["support"] += 1
        else:
            roles["damage"] += 1
    return roles


def get_group_synergy_bonus(mercenaries, template: DungeonTemplate | None = None) -> int:
    roles = _party_roles(mercenaries)
    if template is not None:
        recommended = {
            "tank": template.required_tank_count,
            "support": template.required_support_count,
            "damage": template.required_damage_count,
        }
        if any(recommended.values()):
            return min(6, sum(2 for role, amount in recommended.items() if amount > 0 and roles[role] >= amount))
    present = sum(1 for amount in roles.values() if amount > 0)
    return 5 if present == 3 else 2 if present == 2 else 0


def get_group_synergy_power_bonus(mercenaries, template: DungeonTemplate | None = None) -> int:
    """A complete tank/support/damage formation contributes +200 group power."""
    roles = _party_roles(mercenaries)
    if template is not None and any((template.required_tank_count, template.required_support_count, template.required_damage_count)):
        required = {
            "tank": template.required_tank_count,
            "support": template.required_support_count,
            "damage": template.required_damage_count,
        }
        satisfied = all(roles[role] >= count for role, count in required.items())
    else:
        satisfied = all(roles[role] > 0 for role in ("tank", "support", "damage"))
    return 200 if satisfied else 0


def validate_advanced_party_requirements(db: Session, guild: Guild, template: DungeonTemplate, mercenaries) -> None:
    if template.content_type != "boss":
        return
    introductory_boss = template.level_band == "1-20" and template.recommended_level <= 1
    total_power = get_party_power_score(db, guild.id, mercenaries) + get_group_synergy_power_bonus(mercenaries, template)
    if not introductory_boss and total_power < template.required_total_power:
        raise DungeonError(f"O grupo precisa de Poder Total {template.required_total_power}.")
    if introductory_boss:
        return
    if template.required_class_code and not any(
        mercenary.mercenary_class.code == template.required_class_code for mercenary in mercenaries
    ):
        raise DungeonError("O grupo não possui a classe obrigatória para esta masmorra.")
    roles = _party_roles(mercenaries)
    if roles["tank"] < template.required_tank_count or roles["support"] < template.required_support_count or roles["damage"] < template.required_damage_count:
        raise DungeonError("A composicao do grupo nao atende aos papeis exigidos.")
    if template.required_equipment_tier > 0:
        for mercenary in mercenaries:
            equipment = list_equipment_for_mercenary(db, guild.id, mercenary.id)
            if not any(item.item_template.tier >= template.required_equipment_tier for item in equipment):
                raise DungeonError(f"Todos precisam de equipamento Tier {template.required_equipment_tier} ou superior.")


def apply_introductory_boss_access_rule(db: Session) -> dict[str, int]:
    adjusted = 0
    bosses = list(db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type == "boss",
        DungeonTemplate.level_band == "1-20",
        DungeonTemplate.recommended_level <= 1,
    )))
    expected = {
        "min_party_size": 1,
        "max_party_size": 5,
        "required_class_code": None,
        "required_tank_count": 0,
        "required_support_count": 0,
        "required_damage_count": 0,
        "required_equipment_tier": 0,
    }
    for boss in bosses:
        if any(getattr(boss, field) != value for field, value in expected.items()):
            for field, value in expected.items():
                setattr(boss, field, value)
            db.add(boss)
            adjusted += 1
    if adjusted:
        db.commit()
    return {"adjusted": adjusted, "total": len(bosses)}


def get_advanced_dungeon_chance(db: Session, guild_id: int, template: DungeonTemplate, mercenaries) -> dict[str, int]:
    base = get_party_chance_details(
        db, guild_id, template.base_success_chance, mercenaries,
        template.required_total_power, template.recommended_level,
        power_bonus=get_group_synergy_power_bonus(mercenaries, template),
    )
    skills = get_party_skill_effects(db, mercenaries)
    synergy = get_group_synergy_bonus(mercenaries, template)
    skill_bonus = skills.get("success_chance", 0) + skills.get("dungeon_power", 0) // 10
    base["skill_bonus_chance"] = skill_bonus
    base["synergy_bonus_chance"] = synergy
    base["final_chance"] = max(5, min(95, base["final_chance"] + skill_bonus + synergy))
    return base


def get_final_dungeon_chance(
    db: Session,
    guild_id: int,
    template: DungeonTemplate,
    mercenaries,
    *,
    regional_success_chance: int | None = None,
    regional_recommended_power: int | None = None,
    regional_recommended_level: int | None = None,
) -> int:
    """Return the resolver's chance, including party, skill, synergy, and Scouts bonuses."""
    if regional_success_chance is None:
        chance = get_advanced_dungeon_chance(db, guild_id, template, mercenaries)["final_chance"]
    else:
        details = get_party_chance_details(
            db, guild_id, regional_success_chance, mercenaries,
            regional_recommended_power if regional_recommended_power is not None else template.recommended_power,
            regional_recommended_level if regional_recommended_level is not None else template.recommended_level,
            power_bonus=get_group_synergy_power_bonus(mercenaries, template),
        )
        skills = get_party_skill_effects(db, mercenaries)
        synergy = get_group_synergy_bonus(mercenaries, template)
        skill_bonus = skills.get("success_chance", 0) + skills.get("dungeon_power", 0) // 10
        chance = max(5, min(95, details["final_chance"] + skill_bonus + synergy))
    scouts = scouts_values(get_building_level(db, guild_id, "scouts"))
    return min(95, chance + scouts["success_bonus_percentage_points"])


def get_dungeon_supply_quote(
    db: Session,
    guild: Guild,
    dungeon_template_id: str,
    mercenary_ids: list[str],
    run_multiplier: str = "1",
) -> dict[str, object]:
    """Build an exact server quote for the selected legacy dungeon party and multiplier."""
    if not are_dungeons_available(db, guild.id):
        return {"available": False, "reason": "Masmorras ainda não estão disponíveis para esta guilda."}
    try:
        template_id = int(dungeon_template_id)
        multiplier = int(run_multiplier or "1")
        parsed_ids = parse_dungeon_mercenary_ids(mercenary_ids)
    except (DungeonError, ValueError):
        return {"available": False, "reason": "Masmorra, grupo ou multiplicador inválido."}
    if multiplier < 1 or multiplier > get_max_run_multiplier(db, guild.id):
        return {"available": False, "reason": "Multiplicador indisponível para esta guilda."}
    template = get_active_dungeon_template(db, template_id)
    if template is None:
        return {"available": False, "reason": "Masmorra indisponível."}
    try:
        validate_dungeon_requirements(db, guild, template)
        if len(parsed_ids) < template.min_party_size:
            raise DungeonError("Grupo menor que o mínimo exigido para esta masmorra.")
        if len(parsed_ids) > template.max_party_size:
            raise DungeonError("Grupo maior que o máximo permitido para esta masmorra.")
        mercenaries = list_available_mercenaries_by_ids(db, guild.id, parsed_ids)
        if len(mercenaries) != len(parsed_ids):
            raise DungeonError("Mercenário indisponível.")
        if any(member.level < template.required_min_mercenary_level for member in mercenaries):
            raise DungeonError("Um ou mais mercenários não possuem nível suficiente.")
        validate_advanced_party_requirements(db, guild, template, mercenaries)
    except DungeonError as error:
        return {"available": False, "reason": str(error)}

    base_final_chance = get_final_dungeon_chance(db, guild.id, template, mercenaries)
    applied_bonus_pp = min(5, max(0, 95 - base_final_chance))
    skills = get_party_skill_effects(db, mercenaries)
    success_gold = floor(
        template.base_gold_reward * multiplier * (100 + skills.get("gold_reward", 0)) / 100
    )
    quote = quote_supply(
        rank=_legacy_supply_rank(template.recommended_level),
        success_gold=success_gold,
        expected_drop_sale=estimate_drop_sale_value(
            db, guild.id, list_active_drops_for_dungeon(db, template.id), multiplier,
        ),
        multiplier=multiplier,
        available_gold=guild_gold(db, guild.id),
        applied_bonus_pp=applied_bonus_pp,
    )
    quote.update({
        "base_final_chance": base_final_chance,
        "final_chance": min(95, base_final_chance + applied_bonus_pp),
    })
    return quote


def parse_dungeon_mercenary_ids(values: list[str]) -> list[int]:
    parsed_ids: list[int] = []
    for value in values:
        if not value:
            continue
        try:
            parsed_id = int(value)
        except ValueError as exc:
            raise DungeonError("Mercenário inválido.") from exc
        if parsed_id not in parsed_ids:
            parsed_ids.append(parsed_id)
    return parsed_ids


def get_dungeons_page_context(
    db: Session,
    guild: Guild,
    selected_band: str = "1-20",
    content_type: str = "dungeon",
    page: int = 1,
    selected_difficulty: str = "all",
    selected_sort: str = "level",
) -> dict[str, object]:
    now = utc_now()
    if not are_dungeons_available(db, guild.id):
        return {"dungeons_available": False}
    runs = list_dungeon_runs_by_guild(db, guild.id)
    all_templates = [template for template in list_active_dungeon_templates_for_band(db, selected_band)
        if content_type == "all" or template.content_type == content_type]
    if selected_difficulty != "all":
        all_templates = [template for template in all_templates if template.difficulty == selected_difficulty]
    sorters = {
        "level": lambda template: (template.required_min_mercenary_level, template.id),
        "time": lambda template: (template.duration_seconds, template.required_min_mercenary_level),
        "xp": lambda template: (-template.base_xp_reward, template.required_min_mercenary_level),
        "gold": lambda template: (-template.base_gold_reward, template.required_min_mercenary_level),
        "power": lambda template: (template.required_total_power, template.required_min_mercenary_level),
    }
    all_templates.sort(key=sorters.get(selected_sort, sorters["level"]))
    per_page = 20
    total_pages = max(1, (len(all_templates) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    templates = all_templates[(page - 1) * per_page:page * per_page]
    available_mercenaries = list_available_mercenaries_by_guild(db, guild.id)
    for mercenary in available_mercenaries:
        annotate_mercenary_display(mercenary)
    for template in templates:
        identity = dungeon_identity(template)
        template.gameplay_role = identity["role"]
        template.risk_label = identity["risk"]
        template.recommended_profile = identity["profile"]
        template.maximum_drop_rarity = maximum_drop_rarity(template)
        base_chance = max(5, min(95, template.base_success_chance)) / 100
        template.expected_xp_reward = round(template.base_xp_reward * (base_chance + (1 - base_chance) * 0.25))
        template.expected_gold_reward = round(template.base_gold_reward * base_chance)
        template.visible_drops = [drop for drop in template.item_drops if drop.is_active]
        template.synergy_bonus_max = min(6, sum(2 for amount in (
            template.required_tank_count, template.required_support_count, template.required_damage_count
        ) if amount > 0))
        for drop in template.visible_drops:
            drop.display_name = clean_generated_name(drop.item_template.name)
            drop.rarity_label = rarity_label(drop.item_template.rarity)
            drop.icon_path = get_item_icon_path(drop.item_template)
            drop.base_drop_chance = drop.drop_chance
            drop.effective_drop_chance = min(
                100,
                drop.drop_chance + (
                    get_equipment_drop_bonus_percent(db, guild.id)
                    if drop.item_template.item_type == "equipment" else 0
                ),
            )
    dungeon_chances = {
        dungeon.id: {
            mercenary.id: get_mission_chance_details(db, guild.id, dungeon, mercenary)
            for mercenary in available_mercenaries
        }
        for dungeon in templates
    }
    in_progress_runs = [run for run in runs if run.status == "in_progress"]
    for run in in_progress_runs:
        prepare_timer_context(run, now)
    finished_runs = [run for run in runs if run.status in {"completed", "failed"}][:10]
    for run in finished_runs:
        run.result_view = parse_result_details(run.result_details)
    filter_values = {
        "band": selected_band, "type": content_type,
        "difficulty": selected_difficulty, "sort": selected_sort,
    }
    return {
        "dungeon_templates": templates,
        "available_mercenaries": available_mercenaries,
        "dungeon_chances": dungeon_chances,
        "in_progress_runs": in_progress_runs,
        "locked_dungeon_ids": {
            run.dungeon_template_id for run in runs if run.status == "in_progress"
        },
        "finished_runs": finished_runs,
        "awaiting_loot_count": sum(
            1 for run in runs if run.status == "in_progress" and as_utc(run.ends_at) <= now
        ),
        "dungeons_available": are_dungeons_available(db, guild.id),
        "building_bonuses": get_building_bonus_summary(db, guild.id),
        "max_run_multiplier": get_max_run_multiplier(db, guild.id),
        "now": now,
        "format_duration": format_duration_seconds,
        "level_bands": ("1-20", "21-50", "51-100", "101-130", "131-200", "201-250", "251-300", "301-350"),
        "selected_band": selected_band,
        "selected_content_type": content_type,
        "selected_difficulty": selected_difficulty,
        "selected_sort": selected_sort,
        "filter_query": urlencode(filter_values),
        "type_queries": {
            value: urlencode({**filter_values, "type": value, "page": 1})
            for value in ("dungeon", "boss", "all")
        },
        "band_queries": {
            band: urlencode({**filter_values, "band": band, "page": 1})
            for band in ("1-20", "21-50", "51-100", "101-130", "131-200", "201-250", "251-300", "301-350")
        },
        "current_page": page,
        "total_pages": total_pages,
        "total_templates": len(all_templates),
        "difficulty_labels": {"normal": "Normal", "hard": "Difícil", "heroic": "Heroica", "legendary": "Lendária", "elite": "Elite"},
        "biome_labels": {"mines": "Minas", "woods": "Bosques", "catacombs": "Catacumbas", "ruins": "Ruínas", "fortress": "Fortalezas", "tower": "Torres", "caves": "Cavernas", "swamp": "Pântanos", "sanctuary": "Santuários", "portal": "Portais", "abyss": "Abismos", "lost_city": "Cidades perdidas"},
    }


def start_dungeon(
    db: Session,
    guild: Guild,
    dungeon_template_id: str,
    mercenary_ids: list[str],
    run_multiplier: str = "1",
    *,
    commit: bool = True,
    regional_duration_seconds: int | None = None,
    regional_min_duration_seconds: int | None = None,
    template_snapshot: dict[str, object] | None = None,
    supply_selected: bool = False,
    supply_rank: str | None = None,
    regional_success_chance: int | None = None,
    regional_recommended_power: int | None = None,
    regional_recommended_level: int | None = None,
    regional_party_bounds: tuple[int, int] | None = None,
    regional_required_guild_level: int | None = None,
    supply_include_drops: bool = True,
    supply_snapshot_override: dict[str, object] | None = None,
) -> DungeonRun:
    if not are_dungeons_available(db, guild.id):
        raise DungeonError("Evolua Exploradores para o nível 1 antes de acessar Masmorras.")
    if not dungeon_template_id:
        raise DungeonError("Masmorra é obrigatória.")
    parsed_ids = parse_dungeon_mercenary_ids(mercenary_ids)
    try:
        parsed_template_id = int(dungeon_template_id)
        parsed_multiplier = int(run_multiplier or "1")
    except ValueError as exc:
        raise DungeonError("Masmorra inválida.") from exc
    if parsed_multiplier < 1 or parsed_multiplier > get_max_run_multiplier(db, guild.id):
        raise DungeonError("Multiplicador indisponivel para esta guilda.")

    if template_snapshot is not None:
        if int(template_snapshot.get("id", -1)) != parsed_template_id or db.get(DungeonTemplate, parsed_template_id) is None:
            raise DungeonError("Snapshot da masmorra indisponível.")
        dungeon_template = SimpleNamespace(**template_snapshot)
    else:
        dungeon_template = get_active_dungeon_template(db, parsed_template_id)
        if dungeon_template is None:
            raise DungeonError("Masmorra indisponível.")
    validate_dungeon_requirements(
        db, guild, dungeon_template, required_guild_level=regional_required_guild_level,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(guild.id, dungeon_template.id)))
    elif db.bind is not None and db.bind.dialect.name == "sqlite":
        # SQLite has no advisory locks; serialize starts through the campaign's guild row.
        db.execute(text("UPDATE guilds SET id = id WHERE id = :guild_id"), {"guild_id": guild.id})
    if get_active_dungeon_run_for_template(db, guild.id, dungeon_template.id) is not None:
        raise DungeonError("Esta masmorra está fechada enquanto outro grupo da guilda está em exploração.")

    minimum_party, maximum_party = regional_party_bounds or (
        dungeon_template.min_party_size, dungeon_template.max_party_size,
    )
    if len(parsed_ids) < minimum_party:
        raise DungeonError("Grupo menor que o mínimo exigido para esta masmorra.")
    if len(parsed_ids) > maximum_party:
        raise DungeonError("Grupo maior que o máximo permitido para esta masmorra.")

    mercenaries = list_available_mercenaries_by_ids(db, guild.id, parsed_ids)
    if len(mercenaries) != len(parsed_ids):
        raise DungeonError("Mercenário indisponível.")
    if any(mercenary.level < dungeon_template.required_min_mercenary_level for mercenary in mercenaries):
        raise DungeonError("Um ou mais mercenarios nao possuem nivel suficiente.")
    validate_advanced_party_requirements(db, guild, dungeon_template, mercenaries)

    started_at = utc_now()
    skill_effects = get_party_skill_effects(db, mercenaries)
    scouts = scouts_values(get_building_level(db, guild.id, "scouts"))
    base_duration = regional_duration_seconds or dungeon_template.duration_seconds
    duration = floor(base_duration * parsed_multiplier * (
        100 - min(35, skill_effects.get("duration_reduction", 0) + scouts["duration_reduction_percent"])
    ) / 100)
    if regional_min_duration_seconds is not None:
        duration = max(int(regional_min_duration_seconds), duration)
    ends_at = started_at + timedelta(seconds=max(1, duration))
    supply_snapshot = supply_snapshot_override
    supply_cost = 0
    if supply_selected and supply_snapshot_override is None:
        rank = supply_rank or _legacy_supply_rank(dungeon_template.recommended_level)
        preview_chance = get_final_dungeon_chance(
            db, guild.id, dungeon_template, mercenaries,
            regional_success_chance=regional_success_chance,
            regional_recommended_power=regional_recommended_power,
            regional_recommended_level=regional_recommended_level,
        )
        drops = list_active_drops_for_dungeon(db, dungeon_template.id) if supply_include_drops else []
        success_gold = floor(dungeon_template.base_gold_reward * parsed_multiplier * (100 + skill_effects.get("gold_reward", 0)) / 100)
        try:
            supply_snapshot, supply_cost = prepare_supply_snapshot(
                db, guild.id, rank, success_gold, drops, parsed_multiplier, True, preview_chance,
            )
        except ValueError as error:
            raise DungeonError(str(error)) from error
        debit = db.execute(
            update(GuildResources).where(
                GuildResources.guild_id == guild.id, GuildResources.gold >= supply_cost,
            ).values(gold=GuildResources.gold - supply_cost)
        )
        if debit.rowcount != 1:
            raise DungeonError("Saldo de ouro insuficiente para o suprimento.")
    return create_dungeon_run(
        db,
        guild.id,
        dungeon_template.id,
        mercenaries,
        started_at,
        ends_at,
        parsed_multiplier,
        commit=commit,
        preparation_snapshot_json=encode_supply_snapshot(supply_snapshot),
    )


def _legacy_supply_rank(recommended_level: int) -> str:
    level = max(1, int(recommended_level))
    return "E" if level <= 10 else "D" if level <= 20 else "C" if level <= 30 else "B" if level <= 40 else "A" if level <= 50 else "S"


def claim_dungeon_loot(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    dungeon_run_id: int,
    *,
    commit: bool = True,
) -> DungeonRun:
    from app.repositories.dungeon_repository import get_dungeon_run_by_guild

    if resources is None:
        raise DungeonError("Recursos da guilda indisponiveis.")
    dungeon_run = get_dungeon_run_by_guild(db, guild.id, dungeon_run_id)
    if dungeon_run is None:
        raise DungeonError("Registro nao encontrado ou indisponivel.")
    if dungeon_run.status != "in_progress":
        raise DungeonError("Esta masmorra já foi resolvida.")

    now = utc_now()
    if now < as_utc(dungeon_run.ends_at):
        raise DungeonError("A masmorra ainda não foi concluída.")

    mercenaries = [member.mercenary for member in dungeon_run.members]
    if not mercenaries:
        raise DungeonError("Masmorra sem grupo vinculado.")

    template = dungeon_run.dungeon_template
    portal_event = None
    portal_activity = None
    from app.models.regional import RegionalEvent, RegionalEventActivity

    portal_activity = db.scalar(select(RegionalEventActivity).where(
        RegionalEventActivity.source_type == "dungeon",
        RegionalEventActivity.source_run_id == dungeon_run.id,
        RegionalEventActivity.status == "in_progress",
    ))
    if portal_activity is not None:
        linked_event = db.get(RegionalEvent, portal_activity.event_id)
        if linked_event is not None and linked_event.event_type == "portal" and linked_event.status in {"active", "in_progress"}:
            portal_event = linked_event
    portal_event_summary: dict[str, object] = {}
    portal_boss_snapshot: dict[str, object] = {}
    if portal_event is not None:
        try:
            parsed_summary = json.loads(portal_event.summary_json or "{}")
            portal_event_summary = parsed_summary if isinstance(parsed_summary, dict) else {}
        except (TypeError, json.JSONDecodeError):
            portal_event_summary = {}
        boss_record = portal_event_summary.get("portal_boss")
        boss_data = boss_record.get("template") if isinstance(boss_record, dict) else None
        if isinstance(boss_data, dict) and int(boss_data.get("id", -1)) == dungeon_run.dungeon_template_id:
            portal_boss_snapshot = boss_data
            template = SimpleNamespace(**boss_data)
    regional_offer = None
    if dungeon_run.regional_offer_id is not None:
        from app.models.regional import RegionalOffer

        regional_offer = db.get(RegionalOffer, dungeon_run.regional_offer_id)
    run_multiplier = dungeon_run.run_multiplier or 1
    base_final_chance = get_final_dungeon_chance(
        db, guild.id, template, mercenaries,
        regional_success_chance=regional_offer.success_chance_snapshot if regional_offer else None,
        regional_recommended_power=regional_offer.recommended_power_snapshot if regional_offer else None,
        regional_recommended_level=regional_offer.recommended_level_snapshot if regional_offer else None,
    )
    chance_details = {"final_chance": base_final_chance}
    scouts = scouts_values(get_building_level(db, guild.id, "scouts"))
    supply_snapshot = {}
    if dungeon_run.preparation_snapshot_json:
        try:
            supply_snapshot = json.loads(dungeon_run.preparation_snapshot_json)
        except (TypeError, json.JSONDecodeError):
            supply_snapshot = {}
    if isinstance(supply_snapshot, dict) and supply_snapshot.get("schema") == 1:
        chance_details["final_chance"] = int(supply_snapshot.get("base_final_chance", chance_details["final_chance"]))
    chance_details["final_chance"] = min(95, chance_details["final_chance"] + supply_bonus_from_snapshot(dungeon_run.preparation_snapshot_json))
    skill_effects = get_party_skill_effects(db, mercenaries)
    success = randint(1, 100) <= chance_details["final_chance"]

    if success:
        base_gold = regional_offer.gold_reward_snapshot if regional_offer else template.base_gold_reward
        base_xp = regional_offer.xp_reward_snapshot if regional_offer else template.base_xp_reward
        gold_reward = floor(base_gold * run_multiplier * (100 + skill_effects.get("gold_reward", 0)) / 100)
        xp_reward = apply_xp_bonus(floor(base_xp * run_multiplier * (100 + skill_effects.get("xp_reward", 0)) / 100), db, guild.id)
    else:
        gold_reward = 0
        xp_reward = apply_xp_bonus(floor((regional_offer.xp_reward_snapshot if regional_offer else template.base_xp_reward) * run_multiplier * 0.25), db, guild.id)

    resources.gold += gold_reward
    crystal_rank = dungeon_run.rank_snapshot or (
        "E" if int(getattr(template, "recommended_level", 1)) <= 10 else
        "D" if int(getattr(template, "recommended_level", 1)) <= 20 else
        "C" if int(getattr(template, "recommended_level", 1)) <= 30 else
        "B" if int(getattr(template, "recommended_level", 1)) <= 40 else
        "A" if int(getattr(template, "recommended_level", 1)) <= 50 else "S"
    )
    crystal_drop = int(
        success
        and getattr(template, "content_type", "dungeon") in {"dungeon", "boss"}
        and crystal_rank in {"A", "S"}
        and randint(1, 100) <= (2 if crystal_rank == "A" else 1)
    )
    if crystal_drop:
        resources.crystal_reserve += crystal_drop
        resources.crystals += crystal_drop
    xp_messages: list[str] = []
    level_up_messages: list[str] = []
    for mercenary in mercenaries:
        xp_messages.append(f"{mercenary.name} recebeu {xp_reward} XP.")
        level_up_messages.extend(add_xp_and_apply_levelups(mercenary, xp_reward))
        mercenary.status = "available"
        db.add(mercenary)
    guild_messages = add_guild_xp_from_mercenary_xp(guild, xp_reward * len(mercenaries))

    item_results: list[str] = []
    if crystal_drop:
        item_results.append("Cristais x1")
    portal_loot_result: dict[str, object] | None = None
    if success and portal_event is not None:
        portal_summary = portal_event_summary
        table = portal_summary.get("portal_loot") if isinstance(portal_summary, dict) else None
        table = table if isinstance(table, dict) else {}
        entries = table.get("entries") if isinstance(table.get("entries"), list) else []
        loot_rng = Random(f"{portal_event.seed}:{dungeon_run.id}:{table.get('version', 'missing')}:portal-loot")
        ticket = loot_rng.randint(1, 100)
        cursor = 0
        dropped_item_id = None
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cursor += max(0, min(100 - cursor, int(entry.get("chance_percent", 0))))
            if ticket > cursor:
                continue
            item_id = int(entry.get("item_template_id", 0))
            item_data = entry.get("item_snapshot")
            if isinstance(item_data, dict) and int(item_data.get("id", -1)) == item_id:
                item_template = SimpleNamespace(**item_data)
            else:
                # Older portal snapshots predate frozen item properties.
                item_template = db.get(ItemTemplate, item_id)
            if item_template is None or item_template.item_type != "equipment":
                break
            unlock_codex_reference(db, guild.id, "item", item_template.id)
            instance = create_equipment_instance_from_template(db, guild.id, item_template)
            item_results.append(f"{clean_generated_name(item_template.name)} ({format_equipment_bonus(instance)})")
            dropped_item_id = item_template.id
            break
        portal_loot_result = {
            "table_version": table.get("version"),
            "roll_ticket": ticket,
            "item_template_id": dropped_item_id,
        }
    elif success:
        active_drops = list_active_drops_for_dungeon(db, template.id)
        primary_material = next((drop for drop in active_drops if drop.item_template.item_type != "equipment"), None)
        for drop in active_drops:
            drop_chance = drop.drop_chance
            drop_chance += skill_effects.get("drop_chance", 0)
            drop_chance += scouts["drop_bonus_percentage_points"]
            if drop.item_template.item_type == "equipment":
                drop_chance += get_equipment_drop_bonus_percent(db, guild.id)
            if randint(1, 100) <= min(100, drop_chance):
                unlock_codex_reference(db, guild.id, "item", drop.item_template_id)
                quantity = randint(drop.min_quantity, drop.max_quantity)
                quantity *= run_multiplier
                if drop.item_template.item_type == "equipment":
                    for _ in range(quantity):
                        item_instance = create_equipment_instance_from_template(db, guild.id, drop.item_template)
                        item_results.append(f"{clean_generated_name(drop.item_template.name)} ({format_equipment_bonus(item_instance)})")
                else:
                    quantity = apply_material_quantity_bonus(
                        quantity, db, guild.id,
                        is_primary=primary_material is not None and drop.id == primary_material.id,
                    )
                    stored, discarded = add_inventory_quantity_capped(db, guild, drop.item_template_id, quantity)
                    item_results.append(
                        f"{clean_generated_name(drop.item_template.name)} x{stored}"
                        + (f" · {discarded} excedente descartado (Armazém cheio)" if discarded else "")
                    )

    dungeon_run.status = "completed" if success else "failed"
    dungeon_run.success = success
    dungeon_run.gold_reward = gold_reward
    dungeon_run.xp_reward = xp_reward
    dungeon_run.result_details = serialize_result_details(
        xp_awards=xp_messages,
        level_ups=level_up_messages,
        guild_progress=guild_messages,
        items=item_results,
        notes=([f"Chance final: {chance_details['final_chance']}% (suprimento +{supply_bonus_from_snapshot(dungeon_run.preparation_snapshot_json)} p.p.; custo registrado no início)."] if supply_bonus_from_snapshot(dungeon_run.preparation_snapshot_json) else []),
    )
    if portal_event is not None:
        portal_summary = portal_event_summary
        if not isinstance(portal_summary, dict):
            portal_summary = {}
        if portal_loot_result is None:
            table = portal_summary.get("portal_loot")
            table_version = table.get("version") if isinstance(table, dict) else None
            portal_loot_result = {"table_version": table_version, "roll_ticket": None, "item_template_id": None}
        portal_summary["portal_loot_result"] = portal_loot_result
        portal_event.summary_json = json.dumps(portal_summary, ensure_ascii=False, sort_keys=True)
        db.add(portal_event)
    dungeon_run.resolved_at = now
    db.add(dungeon_run)
    db.add(resources)
    db.add(guild)
    if success:
        record_guild_stat(db, guild.id, "dungeons_completed", 1)
    if template.content_type == "boss" and success:
        record_guild_stat(db, guild.id, "bosses_defeated", 1)
    if success:
        unlock_codex_reference(db, guild.id, "dungeon", template.id)
    if dungeon_run.regional_offer_id is not None:
        from app.services.regional_cycle_service import record_player_offer_result

        record_player_offer_result(
            db, guild,
            source_type="dungeon",
            source_run_id=dungeon_run.id,
            offer_id=dungeon_run.regional_offer_id,
            success=success,
            gold_earned=gold_reward,
            xp_earned=xp_reward * len(mercenaries),
        )
    from app.services.regional_event_service import record_event_activity_result

    event_activity = record_event_activity_result(db, "dungeon", dungeon_run.id, success, now)
    if event_activity is not None:
        from app.models.regional import RegionalEvent

        event = db.get(RegionalEvent, event_activity.event_id)
        if event is not None and event.event_type == "portal":
            from app.services.regional_event_service import resolve_portal_participant

            resolve_portal_participant(db, event_activity, success, now)
            record_guild_stat(db, guild.id, "portals_completed", 1)
    if commit:
        db.commit()
        db.refresh(dungeon_run)
    else:
        db.flush()
    return dungeon_run


def claim_all_ready_dungeon_loot(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
) -> dict[str, int]:
    now = utc_now()
    ready_runs = [
        run for run in list_dungeon_runs_by_guild(db, guild.id)
        if run.status == "in_progress" and as_utc(run.ends_at) <= now
    ]
    if not ready_runs:
        raise DungeonError("Nenhuma recompensa de masmorra ou chefe está pronta para coleta.")
    summary = {
        "resolved": 0, "successes": 0, "failures": 0,
        "gold": 0, "xp_distributed": 0, "loot_entries": 0, "errors": 0,
    }
    for run in ready_runs:
        try:
            with db.begin_nested():
                resolved = claim_dungeon_loot(db, guild, resources, run.id, commit=False)
                details = parse_result_details(resolved.result_details)
                summary["resolved"] += 1
                summary["successes" if resolved.success else "failures"] += 1
                summary["gold"] += resolved.gold_reward or 0
                summary["xp_distributed"] += (resolved.xp_reward or 0) * len(resolved.members)
                summary["loot_entries"] += len(details["items"])
        except (DungeonError, ValueError):
            summary["errors"] += 1
    db.commit()
    return summary


def format_bulk_dungeon_result(summary: dict[str, int]) -> str:
    return (
        f"{summary['resolved']} recompensas coletadas · {summary['successes']} sucessos · "
        f"{summary['failures']} falhas · +{summary['gold']} ouro · "
        f"{summary['xp_distributed']} XP distribuído · {summary['loot_entries']} loots"
        + (f" · {summary['errors']} não coletadas" if summary["errors"] else "")
    )


def get_dungeon_summary(db: Session, guild_id: int) -> dict[str, int]:
    now = utc_now()
    return {
        "in_progress": count_dungeon_runs_by_status(db, guild_id, "in_progress"),
        "awaiting_loot": count_awaiting_dungeon_loot(db, guild_id, now),
        "completed": count_dungeon_runs_by_status(db, guild_id, "completed")
        + count_dungeon_runs_by_status(db, guild_id, "failed"),
    }


def format_dungeon_result_message(dungeon_run: DungeonRun) -> str:
    if dungeon_run.success:
        return "Masmorra concluída com sucesso. Recompensas registradas no histórico."
    return "Masmorra concluída, mas o grupo falhou. Consulte os detalhes no histórico."
