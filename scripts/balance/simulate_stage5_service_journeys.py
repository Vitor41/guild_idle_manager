"""Fresh-save Stage 5 journeys using the live economy and activity services.

Runs only in a disposable SQLite database. Mercenary and guild progression are
advanced only by runtime service rewards; checkpoints preserve daily evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, create_database_engine
from app.models import (CampaignMetadata, DungeonTemplate, Guild, GuildInventoryItem,
                        GuildResources, ItemTemplate, Mercenary, MercenaryClass,
                        MissionTemplate, TavernConfig)
from app.models.item import GuildItemInstance
from app.models.regional import RegionalCycle, RegionalEvent, RegionalEventParticipant, RegionalOffer
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_VERSION
from app.services import building_service as _building_service
from app.services import dungeon_service, market_service, mission_service, salvage_service, tavern_service
from app.services import crafting_service
from app.services.building_balance_service import housing_capacity, mission_office_values
from app.services.building_service import (ensure_guild_buildings, get_upgrade_cost,
                                           get_mercenary_limit, upgrade_guild_building)
from app.services.dungeon_service import DungeonError, claim_dungeon_loot, start_dungeon
from app.services.gathering_service import advance_assignment, assign_worker, release_worker
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.market_service import collect_market_sale, start_material_sale
from app.services.mission_service import MissionError, claim_mission_loot, start_mission
from app.services.offline_progress_service import get_passive_gold_rate
from app.services.salvage_service import collect_salvage, start_salvage
from app.services.skill_service import ensure_mercenary_skills
from app.services.tavern_service import hire_apprentice
from app.services.crafting_service import craft_recipe, list_rotating_recipes, _effective_recipe_gold_cost
from app.services.regional_cycle_service import REGIONS, get_current_player_regional_guild, get_regional_board
from app.services.regional_event_service import (
    active_portals_for_region, attach_event_activity, build_portal_boss_snapshot, expire_due_events,
)
from scripts.balance.funded_progression_simulation import (
    advance_offline_stamina, bootstrap_median_ci_95, wilson_interval_95,
)

_ORIGINAL_BUILDING_CAN_PAY = _building_service.can_pay

PROFILES = (
    {"name": "ativo", "online_hours": 12, "teams": 3, "party": 3, "roster": 9, "office": 10},
    {"name": "casual", "online_hours": 2, "teams": 2, "party": 2, "roster": 4, "office": 1},
    {"name": "offline", "online_hours": 8, "teams": 3, "party": 3, "roster": 9, "office": 10},
    {"name": "produtor", "online_hours": 8, "teams": 1, "party": 2, "roster": 5, "office": 1},
    {"name": "combate", "online_hours": 8, "teams": 3, "party": 3, "roster": 9, "office": 10, "mode": "contract_priority"},
)
PATHS = ("roster_first", "commerce_early")
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
MATERIALS = ("wood", "ore", "leather", "crystals")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _ci_median(values: list[float], seed: int) -> dict[str, object]:
    return bootstrap_median_ci_95(values, seed=seed, resamples=1500)


def _write_json_atomic(path: Path, data: dict[str, object]) -> None:
    """Persist a recoverable checkpoint without exposing a partial JSON file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))


def _marketable_surplus(total_quantity: int, protected_reserve: int) -> int:
    return max(0, int(total_quantity) - max(0, int(protected_reserve)))


def _ensure_fresh_campaign(db: Session, profile: dict[str, object], path: str, seed: int):
    campaign_id = str(uuid5(NAMESPACE_URL, f"stage5-service:{profile['name']}:{path}:{seed}"))
    campaign = CampaignMetadata(
        campaign_id=campaign_id, campaign_name=f"Stage5 {profile['name']} {path}",
        created_at_utc=EPOCH, updated_at_utc=EPOCH, schema_version=5,
        content_version=PACK_VERSION, home_region=REGIONS[0][1], stamina_seconds=8 * 3600,
    )
    guild = Guild(campaign_id=campaign_id, name=f"{profile['name']} {seed}", level=1)
    resources = GuildResources(guild=guild, gold=100, wood=0, ore=0, crystals=0)
    db.add_all((campaign, guild, resources))
    db.flush()
    buildings = {row.building_template.effect_type: row for row in ensure_guild_buildings(db, guild.id)}
    db.commit()
    return campaign, guild, resources, buildings


def _inventory_family(db: Session, guild_id: int, family: str) -> int:
    return int(db.scalar(
        select(func.coalesce(func.sum(GuildInventoryItem.quantity), 0)).join(ItemTemplate).where(
            GuildInventoryItem.guild_id == guild_id,
            ItemTemplate.item_type == "material", ItemTemplate.material_family == family,
        )
    ) or 0)


def _has_equipment_instance(db: Session, guild_id: int) -> bool:
    from app.models.item import GuildItemInstance

    return db.scalar(select(GuildItemInstance.id).where(
        GuildItemInstance.guild_id == guild_id,
    ).limit(1)) is not None


def _is_activated_rebellion(event: RegionalEvent) -> bool:
    """Not-triggered and suppressed roll rows are not rebellion occurrences."""
    return bool(json.loads(event.summary_json or "{}").get("generated_while_campaign_open"))


def _next_targets(profile: dict[str, object], path: str, roster_count: int, buildings: dict[str, object]) -> tuple[str, ...]:
    min_roster = min(2, int(profile["roster"]))
    if path == "commerce_early" and roster_count >= min_roster:
        for effect in ("market", "blacksmith"):
            if buildings[effect].level < 1:
                return (effect,)
    if roster_count < int(profile["roster"]):
        if housing_capacity(buildings["housing"].level) <= roster_count:
            return ("housing",)
        return ("hire",)
    for effect, target in (("contract_office", int(profile["office"])),
                           ("training_ground", 1), ("scouts", 1)):
        if buildings[effect].level < target:
            return (effect,)
    for effect in (("market", "blacksmith") if path == "roster_first" else ("blacksmith", "market")):
        if buildings[effect].level < 1:
            return (effect,)
    return ()


def _purchase_requirements(db: Session, guild: Guild, resources: GuildResources,
                           buildings: dict[str, object], target: str, profile: dict[str, object]) -> dict[str, object]:
    if target == "hire":
        config = db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))
        state = tavern_service.get_or_create_tavern_state(db, guild.id, config)
        cost = tavern_service.get_discounted_hire_cost(
            state.current_apprentice_hire_cost,
            int(tavern_service.get_tavern_apprentice_chances(buildings["tavern"].level, config)["hire_discount_percent"]),
        )
        hire_number = int(db.scalar(select(func.count(Mercenary.id)).where(Mercenary.guild_id == guild.id)) or 0) + 1
        return {"item": f"apprentice_{hire_number}",
                "gold": cost, "materials": {}, "level": guild.level}
    b = buildings[target]
    quote = get_upgrade_cost(b)
    return {"item": f"{target}_{b.level + 1}", "gold": int(quote["gold"]),
            "materials": {m: int(quote[m]) for m in ("wood", "ore", "crystals")},
            "level": max(b.building_template.required_guild_level, b.level + 1)}


def _market_family_reserves(db: Session, guild: Guild, resources: GuildResources,
                            buildings: dict[str, object], profile: dict[str, object],
                            path: str, roster_count: int, base_reserve: int = 30) -> dict[str, int]:
    reserve = max(0, int(base_reserve))
    reserves = {"wood": reserve, "ore": reserve, "leather": reserve}
    target = _next_targets(profile, path, roster_count, buildings)
    if target and target[0] != "hire":
        required = _purchase_requirements(db, guild, resources, buildings, target[0], profile)["materials"]
        for family in ("wood", "ore"):
            reserves[family] += int(required.get(family, 0))
    return reserves


def _craft_one_affordable_surplus_equipment(
    db: Session, guild: Guild, resources: GuildResources, buildings: dict[str, object],
    reserves: dict[str, int], now: datetime,
) -> dict[str, object] | None:
    """Craft one equipment recipe only from materials above protected reserves."""
    if buildings["blacksmith"].level < 1 or get_inventory_usage(db, guild.id) >= get_inventory_capacity(db, guild):
        return None
    recipes, rotation = list_rotating_recipes(db, guild, int(buildings["blacksmith"].level), now=now)
    docks_level = int(buildings["docks"].level)
    candidates = []
    recipe_families = {
        str(component.item_template.material_family or "")
        for recipe in recipes for component in recipe.materials
    }
    family_totals = {family: _inventory_family(db, guild.id, family) for family in recipe_families}
    for recipe in recipes:
        if recipe.output_item_template.item_type != "equipment" or int(recipe.output_quantity) > (
            get_inventory_capacity(db, guild) - get_inventory_usage(db, guild.id)
        ):
            continue
        material_cost: dict[str, int] = {}
        requirements = []
        for component in recipe.materials:
            family = str(component.item_template.material_family or "")
            amount = int(component.quantity)
            material_cost[family] = material_cost.get(family, 0) + amount
            requirements.append((component.item_template, amount))
        if any(family_totals.get(family, 0) - amount < int(reserves.get(family, 0))
               for family, amount in material_cost.items()):
            continue
        if any((db.scalar(select(GuildInventoryItem.quantity).where(
                GuildInventoryItem.guild_id == guild.id,
                GuildInventoryItem.item_template_id == item.id,
            )) or 0) < amount for item, amount in requirements):
            continue
        gold_cost = _effective_recipe_gold_cost(db, recipe, docks_level)
        if int(resources.gold) - gold_cost < 75:
            continue
        candidates.append((gold_cost, int(recipe.output_item_template.base_sell_value), recipe, requirements))
    if not candidates:
        return None
    gold_cost, _sale_value, recipe, requirements = min(candidates, key=lambda row: (row[0], row[1], row[2].id))
    before_ids = set(db.scalars(select(GuildItemInstance.id).where(
        GuildItemInstance.guild_id == guild.id,
    )))
    # The simulated campaign clock determines which actual recipe rotation is open.
    with patch.object(crafting_service, "list_rotating_recipes", return_value=(recipes, rotation)):
        craft_recipe(db, guild, resources, str(recipe.id))
    created = list(db.scalars(select(GuildItemInstance).where(
        GuildItemInstance.guild_id == guild.id,
        GuildItemInstance.id.not_in(before_ids) if before_ids else True,
    )))
    output_ids = [int(item.id) for item in created]
    return {
        "type": "craft", "day": (now - EPOCH).days, "recipe_id": int(recipe.id),
        "output_item_template_id": int(recipe.output_item_template.id),
        "output_name": recipe.output_item_template.name, "output_quantity": len(created),
        "created_instance_ids": output_ids, "gold_cost": int(gold_cost),
        "materials": [{"item_template_id": int(item.id), "family": item.material_family,
                        "quantity": int(amount)} for item, amount in requirements],
        "kept_for_equipment_choice": True,
    }


def _block_snapshot(req: dict[str, object], guild: Guild, resources: GuildResources,
                    db: Session, buildings: dict[str, object]) -> dict[str, object]:
    from app.repositories.item_repository import sync_inventory_resource_totals
    sync_inventory_resource_totals(db, resources)
    material_balances = {family: int(getattr(resources, family)) for family in ("wood", "ore", "crystals")}
    materials = req["materials"]
    return {"item": req["item"], "gold_shortfall": max(0, int(req["gold"]) - int(resources.gold)),
            "material_shortfalls": {m: max(0, int(materials.get(m, 0)) - material_balances[m]) for m in material_balances},
            "guild_level_shortfall": max(0, int(req["level"]) - int(guild.level)),
            "inventory_used": get_inventory_usage(db, guild.id), "inventory_capacity": get_inventory_capacity(db, guild)}


