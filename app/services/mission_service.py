from datetime import datetime, timedelta, timezone
from math import floor
from random import randint
from urllib.parse import urlencode

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.time import as_utc
from app.models.guild import Guild, GuildResources
from app.models.mission import MissionRun, MissionTemplate
from app.repositories.mission_repository import (
    add_gold,
    count_awaiting_loot,
    count_active_long_idle_runs,
    count_mission_runs_by_status,
    create_mission_run,
    create_mission_template,
    get_active_mission_template,
    get_mission_run_by_guild,
    get_mission_template_by_name,
    list_active_mission_templates_for_band,
    list_active_gathering_families,
    list_available_mercenaries_by_guild,
    list_mission_runs_by_guild,
)
from app.repositories.mercenary_repository import list_available_mercenaries_by_ids
from app.repositories.item_repository import add_inventory_quantity, list_active_drops_for_mission
from app.services.building_service import (
    apply_material_quantity_bonus,
    apply_xp_bonus,
    ensure_guild_buildings,
    get_building_bonus_summary,
    get_building_level,
    get_equipment_drop_bonus_percent,
    get_max_run_multiplier,
    get_max_allowed_mission_party_size,
)
from app.services.equipment_service import (
    create_equipment_instance_from_template,
    format_equipment_bonus,
    get_mission_chance_details,
    get_party_chance_details,
)
from app.services.guild_progression_service import add_guild_xp_from_mercenary_xp
from app.services.progression_service import add_xp_and_apply_levelups
from app.services.result_detail_service import parse_result_details, serialize_result_details
from app.services.skill_service import get_party_skill_effects
from app.services.achievement_service import record_guild_stat, unlock_codex_reference
from app.services.profession_service import PROFESSION_COLORS, get_profession_drop_bonus_percentage_points
from app.services.display_service import annotate_mercenary_display, clean_generated_name, rarity_label
from app.services.icon_service import get_item_icon_path
from app.services.building_balance_service import mission_office_values


INITIAL_MISSION_TEMPLATES = [
    {
        "name": "Cacar lobos",
        "description": "Elimine lobos que ameacam as estradas proximas.",
        "duration_seconds": 300,
        "base_gold_reward": 25,
        "base_xp_reward": 10,
        "base_success_chance": 80,
        "min_party_size": 1,
        "max_party_size": 1,
        "required_guild_level": 1,
        "required_min_mercenary_level": 1,
        "required_building_type": None,
        "required_building_level": 0,
        "is_active": True,
    },
    {
        "name": "Patrulhar estrada",
        "description": "Vigie a rota comercial e afaste pequenas ameacas.",
        "duration_seconds": 600,
        "base_gold_reward": 40,
        "base_xp_reward": 15,
        "base_success_chance": 75,
        "min_party_size": 1,
        "max_party_size": 2,
        "required_guild_level": 1,
        "required_min_mercenary_level": 1,
        "required_building_type": "contract_office",
        "required_building_level": 1,
        "is_active": True,
    },
    {
        "name": "Escoltar comerciante",
        "description": "Proteja um comerciante durante uma viagem curta.",
        "duration_seconds": 900,
        "base_gold_reward": 60,
        "base_xp_reward": 20,
        "base_success_chance": 70,
        "min_party_size": 1,
        "max_party_size": 2,
        "required_guild_level": 1,
        "required_min_mercenary_level": 1,
        "required_building_type": "contract_office",
        "required_building_level": 1,
        "is_active": True,
    },
    {
        "name": "Limpar caverna pequena",
        "description": "Um grupo reduzido investiga uma caverna instavel nos arredores.",
        "duration_seconds": 1200,
        "base_gold_reward": 90,
        "base_xp_reward": 35,
        "base_success_chance": 65,
        "min_party_size": 2,
        "max_party_size": 2,
        "required_guild_level": 1,
        "required_min_mercenary_level": 1,
        "required_building_type": "contract_office",
        "required_building_level": 1,
        "is_active": True,
    },
]


class MissionError(ValueError):
    pass


