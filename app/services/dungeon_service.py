from datetime import datetime, timedelta, timezone
from math import floor
from random import randint
from urllib.parse import urlencode

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.time import as_utc
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.guild import Guild, GuildResources
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
from app.repositories.item_repository import add_inventory_quantity, get_item_template_by_name
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


def validate_dungeon_requirements(db: Session, guild: Guild, dungeon_template: DungeonTemplate) -> None:
    if not are_dungeons_available(db, guild.id):
        raise DungeonError("Masmorras ainda não estão disponíveis para esta guilda.")
    if guild.level < dungeon_template.required_guild_level:
        raise DungeonError("Nível da guilda insuficiente para esta masmorra.")
    if dungeon_template.required_building_type and dungeon_template.required_building_level > 0:
        current_level = get_building_level(db, guild.id, dungeon_template.required_building_type)
        if current_level < dungeon_template.required_building_level:
            raise DungeonError("Construção necessária indisponível para esta masmorra.")


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


def validate_advanced_party_requirements(db: Session, guild: Guild, template: DungeonTemplate, mercenaries) -> None:
    if template.content_type != "boss":
        return
    introductory_boss = template.level_band == "1-20" and template.recommended_level <= 1
    total_power = get_party_power_score(db, guild.id, mercenaries)
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
    )
    skills = get_party_skill_effects(db, mercenaries)
    synergy = get_group_synergy_bonus(mercenaries, template)
    skill_bonus = skills.get("success_chance", 0) + skills.get("dungeon_power", 0) // 10
    base["skill_bonus_chance"] = skill_bonus
    base["synergy_bonus_chance"] = synergy
    base["final_chance"] = max(5, min(95, base["final_chance"] + skill_bonus + synergy))
    return base


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
        "in_progress_runs": [run for run in runs if run.status == "in_progress"],
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

    dungeon_template = get_active_dungeon_template(db, parsed_template_id)
    if dungeon_template is None:
        raise DungeonError("Masmorra indisponível.")
    validate_dungeon_requirements(db, guild, dungeon_template)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(guild.id, dungeon_template.id)))
    elif db.bind is not None and db.bind.dialect.name == "sqlite":
        # SQLite has no advisory locks; serialize starts through the campaign's guild row.
        db.execute(text("UPDATE guilds SET id = id WHERE id = :guild_id"), {"guild_id": guild.id})
    if get_active_dungeon_run_for_template(db, guild.id, dungeon_template.id) is not None:
        raise DungeonError("Esta masmorra está fechada enquanto outro grupo da guilda está em exploração.")

    if len(parsed_ids) < dungeon_template.min_party_size:
        raise DungeonError("Grupo menor que o mínimo exigido para esta masmorra.")
    if len(parsed_ids) > dungeon_template.max_party_size:
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
    duration = floor(dungeon_template.duration_seconds * parsed_multiplier * (
        100 - min(35, skill_effects.get("duration_reduction", 0) + scouts["duration_reduction_percent"])
    ) / 100)
    ends_at = started_at + timedelta(seconds=max(1, duration))
    return create_dungeon_run(
        db,
        guild.id,
        dungeon_template.id,
        mercenaries,
        started_at,
        ends_at,
        parsed_multiplier,
    )


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
    run_multiplier = dungeon_run.run_multiplier or 1
    chance_details = get_advanced_dungeon_chance(db, guild.id, template, mercenaries)
    scouts = scouts_values(get_building_level(db, guild.id, "scouts"))
    chance_details["final_chance"] = min(95, chance_details["final_chance"] + scouts["success_bonus_percentage_points"])
    skill_effects = get_party_skill_effects(db, mercenaries)
    success = randint(1, 100) <= chance_details["final_chance"]

    if success:
        gold_reward = floor(template.base_gold_reward * run_multiplier * (100 + skill_effects.get("gold_reward", 0)) / 100)
        xp_reward = apply_xp_bonus(floor(template.base_xp_reward * run_multiplier * (100 + skill_effects.get("xp_reward", 0)) / 100), db, guild.id)
    else:
        gold_reward = 0
        xp_reward = apply_xp_bonus(floor(template.base_xp_reward * run_multiplier * 0.25), db, guild.id)

    resources.gold += gold_reward
    xp_messages: list[str] = []
    level_up_messages: list[str] = []
    for mercenary in mercenaries:
        xp_messages.append(f"{mercenary.name} recebeu {xp_reward} XP.")
        level_up_messages.extend(add_xp_and_apply_levelups(mercenary, xp_reward))
        mercenary.status = "available"
        db.add(mercenary)
    guild_messages = add_guild_xp_from_mercenary_xp(guild, xp_reward * len(mercenaries))

    item_results: list[str] = []
    if success:
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
                    add_inventory_quantity(db, guild.id, drop.item_template_id, quantity)
                    item_results.append(f"{clean_generated_name(drop.item_template.name)} x{quantity}")

    dungeon_run.status = "completed" if success else "failed"
    dungeon_run.success = success
    dungeon_run.gold_reward = gold_reward
    dungeon_run.xp_reward = xp_reward
    dungeon_run.result_details = serialize_result_details(
        xp_awards=xp_messages,
        level_ups=level_up_messages,
        guild_progress=guild_messages,
        items=item_results,
    )
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