def _horizon_blocked_targets(remaining_targets: tuple[str, ...],
                             snapshot: dict[str, object] | None) -> dict[str, dict[str, object]]:
    if not remaining_targets or snapshot is None:
        return {}
    is_blocked = bool(snapshot["gold_shortfall"] or snapshot["guild_level_shortfall"]
                      or any(snapshot["material_shortfalls"].values()))
    return {str(snapshot["item"]): snapshot} if is_blocked else {}


def _buy_if_possible(db: Session, guild: Guild, resources: GuildResources,
                     buildings: dict[str, object], target: str, profile: dict[str, object], seed_rng: random.Random,
                     day: int, purchases: list[dict[str, object]],
                     service_rejections: list[dict[str, object]] | None = None,
                     attempt: str = "unspecified") -> tuple[bool, dict[str, object]]:
    requested_target = target
    req = _purchase_requirements(db, guild, resources, buildings, target, profile)
    blocked = _block_snapshot(req, guild, resources, db, buildings)
    if blocked["gold_shortfall"] or blocked["guild_level_shortfall"] or any(blocked["material_shortfalls"].values()):
        return False, blocked
    gold_before = int(resources.gold)
    redirected_from_hire = False
    if target == "hire":
        config = db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))
        if buildings["tavern"].level < 1:
            target = "tavern"
            redirected_from_hire = True
        elif get_mercenary_limit(db, guild.id) <= int(db.scalar(select(func.count(Mercenary.id)).where(Mercenary.guild_id == guild.id)) or 0):
            target = "housing"
            redirected_from_hire = True
        else:
            state = tavern_service.get_or_create_tavern_state(db, guild.id, config)
            preview = tavern_service.generate_apprentice_preview(config, buildings["tavern"].level)
            hire_apprentice(db, guild, resources, f"{profile['name']}-{len(purchases)+1}", preview=preview)
            newest = db.scalar(select(Mercenary).where(Mercenary.guild_id == guild.id)
                               .order_by(Mercenary.id.desc()).limit(1))
            if newest is not None:
                # This service lazily seeds skills with db.commit(); do it at
                # the hire boundary, before a board action opens a savepoint.
                ensure_mercenary_skills(db, newest)
            purchases.append({"day": day, "item": req["item"], "gold": gold_before - int(resources.gold), "gold_after": int(resources.gold)})
            return True, blocked
    if redirected_from_hire:
        # The initial quote belongs to the hire. Requote and recheck after the
        # target changes to a building so the service never receives a stale budget.
        req = _purchase_requirements(db, guild, resources, buildings, target, profile)
        blocked = _block_snapshot(req, guild, resources, db, buildings)
        has_shortfall = bool(blocked["gold_shortfall"] or blocked["guild_level_shortfall"]
                             or any(blocked["material_shortfalls"].values()))
        if has_shortfall and service_rejections is not None:
            available_materials = {family: int(getattr(resources, family))
                                   for family in ("wood", "ore", "crystals")}
            service_rejections.append({
                "day": day,
                "service": "building_upgrade_precheck",
                "attempt": "redirected_target_precheck",
                "requested_target": requested_target,
                "target": target,
                "target_item": req["item"],
                "building_level": int(buildings[target].level),
                "next_level": int(buildings[target].level) + 1,
                "guild_level": int(guild.level),
                "service_called": False,
                "reason": "Orçamento atualizado insuficiente após redirecionamento da contratação.",
                "precheck": {
                    "available_gold": int(resources.gold),
                    "required_gold": int(req["gold"]),
                    "available_materials": available_materials,
                    "required_materials": {family: int(amount) for family, amount in req["materials"].items()},
                    "gold_shortfall": int(blocked["gold_shortfall"]),
                    "material_shortfalls": {family: int(amount)
                                            for family, amount in blocked["material_shortfalls"].items()},
                    "guild_level_shortfall": int(blocked["guild_level_shortfall"]),
                },
            })
        if has_shortfall:
            return False, blocked
    if target in {"tavern", "housing"}:
        b = buildings[target]
    else:
        b = buildings[target]
    precheck_materials = {family: int(resources_value) for family, resources_value in
                          ((family, getattr(resources, family)) for family in ("wood", "ore", "crystals"))}
    rejection_context: dict[str, object] = {
        "attempt": attempt,
        "target": target,
        "target_item": req["item"],
        "building_level": int(b.level),
        "next_level": int(b.level) + 1,
        "guild_level": int(guild.level),
        "precheck": {
            "available_gold": int(resources.gold),
            "required_gold": int(req["gold"]),
            "available_materials": precheck_materials,
            "required_materials": {family: int(amount) for family, amount in req["materials"].items()},
            "gold_shortfall": int(blocked["gold_shortfall"]),
            "material_shortfalls": {family: int(amount) for family, amount in blocked["material_shortfalls"].items()},
            "guild_level_shortfall": int(blocked["guild_level_shortfall"]),
        },
    }
    actual_can_pay: dict[str, object] = {}

    def capture_actual_can_pay(actual_resources: GuildResources, cost: dict[str, int]) -> bool:
        actual_can_pay.update({
            "available_gold": int(actual_resources.gold),
            "available_materials": {family: int(getattr(actual_resources, family))
                                    for family in ("wood", "ore", "crystals")},
            "required": {str(key): int(value) for key, value in cost.items()},
        })
        return _ORIGINAL_BUILDING_CAN_PAY(actual_resources, cost)

    try:
        with db.begin_nested():
            # Capture the live service inputs after its inventory synchronization.
            with patch.object(_building_service, "can_pay", side_effect=capture_actual_can_pay):
                updated = upgrade_guild_building(db, guild, resources, b.id, commit=False)
    except Exception as exc:
        if service_rejections is not None:
            rejection_context.update({"day": day, "service": "building_upgrade",
                                 "requested_target": requested_target,
                                     "reason": str(exc),
                                     "actual_can_pay": actual_can_pay or None})
            service_rejections.append(rejection_context)
        return False, blocked
    buildings[target] = updated
    purchases.append({"day": day, "item": f"{target}_{updated.level}", "gold": gold_before - int(resources.gold),
                      "gold_after": int(resources.gold)})
    return True, blocked


def _eligible_missions(db: Session, guild: Guild, buildings: dict[str, object], party_size: int,
                       mercenary_level: int | None = None) -> list[MissionTemplate]:
    from app.services.building_service import get_building_level, get_max_allowed_mission_party_size
    if party_size > get_max_allowed_mission_party_size(db, guild.id):
        return []
    minimum_level = int(guild.level if mercenary_level is None else mercenary_level)
    rows = list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.is_active.is_(True), MissionTemplate.mission_type != "long_idle",
        MissionTemplate.required_guild_level <= guild.level,
        MissionTemplate.required_min_mercenary_level <= minimum_level,
        MissionTemplate.min_party_size <= party_size, MissionTemplate.max_party_size >= party_size,
    ).order_by(MissionTemplate.id)))
    return [row for row in rows if not row.required_building_type
            or buildings.get(row.required_building_type) is not None
            and buildings[row.required_building_type].level >= row.required_building_level]


def _mission_score(t: MissionTemplate, mode: str) -> tuple[float, float, int]:
    expected_xp = t.base_xp_reward * (t.base_success_chance + (100 - t.base_success_chance) * 0.25) / 100
    expected_gold = t.base_gold_reward * t.base_success_chance / 100
    score = (expected_gold if mode == "contract_priority" else expected_xp) / max(1, t.duration_seconds)
    return score, expected_gold / max(1, t.duration_seconds), -t.id


def _run_mission(db: Session, guild: Guild, resources: GuildResources,
                 party: list[Mercenary], template: MissionTemplate, at: datetime,
                 rng: random.Random) -> dict[str, object]:
    run_clock = iter((at, at + timedelta(seconds=max(1, int(template.duration_seconds)) + 1)))
    overflows = []
    original_add = mission_service.add_inventory_quantity_capped
    def capture_add(*args, **kwargs):
        result = original_add(*args, **kwargs)
        overflows.append(int(result[1]))
        return result
    with patch.object(mission_service, "utc_now", side_effect=lambda: next(run_clock)), \
            patch.object(mission_service, "randint", side_effect=lambda low, high: rng.randint(low, high)), \
            patch.object(mission_service, "add_inventory_quantity_capped", side_effect=capture_add):
        run = start_mission(db, guild, str(template.id), [str(m.id) for m in party], commit=False)
        db.flush()
        claim_mission_loot(db, guild, resources, run.id, commit=False)
    db.flush()
    ends_at = run.ends_at if run.ends_at.tzinfo else run.ends_at.replace(tzinfo=timezone.utc)
    started_at = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
    return {"id": run.id, "success": bool(run.success), "gold": int(run.gold_reward or 0),
            "xp": int(run.xp_reward or 0), "template": template.name, "party": len(party),
            "discarded": sum(overflows), "duration_seconds": max(1, int((ends_at - started_at).total_seconds()))}


def _run_board_offer(db: Session, campaign: CampaignMetadata, guild: Guild, resources: GuildResources,
                     offer: RegionalOffer, player_state: object, profile: dict[str, object], buildings: dict[str, object],
                     roster: list[Mercenary], at: datetime, rng: random.Random, team_index: int = 0) -> dict[str, object] | None:
    party_size = min(int(profile["party"]), int(offer.max_party_size_snapshot),
                     int(mission_office_values(buildings["contract_office"].level)["party_size"]))
    if party_size < int(offer.min_party_size_snapshot):
        return None
    available = [m for m in roster if m.status == "available"]
    start_index = int(team_index) * party_size
    party = available[start_index:start_index + party_size]
    if len(party) < int(offer.min_party_size_snapshot):
        return None
    offer.status = "player_reserved"
    offer.reserved_by_guild_state_id = int(player_state.id)
    db.add(offer)
    db.flush()
    run_clock = iter((at, at + timedelta(seconds=int(offer.duration_seconds_snapshot) + 1)))
    service = mission_service if offer.offer_type == "contract" else dungeon_service
    start = start_mission if offer.offer_type == "contract" else start_dungeon
    claim = claim_mission_loot if offer.offer_type == "contract" else claim_dungeon_loot
    template_id = offer.mission_template_id if offer.offer_type == "contract" else offer.dungeon_template_id
    overflows = []
    original_add = service.add_inventory_quantity_capped
    def capture_add(*args, **kwargs):
        result = original_add(*args, **kwargs)
        overflows.append(int(result[1]))
        return result
    with patch.object(service, "utc_now", side_effect=lambda: next(run_clock)), \
            patch.object(service, "randint", side_effect=lambda low, high: rng.randint(low, high)), \
            patch.object(service, "add_inventory_quantity_capped", side_effect=capture_add):
        run = start(db, guild, str(template_id), [str(member.id) for member in party], commit=False,
                    regional_duration_seconds=int(offer.duration_seconds_snapshot))
        run.regional_offer_id = offer.id
        run.rank_snapshot = offer.rank
        offer.status = "in_progress"
        offer.claimed_at_utc = run.started_at
        db.add_all((run, offer))
        db.flush()
        claim(db, guild, resources, run.id, commit=False)
    db.flush()
    return {"kind": offer.offer_type, "success": bool(run.success), "gold": int(run.gold_reward or 0),
            "xp": int(run.xp_reward or 0), "discarded": sum(overflows), "template_id": int(template_id),
            "rank": offer.rank}


