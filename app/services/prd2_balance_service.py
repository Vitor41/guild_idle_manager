import json
from collections import defaultdict
from math import ceil, floor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentSeedRun
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.seeds.massive_content import PACK_KEY
from app.services.mission_service import LONG_IDLE_CONFIGS


PRD2_PACK_KEY = "melhorias_prd_2"
PRD2_VERSION = 1

MISSION_EQUIPMENT_DROP_CHANCE = {
    "common": 40, "uncommon": 25, "rare": 12,
    "epic": 5, "legendary": 1, "mythic": 1,
}
GATHERING_EQUIPMENT_DROP_CHANCE = {
    "common": 20, "uncommon": 10, "rare": 4,
    "epic": 1, "legendary": 1, "mythic": 1,
}
DUNGEON_EQUIPMENT_DROP_CHANCE = {
    "common": 45, "uncommon": 35, "rare": 22,
    "epic": 10, "legendary": 3, "mythic": 1,
}
BOSS_EQUIPMENT_DROP_CHANCE = {
    "common": 50, "uncommon": 45, "rare": 35,
    "epic": 20, "legendary": 8, "mythic": 3,
}


def equipment_drop_chance(content_type: str, rarity: str) -> int:
    tables = {
        "gathering": GATHERING_EQUIPMENT_DROP_CHANCE,
        "mission": MISSION_EQUIPMENT_DROP_CHANCE,
        "dungeon": DUNGEON_EQUIPMENT_DROP_CHANCE,
        "boss": BOSS_EQUIPMENT_DROP_CHANCE,
    }
    return tables.get(content_type, MISSION_EQUIPMENT_DROP_CHANCE).get(rarity, 1)


def gathering_xp_for_level(level: int) -> int:
    level = max(1, min(20, level))
    if level <= 9:
        return round(65 + (level - 1) * 2.5)
    return 95 + (level - 10) * 10


def gathering_gold_for_level(level: int) -> int:
    return 12 + max(0, min(20, level) - 1) * 2


def _deactivate_duplicate_gathering(missions: list[MissionTemplate]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int, str], list[MissionTemplate]] = defaultdict(list)
    for mission in missions:
        if mission.mission_type == "gathering" and mission.gathering_family:
            grouped[(mission.level_band, mission.required_min_mercenary_level, mission.gathering_family)].append(mission)

    removed: list[dict[str, object]] = []
    for (band, level, family), candidates in grouped.items():
        if len(candidates) <= 1:
            continue
        candidates.sort(key=lambda mission: (
            -int(any(
                drop.is_active and drop.item_template.item_type == "equipment"
                for drop in mission.item_drops
            )),
            mission.id,
        ))
        keeper = candidates[0]
        for duplicate in candidates[1:]:
            duplicate.is_active = False
            removed.append({
                "id": duplicate.id, "name": duplicate.name, "band": band,
                "level": level, "family": family, "kept_id": keeper.id,
            })
    return removed


def _rebalance_early_game(missions: list[MissionTemplate]) -> dict[str, int]:
    early_gathering = [
        mission for mission in missions
        if mission.is_active and mission.level_band == "1-20" and mission.mission_type == "gathering"
    ]
    for mission in early_gathering:
        mission.base_xp_reward = gathering_xp_for_level(mission.required_min_mercenary_level)
        mission.base_gold_reward = gathering_gold_for_level(mission.required_min_mercenary_level)

    gathering_by_level: dict[int, list[MissionTemplate]] = defaultdict(list)
    for mission in early_gathering:
        gathering_by_level[mission.required_min_mercenary_level].append(mission)

    normal_adjusted = 0
    normal_reviewed = 0
    for mission in missions:
        if (
            not mission.is_active or mission.level_band != "1-20"
            or mission.mission_type in {"gathering", "long_idle"}
        ):
            continue
        normal_reviewed += 1
        available_levels = [level for level in gathering_by_level if level <= mission.required_min_mercenary_level]
        reference_level = max(available_levels, default=min(gathering_by_level, default=1))
        references = gathering_by_level.get(reference_level, [])
        if not references:
            continue
        gathering_xp_per_hour = max(
            reference.base_xp_reward * 3600 / max(1, reference.duration_seconds)
            for reference in references
        )
        gathering_gold_per_hour = max(
            reference.base_gold_reward * 3600 / max(1, reference.duration_seconds)
            for reference in references
        )
        is_elite = mission.mission_type == "elite" or mission.difficulty in {"heroic", "legendary", "elite"}
        xp_factor = 1.40 if is_elite else 1.30
        gold_factor = 1.50 if is_elite else 1.40
        target_xp = ceil(gathering_xp_per_hour * xp_factor * mission.duration_seconds / 3600)
        target_gold = ceil(gathering_gold_per_hour * gold_factor * mission.duration_seconds / 3600)
        before = (mission.base_xp_reward, mission.base_gold_reward)
        mission.base_xp_reward = target_xp
        mission.base_gold_reward = target_gold
        normal_adjusted += int(before != (mission.base_xp_reward, mission.base_gold_reward))
    return {
        "gathering_adjusted": len(early_gathering),
        "normal_reviewed": normal_reviewed,
        "normal_adjusted": normal_adjusted,
    }


