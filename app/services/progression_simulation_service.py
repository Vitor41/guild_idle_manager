from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import ceil
from random import Random
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.building import BuildingTemplate
from app.models.crafting import CraftingRecipeMaterial
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.models.tavern import TavernConfig
from app.seeds.massive_content import PACK_KEY


SIMULATION_RUNS = 1000
PROGRESSION_BANDS = (
    ("1-20", 1, 20, ("1-20",), 1.20),
    ("21-50", 21, 50, ("21-50",), 1.20),
    ("51-100", 51, 100, ("51-100",), 1.15),
    ("101-130", 101, 130, ("101-130",), 1.15),
    ("131-200", 131, 200, ("131-200",), 1.10),
    ("201-350", 201, 350, ("201-250", "251-300", "301-350"), 1.10),
)


@dataclass
class BandSimulation:
    band: str
    level_start: int
    level_end: int
    xp_required: int
    mission_count: int
    gathering_count: int
    dungeon_count: int
    average_xp: float
    average_gold: float
    average_duration_seconds: float
    average_success_chance: float
    expected_attempts: float
    expected_time_hours: float
    expected_gold: float
    gold_per_hour: float
    p50_attempts: int
    p75_attempts: int
    p90_attempts: int
    p95_attempts: int
    p50_time_hours: float
    p90_time_hours: float
    p95_time_hours: float
    p50_gold: int
    p90_gold: int
    recommended_mission_count: int
    recommended_dungeon_count: int
    content_coverage_ok: bool


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, ceil(percentile * len(ordered)) - 1))
    return ordered[position]


def _xp_required(level_start: int, level_end: int) -> int:
    return sum(level * 100 for level in range(level_start, level_end))


def _scenario_chance(base_chance: float, level_end: int) -> float:
    # Representa uma equipe comum adequada, mas não perfeita. O déficit cresce no endgame.
    endgame_penalty = 0 if level_end <= 50 else 5 if level_end <= 100 else 9 if level_end <= 130 else 14 if level_end <= 200 else 20
    return max(0.20, min(0.95, (base_chance - endgame_penalty + 5) / 100))