def _run_player_portal_if_available(
    db: Session, campaign: CampaignMetadata, guild: Guild, resources: GuildResources,
    player_state: object, home_code: str, roster: list[Mercenary], at: datetime, rng: random.Random,
    eligibility_diagnostics: dict[int, dict[str, object]] | None = None,
) -> dict[str, object] | None:
    """Enter and claim one naturally active home-region portal with runtime services."""
    expire_due_events(db, campaign.campaign_id, at)
    for event in active_portals_for_region(db, campaign.campaign_id, home_code):
        if event.dungeon_template_id is None:
            continue
        participant = db.scalar(select(RegionalEventParticipant.id).where(
            RegionalEventParticipant.event_id == event.id,
            RegionalEventParticipant.guild_state_id == player_state.id,
        ))
        if participant is not None:
            continue
        template = db.get(DungeonTemplate, event.dungeon_template_id)
        if template is None:
            continue
        summary = json.loads(event.summary_json or "{}")
        boss_record = summary.get("portal_boss") if isinstance(summary, dict) else None
        snapshot = boss_record.get("template") if isinstance(boss_record, dict) else None
        if not isinstance(snapshot, dict) or int(snapshot.get("id", -1)) != template.id:
            snapshot = build_portal_boss_snapshot(template)
        minimum = int(snapshot.get("min_party_size", template.min_party_size))
        maximum = int(snapshot.get("max_party_size", template.max_party_size))
        needed_level = int(snapshot.get("required_min_mercenary_level", template.required_min_mercenary_level))
        available_levels = sorted(
            (int(member.level) for member in roster if member.status == "available"), reverse=True,
        )
        party = sorted(
            (member for member in roster if member.status == "available" and member.level >= needed_level),
            key=lambda member: (-int(member.level), member.id),
        )[:maximum]
        if len(party) < minimum:
            if eligibility_diagnostics is not None:
                eligibility_diagnostics[int(event.id)] = {
                    "event_id": int(event.id), "template_id": int(template.id),
                    "template_name": template.name, "checks": int(eligibility_diagnostics.get(int(event.id), {}).get("checks", 0)) + 1,
                    "status": "blocked", "reason": "insufficient_mercenary_levels",
                    "required_min_mercenary_level": needed_level, "required_party_size": minimum,
                    "available_member_levels_desc": available_levels,
                    "qualified_members": len(party), "window_deadline_utc": _utc(event.expires_at_utc).isoformat(),
                }
            return None
        from app.services.dungeon_service import validate_advanced_party_requirements, validate_dungeon_requirements
        from types import SimpleNamespace
        snapshot_template = SimpleNamespace(**snapshot)
        try:
            validate_dungeon_requirements(db, guild, snapshot_template)
            validate_advanced_party_requirements(db, guild, snapshot_template, party)
        except DungeonError as exc:
            if eligibility_diagnostics is not None:
                eligibility_diagnostics[int(event.id)] = {
                    "event_id": int(event.id), "template_id": int(template.id),
                    "template_name": template.name, "checks": int(eligibility_diagnostics.get(int(event.id), {}).get("checks", 0)) + 1,
                    "status": "blocked", "reason": str(exc),
                    "required_min_mercenary_level": needed_level, "required_party_size": minimum,
                    "available_member_levels_desc": available_levels,
                    "qualified_members": len(party), "window_deadline_utc": _utc(event.expires_at_utc).isoformat(),
                }
            continue
        if eligibility_diagnostics is not None:
            eligibility_diagnostics[int(event.id)] = {
                "event_id": int(event.id), "template_id": int(template.id),
                "template_name": template.name, "checks": int(eligibility_diagnostics.get(int(event.id), {}).get("checks", 0)) + 1,
                "status": "eligible", "required_min_mercenary_level": needed_level,
                "required_party_size": minimum, "party_levels": [int(member.level) for member in party],
                "window_deadline_utc": _utc(event.expires_at_utc).isoformat(),
            }
        now = [at]
        original_add = dungeon_service.add_inventory_quantity_capped
        overflows: list[int] = []

        def capture_add(*args, **kwargs):
            result = original_add(*args, **kwargs)
            overflows.append(int(result[1]))
            return result

        with patch.object(dungeon_service, "utc_now", side_effect=lambda: now[0]), \
                patch.object(dungeon_service, "randint", side_effect=lambda low, high: rng.randint(low, high)), \
                patch.object(dungeon_service, "add_inventory_quantity_capped", side_effect=capture_add):
            run = start_dungeon(
                db, guild, str(template.id), [str(member.id) for member in party], commit=False,
                regional_duration_seconds=max(3600, int(snapshot.get("duration_seconds", template.duration_seconds))),
                regional_min_duration_seconds=3600, template_snapshot=snapshot,
            )
            attach_event_activity(db, event, player_state, "dungeon", run.id)
            db.flush()
            now[0] = (run.ends_at.replace(tzinfo=timezone.utc) if run.ends_at.tzinfo is None else run.ends_at) + timedelta(seconds=1)
            claim_dungeon_loot(db, guild, resources, run.id, commit=False)
        resolved_summary = json.loads(event.summary_json or "{}")
        portal_loot = resolved_summary.get("portal_loot_result", {})
        db.flush()
        return {
            "kind": "portal", "event_id": event.id, "success": bool(run.success),
            "gold": int(run.gold_reward or 0), "xp": int(run.xp_reward or 0),
            "template_id": template.id, "party": len(party), "discarded": sum(overflows),
            "loot_item_template_id": portal_loot.get("item_template_id"),
            "duration_seconds": max(1, int((run.ends_at - run.started_at).total_seconds())),
        }
    return None


def _gathering_schedule(day_start: datetime, online_windows: dict[int, float],
                       offline_seconds: int) -> list[dict[str, object]]:
    """Build gathering checkpoints from online windows and stamina-backed absence."""
    schedule: list[dict[str, object]] = []
    windows = sorted(
        (day_start + timedelta(hours=cycle * 6), max(0, int(hours * 3600)))
        for cycle, hours in online_windows.items() if hours > 0
    )
    day_end = day_start + timedelta(days=1)
    remaining_offline = min(24 * 60 * 60, max(0, int(offline_seconds)))
    cursor = day_start

    for index, (window_start, online_budget) in enumerate(windows):
        if window_start > cursor:
            credited = min(remaining_offline, int((window_start - cursor).total_seconds()))
            if credited:
                schedule.append({"at": cursor + timedelta(seconds=credited),
                                 "max_seconds": credited, "kind": "offline"})
                remaining_offline -= credited
        online_end = window_start + timedelta(seconds=online_budget)
        schedule.append({"at": online_end, "max_seconds": online_budget, "kind": "online"})
        cursor = online_end

    if cursor < day_end and remaining_offline:
        credited = min(remaining_offline, int((day_end - cursor).total_seconds()))
        if credited:
            schedule.append({"at": cursor + timedelta(seconds=credited),
                             "max_seconds": credited, "kind": "offline"})
    # Move service checkpoints over uncredited wall time so release_worker cannot
    # accidentally turn the remainder of the day into extra gathering.
    schedule.append({"at": day_end, "max_seconds": 0, "kind": "checkpoint"})
    return schedule


def _advance_gathering(db: Session, guild: Guild, assignments: dict[str, object],
                       schedule: list[dict[str, object]]) -> dict[str, object]:
    totals = {"produced": 0, "stored": 0, "discarded": 0, "paused": 0,
              "pause_checkpoints": 0, "checkpoints": 0, "paused_seconds": 0}
    by_family = {}
    for family in assignments:
        by_family[family] = {key: 0 for key in ("produced", "stored", "discarded", "cycles")}
        by_family[family]["paused"] = False
    for interval in schedule:
        totals["checkpoints"] += len(assignments)
        for family, assignment in list(assignments.items()):
            result = advance_assignment(
                db, guild, assignment, now=interval["at"], max_seconds=int(interval["max_seconds"]),
            )
            for key in ("produced", "stored", "discarded", "cycles"):
                by_family[family][key] += int(result[key])
            by_family[family]["paused"] = bool(result["paused"])
            for key in ("produced", "stored", "discarded"):
                totals[key] += int(result[key])
            totals["paused"] += int(bool(result["paused"]))
            totals["pause_checkpoints"] += int(bool(result["paused"]))
            totals["paused_seconds"] += int(result.get("paused_seconds", 0))
    totals["by_family"] = by_family
    totals["credited_seconds"] = sum(int(interval["max_seconds"]) for interval in schedule)
    totals["schedule"] = [{"kind": interval["kind"], "max_seconds": int(interval["max_seconds"]),
                           "at": interval["at"].isoformat()} for interval in schedule]
    return totals


def _sell_surplus(db: Session, guild: Guild, resources: GuildResources, now: datetime,
                  family_reserves: dict[str, int], events: list[dict[str, object]]) -> None:
    rows = list(db.scalars(select(GuildInventoryItem).join(ItemTemplate).where(
        GuildInventoryItem.guild_id == guild.id, ItemTemplate.item_type == "material",
        ItemTemplate.material_family.in_(family_reserves), GuildInventoryItem.quantity > 0,
    ).order_by(GuildInventoryItem.quantity.desc())))
    if not rows:
        return
    totals: dict[str, int] = {}
    for row in rows:
        family = str(row.item_template.material_family)
        totals[family] = totals.get(family, 0) + int(row.quantity)
    candidates = [
        (_marketable_surplus(totals[str(row.item_template.material_family)],
                             int(family_reserves.get(str(row.item_template.material_family), 0))), row)
        for row in rows
        if _marketable_surplus(totals[str(row.item_template.material_family)],
                               int(family_reserves.get(str(row.item_template.material_family), 0))) > 0
    ]
    if not candidates:
        return
    excess, stack = max(candidates, key=lambda item: item[0])
    quota = market_service.get_material_sale_quota(db, guild.id, now=now)
    amount = min(int(stack.quantity), excess, int(quota["remaining"]))
    if amount < 1:
        return
    market_bonus = market_service.get_market_bonuses(db, guild.id)
    sale_clock = iter((now, now + timedelta(days=1)))
    with patch.object(market_service, "utc_now", side_effect=lambda: next(sale_clock)):
        sale = start_material_sale(db, guild, str(stack.item_template_id), str(amount), commit=False)
    end_time = sale.ends_at.replace(tzinfo=timezone.utc) if sale.ends_at.tzinfo is None else sale.ends_at
    with patch.object(market_service, "utc_now", return_value=max(now + timedelta(days=1), end_time + timedelta(seconds=1))):
        collect_market_sale(db, guild, resources, sale.id, commit=False)
    events.append({"type": "market_sale", "day": (now - EPOCH).days,
                   "family": stack.item_template.material_family, "item_template_id": int(stack.item_template_id),
                   "units": amount, "base_unit_value": int(stack.item_template.base_sell_value),
                   "market_level": int(market_bonus["level"]),
                   "value_bonus_percent": int(market_bonus["value_bonus_percent"]),
                   "material_quota_limit": quota["limit"], "material_quota_used_before": quota["used"],
                   "effective_unit_value": int(sale.unit_value), "gold": int(sale.total_value)})