def _rebalance_equipment_drops(db: Session) -> dict[str, int]:
    mission_count = 0
    for drop in db.scalars(
        select(MissionTemplateItemDrop)
        .join(MissionTemplate)
        .join(ItemTemplate, ItemTemplate.id == MissionTemplateItemDrop.item_template_id)
        .where(ItemTemplate.item_type == "equipment")
    ):
        if drop.mission_template.mission_type == "long_idle":
            drop.is_active = False
            continue
        content_type = "gathering" if drop.mission_template.mission_type == "gathering" else "mission"
        drop.drop_chance = equipment_drop_chance(content_type, drop.item_template.rarity)
        mission_count += 1

    dungeon_count = 0
    for drop in db.scalars(
        select(DungeonTemplateItemDrop)
        .join(DungeonTemplate)
        .join(ItemTemplate, ItemTemplate.id == DungeonTemplateItemDrop.item_template_id)
        .where(ItemTemplate.item_type == "equipment")
    ):
        content_type = "boss" if drop.dungeon_template.content_type == "boss" else "dungeon"
        drop.drop_chance = equipment_drop_chance(content_type, drop.item_template.rarity)
        dungeon_count += 1
    return {"mission_equipment_drops": mission_count, "dungeon_equipment_drops": dungeon_count}


def _ensure_early_common_equipment_utility(db: Session) -> int:
    adjusted = 0
    items = db.scalars(select(ItemTemplate).where(
        ItemTemplate.item_type == "equipment",
        ItemTemplate.tier == 1,
        ItemTemplate.rarity == "common",
    ))
    for item in items:
        base_total = sum(getattr(item, field) for field in (
            "bonus_power", "bonus_vitality", "bonus_agility",
            "bonus_intelligence", "bonus_luck", "bonus_armor",
        ))
        if base_total <= 0:
            item.bonus_power = 1
            adjusted += 1
        if item.rng_bonus_min < 1:
            item.rng_bonus_min = 1
            adjusted += 1
        if item.rng_bonus_max < item.rng_bonus_min:
            item.rng_bonus_max = item.rng_bonus_min
    return adjusted


def _rebalance_long_idle_rewards(db: Session) -> int:
    rules = {hours: chance for hours, chance, _ in LONG_IDLE_CONFIGS}
    adjusted = 0
    long_missions = list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.mission_type == "long_idle",
        MissionTemplate.is_active.is_(True),
    )))
    for mission in long_missions:
        active_missions = list(db.scalars(select(MissionTemplate).where(
            MissionTemplate.level_band == mission.level_band,
            MissionTemplate.is_active.is_(True),
            ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
        )))
        max_gold_per_hour = max((
            template.base_gold_reward * 3600 / max(1, template.duration_seconds)
            for template in active_missions
        ), default=1)
        max_xp_per_hour = max((
            template.base_xp_reward * 3600 / max(1, template.duration_seconds)
            for template in active_missions
        ), default=1)
        duration_hours = mission.duration_seconds // 3600
        mission.base_gold_reward = max(1, floor(max_gold_per_hour * 0.5 * duration_hours))
        mission.base_xp_reward = max(1, floor(max_xp_per_hour * 0.5 * duration_hours))
        mission.base_success_chance = rules.get(duration_hours, mission.base_success_chance)
        mission.min_party_size = 1
        mission.max_party_size = 5
        adjusted += 1
    return adjusted


def apply_prd2_balance(db: Session, force: bool = False) -> dict[str, object]:
    marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == PRD2_PACK_KEY,
        ContentSeedRun.version == PRD2_VERSION,
    ))
    if marker is not None and not force:
        return json.loads(marker.report_json)

    generated_missions = list(db.scalars(
        select(MissionTemplate)
        .where(MissionTemplate.content_pack == PACK_KEY)
        .order_by(MissionTemplate.level_band, MissionTemplate.required_min_mercenary_level, MissionTemplate.id)
    ))
    previous_report = json.loads(marker.report_json) if marker is not None else {}
    removed = _deactivate_duplicate_gathering(generated_missions)
    if not removed:
        removed = previous_report.get("duplicates_deactivated", [])
    all_missions = list(db.scalars(select(MissionTemplate).order_by(MissionTemplate.id)))
    early_report = _rebalance_early_game(all_missions)
    early_report["gathering_adjusted"] = max(
        early_report["gathering_adjusted"], previous_report.get("gathering_adjusted", 0)
    )
    early_report["normal_adjusted"] = max(
        early_report["normal_adjusted"], previous_report.get("normal_adjusted", 0)
    )
    drop_report = _rebalance_equipment_drops(db)
    utility_adjusted = _ensure_early_common_equipment_utility(db)
    long_idle_adjusted = _rebalance_long_idle_rewards(db)
    report = {
        "duplicates_deactivated": removed,
        **early_report,
        **drop_report,
        "early_common_equipment_adjusted": utility_adjusted,
        "long_idle_adjusted": long_idle_adjusted,
    }
    if marker is None:
        db.add(ContentSeedRun(
            pack_key=PRD2_PACK_KEY,
            version=PRD2_VERSION,
            report_json=json.dumps(report, ensure_ascii=False),
        ))
    else:
        marker.report_json = json.dumps(report, ensure_ascii=False)
        db.add(marker)
    db.commit()
    return report