def _simulate_band(
    band_label: str,
    level_start: int,
    level_end: int,
    missions: list[MissionTemplate],
    gathering_count: int,
    dungeon_count: int,
    diversity_factor: float,
) -> BandSimulation:
    xp_required = _xp_required(level_start, level_end)
    average_xp = mean(mission.base_xp_reward for mission in missions)
    average_gold = mean(mission.base_gold_reward for mission in missions)
    average_duration = mean(mission.duration_seconds for mission in missions)
    base_chance = mean(mission.base_success_chance for mission in missions)
    chance = _scenario_chance(base_chance, level_end)
    expected_xp = average_xp * (chance + (1 - chance) * 0.25)
    expected_attempts = xp_required / max(1, expected_xp)
    expected_time_hours = expected_attempts * average_duration / 3600
    expected_gold = expected_attempts * average_gold * chance
    gold_per_hour = expected_gold / max(0.01, expected_time_hours)

    rng = Random(35000 + level_start)
    attempts_samples: list[int] = []
    time_samples: list[float] = []
    gold_samples: list[int] = []
    for _ in range(SIMULATION_RUNS):
        xp = 0
        attempts = 0
        gold = 0
        elapsed = 0.0
        while xp < xp_required and attempts < 100_000:
            mission = missions[rng.randrange(len(missions))]
            success = rng.random() <= _scenario_chance(mission.base_success_chance, level_end)
            xp += mission.base_xp_reward if success else max(1, mission.base_xp_reward // 4)
            gold += mission.base_gold_reward if success else 0
            elapsed += mission.duration_seconds
            attempts += 1
        attempts_samples.append(attempts)
        time_samples.append(elapsed / 3600)
        gold_samples.append(gold)

    p90_attempts = int(_percentile(attempts_samples, 0.90))
    recommended_missions = max(20, ceil(p90_attempts * diversity_factor))
    recommended_dungeons = max(5, ceil(recommended_missions * (0.16 if level_end <= 50 else 0.20)))
    return BandSimulation(
        band=band_label,
        level_start=level_start,
        level_end=level_end,
        xp_required=xp_required,
        mission_count=len(missions),
        gathering_count=gathering_count,
        dungeon_count=dungeon_count,
        average_xp=round(average_xp, 2),
        average_gold=round(average_gold, 2),
        average_duration_seconds=round(average_duration, 2),
        average_success_chance=round(chance * 100, 2),
        expected_attempts=round(expected_attempts, 2),
        expected_time_hours=round(expected_time_hours, 2),
        expected_gold=round(expected_gold, 2),
        gold_per_hour=round(gold_per_hour, 2),
        p50_attempts=int(_percentile(attempts_samples, 0.50)),
        p75_attempts=int(_percentile(attempts_samples, 0.75)),
        p90_attempts=p90_attempts,
        p95_attempts=int(_percentile(attempts_samples, 0.95)),
        p50_time_hours=round(_percentile(time_samples, 0.50), 2),
        p90_time_hours=round(_percentile(time_samples, 0.90), 2),
        p95_time_hours=round(_percentile(time_samples, 0.95), 2),
        p50_gold=int(_percentile(gold_samples, 0.50)),
        p90_gold=int(_percentile(gold_samples, 0.90)),
        recommended_mission_count=recommended_missions,
        recommended_dungeon_count=recommended_dungeons,
        content_coverage_ok=len(missions) >= recommended_missions and dungeon_count >= recommended_dungeons,
    )


def simulate_progression(db: Session) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for label, level_start, level_end, db_bands, diversity in PROGRESSION_BANDS:
        missions = list(db.scalars(select(MissionTemplate).where(
            MissionTemplate.content_pack == PACK_KEY,
            MissionTemplate.level_band.in_(db_bands),
            MissionTemplate.mission_type != "gathering",
            MissionTemplate.is_active.is_(True),
        )))
        gathering_count = len(list(db.scalars(select(MissionTemplate.id).where(
            MissionTemplate.content_pack == PACK_KEY,
            MissionTemplate.level_band.in_(db_bands),
            MissionTemplate.mission_type == "gathering",
            MissionTemplate.is_active.is_(True),
        ))))
        dungeon_count = len(list(db.scalars(select(DungeonTemplate.id).where(
            DungeonTemplate.content_pack == PACK_KEY,
            DungeonTemplate.level_band.in_(db_bands),
            DungeonTemplate.content_type == "dungeon",
            DungeonTemplate.is_active.is_(True),
        ))))
        if missions:
            results.append(asdict(_simulate_band(
                label, level_start, level_end, missions, gathering_count, dungeon_count, diversity,
            )))
    return results


def build_material_economy(db: Session) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    families = sorted(set(db.scalars(select(ItemTemplate.material_family).where(
        ItemTemplate.content_pack == PACK_KEY,
        ItemTemplate.material_family.is_not(None),
    ))))
    for family in families:
        drops = list(db.scalars(select(MissionTemplateItemDrop).join(ItemTemplate).where(
            ItemTemplate.content_pack == PACK_KEY,
            ItemTemplate.material_family == family,
            MissionTemplateItemDrop.is_active.is_(True),
        )))
        expected_quantity = sum(
            drop.drop_chance / 100 * (drop.min_quantity + drop.max_quantity) / 2 for drop in drops
        )
        rows.append({
            "family": family,
            "mission_sources": len(drops),
            "expected_quantity_per_full_rotation": round(expected_quantity, 2),
            "has_demand": (
                bool(db.scalar(select(CraftingRecipeMaterial.id).join(ItemTemplate).where(ItemTemplate.material_family == family).limit(1)))
                or family in {"wood", "ore", "gem"}
                or bool(db.scalar(select(ItemTemplate.id).where(ItemTemplate.material_family == family, ItemTemplate.base_sell_value > 0).limit(1)))
            ),
        })
    return rows


def build_gold_economy(db: Session, progression: list[dict[str, object]]) -> dict[str, object]:
    dungeon_sources = []
    for label, _, _, db_bands, _ in PROGRESSION_BANDS:
        dungeons = list(db.scalars(select(DungeonTemplate).where(
            DungeonTemplate.content_pack == PACK_KEY,
            DungeonTemplate.level_band.in_(db_bands),
            DungeonTemplate.content_type == "dungeon",
        )))
        dungeon_sources.append({
            "band": label,
            "gold_per_hour": round(mean(d.base_gold_reward / max(1, d.duration_seconds) * 3600 * d.base_success_chance / 100 for d in dungeons), 2) if dungeons else 0,
            "risk": "alto",
            "requirement": "grupo, poder e equipamento",
        })
    buildings = list(db.scalars(select(BuildingTemplate).where(BuildingTemplate.is_active.is_(True))))
    tavern = db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))
    return {
        "sources": {
            "missions": [{"band": row["band"], "gold_per_hour": row["gold_per_hour"], "risk": "médio"} for row in progression],
            "dungeons": dungeon_sources,
            "offline_gold_per_hour": 5,
            "market": "valor complementar limitado por slots e tempo",
        },
        "drains": {
            "tavern_initial_hire": tavern.base_apprentice_cost if tavern else 50,
            "tavern_refresh": 100,
            "building_base_costs": {building.effect_type: building.base_upgrade_gold_cost for building in buildings},
            "docks": "preço de compra superior ao valor de venda; alternativa para completar materiais",
            "crafting": "ouro e materiais por receita",
            "refinement": "custo crescente por nível e raridade",
        },
    }


def build_balance_report(db: Session) -> dict[str, object]:
    progression = simulate_progression(db)
    return {
        "simulation_runs_per_band": SIMULATION_RUNS,
        "progression": progression,
        "materials": build_material_economy(db),
        "gold_economy": build_gold_economy(db, progression),
    }