def _salvage_available(db: Session, guild: Guild, resources: GuildResources, buildings: dict[str, object],
                       now: datetime, rng: random.Random, events: list[dict[str, object]],
                       protected_item_ids: set[int] | None = None) -> None:
    if buildings["blacksmith"].level < 1 or int(resources.gold) < 75:
        return
    from app.models.item import GuildItemInstance
    candidates = list(db.scalars(select(GuildItemInstance).where(
        GuildItemInstance.guild_id == guild.id,
        GuildItemInstance.equipped_to_mercenary_id.is_(None),
    ).order_by(GuildItemInstance.id)))
    protected_item_ids = protected_item_ids or set()
    item = next((candidate for candidate in candidates if int(candidate.id) not in protected_item_ids), None)
    if item is None:
        return
    with patch.object(salvage_service, "utc_now", return_value=now):
        job = start_salvage(db, guild, resources, "1", str(item.item_template_id), "1", commit=False)
    end_time = job.ends_at.replace(tzinfo=timezone.utc) if job.ends_at.tzinfo is None else job.ends_at
    overflows = []
    original_add = salvage_service.add_inventory_quantity_capped
    def capture_add(*args, **kwargs):
        result = original_add(*args, **kwargs)
        overflows.append(int(result[1]))
        return result
    with patch.object(salvage_service, "utc_now", return_value=end_time + timedelta(seconds=1)), \
            patch.object(salvage_service, "add_inventory_quantity_capped", side_effect=capture_add), \
            patch.object(salvage_service, "SystemRandom", return_value=rng):
        collect_salvage(db, guild, str(job.id), commit=False)
    salvaged_material = db.get(ItemTemplate, job.material_template_id)
    events.append({"type": "salvage", "day": (now - EPOCH).days,
                   "family": salvaged_material.material_family if salvaged_material else None,
                   "gold_cost": int(job.gold_cost),
                   "materials": int(job.result_quantity or 0), "discarded": sum(overflows)})


def _run_dungeon_once(db: Session, guild: Guild, resources: GuildResources, buildings: dict[str, object],
                      available: list[Mercenary], now: datetime, rng: random.Random) -> dict[str, object] | None:
    if buildings["scouts"].level < 1:
        return None
    party_cap = min(len(available), int(mission_office_values(buildings["contract_office"].level)["party_size"]))
    templates = list(db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "dungeon",
        DungeonTemplate.required_guild_level <= guild.level,
        DungeonTemplate.required_min_mercenary_level <= min(
            (int(member.level) for member in available[:party_cap]), default=0,
        ),
        DungeonTemplate.min_party_size <= party_cap, DungeonTemplate.max_party_size >= party_cap,
    ).order_by(DungeonTemplate.required_guild_level, DungeonTemplate.id)))
    if not templates:
        return None
    template = templates[0]
    run_clock = iter((now, now + timedelta(seconds=max(1, int(template.duration_seconds)) + 1)))
    overflows = []
    original_add = dungeon_service.add_inventory_quantity_capped
    def capture_add(*args, **kwargs):
        result = original_add(*args, **kwargs)
        overflows.append(int(result[1]))
        return result
    with patch.object(dungeon_service, "utc_now", side_effect=lambda: next(run_clock)), \
            patch.object(dungeon_service, "randint", side_effect=lambda low, high: rng.randint(low, high)), \
            patch.object(dungeon_service, "add_inventory_quantity_capped", side_effect=capture_add):
        run = start_dungeon(db, guild, str(template.id), [str(m.id) for m in available[:party_cap]], commit=False)
        db.flush()
        claim_dungeon_loot(db, guild, resources, run.id, commit=False)
    db.flush()
    return {"template": template.name, "success": bool(run.success), "gold": int(run.gold_reward or 0),
            "xp": int(run.xp_reward or 0), "discarded": sum(overflows)}