MISSION_LEVEL_BANDS = ("1-20", "21-50", "51-100", "101-130", "131-200", "201-250", "251-300", "301-350")
MISSION_DIFFICULTY_LABELS = {
    "very_easy": "Muito fácil",
    "easy": "Fácil",
    "normal": "Normal",
    "hard": "Difícil",
    "dangerous": "Perigosa",
    "heroic": "Heroica",
    "legendary": "Lendária",
    "elite": "Elite",
}

LONG_IDLE_LIMIT = 3
LONG_IDLE_DURATION_SECONDS = 8 * 60 * 60
LONG_IDLE_CONFIGS = (
    (1, 75, "Vigia Breve"),
    (3, 70, "Ronda Estendida"),
    (8, 60, "Vigília Completa"),
)
LONG_IDLE_NAMES = {
    "1-20": "Patrulha Noturna dos Arredores",
    "21-50": "Vigia da Estrada Velha",
    "51-100": "Ronda nos Bosques da Guilda",
    "101-130": "Guarda dos Portões Externos",
    "131-200": "Patrulha Contra Saqueadores",
    "201-250": "Vigia das Ruínas Distantes",
    "251-300": "Sentinela da Fronteira Sombria",
    "301-350": "Patrulha Final Contra Invasões",
}


def can_start_long_idle_mission(active_count: int) -> bool:
    return max(0, int(active_count)) < LONG_IDLE_LIMIT


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def split_duration_seconds(duration_seconds: int) -> dict[str, int]:
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    return {"hours": hours, "minutes": minutes, "seconds": seconds}


def format_duration_seconds(duration_seconds: int) -> str:
    duration = split_duration_seconds(duration_seconds)
    return (
        f"{duration['hours']:02d}:"
        f"{duration['minutes']:02d}:"
        f"{duration['seconds']:02d}"
    )


def seed_initial_mission_templates(db: Session) -> None:
    created_any = False
    for template_data in INITIAL_MISSION_TEMPLATES:
        if get_mission_template_by_name(db, str(template_data["name"])):
            continue
        create_mission_template(db, template_data)
        created_any = True

    if created_any:
        db.commit()


def seed_long_idle_missions(db: Session) -> None:
    created = False
    for order, band in enumerate(MISSION_LEVEL_BANDS, start=1):
        lower_level = int(band.split("-")[0])
        active_missions = list(db.scalars(select(MissionTemplate).where(
            MissionTemplate.level_band == band,
            MissionTemplate.is_active.is_(True),
            ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
        )))
        max_gold_per_hour = max(
            (mission.base_gold_reward * 3600 / max(1, mission.duration_seconds) for mission in active_missions),
            default=max(25, lower_level * 2),
        )
        max_xp_per_hour = max(
            (mission.base_xp_reward * 3600 / max(1, mission.duration_seconds) for mission in active_missions),
            default=max(25, lower_level * 2),
        )
        for duration_hours, success_chance, prefix in LONG_IDLE_CONFIGS:
            slug = f"long-idle-{band}" if duration_hours == 8 else f"long-idle-{duration_hours}h-{band}"
            existing = db.scalar(select(MissionTemplate).where(MissionTemplate.slug == slug))
            if existing is not None:
                continue
            name = LONG_IDLE_NAMES[band] if duration_hours == 8 else f"{prefix}: {LONG_IDLE_NAMES[band]}"
            create_mission_template(db, {
                "slug": slug, "name": name,
                "description": f"Missão de proteção de {duration_hours}h com chance fixa e apenas recompensas de ouro e XP.",
                "display_order": 9000 + order * 10 + duration_hours, "difficulty": "normal", "level_band": band,
                "mission_type": "long_idle", "content_pack": "prd_improvements_2",
                "recommended_level": lower_level, "recommended_power": max(10, lower_level * 5),
                "duration_seconds": duration_hours * 3600,
                "base_gold_reward": max(1, floor(max_gold_per_hour * 0.5 * duration_hours)),
                "base_xp_reward": max(1, floor(max_xp_per_hour * 0.5 * duration_hours)),
                "base_success_chance": success_chance, "min_party_size": 1, "max_party_size": 5,
                "required_guild_level": 1, "required_min_mercenary_level": lower_level,
                "required_building_type": None, "required_building_level": 0, "is_active": True,
            })
            created = True
    if created:
        db.commit()


