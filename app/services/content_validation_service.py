import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.content import ProfessionTemplate
from app.models.dock import MerchantOfferTemplate, MerchantTemplate
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.seeds.massive_content import BANDS, PACK_KEY
from app.services.balance_service import CLASS_PRIMARY_ATTRIBUTES
from app.services.progression_simulation_service import build_balance_report
from app.models.mercenary import MercenaryClass
from app.models.skill import SkillTemplate


VALID_RARITIES = {"common", "uncommon", "rare", "epic", "legendary", "mythic"}
SEQUENTIAL_NAME_PATTERN = re.compile(r"(?:\s\d+-\d{2,4}|[-_]\d{3,4})$", re.IGNORECASE)


def _count(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def build_content_report(db: Session) -> dict[str, object]:
    materials = _count(db, select(func.count(ItemTemplate.id)).where(ItemTemplate.content_pack == PACK_KEY, ItemTemplate.item_type == "material"))
    equipment = _count(db, select(func.count(ItemTemplate.id)).where(ItemTemplate.content_pack == PACK_KEY, ItemTemplate.item_type == "equipment"))
    missions = _count(db, select(func.count(MissionTemplate.id)).where(MissionTemplate.content_pack == PACK_KEY, MissionTemplate.mission_type != "gathering"))
    gathering = _count(db, select(func.count(MissionTemplate.id)).where(MissionTemplate.content_pack == PACK_KEY, MissionTemplate.mission_type == "gathering"))
    dungeons = _count(db, select(func.count(DungeonTemplate.id)).where(DungeonTemplate.content_pack == PACK_KEY, DungeonTemplate.content_type == "dungeon"))
    bosses = _count(db, select(func.count(DungeonTemplate.id)).where(DungeonTemplate.content_pack == PACK_KEY, DungeonTemplate.content_type == "boss"))
    professions = _count(db, select(func.count(ProfessionTemplate.id)))
    merchants = _count(db, select(func.count(MerchantTemplate.id)).where(MerchantTemplate.content_pack == PACK_KEY))
    dock_offers = _count(db, select(func.count(MerchantOfferTemplate.id)).join(MerchantTemplate).where(MerchantTemplate.content_pack == PACK_KEY))

    by_band = []
    for band, *_ in BANDS:
        by_band.append({
            "band": band,
            "missions": _count(db, select(func.count(MissionTemplate.id)).where(MissionTemplate.content_pack == PACK_KEY, MissionTemplate.level_band == band, MissionTemplate.mission_type != "gathering")),
            "gathering": _count(db, select(func.count(MissionTemplate.id)).where(MissionTemplate.content_pack == PACK_KEY, MissionTemplate.level_band == band, MissionTemplate.mission_type == "gathering")),
            "dungeons": _count(db, select(func.count(DungeonTemplate.id)).where(DungeonTemplate.content_pack == PACK_KEY, DungeonTemplate.level_band == band, DungeonTemplate.content_type == "dungeon")),
            "bosses": _count(db, select(func.count(DungeonTemplate.id)).where(DungeonTemplate.content_pack == PACK_KEY, DungeonTemplate.level_band == band, DungeonTemplate.content_type == "boss")),
            "equipment": _count(db, select(func.count(ItemTemplate.id)).where(ItemTemplate.content_pack == PACK_KEY, ItemTemplate.level_band == band, ItemTemplate.item_type == "equipment")),
        })

    item_has_mission_source = select(MissionTemplateItemDrop.id).where(MissionTemplateItemDrop.item_template_id == ItemTemplate.id).exists()
    item_has_dungeon_source = select(DungeonTemplateItemDrop.id).where(DungeonTemplateItemDrop.item_template_id == ItemTemplate.id).exists()
    item_has_dock_source = select(MerchantOfferTemplate.id).where(MerchantOfferTemplate.item_template_id == ItemTemplate.id).exists()
    checks = {
        "itens_sem_fonte": _count(db, select(func.count(ItemTemplate.id)).where(ItemTemplate.content_pack == PACK_KEY, ~item_has_mission_source, ~item_has_dungeon_source, ~item_has_dock_source)),
        "missoes_sem_drop": _count(db, select(func.count(MissionTemplate.id)).where(MissionTemplate.content_pack == PACK_KEY, ~select(MissionTemplateItemDrop.id).where(MissionTemplateItemDrop.mission_template_id == MissionTemplate.id).exists())),
        "dungeons_sem_drop": _count(db, select(func.count(DungeonTemplate.id)).where(DungeonTemplate.content_pack == PACK_KEY, ~select(DungeonTemplateItemDrop.id).where(DungeonTemplateItemDrop.dungeon_template_id == DungeonTemplate.id).exists())),
        "raridades_invalidas": _count(db, select(func.count(ItemTemplate.id)).where(ItemTemplate.content_pack == PACK_KEY, ~ItemTemplate.rarity.in_(VALID_RARITIES))),
        "equipamentos_sem_slot": _count(db, select(func.count(ItemTemplate.id)).where(ItemTemplate.content_pack == PACK_KEY, ItemTemplate.item_type == "equipment", ItemTemplate.equipment_slot.is_(None))),
        "textos_vazios": _count(db, select(func.count(ItemTemplate.id)).where(ItemTemplate.content_pack == PACK_KEY, or_(ItemTemplate.name == "", ItemTemplate.description == ""))),
        "ofertas_invalidas": _count(db, select(func.count(MerchantOfferTemplate.id)).where(or_(MerchantOfferTemplate.base_price <= 0, MerchantOfferTemplate.max_stock <= 0))),
    }
    minima = {"materials": materials >= 400, "equipment": equipment >= 1500, "missions": missions >= 1500,
        "gathering": gathering >= 500, "dungeons": dungeons >= 300, "bosses": bosses >= 80,
        "professions": professions >= 8, "merchants": merchants >= 80, "dock_offers": dock_offers >= 1000}
    coverage_ok = all(all(row[key] > 0 for key in ("missions", "gathering", "dungeons", "equipment")) for row in by_band)
    return {
        "totals": {"materials": materials, "equipment": equipment, "missions": missions, "gathering": gathering,
            "dungeons": dungeons, "bosses": bosses, "professions": professions, "merchants": merchants, "dock_offers": dock_offers},
        "by_band": by_band, "checks": checks, "minimums": minima,
        "passed": all(minima.values()) and coverage_ok and not any(checks.values()),
    }


def _normalized_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", normalized.lower())).strip()


def build_refinement_validation_report(db: Session) -> dict[str, object]:
    missions = list(db.scalars(select(MissionTemplate).where(MissionTemplate.content_pack == PACK_KEY)))
    dungeons = list(db.scalars(select(DungeonTemplate).where(DungeonTemplate.content_pack == PACK_KEY)))
    items = list(db.scalars(select(ItemTemplate).where(ItemTemplate.content_pack == PACK_KEY)))
    issues: list[dict[str, object]] = []

    for kind, entries in (("missão", missions), ("dungeon", dungeons)):
        names: dict[str, list[int]] = {}
        for entry in entries:
            if SEQUENTIAL_NAME_PATTERN.search(entry.name):
                issues.append({"code": "sequential_name", "kind": kind, "id": entry.id, "name": entry.name})
            names.setdefault(_normalized_name(entry.name), []).append(entry.id)
        for name, ids in names.items():
            if len(ids) > 1:
                issues.append({"code": "duplicate_name", "kind": kind, "name": name, "ids": ids[:10]})

    band_metrics = []
    previous_mission_xp = previous_mission_gold = previous_dungeon_xp = previous_dungeon_gold = 0.0
    for band, *_ in BANDS:
        band_missions = [mission for mission in missions if mission.level_band == band and mission.mission_type != "gathering"]
        band_dungeons = [dungeon for dungeon in dungeons if dungeon.level_band == band and dungeon.content_type == "dungeon"]
        mission_xp = sum(item.base_xp_reward for item in band_missions) / max(1, len(band_missions))
        mission_gold = sum(item.base_gold_reward for item in band_missions) / max(1, len(band_missions))
        dungeon_xp = sum(item.base_xp_reward for item in band_dungeons) / max(1, len(band_dungeons))
        dungeon_gold = sum(item.base_gold_reward for item in band_dungeons) / max(1, len(band_dungeons))
        if mission_xp < previous_mission_xp or mission_gold < previous_mission_gold:
            issues.append({"code": "mission_curve_regression", "band": band})
        if dungeon_xp < previous_dungeon_xp or dungeon_gold < previous_dungeon_gold:
            issues.append({"code": "dungeon_curve_regression", "band": band})
        previous_mission_xp, previous_mission_gold = mission_xp, mission_gold
        previous_dungeon_xp, previous_dungeon_gold = dungeon_xp, dungeon_gold
        band_metrics.append({
            "band": band, "missions": len(band_missions), "dungeons": len(band_dungeons),
            "mission_xp_average": round(mission_xp, 2), "mission_gold_average": round(mission_gold, 2),
            "dungeon_xp_average": round(dungeon_xp, 2), "dungeon_gold_average": round(dungeon_gold, 2),
        })

    early_forbidden = [item.id for item in items if item.level_band == "1-20" and item.rarity in {"epic", "legendary", "mythic"}]
    if early_forbidden:
        issues.append({"code": "early_high_rarity", "count": len(early_forbidden), "ids": early_forbidden[:10]})
    no_origin = [item.id for item in items if not (item.mission_drops or item.dungeon_drops) and item.base_sell_value <= 0]
    if no_origin:
        issues.append({"code": "items_without_origin_or_destination", "count": len(no_origin), "ids": no_origin[:10]})

    classes = list(db.scalars(select(MercenaryClass).where(MercenaryClass.is_active.is_(True))))
    skills_by_class = {
        class_id: count for class_id, count in db.execute(
            select(SkillTemplate.class_id, func.count(SkillTemplate.id)).where(SkillTemplate.is_active.is_(True)).group_by(SkillTemplate.class_id)
        )
    }
    for mercenary_class in classes:
        if not CLASS_PRIMARY_ATTRIBUTES.get(mercenary_class.code or ""):
            issues.append({"code": "class_without_attributes", "class": mercenary_class.code})
        if not skills_by_class.get(mercenary_class.id):
            issues.append({"code": "class_without_skill", "class": mercenary_class.code})
    if CLASS_PRIMARY_ATTRIBUTES.get("rogue")[:2] != ("agility", "intelligence"):
        issues.append({"code": "rogue_attribute_identity"})
    if CLASS_PRIMARY_ATTRIBUTES.get("rogue") == CLASS_PRIMARY_ATTRIBUTES.get("archer"):
        issues.append({"code": "rogue_archer_overlap"})

    balance_report = build_balance_report(db)
    uncovered = [row["band"] for row in balance_report["progression"] if not row["content_coverage_ok"]]
    if uncovered:
        issues.append({"code": "insufficient_content_coverage", "bands": uncovered})
    return {
        "passed": not issues,
        "issues": issues,
        "sequential_names": sum(1 for issue in issues if issue["code"] == "sequential_name"),
        "duplicate_names": sum(1 for issue in issues if issue["code"] == "duplicate_name"),
        "band_metrics": band_metrics,
        "balance": balance_report,
    }