def run_journey(db: Session, profile: dict[str, object], path: str, seed: int, max_days: int,
                max_wall_seconds: float | None = None,
                checkpoint_day=None, market_reserve_base: int = 30,
                craft_policy: str = "none", full_horizon: bool = False) -> dict[str, object]:
    journey_started = time.perf_counter()
    stage_seconds = {"campaign_setup": 0.0, "actions_claims": 0.0, "regional_cycles": 0.0,
                     "gathering": 0.0, "market_salvage": 0.0, "purchases": 0.0}
    stage_mark = time.perf_counter()
    campaign, guild, resources, buildings = _ensure_fresh_campaign(db, profile, path, seed)
    stage_seconds["campaign_setup"] += time.perf_counter() - stage_mark
    rng = random.Random(f"{seed}:{profile['name']}:{path}")
    apprentice = db.scalar(select(MercenaryClass).where(MercenaryClass.code == "apprentice"))
    base_time = EPOCH
    roster = []
    assignments: dict[str, object] = {}
    purchases: list[dict[str, object]] = []
    first_block: dict[str, dict[str, object]] = {}
    actions: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    bootstrap_diagnostics: list[dict[str, object]] = []
    service_rejections: list[dict[str, object]] = []
    portal_eligibility_diagnostics: dict[int, dict[str, object]] = {}
    crafting_decisions: list[dict[str, object]] = []
    protected_crafted_items: set[int] = set()
    daily = []
    failures = 0
    overflows = {"mission": 0, "dungeon": 0, "gathering": 0, "salvage": 0}
    first_gear_day = first_dungeon_gate_day = first_dungeon_run_day = first_portal_day = first_rebellion_day = None
    dungeon_attempts = dungeon_wins = 0
    level_milestones: dict[str, int] = {}
    stamina = 8.0
    # A real fresh-save minimum start: Tavern 1, Housing 1, first apprentice.
    for effect in ("tavern", "housing"):
        upgrade_guild_building(db, guild, resources, buildings[effect].id)
        buildings[effect] = db.scalar(select(type(buildings[effect])).where(type(buildings[effect]).id == buildings[effect].id))
    cfg = db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))
    random.seed(seed)
    preview = tavern_service.generate_apprentice_preview(cfg, buildings["tavern"].level)
    # Keep recruitment deterministic while preserving the runtime hire/cost/capacity service.
    with patch.object(tavern_service, "generate_apprentice_preview", return_value=preview):
        hire_apprentice(db, guild, resources, f"{profile['name']}-1", preview=preview)
    roster = list(db.scalars(select(Mercenary).where(Mercenary.guild_id == guild.id).order_by(Mercenary.id)))
    for member in roster:
        ensure_mercenary_skills(db, member)
    purchases.extend([{"day": 0, "item": "tavern_1", "gold": 10}, {"day": 0, "item": "housing_1", "gold": 10},
                      {"day": 0, "item": "apprentice_1", "gold": 50}])
    db.commit()

    for day in range(1, max_days + 1):
        now = base_time + timedelta(days=day)
        begin_gold = int(resources.gold)
        materials_start = {family: _inventory_family(db, guild.id, family)
                           for family in ("wood", "ore", "leather")}
        day_actions_start = len(actions)
        day_purchases_start = len(purchases)
        day_events_start = len(events)
        day_actions_start = len(actions)
        day_purchases_start = len(purchases)
        day_events_start = len(events)
        missions_today = 0
        # Real offline gold formula with the persistent stamina schedule used in the balance model.
        from scripts.balance.funded_progression_simulation import advance_offline_stamina
        stamina_row = advance_offline_stamina(float(profile["online_hours"]), stamina)
        stamina = float(stamina_row["stamina_end_hours"])
        offline_seconds = int(stamina_row["offline_credited_seconds"])
        passive_gold_credited = get_passive_gold_rate(db, guild)["total"] * offline_seconds // 3600
        resources.gold += passive_gold_credited

        # Recruit and purchase the next required target; capture every same-item blocker.
        for _ in range(5):
            targets = _next_targets(profile, path, len(roster), buildings)
            if not targets:
                break
            target = targets[0]
            if target == "hire" and buildings["housing"].level == 0:
                target = "housing"
            req = _purchase_requirements(db, guild, resources, buildings, target, profile)
            blocked = _block_snapshot(req, guild, resources, db, buildings)
            if any((blocked["gold_shortfall"], blocked["guild_level_shortfall"], *blocked["material_shortfalls"].values())):
                first_block.setdefault(str(req["item"]), {**blocked, "day": day})
                break
            stage_mark = time.perf_counter()
            bought, purchase_blocked = _buy_if_possible(
                db, guild, resources, buildings, target, profile, rng, day, purchases,
                service_rejections=service_rejections, attempt="planned_target",
            )
            stage_seconds["purchases"] += time.perf_counter() - stage_mark
            if not bought:
                if (purchase_blocked["gold_shortfall"] or purchase_blocked["guild_level_shortfall"]
                        or any(purchase_blocked["material_shortfalls"].values())):
                    first_block.setdefault(str(purchase_blocked["item"]),
                                           {**purchase_blocked, "day": day})
                break
            roster = list(db.scalars(select(Mercenary).where(Mercenary.guild_id == guild.id).order_by(Mercenary.id)))

        # Assign workers to profile production or the first missing building material.
        target = _next_targets(profile, path, len(roster), buildings)
        needed = set()
        if target and target[0] != "hire" and target[0] not in {"market", "blacksmith"}:
            quote = get_upgrade_cost(buildings[target[0]])
            for family in ("wood", "ore"):
                if _inventory_family(db, guild.id, family) < int(quote[family]):
                    needed.add(family)
        families = list(needed)
        if profile["name"] == "produtor" and len(roster) >= 5:
            families = list(dict.fromkeys([*families, "wood", "ore", "leather"]))
        gather_start = now - timedelta(days=1)
        desired_families = set(families)
        for family, assignment in list(assignments.items()):
            if family not in desired_families:
                release_worker(db, guild, assignment.id, now=gather_start)
                del assignments[family]
        available_for_gather = [m for m in roster if m.status == "available"]
        # Keep one worker available for the player's online mission window.
        # The previous order assigned the only apprentice to wood collection
        # before testing the real level-1 mission catalog, creating an artificial
        # zero-action bootstrap stall that the live game does not require.
        available_for_gather = available_for_gather[:-1]
        for family in families:
            if family not in assignments and available_for_gather:
                worker = available_for_gather.pop()
                assignment = assign_worker(db, guild, worker.id, family, now=gather_start)
                assignments[family] = assignment
        # Advance four production cycles; only start activities in the profile's online windows.
        if profile["name"] == "ativo":
            online_windows = {0: 6.0, 1: 6.0}
        elif profile["name"] == "casual":
            online_windows = {0: 2.0}
        elif profile["name"] == "offline":
            # Four hours before an eight-hour absence, then four after returning.
            online_windows = {0: 4.0, 2: 4.0}
        else:
            online_windows = {0: 6.0, 1: 2.0}
        for cycle_in_day in range(4):
            cycle_start = EPOCH + timedelta(days=day - 1, hours=cycle_in_day * 6)
            stage_mark = time.perf_counter()
            get_regional_board(db, campaign, guild, cycle_start)
            stage_seconds["regional_cycles"] += time.perf_counter() - stage_mark
            if cycle_in_day not in online_windows:
                continue
            cycle_number = (day - 1) * 4 + cycle_in_day
            cycle = db.scalar(select(RegionalCycle).where(
                RegionalCycle.campaign_id == campaign.campaign_id, RegionalCycle.cycle_number == cycle_number,
            ))
            if cycle is None:
                continue
            player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
            home_code = next((code for code, region_name in REGIONS if region_name == campaign.home_region), REGIONS[0][0])
            offers = list(db.scalars(select(RegionalOffer).where(
                RegionalOffer.cycle_id == cycle.id, RegionalOffer.region_code == home_code,
                RegionalOffer.offer_type.in_(("contract", "dungeon")), RegionalOffer.status == "available",
            ).order_by(RegionalOffer.offer_type, RegionalOffer.slot)))
            if profile.get("mode") == "contract_priority":
                offers.sort(key=lambda offer: ("EDCBAS".find(offer.rank), offer.slot))
            else:
                offers.sort(key=lambda offer: (offer.offer_type != "contract", offer.slot))
            portal_result = None
            if cycle_in_day in online_windows:
                try:
                    portal_result = _run_player_portal_if_available(
                        db, campaign, guild, resources, player_state, home_code, roster, cycle_start, rng,
                        portal_eligibility_diagnostics,
                    )
                except DungeonError as exc:
                    service_rejections.append({"day": day, "cycle": cycle_number,
                                               "offer_type": "portal", "reason": str(exc)})
                if portal_result is not None:
                    actions.append({"day": day, "cycle": cycle_number, **portal_result})
                    first_dungeon_gate_day = first_dungeon_gate_day or day
                    first_dungeon_run_day = first_dungeon_run_day or day
                    dungeon_attempts += 1
                    dungeon_wins += int(portal_result["success"])
                    overflows["dungeon"] += int(portal_result["discarded"])
            executed = False
            team_hours = float(online_windows[cycle_in_day])
            for team in range(int(profile["teams"])):
                elapsed = int(portal_result["duration_seconds"]) if team == 0 and portal_result else 0
                team_budget = int(team_hours * 3600)
                for offer in offers:
                    if offer.status != "available":
                        continue
                    duration = int(offer.duration_seconds_snapshot)
                    if duration > team_budget - elapsed:
                        continue
                    template_id = offer.mission_template_id if offer.offer_type == "contract" else offer.dungeon_template_id
                    template = db.get(MissionTemplate if offer.offer_type == "contract" else DungeonTemplate, template_id)
                    if template is None or int(template.required_guild_level) > guild.level:
                        continue
                    if template.required_building_type and buildings.get(template.required_building_type, SimpleNamespace(level=0)).level < template.required_building_level:
                        continue
                    if offer.offer_type == "dungeon" and buildings["scouts"].level < 1:
                        continue
                    party_size = min(int(profile["party"]), int(offer.max_party_size_snapshot),
                                     int(mission_office_values(buildings["contract_office"].level)["party_size"]))
                    party_start = team * party_size
                    candidate_party = [m for m in roster if m.status == "available"][party_start:party_start + party_size]
                    if len(candidate_party) < int(offer.min_party_size_snapshot) or min(
                            (int(member.level) for member in candidate_party), default=0
                    ) < int(template.required_min_mercenary_level):
                        continue
                    try:
                        with db.begin_nested():
                            stage_mark = time.perf_counter()
                            result = _run_board_offer(db, campaign, guild, resources, offer, player_state,
                                                      profile, buildings, roster,
                                                      cycle_start + timedelta(seconds=elapsed), rng, team_index=team)
                            stage_seconds["actions_claims"] += time.perf_counter() - stage_mark
                    except (MissionError, DungeonError) as exc:
                        service_rejections.append({"day": day, "cycle": cycle_number, "offer_id": offer.id,
                                                   "offer_type": offer.offer_type, "reason": str(exc)})
                        continue
                    except Exception as exc:
                        import traceback
                        raise RuntimeError(
                            f"service failure profile={profile['name']} path={path} seed={seed} "
                            f"day={day} cycle={cycle_number} offer={offer.id} type={offer.offer_type}: {exc}\n"
                            f"{traceback.format_exc()}"
                        ) from exc
                    if result is None:
                        continue
                    executed = True
                    elapsed += duration
                    actions.append({"day": day, "cycle": cycle_number, **result})
                    if result["kind"] == "contract":
                        missions_today += 1
                        failures += int(not result["success"])
                        overflows["mission"] += int(result["discarded"])
                    else:
                        first_dungeon_gate_day = first_dungeon_gate_day or day
                        first_dungeon_run_day = first_dungeon_run_day or day
                        dungeon_attempts += 1
                        dungeon_wins += int(result["success"])
                        overflows["dungeon"] += int(result["discarded"])
                    if first_gear_day is None and _has_equipment_instance(db, guild.id):
                        first_gear_day = day
                    db.flush()
            if not executed:
                # Fresh-save bootstrap through active catalog missions until a regional-board
                # offer becomes eligible. These still use mission_service and runtime rewards.
                diagnostic_party = min(int(profile["party"]),
                                        int(mission_office_values(buildings["contract_office"].level)["party_size"]))
                diagnostic_available = [m for m in roster if m.status == "available"]
                diagnostic_party = min(diagnostic_party, len(diagnostic_available))
                diagnostic_members = diagnostic_available[:diagnostic_party]
                bootstrap_diagnostics.append({
                    "day": day, "cycle": cycle_number, "available_mercenaries": len(diagnostic_available),
                    "eligible_templates": len(_eligible_missions(
                        db, guild, buildings, diagnostic_party,
                        min((int(member.level) for member in diagnostic_members), default=0),
                    ))
                    if diagnostic_party > 0 else 0,
                })
                for team in range(int(profile["teams"])):
                    elapsed = 0
                    budget = int(team_hours * 3600)
                    turn = 0
                    while elapsed < budget:
                        available = [m for m in roster if m.status == "available"]
                        party_size = min(int(profile["party"]),
                                         int(mission_office_values(buildings["contract_office"].level)["party_size"]),
                                         len(available))
                        if party_size <= 0:
                            break
                        party = available[team * party_size:(team + 1) * party_size]
                        if len(party) < party_size:
                            break
                        pool = [t for t in _eligible_missions(
                                    db, guild, buildings, party_size,
                                    min((int(member.level) for member in party), default=0),
                                )
                                if int(t.duration_seconds) <= budget - elapsed]
                        if not pool:
                            break
                        pool.sort(key=lambda t: _mission_score(t, str(profile.get("mode", "mission"))), reverse=True)
                        template = pool[(day + team + turn + seed) % len(pool)]
                        stage_mark = time.perf_counter()
                        result = _run_mission(db, guild, resources, party, template,
                                              cycle_start + timedelta(seconds=elapsed), rng)
                        stage_seconds["actions_claims"] += time.perf_counter() - stage_mark
                        elapsed += int(result["duration_seconds"])
                        turn += 1
                        actions.append({"day": day, "cycle": cycle_number, "bootstrap_starter_template": True,
                                        "kind": "mission", **result})
                        missions_today += 1
                        failures += int(not result["success"])
                        overflows["mission"] += int(result["discarded"])
                        if first_gear_day is None and _has_equipment_instance(db, guild.id):
                            first_gear_day = day
        # Advance actual assignment checkpoints through this day's elapsed time.
        stage_mark = time.perf_counter()
        gathering_schedule = _gathering_schedule(
            EPOCH + timedelta(days=day - 1), online_windows, offline_seconds,
        )
        gather = _advance_gathering(db, guild, assignments, gathering_schedule)
        inventory_before_market_sale = get_inventory_usage(db, guild.id)
        stage_seconds["gathering"] += time.perf_counter() - stage_mark
        overflows["gathering"] += gather["discarded"]
        if craft_policy == "first_surplus_equipment_once" and not any(
            decision.get("crafted") for decision in crafting_decisions
        ) and buildings["blacksmith"].level >= 1:
            family_reserves = _market_family_reserves(
                db, guild, resources, buildings, profile, path, len(roster),
                base_reserve=market_reserve_base,
            )
            stage_mark = time.perf_counter()
            craft_event = _craft_one_affordable_surplus_equipment(
                db, guild, resources, buildings, family_reserves, now,
            )
            stage_seconds["market_salvage"] += time.perf_counter() - stage_mark
            if craft_event is not None:
                events.append(craft_event)
                protected_crafted_items.update(craft_event["created_instance_ids"])
                crafting_decisions.append({"day": day, "crafted": True,
                                           "output_item_template_id": craft_event["output_item_template_id"],
                                           "gold_cost": craft_event["gold_cost"]})
        # Material sales and salvage use their real timers and transactions after their buildings unlock.
        if buildings["market"].level >= 1:
            try:
                stage_mark = time.perf_counter()
                with db.begin_nested():
                    reserves = _market_family_reserves(
                        db, guild, resources, buildings, profile, path, len(roster),
                        base_reserve=market_reserve_base,
                    )
                    _sell_surplus(db, guild, resources, now, family_reserves=reserves, events=events)
                stage_seconds["market_salvage"] += time.perf_counter() - stage_mark
            except Exception as exc:
                service_rejections.append({"day": day, "service": "market_sale", "reason": str(exc)})
        if buildings["blacksmith"].level >= 1:
            try:
                stage_mark = time.perf_counter()
                with db.begin_nested():
                    before_usage = get_inventory_usage(db, guild.id)
                    _salvage_available(db, guild, resources, buildings, now, rng, events,
                                       protected_item_ids=protected_crafted_items)
                stage_seconds["market_salvage"] += time.perf_counter() - stage_mark
                overflows["salvage"] += sum(int(event.get("discarded", 0)) for event in events
                                             if event["type"] == "salvage" and event["day"] == day)
            except Exception as exc:
                service_rejections.append({"day": day, "service": "salvage", "reason": str(exc)})

        # Four real cycle boundaries were advanced above, including unattended periods.
        events_rows = list(db.scalars(select(RegionalEvent).where(
            RegionalEvent.campaign_id == campaign.campaign_id,
        )))
        rebellion_triggered = []
        rebellion_eligible_region_cycles = 0
        rebellion_candidate_region_cycles = 0
        for event in events_rows:
            trigger_day = max(1, int(event.trigger_cycle_number) // 4 + 1)
            if event.event_type == "portal" and first_portal_day is None:
                first_portal_day = trigger_day
            if event.event_type == "rebellion":
                summary = json.loads(event.summary_json or "{}")
                rebellion_eligible_region_cycles += int(bool(summary.get("eligible")))
                rebellion_candidate_region_cycles += int(bool(
                    summary.get("generated_while_campaign_open") or summary.get("suppressed_by_global_limit")
                ))
                if _is_activated_rebellion(event):
                    rebellion_triggered.append(trigger_day)
        if first_rebellion_day is None and rebellion_triggered:
            first_rebellion_day = min(rebellion_triggered)
        # Retry the same blocked milestone; preserve day and exact purchase identity.
        for key, blocked in list(first_block.items()):
            if any(p.get("item") == key and int(p.get("day", 0)) > int(blocked["day"]) for p in purchases):
                continue
            current_targets = _next_targets(profile, path, len(roster), buildings)
            if current_targets:
                current_req = _purchase_requirements(db, guild, resources, buildings, current_targets[0], profile)
                if str(current_req["item"]) == key:
                    if not any((_block_snapshot(current_req, guild, resources, db, buildings)["gold_shortfall"],
                                _block_snapshot(current_req, guild, resources, db, buildings)["guild_level_shortfall"],
                                *(_block_snapshot(current_req, guild, resources, db, buildings)["material_shortfalls"].values()))):
                        bought, _ = _buy_if_possible(
                            db, guild, resources, buildings, current_targets[0], profile, rng, day, purchases,
                            service_rejections=service_rejections, attempt="first_block_retry",
                        )
                        if bought:
                            blocked["recovered_day"] = day
        db.commit()
        day_actions = actions[day_actions_start:]
        day_purchases = [purchase for purchase in purchases[day_purchases_start:]
                         if int(purchase.get("day", 0)) == day]
        day_events = [event for event in events[day_events_start:]
                      if int(event.get("day", 0)) == day]
        gathering_assignment_state = []
        for family, assignment in sorted(assignments.items()):
            worker = db.get(Mercenary, assignment.mercenary_id)
            gathering_assignment_state.append({
                "family": family,
                "mercenary_id": int(assignment.mercenary_id),
                "mercenary_name": worker.name if worker else None,
                "worker_status": worker.status if worker else None,
                "capacity_paused": bool(assignment.capacity_paused),
                "progress_seconds": int(assignment.progress_seconds),
            })
        worker_state = {
            "roster_count": len(roster),
            "available_count": sum(1 for member in roster if member.status == "available"),
            "gathering_count": sum(1 for member in roster if member.status == "gathering"),
            "assignments": gathering_assignment_state,
            "inventory_used": get_inventory_usage(db, guild.id),
            "inventory_capacity": get_inventory_capacity(db, guild),
        }
        mission_gold = sum(int(action.get("gold", 0)) for action in day_actions
                           if action.get("kind") in {"mission", "contract"})
        dungeon_gold = sum(int(action.get("gold", 0)) for action in day_actions
                           if action.get("kind") in {"dungeon", "portal"})
        market_gold = sum(int(event.get("gold", 0)) for event in day_events
                          if event.get("type") == "market_sale")
        salvage_cost = sum(int(event.get("gold_cost", 0)) for event in day_events
                           if event.get("type") == "salvage")
        crafting_cost = sum(int(event.get("gold_cost", 0)) for event in day_events
                            if event.get("type") == "craft")
        purchase_gold = sum(int(purchase.get("gold", 0)) for purchase in day_purchases)
        gold_end = int(resources.gold)
        accounted_delta = passive_gold_credited + mission_gold + dungeon_gold + market_gold \
            - salvage_cost - crafting_cost - purchase_gold
        daily_actions = [action for action in actions if int(action.get("day", -1)) == day]
        overflow_by_source = {
            "mission": sum(int(action.get("discarded", 0)) for action in daily_actions
                            if action.get("kind") in ("contract", "mission")),
            "dungeon": sum(int(action.get("discarded", 0)) for action in daily_actions
                           if action.get("kind") in ("dungeon", "portal")),
            "gathering": int(gather["discarded"]),
            "salvage": sum(int(event.get("discarded", 0)) for event in day_events
                           if event.get("type") == "salvage"),
        }
        daily.append({"day": day, "guild_level": int(guild.level), "gold_start": begin_gold,
                      "gold_end": gold_end, "missions": missions_today, "mission_failures_cumulative": failures,
                      "gold_ledger": {
                          "passive_offline": int(passive_gold_credited), "missions": mission_gold,
                          "dungeons": dungeon_gold, "market_sales": market_gold,
                          "salvage_fees": salvage_cost, "building_and_hire_purchases": purchase_gold,
                          "crafting_fees": crafting_cost,
                          "observed_delta": gold_end - begin_gold,
                          "unattributed_residual": gold_end - begin_gold - accounted_delta,
                      },
                      "materials_start": materials_start,
                      "materials_end": {family: _inventory_family(db, guild.id, family)
                                         for family in ("wood", "ore", "leather")},
                      "inventory_used": get_inventory_usage(db, guild.id), "inventory_capacity": get_inventory_capacity(db, guild),
                      "gathering_produced": gather["produced"], "gathering_stored": gather["stored"],
                      "gathering_by_family": gather["by_family"],
                          "gathering_credited_seconds": gather["credited_seconds"],
                          "gathering_schedule": gather["schedule"],
                      "gathering_discarded": gather["discarded"],
                      "gathering_paused_checkpoints": gather["pause_checkpoints"],
                      "gathering_checkpoints": gather["checkpoints"],
                      "gathering_paused_seconds": gather["paused_seconds"],
                      "overflow_by_source": overflow_by_source,
                      "inventory_used_before_market_sale": inventory_before_market_sale,
                          "worker_state": worker_state,
                      "market_and_salvage_events": day_events, "daily_purchases": day_purchases,
                      "purchase_count_cumulative": len(purchases)})
        for milestone_level in (10, 25, 50):
            key = str(milestone_level)
            if int(guild.level) >= milestone_level and key not in level_milestones:
                level_milestones[key] = day
        if checkpoint_day is not None:
            checkpoint_day({
                "profile": profile["name"], "path": path, "seed": seed, "day": day,
                "guild_level": int(guild.level), "guild_xp": int(guild.xp),
                "mercenary_levels": [int(member.level) for member in roster],
                "level_milestones": dict(level_milestones), "daily": list(daily),
                "actions_count": len(actions), "purchases_count": len(purchases),
                "events_count": len(events), "elapsed_seconds": round(time.perf_counter() - journey_started, 3),
            })
        if not full_horizon and guild.level >= 50 and not _next_targets(profile, path, len(roster), buildings):
            break
        if max_wall_seconds is not None and time.perf_counter() - journey_started >= max_wall_seconds:
            break
    gear_instances = db.scalar(select(GuildInventoryItem.quantity).join(ItemTemplate).where(
        GuildInventoryItem.guild_id == guild.id, ItemTemplate.item_type == "equipment").limit(1)) or 0
    recovered = []
    historical_unrecovered = []
    for key, value in first_block.items():
        later_purchase_days = [int(purchase["day"]) for purchase in purchases
                               if purchase.get("item") == key
                               and int(purchase.get("day", 0)) > int(value["day"])]
        if value.get("recovered_day") is not None or later_purchase_days:
            recovered.append(key)
            if value.get("recovered_day") is None:
                value["recovered_day"] = min(later_purchase_days)
        else:
            historical_unrecovered.append(key)
    remaining_targets = _next_targets(profile, path, len(roster), buildings)
    horizon_snapshot = None
    if remaining_targets:
        horizon_req = _purchase_requirements(
            db, guild, resources, buildings, remaining_targets[0], profile,
        )
        horizon_snapshot = _block_snapshot(horizon_req, guild, resources, db, buildings)
    horizon_block_snapshots = _horizon_blocked_targets(remaining_targets, horizon_snapshot)
    horizon_blocked = list(horizon_block_snapshots)
    stop_reason = (
        "full_horizon" if full_horizon and len(daily) >= max_days
        else "wall_budget" if max_wall_seconds is not None and
        time.perf_counter() - journey_started >= max_wall_seconds
        else "level_50_and_targets_complete" if guild.level >= 50 and not remaining_targets
        else "max_days"
    )
    return {
        "profile": profile["name"], "path": path, "seed": seed, "days": len(daily),
        "market_reserve_base": max(0, int(market_reserve_base)),
        "craft_policy": craft_policy,
        "crafting_decisions": crafting_decisions,
        "crafts_completed": sum(bool(entry.get("crafted")) for entry in crafting_decisions),
        "market_level_end": int(buildings["market"].level),
        "valid": True, "elapsed_seconds": round(time.perf_counter() - journey_started, 3),
        "stage_seconds": {key: round(value, 3) for key, value in stage_seconds.items()},
        "guild_level": int(guild.level), "guild_xp_end": int(guild.xp),
        "mercenary_levels_end": [int(member.level) for member in roster],
        "reached_level_50": int(guild.level) >= 50,
        "level_milestone_days": level_milestones,
        "budget_exhausted": bool(max_wall_seconds is not None and
                                  time.perf_counter() - journey_started >= max_wall_seconds and len(daily) < max_days),
        "full_horizon_requested": bool(full_horizon),
        "stop_reason": stop_reason,
        "planned_upgrade_targets_complete": not remaining_targets,
        "planned_upgrade_targets_remaining": remaining_targets,
        "first_equipment_day": first_gear_day, "first_dungeon_gate_day": first_dungeon_gate_day,
        "first_dungeon_run_day": first_dungeon_run_day, "dungeon_attempts": dungeon_attempts,
        "dungeon_wins": dungeon_wins, "first_portal_day": first_portal_day,
        "first_rebellion_day": first_rebellion_day,
        "regional_event_opportunities": {
            "rebellion_eligible_region_cycles": rebellion_eligible_region_cycles,
            "rebellion_candidate_region_cycles": rebellion_candidate_region_cycles,
            "rebellion_activated": len(rebellion_triggered),
            "portal_created": sum(event.event_type == "portal" for event in events_rows),
            "portal_resolved": sum(event.event_type == "portal" and event.status in {"resolved", "expired"}
                                    for event in events_rows),
        },
        "mission_count": sum(action["kind"] == "mission" for action in actions),
        "mission_successes": sum(action.get("success", False) for action in actions if action["kind"] == "mission"),
        "mission_failures": failures, "missions_xp": sum(int(action.get("xp", 0)) for action in actions if action["kind"] == "mission"),
        "purchases": purchases, "blocked_upgrades": first_block,
        "same_upgrade_blocked_then_bought": len(recovered),
        "blocked_upgrade_at_horizon_count": len(horizon_blocked),
        "blocked_upgrades_at_horizon": horizon_blocked,
        "blocked_upgrade_snapshots_at_horizon": horizon_block_snapshots,
        "historical_unrecovered_blocked_targets": historical_unrecovered,
        "ending_gold": int(resources.gold), "ending_materials": {m: _inventory_family(db, guild.id, m) for m in ("wood", "ore", "leather")},
        "inventory_peak": max((int(d["inventory_used"]) for d in daily), default=0),
        "inventory_peak_before_market_sale": max(
            (int(d["inventory_used_before_market_sale"]) for d in daily), default=0,
        ),
        "gathering_pause_checkpoints": sum(int(d["gathering_paused_checkpoints"]) for d in daily),
        "gathering_checkpoints": sum(int(d["gathering_checkpoints"]) for d in daily),
        "gathering_paused_seconds": sum(int(d["gathering_paused_seconds"]) for d in daily),
        "inventory_capacity_end": get_inventory_capacity(db, guild), "overflow": overflows,
        "events": events, "service_rejections": service_rejections,
        "portal_eligibility_diagnostics": list(portal_eligibility_diagnostics.values()),
        "bootstrap_diagnostics": bootstrap_diagnostics, "daily": daily, "actions": actions,
    }


def summarize(rows: list[dict[str, object]], seed: int) -> dict[str, object]:
    n = len(rows)
    reached = sum(bool(row["reached_level_50"]) for row in rows)
    complete = sum(bool(row["planned_upgrade_targets_complete"]) for row in rows)
    unresolved = sum(int(row["blocked_upgrade_at_horizon_count"]) > 0 for row in rows)
    event_times = [float(row["first_portal_day"]) for row in rows if row["first_portal_day"] is not None]
    rebellion_times = [float(row["first_rebellion_day"]) for row in rows if row["first_rebellion_day"] is not None]
    gears = [float(row["first_equipment_day"]) for row in rows if row["first_equipment_day"] is not None]
    dungeons = [float(row["first_dungeon_run_day"]) for row in rows if row["first_dungeon_run_day"] is not None]
    return {
        "n": n, "reached_level_50": reached, "reached_rate_wilson_95": wilson_interval_95(reached, n),
        "planned_upgrade_targets_complete": complete,
        "planned_upgrade_targets_complete_rate_wilson_95": wilson_interval_95(complete, n),
        "blocked_upgrade_at_horizon_rate_wilson_95": wilson_interval_95(unresolved, n),
        "same_upgrade_blocked_then_bought_total": sum(int(row["same_upgrade_blocked_then_bought"]) for row in rows),
        "ending_gold_p50_ci95": _ci_median([float(row["ending_gold"]) for row in rows], seed),
        "first_equipment_day_p50_ci95": _ci_median(gears, seed + 1),
        "first_dungeon_run_day_p50_ci95": _ci_median(dungeons, seed + 2),
        "first_portal_day_p50_ci95": _ci_median(event_times, seed + 3),
        "first_rebellion_day_p50_ci95": _ci_median(rebellion_times, seed + 4),
        "missions": {"count": sum(int(row["mission_count"]) for row in rows),
                     "failures": sum(int(row["mission_failures"]) for row in rows)},
        "dungeons": {"attempts": sum(int(row["dungeon_attempts"]) for row in rows),
                     "wins": sum(int(row["dungeon_wins"]) for row in rows)},
        "overflow": {kind: sum(int(row["overflow"][kind]) for row in rows)
                      for kind in ("mission", "dungeon", "gathering", "salvage")},
        "level_milestone_days": {
            str(level): [row.get("level_milestone_days", {}).get(str(level)) for row in rows]
            for level in (10, 25, 50)
        },
        "gold_ledger_totals": {
            key: sum(int(entry["gold_ledger"][key]) for row in rows for entry in row["daily"])
            for key in ("passive_offline", "missions", "dungeons", "market_sales", "salvage_fees",
                        "crafting_fees", "building_and_hire_purchases", "observed_delta", "unattributed_residual")
        },
        "crafting": {
            "completed": sum(int(row.get("crafts_completed", 0)) for row in rows),
            "policy": sorted({str(row.get("craft_policy", "none")) for row in rows}),
        },
        "inventory_peak_used": max((int(row["inventory_peak"]) for row in rows), default=0),
        "inventory_capacity_end": [int(row["inventory_capacity_end"]) for row in rows],
        "recovered_blocked_targets_total": sum(int(row["same_upgrade_blocked_then_bought"]) for row in rows),
        "blocked_targets_at_horizon_total": sum(int(row["blocked_upgrade_at_horizon_count"]) for row in rows),
        "event_activity": {
            "player_portal_entries": sum(
                sum(action.get("kind") == "portal" for action in row["actions"]) for row in rows
            ),
            "player_portal_successes": sum(
                sum(action.get("kind") == "portal" and action.get("success") for action in row["actions"])
                for row in rows
            ),
            "player_portal_equipment_drops": sum(
                sum(action.get("kind") == "portal" and action.get("loot_item_template_id") is not None
                    for action in row["actions"]) for row in rows
            ),
            "portal_created": sum(int(row["regional_event_opportunities"]["portal_created"]) for row in rows),
            "portal_resolved_or_expired": sum(int(row["regional_event_opportunities"]["portal_resolved"]) for row in rows),
            "rebellion_eligible_region_cycles": sum(int(row["regional_event_opportunities"]["rebellion_eligible_region_cycles"]) for row in rows),
            "rebellions_activated": sum(int(row["regional_event_opportunities"]["rebellion_activated"]) for row in rows),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-per-cell", type=int, default=1, help="Use 1 for pilot before increasing N.")
    parser.add_argument("--seed-start", type=int, default=2026103000)
    parser.add_argument("--max-days", type=int, default=365)
    parser.add_argument("--max-wall-seconds", type=float, default=600,
                        help="Maximum wall-clock seconds per fresh journey; checkpointed daily.")
    parser.add_argument("--market-reserve-base", type=int, default=30,
                        help="Fixed material units reserved per family before sales; next-upgrade wood/ore costs are added.")
    parser.add_argument("--market-base-units-per-24h", type=int,
                        help="Override the rolling 24h material-sale allowance at Market 1 for sensitivity runs.")
    parser.add_argument("--market-unlimited-materials", action="store_true",
                        help="Disable the material-sale allowance for a paired sensitivity baseline only.")
    parser.add_argument("--craft-policy", choices=("none", "first_surplus_equipment_once"), default="none",
                        help="Optional one-time real craft from stock above the protected reserve; keeps the output gear.")
    parser.add_argument("--full-horizon", action="store_true",
                        help="Continue real-service activity to max-days after planned level-50 targets complete.")
    parser.add_argument("--profile", choices=[p["name"] for p in PROFILES], help="Optional single-cell pilot profile.")
    parser.add_argument("--path", choices=PATHS, help="Optional single-cell pilot policy.")
    parser.add_argument("--output-stem", default="stage5_service_journeys_2026-10-29")
    args = parser.parse_args()
    if args.market_unlimited_materials and args.market_base_units_per_24h is not None:
        parser.error("Use either --market-unlimited-materials or --market-base-units-per-24h, not both.")
    if args.market_base_units_per_24h is not None and args.market_base_units_per_24h < 1:
        parser.error("--market-base-units-per-24h must be positive.")
    if args.market_unlimited_materials:
        market_service.MATERIAL_BASE_UNITS_PER_24H = None
    elif args.market_base_units_per_24h is not None:
        market_service.MATERIAL_BASE_UNITS_PER_24H = args.market_base_units_per_24h
    start = time.perf_counter()
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    checkpoint_path = report_dir / f"{args.output_stem}.checkpoint.json"
    with TemporaryDirectory(prefix="gim-stage5-service-journeys-") as temp_dir:
        init_start = time.perf_counter()
        engine = create_database_engine(f"sqlite:///{(Path(temp_dir) / 'journeys.sqlite3').as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            db_init_seconds = time.perf_counter() - init_start
            with factory() as db:
                seed_start_time = time.perf_counter()
                apply_initial_campaign_content(db)
                db.commit()
                content_seed_seconds = time.perf_counter() - seed_start_time
                rows = []
                errors = []
                chosen_profiles = [(i, p) for i, p in enumerate(PROFILES) if args.profile is None or p["name"] == args.profile]
                chosen_paths = [(i, p) for i, p in enumerate(PATHS) if args.path is None or p == args.path]
                for pi, profile in chosen_profiles:
                    for hi, path in chosen_paths:
                        cell = []
                        for rep in range(max(1, args.runs_per_cell)):
                            seed = args.seed_start + pi * 100_000 + hi * 10_000 + rep
                            try:
                                def checkpoint_day(progress: dict[str, object]) -> None:
                                    _write_json_atomic(checkpoint_path, {
                                        "checkpoint_version": 2,
                                        "checkpoint_kind": "daily_evidence_not_database_resume",
                                        "parameters": {
                                            "runs_per_cell": args.runs_per_cell,
                                            "seed_start": args.seed_start,
                                            "max_days": args.max_days,
                                            "max_wall_seconds": args.max_wall_seconds,
                                            "market_reserve_base": args.market_reserve_base,
                                            "craft_policy": args.craft_policy,
                                            "full_horizon": args.full_horizon,
                                            "market_base_units_per_24h": market_service.MATERIAL_BASE_UNITS_PER_24H,
                                            "profiles": [dict(p) for _, p in chosen_profiles],
                                            "paths": [p for _, p in chosen_paths],
                                            "output_stem": args.output_stem,
                                        },
                                        "completed_cells": sorted({
                                            f"{row['profile']}/{row['path']}" for row in [*rows, *cell]
                                        }),
                                        "completed_seeds": len(rows) + len(cell),
                                        "active_journey_checkpoint": progress,
                                        "journey_errors": errors,
                                        "journeys": [*rows, *cell],
                                    })
                                journey = run_journey(
                                    db, profile, path, seed, max(1, args.max_days),
                                    max_wall_seconds=max(0.1, args.max_wall_seconds),
                                    checkpoint_day=checkpoint_day,
                                    market_reserve_base=max(0, args.market_reserve_base),
                                    craft_policy=args.craft_policy,
                                    full_horizon=args.full_horizon,
                                )
                                cell.append(journey)
                                print(f"done {profile['name']}/{path} seed={seed} days={journey['days']} lvl={journey['guild_level']} elapsed={journey['elapsed_seconds']}s", flush=True)
                            except Exception as exc:
                                import traceback
                                errors.append({"profile": profile["name"], "path": path, "seed": seed,
                                               "error": str(exc), "traceback": traceback.format_exc()})
                                print(f"ERROR {profile['name']}/{path} seed={seed}: {exc}", flush=True)
                            # Valid journey days commit their own state. This rollback only clears
                            # any failed journey's leftover transaction before the next seed.
                            db.rollback()
                            _write_json_atomic(checkpoint_path, {
                                "checkpoint_version": 1,
                                "parameters": {
                                    "runs_per_cell": args.runs_per_cell,
                                    "seed_start": args.seed_start,
                                    "max_days": args.max_days,
                                    "max_wall_seconds": args.max_wall_seconds,
                                    "market_reserve_base": args.market_reserve_base,
                                    "market_base_units_per_24h": market_service.MATERIAL_BASE_UNITS_PER_24H,
                                    "profiles": [dict(p) for _, p in chosen_profiles],
                                    "paths": [p for _, p in chosen_paths],
                                    "output_stem": args.output_stem,
                                },
                                "completed_cells": sorted({
                                    f"{row['profile']}/{row['path']}" for row in [*rows, *cell]
                                } | {
                                    f"{error['profile']}/{error['path']}" for error in errors
                                }),
                                "completed_seeds": len(rows) + len(cell) + len(errors),
                                "journey_errors": errors,
                                "journeys": [*rows, *cell],
                            })
                        rows.extend(cell)
            report = {
                "report_id": "gim-stage5-live-service-journeys-20261030-v6",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "pilot": args.runs_per_cell < 100,
                "runs_per_cell": args.runs_per_cell,
                "seed_start": args.seed_start,
                "max_days": args.max_days,
                "max_wall_seconds": args.max_wall_seconds,
                "market_reserve_base": args.market_reserve_base,
                "craft_policy": args.craft_policy,
                "full_horizon": args.full_horizon,
                "market_base_units_per_24h": market_service.MATERIAL_BASE_UNITS_PER_24H,
                "market_material_quota_disabled_for_sensitivity": market_service.MATERIAL_BASE_UNITS_PER_24H is None,
                "elapsed_seconds": round(time.perf_counter() - start, 2),
                "database_init_seconds": round(db_init_seconds, 3),
                "content_seed_seconds": round(content_seed_seconds, 3),
                "journey_errors": errors,
                "service_rejection_count": sum(len(row.get("service_rejections", [])) for row in rows),
                "service_rejection_reasons": [
                    {"service": service, "reason": reason, "count": count}
                    for (service, reason), count in sorted(Counter(
                        (str(entry.get("service", "unknown")), str(entry.get("reason", "unspecified")))
                        for row in rows for entry in row.get("service_rejections", [])
                    ).items())
                ],
                "n_policy_cells": len(chosen_profiles) * len(chosen_paths),
                "profiles": [dict(p) for _, p in chosen_profiles], "paths": [p for _, p in chosen_paths],
                "cell_summaries": {
                    f"{profile['name']}/{path}": summarize(
                        [r for r in rows if r.get("valid") and r["profile"] == profile["name"] and r["path"] == path],
                        args.seed_start + profile_index * 1000 + path_index * 37,
                    )
                    for profile_index, (profile_pos, profile) in enumerate(chosen_profiles)
                    for path_index, (path_pos, path) in enumerate(chosen_paths)
                },
                "journeys": rows,
                "limits": [
                    "Fresh campaign rows and all outputs live in a disposable SQLite file; real user saves are never opened.",
                    "Guild and mercenary levels advance only through runtime service rewards; the journey never synchronizes mercenary level to guild level or fabricates resources.",
                    "Home regional boards are finite and each offer is reserved/completed at most once. During fresh-save bootstrap without an accessible regional offer, active catalog templates use mission_service directly; they are not regional-board offers.",
                    "Regional world advances through four real six-hour boundaries per day. Starts occur only in defined online windows; offline profile uses 4h before an 8h absence and 4h after return, while event timers continue during unattended cycles. First-event timing is measured to the day.",
                    "Naturally active home-region portals are entered and claimed through start_dungeon, attach_event_activity and claim_dungeon_loot during an online window when the available party meets the snapshot requirements; portal equipment loot and failure are recorded. Other regional opportunities/closures are observed. Rebellion participation remains outside this player policy. Portal counts combine resolved and expired states; they are not player victories. The accepted rules remain 2% rebellion chance per eligible Vigil and a portal deadline that continues during offline catch-up.",
                    "Each team has a separate per-window budget and uses a disjoint roster slice when enough mercenaries exist. Claims return mercenaries before their next assignment; no team shares a busy mercenary.",
                    "No new sink or price is added. Salvage is attempted only with spare gold above 75; the fixed material reserve and optional one-time crafting policy are explicit simulator choices, not game rules.",
                    f"Market sales reserve {max(0, args.market_reserve_base)} units per material family plus the full material cost of the current planned upgrade for wood/ore.",
                    "Gathering uses the configured online windows and the persistent-stamina offline credit for each day, advancing real gathering_service checkpoints with max_seconds. It does not accrue 24 hours of gathering merely because the campaign clock advanced by one day.",
                    f"When a milestone changes the required material, the synthetic worker is released and reassigned via gathering_service.release_worker/assign_worker. Market sales protect {max(0, args.market_reserve_base)} units per material family plus the full material cost of the current planned upgrade for wood/ore. This is an explicit recovery policy, not a game rule.",
                    f"Crafting policy is {args.craft_policy}. When enabled, the runner selects at most one affordable rotating equipment recipe using only material stock above the protected reserve, keeps the crafted item out of automatic salvage, and records actual gold/material costs. This is an explicit journey choice, not a new game rule.",
                    f"Material sales use the live service's rolling 24h throughput allowance: base={market_service.MATERIAL_BASE_UNITS_PER_24H!r} at Market 1, increasing by 5 units at each five-level milestone; it applies to all material sources and does not cap equipment sales.",
                    "Daily JSON checkpoints preserve ledger, milestone, roster-level and event/action counts during a run, but are evidence checkpoints rather than a resumable SQLite snapshot. Each journey has max_days and max_wall_seconds budgets. N=1 per profile/path cannot support rare-event or stable-rate claims.",
                    "A horizon blocker is the next planned target still pending at the end whose current gold, level, or material requirements are unmet. Historical blocked snapshots without a same-target retry are reported separately; neither metric proves a permanent softlock. Finite policy journeys do not establish whole-game hard-softlock absence or economic stability.",
                ],
            }
            stem = args.output_stem
            (report_dir / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            ledger_path = report_dir / f"{stem}.ledger.csv"
            ledger_temp = ledger_path.with_name(ledger_path.name + ".tmp")
            with ledger_temp.open("w", encoding="utf-8-sig", newline="") as ledger_file:
                ledger_writer = csv.DictWriter(ledger_file, fieldnames=(
                    "profile", "path", "seed", "day", "guild_level", "gold_start", "passive_offline",
                    "mission_gold", "dungeon_gold", "market_sales_gold", "salvage_fees",
                    "building_hire_purchases", "gold_end", "unattributed_residual",
                    "wood_start", "wood_end", "ore_start", "ore_end", "leather_start", "leather_end",
                    "gathering_produced", "gathering_credited_seconds", "gathering_by_family_json",
                    "worker_state_json", "events_json", "purchases_json",
                    "overflow_mission", "overflow_dungeon", "overflow_gathering", "overflow_salvage",
                    "gathering_paused_worker_seconds",
                ))
                ledger_writer.writeheader()
                for journey in rows:
                    for entry in journey["daily"]:
                        gold = entry["gold_ledger"]
                        materials_before = entry["materials_start"]
                        materials_after = entry["materials_end"]
                        ledger_writer.writerow({
                            "profile": journey["profile"], "path": journey["path"], "seed": journey["seed"],
                            "day": entry["day"], "guild_level": entry["guild_level"],
                            "gold_start": entry["gold_start"], "passive_offline": gold["passive_offline"],
                            "mission_gold": gold["missions"], "dungeon_gold": gold["dungeons"],
                            "market_sales_gold": gold["market_sales"], "salvage_fees": gold["salvage_fees"],
                            "building_hire_purchases": gold["building_and_hire_purchases"],
                            "gold_end": entry["gold_end"], "unattributed_residual": gold["unattributed_residual"],
                            "wood_start": materials_before["wood"], "wood_end": materials_after["wood"],
                            "ore_start": materials_before["ore"], "ore_end": materials_after["ore"],
                            "leather_start": materials_before["leather"], "leather_end": materials_after["leather"],
                            "gathering_produced": entry["gathering_produced"],
                            "gathering_credited_seconds": entry["gathering_credited_seconds"],
                            "gathering_by_family_json": json.dumps(entry["gathering_by_family"], ensure_ascii=False),
                            "worker_state_json": json.dumps(entry["worker_state"], ensure_ascii=False),
                            "events_json": json.dumps(entry["market_and_salvage_events"], ensure_ascii=False),
                            "purchases_json": json.dumps(entry["daily_purchases"], ensure_ascii=False),
                            "overflow_mission": entry["overflow_by_source"]["mission"],
                            "overflow_dungeon": entry["overflow_by_source"]["dungeon"],
                            "overflow_gathering": entry["overflow_by_source"]["gathering"],
                            "overflow_salvage": entry["overflow_by_source"]["salvage"],
                            "gathering_paused_worker_seconds": entry["gathering_paused_seconds"],
                        })
            ledger_temp.replace(ledger_path)
            lines = ["# Jornadas fresh-save com serviços reais — Stage 5", "",
                     f"Pilot={report['pilot']} · N={args.runs_per_cell}/célula · {len(chosen_profiles)} perfis × {len(chosen_paths)} políticas · horizonte={args.max_days} dias · teto={args.max_wall_seconds}s/jornada · reserva fixa de material={max(0, args.market_reserve_base)} unidades/família · cota L1={market_service.MATERIAL_BASE_UNITS_PER_24H!r}, +5 nos níveis 5, 10, 15... · política de crafting={args.craft_policy} · tempo={report['elapsed_seconds']}s · setup SQLite={db_init_seconds:.2f}s · seed de conteúdo={content_seed_seconds:.2f}s.",
                     "", "| Perfil/caminho | Nível 50 | Alvos planejados completos | Falhas de missão | Dungeon tentadas/vencidas | Ouro final p50 (IC95% bootstrap; não estimável em N<2) | Primeiro equipamento | Dungeon | Portal criado | Rebelião ativada | Upgrade-alvo ainda bloqueado no horizonte |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
            for key, s in report["cell_summaries"].items():
                def rt(d): return f"{d['events']}/{d['n']} ({d['rate_percent']}%; {d['lower_percent']}–{d['upper_percent']}%)"
                def mt(d):
                    if not d["n"]:
                        return "—"
                    if d["n"] < 2:
                        return f"{d['median']} (n={d['n']}; IC95% não estimável)"
                    return f"{d['median']} ({d['lower_95']}–{d['upper_95']}; n={d['n']})"
                lines.append(f"| {key} | {rt(s['reached_rate_wilson_95'])} | {rt(s['planned_upgrade_targets_complete_rate_wilson_95'])} | {s['missions']['failures']} | {s['dungeons']['attempts']}/{s['dungeons']['wins']} | {mt(s['ending_gold_p50_ci95'])} | {mt(s['first_equipment_day_p50_ci95'])} | {mt(s['first_dungeon_run_day_p50_ci95'])} | {mt(s['first_portal_day_p50_ci95'])} | {mt(s['first_rebellion_day_p50_ci95'])} | {rt(s['blocked_upgrade_at_horizon_rate_wilson_95'])} |")
            lines.extend(["", "## Ledger, capacidade, marcos e eventos por célula", "",
                          "O ledger diário completo está no CSV; residual zero indica que as fontes/drenos contabilizados reconciliam o delta observado de ouro.",
                          "", "| Perfil/caminho | D10/D25/D50 da guilda | Fontes de ouro: offline/missões/masmorra/Market | Drenos: compras/salvage/crafting | Delta/resíduo | Pico/capacidade | Overflow M/D/G/S | Recuperações/bloqueios finais | Portal: dia/criados/encerrados* | Rebelião: dia/ativações/oportunidades | Craft: feitos/política |",
                          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
            journey_by_cell = {f"{row['profile']}/{row['path']}": row for row in rows}
            for key, summary_row in report["cell_summaries"].items():
                journey = journey_by_cell.get(key)
                if journey is None:
                    continue
                totals = summary_row["gold_ledger_totals"]
                milestone_days = summary_row["level_milestone_days"]
                milestones = "/".join(str((milestone_days.get(str(level)) or [None])[0] or "—")
                                       for level in (10, 25, 50))
                events_row = journey["regional_event_opportunities"]
                lines.append(
                    f"| {key} | {milestones} | {totals['passive_offline']}/{totals['missions']}/{totals['dungeons']}/{totals['market_sales']} "
                    f"| {totals['building_and_hire_purchases']}/{totals['salvage_fees']}/{totals['crafting_fees']} "
                    f"| {totals['observed_delta']}/{totals['unattributed_residual']} "
                    f"| {journey['inventory_peak']}/{journey['inventory_capacity_end']} "
                    f"| {journey['overflow']['mission']}/{journey['overflow']['dungeon']}/{journey['overflow']['gathering']}/{journey['overflow']['salvage']} "
                    f"| {journey['same_upgrade_blocked_then_bought']}/{journey['blocked_upgrade_at_horizon_count']} "
                    f"| D{journey['first_portal_day']}/{events_row['portal_created']}/{events_row['portal_resolved']} "
                    f"| D{journey['first_rebellion_day']}/{events_row['rebellion_activated']}/{events_row['rebellion_eligible_region_cycles']} "
                    f"| {journey['crafts_completed']}/{journey['craft_policy']} |"
                )
            lines.extend(["", f"*Portal encerrado inclui estados resolvidos ou expirados. Portais ativos da região natal são iniciados e resgatados pelo jogador via serviços reais se estiverem disponíveis durante uma janela online e a equipe cumprir o snapshot; portais não observados continuam ausentes. Rebeliões têm oportunidades naturais e resultados de CPU, mas esta política não aceita convites nem vincula atividade do jogador. A chance aprovada de rebelião é 2% por Vigília elegível e o prazo do portal avança durante catch-up offline. Venda de materiais segue cota L1={market_service.MATERIAL_BASE_UNITS_PER_24H!r}, +5 em cada marco de cinco níveis; sensibilidade está em relatório separado."])
            lines.extend(["", "## Limites e definições", ""] + [f"- {lim}" for lim in report["limits"]])
            lines.extend(["", "## Reprodução", "", "```powershell",
                          f".venv-desktop\\Scripts\\python.exe scripts\\balance\\simulate_stage5_service_journeys.py --runs-per-cell {args.runs_per_cell} --seed-start {args.seed_start} --max-days {args.max_days} --max-wall-seconds {args.max_wall_seconds} --market-reserve-base {max(0, args.market_reserve_base)} --craft-policy {args.craft_policy}" + (" --market-unlimited-materials" if args.market_unlimited_materials else f" --market-base-units-per-24h {args.market_base_units_per_24h}" if args.market_base_units_per_24h is not None else "") + f" --output-stem {stem}" + (f" --profile {args.profile}" if args.profile else "") + (f" --path {args.path}" if args.path else ""), "```", ""])
            (report_dir / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")
            print(f"report={stem}; ledger={ledger_path.name}; elapsed={report['elapsed_seconds']}s", flush=True)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