def repair_long_idle_mission_catalog(db: Session) -> dict[str, int]:
    repaired = 0
    missions = list(db.scalars(select(MissionTemplate).where(MissionTemplate.slug.like("long-idle-%"))))
    for mission in missions:
        level_band = next((band for band in MISSION_LEVEL_BANDS if mission.slug.endswith(band)), None)
        if level_band is None:
            continue
        expected = {
            "mission_type": "long_idle",
            "level_band": level_band,
            "min_party_size": 1,
            "max_party_size": 5,
            "gathering_family": None,
            "profession_code": None,
        }
        if any(getattr(mission, key) != value for key, value in expected.items()):
            for key, value in expected.items():
                setattr(mission, key, value)
            db.add(mission)
            repaired += 1
    if repaired:
        db.commit()
    return {"repaired": repaired, "total": len(missions)}


def get_missions_page_context(
    db: Session,
    guild: Guild,
    selected_band: str = "1-20",
    selected_category: str = "combat",
    page: int = 1,
    selected_focus: str = "all",
    selected_sort: str = "level",
    selected_mode: str = "standard",
    selected_levels: tuple[int, ...] = (),
    selected_material: str = "all",
) -> dict[str, object]:
    now = utc_now()
    ensure_guild_buildings(db, guild.id)
    runs = list_mission_runs_by_guild(db, guild.id)
    if selected_band not in MISSION_LEVEL_BANDS:
        selected_band = MISSION_LEVEL_BANDS[0]
    band_start, band_end = (int(value) for value in selected_band.split("-"))
    selected_levels = tuple(sorted({level for level in selected_levels if band_start <= level <= band_end}))
    gathering_families = list_active_gathering_families(db)
    if selected_material not in gathering_families:
        selected_material = "all"
    all_templates = [
        mission for mission in list_active_mission_templates_for_band(
            db, selected_band, selected_levels,
            selected_material if selected_category == "gathering" and selected_material != "all" else None,
        )
        if mission_is_unlocked(db, guild, mission)
        and (selected_category == "all" or (mission.mission_type == "gathering") == (selected_category == "gathering"))
        and (
            selected_mode == "all"
            or (selected_mode == "long" and mission.mission_type == "long_idle")
            or (selected_mode == "standard" and mission.mission_type != "long_idle")
        )
    ]
    if selected_focus == "gold":
        all_templates = [mission for mission in all_templates if mission.base_gold_reward >= mission.base_xp_reward]
    elif selected_focus == "xp":
        all_templates = [mission for mission in all_templates if mission.base_xp_reward > mission.base_gold_reward]
    elif selected_focus == "equipment":
        all_templates = [
            mission for mission in all_templates
            if any(drop.is_active and drop.item_template.item_type == "equipment" for drop in mission.item_drops)
        ]
    sorters = {
        "level": lambda mission: (mission.required_min_mercenary_level, mission.display_order),
        "time": lambda mission: (mission.duration_seconds, mission.required_min_mercenary_level),
        "xp": lambda mission: (-mission.base_xp_reward, mission.required_min_mercenary_level),
        "gold": lambda mission: (-mission.base_gold_reward, mission.required_min_mercenary_level),
        "chance": lambda mission: (-mission.base_success_chance, mission.required_min_mercenary_level),
    }
    selected_sorter = sorters.get(selected_sort, sorters["level"])
    all_templates.sort(key=lambda mission: (
        mission.mission_type == "long_idle",
        *selected_sorter(mission),
    ))
    per_page = 24
    total_pages = max(1, (len(all_templates) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    mission_templates = all_templates[(page - 1) * per_page:page * per_page]
    available_mercenaries = list_available_mercenaries_by_guild(db, guild.id)
    for mercenary in available_mercenaries:
        annotate_mercenary_display(mercenary)
    for mission in mission_templates:
        mission.is_long_idle = mission.mission_type == "long_idle"
        mission.long_idle_hours = mission.duration_seconds // 3600 if mission.is_long_idle else 0
        mission.visible_drops = [drop for drop in mission.item_drops if drop.is_active]
        for drop in mission.visible_drops:
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
    mission_mercenaries = {
        mission.id: [
            mercenary for mercenary in available_mercenaries
            if mercenary.level >= mission.required_min_mercenary_level
        ]
        for mission in mission_templates
    }
    mission_chances = {
        mission.id: {
            mercenary.id: get_mission_chance_details(db, guild.id, mission, mercenary)
            for mercenary in mission_mercenaries[mission.id]
        }
        for mission in mission_templates
    }
    for mission in mission_templates:
        if mission.mission_type == "long_idle":
            for details in mission_chances[mission.id].values():
                details.update({
                    "final_chance": mission.base_success_chance, "bonus_chance": 0, "class_bonus_chance": 0,
                    "skill_bonus_chance": 0, "rarity_bonus_chance": 0,
                })
    finished_runs = [run for run in runs if run.status in {"completed", "failed"}][:10]
    for run in finished_runs:
        run.result_view = parse_result_details(run.result_details)
    filter_values = {
        "band": selected_band, "category": selected_category,
        "focus": selected_focus, "sort": selected_sort,
        "mode": selected_mode,
        "material": selected_material, "levels": list(selected_levels),
    }
    return {
        "mission_templates": mission_templates,
        "available_mercenaries": available_mercenaries,
        "mission_mercenaries": mission_mercenaries,
        "mission_chances": mission_chances,
        "in_progress_runs": [run for run in runs if run.status == "in_progress"],
        "finished_runs": finished_runs,
        "awaiting_loot_count": sum(
            1 for run in runs if run.status == "in_progress" and as_utc(run.ends_at) <= now
        ),
        "max_allowed_party_size": get_max_allowed_mission_party_size(db, guild.id),
        "building_bonuses": get_building_bonus_summary(db, guild.id),
        "max_run_multiplier": get_max_run_multiplier(db, guild.id),
        "long_idle_active_count": count_active_long_idle_runs(db, guild.id),
        "long_idle_limit": LONG_IDLE_LIMIT,
        "now": now,
        "format_duration": format_duration_seconds,
        "mission_level_bands": MISSION_LEVEL_BANDS,
        "selected_band": selected_band,
        "selected_category": selected_category,
        "selected_focus": selected_focus,
        "selected_sort": selected_sort,
        "selected_mode": selected_mode,
        "selected_levels": selected_levels,
        "selected_material": selected_material,
        "gathering_families": gathering_families,
        "available_levels": range(band_start, band_end + 1),
        "filter_query": urlencode(filter_values, doseq=True),
        "category_queries": {
            category: urlencode({
                **filter_values,
                "category": category,
                "mode": "standard" if category == "gathering" else selected_mode,
                "page": 1,
            }, doseq=True)
            for category in ("combat", "gathering", "all")
        },
        "band_queries": {
            band: urlencode({**filter_values, "band": band, "levels": [], "page": 1}, doseq=True)
            for band in MISSION_LEVEL_BANDS
        },
        "current_page": page,
        "total_pages": total_pages,
        "total_templates": len(all_templates),
        "difficulty_labels": MISSION_DIFFICULTY_LABELS,
        "profession_labels": {"woodcutter": "Lenhador", "miner": "Minerador", "herbalist": "Herborista", "leatherworker": "Coureiro", "weaver": "Tecelão", "prospector": "Garimpeiro", "reliquary": "Relicário", "alchemist": "Alquimista"},
        "profession_colors": PROFESSION_COLORS,
        "family_labels": {"wood": "Madeiras", "ore": "Minérios", "herb": "Ervas", "leather": "Couros", "cloth": "Fibras", "gem": "Gemas", "relic": "Relíquias", "essence": "Essências"},
    }


def parse_mercenary_ids(values: list[str]) -> list[int]:
    parsed_ids: list[int] = []
    for value in values:
        if not value:
            continue
        try:
            parsed_id = int(value)
        except ValueError as exc:
            raise MissionError("Mercenário inválido.") from exc
        if parsed_id not in parsed_ids:
            parsed_ids.append(parsed_id)
    return parsed_ids


def validate_mission_requirements(db: Session, guild: Guild, mission_template: MissionTemplate) -> None:
    if guild.level < mission_template.required_guild_level:
        raise MissionError("Nível da guilda insuficiente para esta missão.")
    if mission_template.required_building_type and mission_template.required_building_level > 0:
        current_level = get_building_level(db, guild.id, mission_template.required_building_type)
        if current_level < mission_template.required_building_level:
            raise MissionError("Construção necessária indisponível para esta missão.")


def mission_is_unlocked(db: Session, guild: Guild, mission_template: MissionTemplate) -> bool:
    try:
        validate_mission_requirements(db, guild, mission_template)
    except MissionError:
        return False
    return True


def start_mission(
    db: Session,
    guild: Guild,
    mission_template_id: str,
    mercenary_ids: list[str],
    run_multiplier: str = "1",
) -> MissionRun:
    if not mission_template_id:
        raise MissionError("Missao e obrigatoria.")
    if not mercenary_ids:
        raise MissionError("Mercenário é obrigatório.")

    try:
        parsed_template_id = int(mission_template_id)
        parsed_multiplier = int(run_multiplier or "1")
    except ValueError as exc:
        raise MissionError("Dados da missão inválidos.") from exc
    parsed_mercenary_ids = parse_mercenary_ids(mercenary_ids)
    if parsed_multiplier < 1 or parsed_multiplier > get_max_run_multiplier(db, guild.id):
        raise MissionError("Multiplicador indisponivel para esta guilda.")

    mission_template = get_active_mission_template(db, parsed_template_id)
    if mission_template is None:
        raise MissionError("Missao indisponivel.")
    validate_mission_requirements(db, guild, mission_template)
    if mission_template.mission_type == "long_idle":
        if parsed_multiplier != 1:
            raise MissionError("Missões longas não aceitam multiplicador.")
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(select(func.pg_advisory_xact_lock(guild.id, 350044)))
        elif db.bind is not None and db.bind.dialect.name == "sqlite":
            # SQLite has no advisory locks; a no-op write serializes competing starts per DB.
            db.execute(text("UPDATE guilds SET id = id WHERE id = :guild_id"), {"guild_id": guild.id})
        if not can_start_long_idle_mission(count_active_long_idle_runs(db, guild.id)):
            raise MissionError("O limite de 3 missões longas ativas foi atingido.")

    if len(parsed_mercenary_ids) < mission_template.min_party_size:
        raise MissionError("Grupo menor que o mínimo exigido para esta missão.")
    if len(parsed_mercenary_ids) > mission_template.max_party_size:
        raise MissionError("Grupo maior que o máximo permitido para esta missão.")
    if len(parsed_mercenary_ids) > get_max_allowed_mission_party_size(db, guild.id):
        raise MissionError("O Escritório de Missões não permite um grupo deste tamanho.")

    mercenaries = list_available_mercenaries_by_ids(db, guild.id, parsed_mercenary_ids)
    if len(mercenaries) != len(parsed_mercenary_ids):
        raise MissionError("Mercenário indisponível.")
    if any(mercenary.level < mission_template.required_min_mercenary_level for mercenary in mercenaries):
        raise MissionError("Um ou mais mercenarios nao possuem nivel suficiente.")

    started_at = utc_now()
    skill_effects = get_party_skill_effects(db, mercenaries)
    office = mission_office_values(get_building_level(db, guild.id, "contract_office"))
    duration = mission_template.duration_seconds if mission_template.mission_type == "long_idle" else floor(
        mission_template.duration_seconds * parsed_multiplier
        * (100 - min(30, skill_effects.get("duration_reduction", 0) + office["duration_reduction_percent"])) / 100
    )
    ends_at = started_at + timedelta(seconds=max(1, duration))
    return create_mission_run(
        db=db,
        guild_id=guild.id,
        mission_template_id=mission_template.id,
        mercenaries=mercenaries,
        started_at=started_at,
        ends_at=ends_at,
        run_multiplier=parsed_multiplier,
    )


def claim_mission_loot(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    mission_run_id: int,
    *,
    commit: bool = True,
) -> MissionRun:
    if resources is None:
        raise MissionError("Recursos da guilda indisponiveis.")

    mission_run = get_mission_run_by_guild(db, guild.id, mission_run_id)
    if mission_run is None:
        raise MissionError("Registro nao encontrado ou indisponivel.")
    if mission_run.status != "in_progress":
        raise MissionError("Esta missão já foi resolvida.")

    now = utc_now()
    if now < as_utc(mission_run.ends_at):
        raise MissionError("A missão ainda não foi concluída.")

    mercenaries = [member.mercenary for member in mission_run.members]
    if not mercenaries:
        raise MissionError("Missao sem mercenario vinculado.")

    mission_template = mission_run.mission_template
    run_multiplier = mission_run.run_multiplier or 1
    chance_details = get_party_chance_details(
        db, guild.id, mission_template.base_success_chance, mercenaries,
        mission_template.recommended_power, mission_template.recommended_level,
    )
    skill_effects = get_party_skill_effects(db, mercenaries)
    success_chance = mission_template.base_success_chance if mission_template.mission_type == "long_idle" else max(
        5, min(95, chance_details["final_chance"] + skill_effects.get("success_chance", 0))
    )
    success = randint(1, 100) <= success_chance

    if success:
        office_reward = 0 if mission_template.mission_type == "long_idle" else mission_office_values(
            get_building_level(db, guild.id, "contract_office")
        )["reward_bonus_percent"]
        gold_reward = floor(mission_template.base_gold_reward * run_multiplier * (100 + skill_effects.get("gold_reward", 0) + office_reward) / 100)
        xp_reward = apply_xp_bonus(floor(mission_template.base_xp_reward * run_multiplier * (100 + skill_effects.get("xp_reward", 0) + office_reward) / 100), db, guild.id)
    else:
        gold_reward = 0
        xp_reward = 0 if mission_template.mission_type == "long_idle" else apply_xp_bonus(
            floor(mission_template.base_xp_reward * run_multiplier * 0.25), db, guild.id
        )

    add_gold(resources, gold_reward)
    xp_messages: list[str] = []
    level_up_messages: list[str] = []
    for mercenary in mercenaries:
        xp_messages.append(f"{mercenary.name} recebeu {xp_reward} XP.")
        level_up_messages.extend(add_xp_and_apply_levelups(mercenary, xp_reward))
        mercenary.status = "available"
        db.add(mercenary)
    guild_messages = add_guild_xp_from_mercenary_xp(guild, xp_reward * len(mercenaries))

    item_results: list[str] = []
    profession_bonus = get_profession_drop_bonus_percentage_points(mercenaries, mission_template.profession_code)
    if success:
        active_drops = list_active_drops_for_mission(db, mission_template.id)
        material_drops = [drop for drop in active_drops if drop.item_template.item_type != "equipment"]
        primary_material = next((
            drop for drop in material_drops
            if mission_template.mission_type == "gathering"
            and drop.item_template.material_family == mission_template.gathering_family
        ), material_drops[0] if material_drops else None)
        for drop in active_drops:
            drop_chance = drop.drop_chance
            drop_chance += skill_effects.get("drop_chance", 0)
            is_primary_material = primary_material is not None and drop.id == primary_material.id
            if is_primary_material and mission_template.mission_type == "gathering":
                drop_chance += profession_bonus
            if drop.item_template.item_type == "equipment":
                drop_chance += get_equipment_drop_bonus_percent(db, guild.id)
            if randint(1, 100) <= min(100, drop_chance):
                unlock_codex_reference(db, guild.id, "item", drop.item_template_id)
                quantity = randint(drop.min_quantity, drop.max_quantity)
                quantity *= run_multiplier
                if drop.item_template.item_type == "equipment":
                    for _ in range(quantity):
                        item_instance = create_equipment_instance_from_template(db, guild.id, drop.item_template)
                        item_results.append(
                            f"{clean_generated_name(drop.item_template.name)} ({format_equipment_bonus(item_instance)})"
                        )
                else:
                    quantity = apply_material_quantity_bonus(quantity, db, guild.id, is_primary=is_primary_material)
                    add_inventory_quantity(db, guild.id, drop.item_template_id, quantity)
                    item_results.append(f"{clean_generated_name(drop.item_template.name)} x{quantity}")
                    if is_primary_material and profession_bonus:
                        record_guild_stat(db, guild.id, "profession_bonus_uses", 1)

    mission_run.status = "completed" if success else "failed"
    mission_run.success = success
    mission_run.gold_reward = gold_reward
    mission_run.xp_reward = xp_reward
    mission_run.result_details = serialize_result_details(
        xp_awards=xp_messages,
        level_ups=level_up_messages,
        guild_progress=guild_messages,
        items=item_results,
    )
    mission_run.resolved_at = now
    db.add(mission_run)
    db.add(resources)
    db.add(guild)
    if success:
        record_guild_stat(db, guild.id, "missions_completed", 1)
        if mission_template.mission_type == "gathering":
            record_guild_stat(db, guild.id, "gathering_completed", 1)
    if commit:
        db.commit()
        db.refresh(mission_run)
    else:
        db.flush()
    return mission_run


def claim_all_ready_mission_loot(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
) -> dict[str, int]:
    now = utc_now()
    ready_runs = [
        run for run in list_mission_runs_by_guild(db, guild.id)
        if run.status == "in_progress" and as_utc(run.ends_at) <= now
    ]
    if not ready_runs:
        raise MissionError("Nenhuma recompensa de missão está pronta para coleta.")
    summary = {
        "resolved": 0, "successes": 0, "failures": 0,
        "gold": 0, "xp_distributed": 0, "loot_entries": 0, "errors": 0,
    }
    for run in ready_runs:
        try:
            with db.begin_nested():
                resolved = claim_mission_loot(
                    db, guild, resources, run.id, commit=False
                )
                details = parse_result_details(resolved.result_details)
                summary["resolved"] += 1
                summary["successes" if resolved.success else "failures"] += 1
                summary["gold"] += resolved.gold_reward or 0
                summary["xp_distributed"] += (resolved.xp_reward or 0) * len(resolved.members)
                summary["loot_entries"] += len(details["items"])
        except (MissionError, ValueError):
            summary["errors"] += 1
    db.commit()
    return summary


def format_bulk_mission_result(summary: dict[str, int]) -> str:
    return (
        f"{summary['resolved']} missões coletadas · {summary['successes']} sucessos · "
        f"{summary['failures']} falhas · +{summary['gold']} ouro · "
        f"{summary['xp_distributed']} XP distribuído · {summary['loot_entries']} loots"
        + (f" · {summary['errors']} não coletadas" if summary["errors"] else "")
    )


def get_mission_summary(db: Session, guild_id: int) -> dict[str, int]:
    now = utc_now()
    return {
        "in_progress": count_mission_runs_by_status(db, guild_id, "in_progress"),
        "awaiting_loot": count_awaiting_loot(db, guild_id, now),
        "completed": count_mission_runs_by_status(db, guild_id, "completed")
        + count_mission_runs_by_status(db, guild_id, "failed"),
    }


def format_result_message(mission_run: MissionRun) -> str:
    if mission_run.success:
        return "Missão concluída com sucesso. Recompensas registradas no histórico."
    return "Missão concluída, mas o grupo falhou. Consulte os detalhes no histórico."
