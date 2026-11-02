"""Funded 1-50 purchase simulation using seeded service prices and rewards.

This is a reproducible sensitivity model, not a new balance rule. It runs in a
throwaway SQLite file and deletes it when the process exits.
"""
from __future__ import annotations

import json
import hashlib
import random
from math import ceil, sqrt
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from uuid import uuid5, NAMESPACE_URL

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, create_database_engine
from app.core.game_balance import OFFLINE_CAP_SECONDS
from app.models.campaign import CampaignMetadata
from app.models.guild import Guild, GuildResources
from app.models.item import GuildInventoryItem, ItemTemplate
from app.models.dungeon import DungeonTemplate
from app.models.mercenary import Mercenary
from app.models.tavern import GuildTavernState
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_VERSION
from app.services.building_balance_service import (
    housing_capacity, mission_office_values, required_guild_level_for_upgrade,
    training_xp_bonus,
)
from app.services.building_service import ensure_guild_buildings, get_upgrade_cost
from app.services.guild_progression_service import add_guild_xp
from app.repositories.item_repository import (
    RESOURCE_MATERIAL_FAMILIES, consume_inventory_resource, get_inventory_resource_totals,
    sync_inventory_resource_totals,
)
from app.services.gathering_service import _material_template
from app.services.inventory_capacity_service import (
    add_inventory_quantity_capped, get_inventory_capacity, get_inventory_usage,
)
from app.services.offline_progress_service import get_passive_gold_rate
from app.services.tavern_service import get_discounted_hire_cost, get_tavern_apprentice_chances, next_apprentice_cost
from app.services.regional_cycle_service import REGIONS
from app.models.building import GuildBuilding
from app.models.tavern import TavernConfig
from scripts.balance.simulate_guild_progression_profiles import (
    Profile, _create_abstract_roster, _cycle_outcome, _sample_real_home_board,
    _sync_abstract_roster, _offline_cycle_window,
)


STRATEGIES = (
    # Profiles and starting roster shapes match GDD §23; purchase targets are
    # explicit audit assumptions, not approved balance rules.
    {"name": "ativo", "online_hours": 12.0, "teams": 3, "party_size": 3,
     "roster_target": 9, "office_target": 10, "mode": "mission"},
    {"name": "casual", "online_hours": 2.0, "teams": 2, "party_size": 2,
     "roster_target": 4, "office_target": 1, "mode": "mission"},
    {"name": "offline", "online_hours": 8.0, "teams": 3, "party_size": 3,
     "roster_target": 9, "office_target": 10, "mode": "mission"},
    {"name": "produtor", "online_hours": 8.0, "teams": 1, "party_size": 2,
     "roster_target": 5, "office_target": 1, "mode": "mission",
     "continuous_gathering": ["wood", "ore", "leather"]},
    {"name": "combate", "online_hours": 8.0, "teams": 3, "party_size": 3,
     "roster_target": 9, "office_target": 10, "mode": "contract_priority"},
)
MATERIALS = ("wood", "ore", "leather", "crystals")
BUILDING_MATERIALS = ("wood", "ore", "crystals")
GATHERABLE_MATERIALS = ("wood", "ore", "leather")
MAX_DAYS = 365
OFFLINE_STAMINA_CAP_HOURS = 8
OFFLINE_STAMINA_RESTORED_PER_ONLINE_HOUR = 2
SOFTLOCK_OBSERVATION_WINDOW_DAYS = 14


def daily_offline_seconds(online_hours: float, stamina_hours: float = OFFLINE_STAMINA_CAP_HOURS) -> int:
    """Return offline credit after persistent stamina regeneration and consumption."""
    absent = max(0, 24.0 - float(online_hours)) * 3600
    regenerated = min(OFFLINE_STAMINA_CAP_HOURS,
                      max(0.0, float(stamina_hours)) + max(0.0, float(online_hours)) * OFFLINE_STAMINA_RESTORED_PER_ONLINE_HOUR)
    return min(int(absent), OFFLINE_CAP_SECONDS, int(regenerated * 3600))


def advance_offline_stamina(online_hours: float, stamina_hours: float) -> dict[str, float | int]:
    """Regenerate persistent stamina, credit the absence, and return the remaining balance."""
    start = min(OFFLINE_STAMINA_CAP_HOURS, max(0.0, float(stamina_hours)))
    regenerated = min(OFFLINE_STAMINA_CAP_HOURS,
                      start + max(0.0, float(online_hours)) * OFFLINE_STAMINA_RESTORED_PER_ONLINE_HOUR)
    absent_hours = max(0.0, 24.0 - float(online_hours))
    credited = min(absent_hours, OFFLINE_STAMINA_CAP_HOURS, regenerated)
    return {
        "stamina_start_hours": start,
        "stamina_regenerated_hours": regenerated - start,
        "stamina_available_hours": regenerated,
        "offline_credited_hours": credited,
        "offline_credited_seconds": int(credited * 3600),
        "stamina_end_hours": regenerated - credited,
    }


def offline_stamina_restored(online_hours: float) -> int:
    return min(OFFLINE_STAMINA_CAP_HOURS,
               max(0, int(float(online_hours) * OFFLINE_STAMINA_RESTORED_PER_ONLINE_HOUR)))


def gather_with_capacity(
    balances: dict[str, int], *, family: str, requested: int, free_capacity: int,
    worker_count: int, offline_seconds: int,
) -> tuple[int, int]:
    """Mirror base gathering: one unit/minute/worker, one worker/family, capped."""
    if family not in GATHERABLE_MATERIALS or worker_count <= 0:
        return 0, 0
    available_cycles = max(0, int(offline_seconds)) // 60
    stored = min(max(0, int(requested)), available_cycles, max(0, int(free_capacity)))
    balances[family] = int(balances.get(family, 0)) + stored
    return stored, stored * 60


def _balance_snapshot(gold: int, materials: dict[str, int], capacity: int) -> dict[str, object]:
    return {
        "gold": int(gold), "materials": {name: int(materials.get(name, 0)) for name in MATERIALS},
        "inventory_used": sum(int(materials.get(name, 0)) for name in MATERIALS),
        "inventory_capacity": int(capacity),
    }


def _inventory_material_balance(db, guild: Guild, resources: GuildResources) -> dict[str, int]:
    """Return live GuildResources totals derived from material inventory stacks."""
    sync_inventory_resource_totals(db, resources)
    leather = db.scalar(
        select(func.coalesce(func.sum(GuildInventoryItem.quantity), 0))
        .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
        .where(GuildInventoryItem.guild_id == guild.id, ItemTemplate.item_type == "material",
               ItemTemplate.material_family == "leather")
    ) or 0
    return {"wood": int(resources.wood), "ore": int(resources.ore),
            "leather": int(leather), "crystals": int(resources.crystals)}


def _balance_snapshot_live(db, guild: Guild, gold: int, resources: GuildResources) -> dict[str, object]:
    material_balance = _inventory_material_balance(db, guild, resources)
    capacity = get_inventory_capacity(db, guild)
    return {
        "gold": int(gold), "materials": material_balance,
        "inventory_used": get_inventory_usage(db, guild.id),
        "inventory_capacity": capacity,
    }


def _roster_party_minimum_level(roster: list[Mercenary], party_size: int, *,
                                active_count: int | None = None) -> int:
    """Highest minimum level obtainable from the currently active abstract roster."""
    limit = len(roster) if active_count is None else min(len(roster), max(0, int(active_count)))
    levels = sorted((int(mercenary.level) for mercenary in roster[:limit]), reverse=True)
    if int(party_size) <= 0 or len(levels) < int(party_size):
        return 0
    return levels[int(party_size) - 1]


def _simulated_party_size(target_party_size: int, active_roster_size: int) -> int:
    """Party size is limited by the profile and roster, never by a building."""
    return min(int(target_party_size), max(1, int(active_roster_size)))


def wilson_interval_95(successes: int, trials: int) -> dict[str, float | int | None]:
    """Wilson score interval for a binomial rate; safe for zero/all successes."""
    n = int(trials)
    k = int(successes)
    if n <= 0:
        return {"n": 0, "events": k, "rate_percent": None, "lower_percent": None, "upper_percent": None}
    z = 1.959963984540054
    p = k / n
    denominator = 1 + (z * z / n)
    center = (p + z * z / (2 * n)) / denominator
    half = z * sqrt((p * (1 - p) / n) + (z * z / (4 * n * n))) / denominator
    return {
        "n": n, "events": k, "rate_percent": round(100 * p, 2),
        "lower_percent": round(100 * max(0, center - half), 2),
        "upper_percent": round(100 * min(1, center + half), 2),
    }


def bootstrap_median_ci_95(values: list[float], *, seed: int, resamples: int = 3000) -> dict[str, float | int | None]:
    """Deterministic percentile bootstrap interval for a sample median."""
    clean = [float(value) for value in values]
    if not clean:
        return {"n": 0, "median": None, "lower_95": None, "upper_95": None}
    rng = random.Random(seed)
    n = len(clean)
    medians = sorted(median([clean[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples))
    lo = medians[max(0, int(0.025 * resamples) - 1)]
    hi = medians[min(resamples - 1, int(0.975 * resamples))]
    return {"n": n, "median": median(clean), "lower_95": round(lo, 2), "upper_95": round(hi, 2)}


def modeled_no_route_stall(rows: list[dict[str, object]], *, window_days: int = SOFTLOCK_OBSERVATION_WINDOW_DAYS) -> bool | None:
    """Find a continuous blocked milestone window with no modeled route to recover.

    This is only an observable model proxy: every day in a full window must show
    an unaffordable next mandatory purchase and no gold, material, or XP route.
    Missing requirement/source fields return None instead of a false zero.
    """
    if len(rows) < window_days:
        return None
    for start in range(len(rows) - window_days + 1):
        window = rows[start:start + window_days]
        requirements = [row.get("next_purchase_requirements") for row in window]
        if any("next_purchase_requirements" not in row for row in window):
            return None
        if any(item is None for item in requirements):
            # The finite purchase plan has already completed in this window.
            continue
        if any(not isinstance(item, dict) for item in requirements):
            return None
        if any(item.get("item") is None for item in requirements):
            continue
        if len({item["item"] for item in requirements}) != 1:
            continue
        gold_route = any(int(row.get("contract_gold", 0)) + int(row.get("offline_gold", 0)) > 0 for row in window)
        xp_route = any(int(row.get("action_count", 0)) > 0 for row in window)
        material_routes: set[str] = set()
        for row in window:
            workers = int(row.get("gather_workers_available", -1))
            gather_seconds = int(row.get("gather_seconds_available", 0))
            has_capacity_evidence = "inventory_used" in row and "inventory_capacity" in row
            if not has_capacity_evidence:
                return None
            has_free_capacity = int(row["inventory_used"]) < int(row["inventory_capacity"])
            if workers > 0 and gather_seconds >= 60 and has_free_capacity:
                material_routes.update(GATHERABLE_MATERIALS)
            if has_free_capacity:
                material_routes.update(str(family) for family in row.get("mission_material_drop_route_families", []))
        blocked_gold = any(int(item.get("gold_shortfall", 0)) > 0 for item in requirements)
        blocked_level = any(int(item.get("guild_level_shortfall", 0)) > 0 for item in requirements)
        blocked_materials = {
            family for family in MATERIALS
            if any(int(item.get("material_shortfalls", {}).get(family, 0)) > 0 for item in requirements)
        }
        unrecoverable = (
            (blocked_gold and not gold_route)
            or (bool(blocked_materials) and not blocked_materials.issubset(material_routes))
            or (blocked_level and not xp_route)
        )
        if unrecoverable:
            return True
    return False


def _next_step_quote(strategy: dict[str, object], roster_count: int, buildings: dict[str, GuildBuilding],
                     guild: Guild, db, tavern_state: GuildTavernState, config: TavernConfig) -> dict[str, object] | None:
    step = _next_purchase(strategy, roster_count, buildings)
    if step is None:
        return None
    item, building = step
    if item == "apprentice_hire":
        gold = get_discounted_hire_cost(
            int(tavern_state.current_apprentice_hire_cost),
            int(get_tavern_apprentice_chances(buildings["tavern"].level, config)["hire_discount_percent"]),
        )
        material = {name: 0 for name in MATERIALS}
        required_level = guild.level
        name = f"apprentice_{roster_count + 1}"
    else:
        assert building is not None
        quote = get_upgrade_cost(building)
        gold = int(quote["gold"])
        material = {name: int(quote.get(name, 0)) for name in MATERIALS}
        required_level = _required_level(building)
        name = f"{building.building_template.effect_type}_{building.level + 1}"
    # Caller fills balances and shortfalls from the current trajectory state.
    return {"item": name, "gold_cost": gold, "material_cost": material,
            "guild_level_required": required_level, "is_modeled_milestone": True}


def _next_purchase(
    strategy: dict[str, object], roster_count: int, buildings: dict[str, GuildBuilding],
) -> tuple[str, GuildBuilding | None] | None:
    housing = buildings["housing"]
    office = buildings["contract_office"]
    path_variant = str(strategy.get("path_variant", "roster_first"))
    # Alternative funded route: invest in optional Office bonuses after the
    # profile can already field its minimum party, before filling its roster.
    if (path_variant == "office_after_minimum_party"
            and roster_count >= int(strategy["party_size"])
            and office.level < int(strategy.get("office_target", 1))):
        return "contract_office_upgrade", office
    if roster_count < int(strategy["roster_target"]):
        if housing_capacity(housing.level) < roster_count + 1:
            return "housing_upgrade", housing
        return "apprentice_hire", None
    if office.level < int(strategy.get("office_target", 1)):
        return "contract_office_upgrade", office
    training = buildings["training_ground"]
    if training.level < 1:
        return "training_ground_upgrade", training
    scouts = buildings["scouts"]
    if strategy.get("include_scouts_objective") and scouts.level < 1:
        return "scouts_upgrade", scouts
    return None


def _required_level(building: GuildBuilding) -> int:
    return required_guild_level_for_upgrade(building.level + 1, building.building_template.required_guild_level)


def _run_trajectory(db, strategy: dict[str, object], seed: int, run_index: int,
                    max_days: int = MAX_DAYS,
                    sink_policy: dict[str, object] | None = None,
                    integrate_item_sources: bool = False) -> dict[str, object]:
    campaign_id = str(uuid5(NAMESPACE_URL, f"funded-trajectory:{strategy['name']}:{seed}"))
    campaign = CampaignMetadata(
        campaign_id=campaign_id, campaign_name=f"Funded {strategy['name']}",
        schema_version=5, content_version=PACK_VERSION, home_region=REGIONS[0][1],
    )
    guild = Guild(campaign_id=campaign_id, name=f"Guilda {strategy['name']}", level=1)
    resources = GuildResources(guild=guild, gold=100, wood=0, ore=0, crystals=0)
    db.add_all((campaign, guild, resources))
    db.flush()
    buildings = {row.building_template.effect_type: row for row in ensure_guild_buildings(db, guild.id)}
    dungeon_templates = list(db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "dungeon",
    ))) if integrate_item_sources and strategy.get("include_scouts_objective") else []
    config = db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))
    if config is None:
        raise RuntimeError("Seeded TavernConfig is missing")
    tavern_state = GuildTavernState(
        guild_id=guild.id, apprentice_hire_count=0,
        current_apprentice_hire_cost=int(config.base_apprentice_cost),
        next_special_check_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    db.add(tavern_state)
    db.flush()
    roster: list[Mercenary] = []
    material_balance = ({name: 0 for name in MATERIALS} if not integrate_item_sources
                        else _inventory_material_balance(db, guild, resources))
    purchase_rows: list[dict[str, object]] = []
    blocked_reason_counts: dict[str, int] = {}
    gold_sources = {"regional_contracts": 0, "offline_passive": 0}
    day_gold = []
    level50_day = None
    actions = 0
    successes = 0
    actionless_days = 0
    collection_paused_days = 0
    cumulative_spend = 0
    sink_paid_total = 0
    sink_due_total = 0
    sink_unpaid_total = 0
    purchase_sequence = 0
    first_gear_day: int | None = None
    first_dungeon_gate_day: int | None = None
    first_dungeon_offer_day: int | None = None
    realized_gear_drops: list[dict[str, object]] = []
    material_drop_roll_count = 0
    material_drop_award_count = 0
    material_drop_stored_total = 0
    material_drop_discarded_total = 0
    recovery_actions: list[dict[str, object]] = []

    def balance_snapshot() -> dict[str, object]:
        if integrate_item_sources:
            return _balance_snapshot_live(db, guild, resources.gold, resources)
        return _balance_snapshot(resources.gold, material_balance, get_inventory_capacity(db, guild))

    def inventory_used() -> int:
        return get_inventory_usage(db, guild.id) if integrate_item_sources else sum(material_balance.values())

    def hire(day: int, *, initial: bool = False) -> None:
        nonlocal purchase_sequence, cumulative_spend
        chances = get_tavern_apprentice_chances(buildings["tavern"].level, config)
        base_cost = int(tavern_state.current_apprentice_hire_cost)
        cost = get_discounted_hire_cost(base_cost, int(chances["hire_discount_percent"]))
        gold_before = int(resources.gold)
        resources.gold -= cost
        tavern_state.current_apprentice_hire_cost = next_apprentice_cost(base_cost, config)
        tavern_state.apprentice_hire_count += 1
        created = _create_abstract_roster(db, guild, Profile("funded", "mission", 0, 1, 1))[0]
        created.hire_cost = cost
        roster.append(created)
        add_guild_xp(guild, 10)
        if not initial:
            purchase_sequence += 1
            cumulative_spend += cost
            purchase_rows.append({"step": purchase_sequence, "item": f"apprentice_{len(roster)}",
                                  "day": day, "gold_cost": cost, "material_cost": {},
                                  "gold_balance_before": gold_before, "affordable_at_purchase": True,
                                  "balance_after": balance_snapshot()})

    # Execute the same minimum start used by the real fresh-save smoke: Tavern 1,
    # Housing 1, then first apprentice. Quotes are queried from the building and
    # tavern services; the purchases themselves are recorded in this temp model.
    for effect in ("tavern", "housing"):
        building = buildings[effect]
        cost = get_upgrade_cost(building)
        gold_before = int(resources.gold)
        resources.gold -= cost["gold"]
        building.level += 1
        add_guild_xp(guild, 10)
        purchase_rows.append({"step": len(purchase_rows) + 1, "item": f"{effect}_1", "day": 0,
                              "gold_cost": cost["gold"], "material_cost": {k: cost[k] for k in BUILDING_MATERIALS},
                              "gold_balance_before": gold_before, "affordable_at_purchase": True,
                              "balance_after": balance_snapshot()})
        cumulative_spend += cost["gold"]
    hire(0, initial=True)
    purchase_rows.append({"step": len(purchase_rows) + 1, "item": "apprentice_1", "day": 0,
                          "gold_cost": int(config.base_apprentice_cost), "material_cost": {},
                          "gold_balance_before": 80, "affordable_at_purchase": True,
                          "balance_after": balance_snapshot()})
    cumulative_spend += int(config.base_apprentice_cost)
    purchase_sequence = len(purchase_rows)
    start_gold = int(resources.gold)
    if start_gold < 0:
        raise AssertionError("The selected fresh-save minimum setup must be affordable")

    offline_stamina_hours = float(OFFLINE_STAMINA_CAP_HOURS)
    for day in range(1, max(1, int(max_days)) + 1):
        stamina_day = advance_offline_stamina(float(strategy["online_hours"]), offline_stamina_hours)
        offline_stamina_hours = float(stamina_day["stamina_end_hours"])
        credited_offline_seconds = int(stamina_day["offline_credited_seconds"])
        start_gold_day = int(resources.gold)
        sink_paid_today = 0
        sink_due_today = 0
        sink_unpaid_today = 0
        if sink_policy and sink_policy["type"] == "roster_payroll":
            sink_due_today = int(sink_policy["gold_per_mercenary_day"]) * len(roster)
            sink_paid_today = min(int(resources.gold), sink_due_today)
            sink_unpaid_today = sink_due_today - sink_paid_today
            resources.gold -= sink_paid_today
            sink_paid_total += sink_paid_today
            sink_due_total += sink_due_today
            sink_unpaid_total += sink_unpaid_today
        gold_today = 0
        material_drop_rolls_today = 0
        material_drop_awards_today = 0
        material_drop_stored_today = 0
        material_drop_discarded_today = 0
        material_drop_route_families_today: set[str] = set()
        gathered_today = {name: 0 for name in MATERIALS}
        materials_spent_today = {name: 0 for name in MATERIALS}
        inventory_peak_used = inventory_used()
        _sync_abstract_roster(roster, guild.level)
        continuous_families = (list(strategy.get("continuous_gathering", []))
                               if len(roster) >= int(strategy["roster_target"]) else [])
        active_roster_size = max(0, len(roster) - len(continuous_families))
        action_count_today = 0
        # Offline follows the earlier 8h dispatch/catch-up schedule. Online
        # profiles divide their presence budget over touched six-hour boards.
        if strategy["name"] == "offline":
            windows = [(_offline_cycle_window(index)[0], _offline_cycle_window(index)[1], index,
                        _offline_cycle_window(index)[2]) for index in range(4)]
        else:
            remaining = float(strategy["online_hours"])
            windows = []
            index = 0
            while remaining > 0:
                hours = min(6.0, remaining)
                windows.append((hours, None, index, "online"))
                remaining -= hours
                index += 1
        for action_hours, max_actions, cycle_index, window_kind in windows:
            board, player_power, _ = _sample_real_home_board(db, campaign, guild, (day - 1) * 4 + cycle_index)
            if window_kind == "unattended":
                continue
            if integrate_item_sources and buildings["scouts"].level >= 1:
                current_party_size = _simulated_party_size(strategy["party_size"], active_roster_size)
                current_party_min_level = _roster_party_minimum_level(
                    roster, current_party_size, active_count=active_roster_size,
                )
                for offer in board:
                    if (offer["offer_type"] == "dungeon"
                            and int(offer["min_party_size"]) <= current_party_size <= int(offer["max_party_size"])
                            and int(offer["required_guild_level"]) <= guild.level
                            and int(offer["required_min_mercenary_level"]) <= current_party_min_level):
                        first_dungeon_offer_day = first_dungeon_offer_day or day
                        break
            if sink_policy and sink_policy["type"] == "wallet_dues":
                due = ceil(int(resources.gold) * float(sink_policy["rate"]))
                paid = min(int(resources.gold), due)
                resources.gold -= paid
                sink_paid_today += paid
                sink_due_today += due
                sink_unpaid_today += due - paid
                sink_paid_total += paid
                sink_due_total += due
                sink_unpaid_total += due - paid
            office_level = buildings["contract_office"].level
            max_party = _simulated_party_size(strategy["party_size"], active_roster_size)
            party_min_level = _roster_party_minimum_level(
                roster, max_party, active_count=active_roster_size,
            )
            slots = min(int(strategy["teams"]), max(1, active_roster_size // max_party))
            cycle_profile = Profile(str(strategy["name"]), str(strategy["mode"]), float(strategy["online_hours"]),
                                    slots, max_party, party_selection_policy="selectable")
            result = _cycle_outcome(
                cycle_profile, board, seed + day * 7919 + cycle_index * 104729,
                action_hours=action_hours, max_actions_per_team=max_actions,
                guild=guild, player_power_snapshot=player_power,
                roster_size=active_roster_size, training_bonus_percent=training_xp_bonus(buildings["training_ground"].level),
                reward_bonus_percent=mission_office_values(office_level)["reward_bonus_percent"],
                eligibility_mercenary_level=party_min_level,
                track_item_drops=integrate_item_sources,
            )
            if integrate_item_sources:
                for roll in result["item_drop_rolls"]:
                    if roll["item_type"] == "material":
                        for resource_name, families in RESOURCE_MATERIAL_FAMILIES.items():
                            if roll.get("material_family") in families:
                                material_drop_route_families_today.add(resource_name)
                        material_drop_roll_count += 1
                        material_drop_rolls_today += 1
                        material_drop_award_count += int(roll["awarded"] is True)
                        material_drop_awards_today += int(roll["awarded"] is True)
                for event in result["item_drop_events"]:
                    if event["item_type"] == "equipment":
                        first_gear_day = first_gear_day or day
                        realized_gear_drops.append({"day": day, **event})
                    elif event["item_type"] == "material":
                        item_template = db.get(ItemTemplate, int(event["item_template_id"]))
                        stored, discarded = add_inventory_quantity_capped(
                            db, guild, item_template.id, int(event["quantity_requested"]),
                        )
                        material_drop_stored_total += stored
                        material_drop_discarded_total += discarded
                        material_drop_stored_today += stored
                        material_drop_discarded_today += discarded
                        if stored:
                            material_balance = _inventory_material_balance(db, guild, resources)
                            recovery_actions.append({
                                "day": day, "source": "mission_drop", "item": item_template.name,
                                "family": item_template.material_family, "stored": stored,
                                "inventory_used": get_inventory_usage(db, guild.id),
                            })
            gold_today += result["gold"]
            action_count_today += result["actions"]
            gold_sources["regional_contracts"] += result["gold"]
            actions += result["actions"]
            successes += result["successes"]
            for name, count in result["blocked_window_reasons"].items():
                blocked_reason_counts[name] = blocked_reason_counts.get(name, 0) + count

        # The passive formula is the live offline service formula and shares
        # the actual 8h credit cap. Offline awards no ordinary materials.
        passive_rate = get_passive_gold_rate(db, guild)["total"]
        passive_gold = passive_rate * credited_offline_seconds // 3600
        offline_crystals_earned = int(
            integrate_item_sources and credited_offline_seconds >= OFFLINE_CAP_SECONDS
        )
        resources.crystals += offline_crystals_earned
        gross_gold_today = gold_today + passive_gold
        if sink_policy and sink_policy["type"] == "earnings_levy":
            due = ceil(gross_gold_today * float(sink_policy["rate"]))
            paid = min(gross_gold_today, due)
            sink_paid_today += paid
            sink_due_today += due
            sink_unpaid_today += due - paid
            sink_paid_total += paid
            sink_due_total += due
            sink_unpaid_total += due - paid
            resources.gold += gross_gold_today - paid
        else:
            resources.gold += gross_gold_today
        gold_sources["offline_passive"] += passive_gold

        # Persistent producer assignments use the existing one-worker-per-
        # family, one-unit-per-minute rule and share the live inventory cap.
        continuous_pause_today = False
        if continuous_families:
            offline_seconds = credited_offline_seconds
            used_now = inventory_used()
            remaining_capacity = max(0, get_inventory_capacity(db, guild) - used_now)
            if remaining_capacity <= 0:
                continuous_pause_today = True
            for family in sorted(continuous_families):
                if remaining_capacity <= 0:
                    continuous_pause_today = True
                    break
                requested = offline_seconds // 60
                if integrate_item_sources:
                    template = _material_template(db, family, guild.level)
                    stored, _ = add_inventory_quantity_capped(db, guild, template.id, requested) if template else (0, requested)
                    material_balance = _inventory_material_balance(db, guild, resources)
                else:
                    stored, _ = gather_with_capacity(
                        material_balance, family=family, requested=requested,
                        free_capacity=remaining_capacity, worker_count=1,
                        offline_seconds=offline_seconds,
                    )
                gathered_today[family] += stored
                current_used = inventory_used()
                inventory_peak_used = max(inventory_peak_used, current_used)
                remaining_capacity -= stored
                if stored < requested:
                    continuous_pause_today = True

        # If the next queued purchase is already cash-affordable, use the
        # existing gathering rule for missing building materials during the
        # offline interval. It is one unit/minute, one worker per family, and
        # every stored unit shares the service's inventory cap.
        next_step = _next_purchase(strategy, len(roster), buildings)
        if next_step:
            item, building = next_step
            if item == "apprentice_hire":
                quote_gold = get_discounted_hire_cost(
                    int(tavern_state.current_apprentice_hire_cost),
                    int(get_tavern_apprentice_chances(buildings["tavern"].level, config)["hire_discount_percent"]),
                )
                quote_materials = {name: 0 for name in MATERIALS}
                level_ok = True
            else:
                assert building is not None
                quote = get_upgrade_cost(building)
                quote_gold = int(quote["gold"])
                quote_materials = {name: int(quote[name]) for name in BUILDING_MATERIALS}
                quote_materials.update({"leather": 0})
                level_ok = guild.level >= _required_level(building)
            if level_ok and resources.gold >= quote_gold:
                offline_seconds = credited_offline_seconds
                workers_available = max(0, len(roster) - len(continuous_families))
                for family in BUILDING_MATERIALS:
                    if integrate_item_sources:
                        material_balance = _inventory_material_balance(db, guild, resources)
                    missing = max(0, quote_materials[family] - material_balance[family])
                    if not missing or workers_available <= 0:
                        continue
                    capacity = get_inventory_capacity(db, guild)
                    used = inventory_used()
                    if integrate_item_sources and family in GATHERABLE_MATERIALS:
                        template = _material_template(db, family, guild.level)
                        stored, _discarded = add_inventory_quantity_capped(
                            db, guild, template.id, min(missing, offline_seconds // 60),
                        ) if template else (0, missing)
                        material_balance = _inventory_material_balance(db, guild, resources)
                    else:
                        stored, _ = gather_with_capacity(
                            material_balance, family=family, requested=missing,
                            free_capacity=capacity - used,
                            worker_count=1, offline_seconds=offline_seconds,
                        )
                    # Different families can be gathered in parallel by distinct
                    # workers. Current requirement set never exceeds 3 families.
                    if stored:
                        gathered_today[family] += stored
                        inventory_peak_used = max(inventory_peak_used, inventory_used())
                        recovery_actions.append({
                            "day": day, "source": "assigned_gathering", "family": family,
                            "stored": stored, "inventory_used": inventory_used(),
                        })
                        workers_available -= 1

        # Buy the next policy item only at its exact service quote. Continue
        # immediately if a previous purchase unlocked another affordable step.
        while True:
            next_step = _next_purchase(strategy, len(roster), buildings)
            if next_step is None:
                break
            item, building = next_step
            if item == "apprentice_hire":
                chances = get_tavern_apprentice_chances(buildings["tavern"].level, config)
                quote_gold = get_discounted_hire_cost(int(tavern_state.current_apprentice_hire_cost),
                                                      int(chances["hire_discount_percent"]))
                quote_materials = {name: 0 for name in MATERIALS}
                level_ok = True
            else:
                assert building is not None
                quote = get_upgrade_cost(building)
                quote_gold = int(quote["gold"])
                quote_materials = {name: int(quote[name]) for name in BUILDING_MATERIALS}
                quote_materials.update({"leather": 0})
                level_ok = guild.level >= _required_level(building)
            if integrate_item_sources:
                material_balance = _inventory_material_balance(db, guild, resources)
            if not level_ok or resources.gold < quote_gold or any(
                material_balance[name] < quote_materials.get(name, 0) for name in BUILDING_MATERIALS
            ):
                break
            before = int(resources.gold)
            if item == "apprentice_hire":
                hire(day)
            else:
                assert building is not None
                resources.gold -= quote_gold
                for name in BUILDING_MATERIALS:
                    if integrate_item_sources:
                        consumed = consume_inventory_resource(db, resources, name, quote_materials[name])
                        if not consumed:
                            raise AssertionError(f"Service inventory could not pay {name} for {item}")
                    else:
                        material_balance[name] -= quote_materials[name]
                    materials_spent_today[name] += quote_materials[name]
                if integrate_item_sources:
                    material_balance = _inventory_material_balance(db, guild, resources)
                building.level += 1
                add_guild_xp(guild, 10)
                purchase_sequence += 1
                cumulative_spend += quote_gold
                purchase_rows.append({"step": purchase_sequence, "item": f"{building.building_template.effect_type}_{building.level}",
                                      "day": day, "gold_cost": quote_gold,
                                      "material_cost": quote_materials,
                                      "gold_balance_before": before, "affordable_at_purchase": True,
                                      "balance_after": balance_snapshot()})
            if before - int(resources.gold) != quote_gold:
                raise AssertionError("Purchase ledger does not match the charged service quote")

        next_req = _next_step_quote(strategy, len(roster), buildings, guild, db, tavern_state, config)
        if integrate_item_sources:
            material_balance = _inventory_material_balance(db, guild, resources)
        if next_req is not None:
            next_req["gold_balance"] = int(resources.gold)
            next_req["gold_shortfall"] = max(0, int(next_req["gold_cost"]) - int(resources.gold))
            next_req["guild_level_current"] = int(guild.level)
            next_req["guild_level_shortfall"] = max(0, int(next_req["guild_level_required"]) - int(guild.level))
            next_req["material_balance"] = dict(material_balance)
            next_req["material_shortfalls"] = {
                family: max(0, int(next_req["material_cost"].get(family, 0)) - int(material_balance[family]))
                for family in MATERIALS
            }
        day_gold.append({"day": day, "contract_gold": gold_today, "offline_gold": passive_gold,
                         "sink_paid_gold": sink_paid_today, "sink_due_gold": sink_due_today,
                         "sink_unpaid_gold": sink_unpaid_today,
                         "spent_gold": start_gold_day + gold_today + passive_gold - int(resources.gold),
                         "balance_gold": int(resources.gold),
                         "guild_level": guild.level, "roster_size": len(roster),
                         "active_roster_size": active_roster_size,
                         "action_count": action_count_today,
                         "continuous_gathering_pause": continuous_pause_today,
                         "materials_gathered": gathered_today,
                         "materials_spent": materials_spent_today,
                         "materials_balance": dict(material_balance),
                         "mission_material_drop_rolls": material_drop_rolls_today,
                         "mission_material_drop_awards": material_drop_awards_today,
                         "mission_material_drop_stored_today": material_drop_stored_today,
                         "mission_material_drop_discarded_today": material_drop_discarded_today,
                         "mission_material_drop_route_families": sorted(material_drop_route_families_today),
                         "inventory_peak_used": inventory_peak_used,
                         "inventory_used": inventory_used(),
                         "inventory_capacity": get_inventory_capacity(db, guild),
                         "next_purchase_requirements": next_req,
                         "gather_workers_available": max(0, len(roster) - len(continuous_families)),
                         "gather_seconds_available": credited_offline_seconds,
                         "offline_crystals_earned": offline_crystals_earned,
                         "scouts_level": buildings["scouts"].level,
                         "dungeon_gate_open": first_dungeon_gate_day is not None,
                         "first_dungeon_offer_seen": first_dungeon_offer_day == day,
                         **stamina_day})
        if action_count_today == 0:
            actionless_days += 1
        if continuous_pause_today:
            collection_paused_days += 1
        if guild.level >= 50 and level50_day is None:
            level50_day = day
        if integrate_item_sources and strategy.get("include_scouts_objective") and buildings["scouts"].level >= 1:
            dungeon_party_size = _simulated_party_size(strategy["party_size"], active_roster_size)
            dungeon_party_min_level = _roster_party_minimum_level(
                roster, dungeon_party_size, active_count=active_roster_size,
            )
            gate_open = any(
                int(template.required_guild_level) <= guild.level
                and int(template.required_min_mercenary_level) <= dungeon_party_min_level
                and int(template.min_party_size) <= dungeon_party_size <= int(template.max_party_size)
                for template in dungeon_templates
            )
            if gate_open:
                first_dungeon_gate_day = first_dungeon_gate_day or day
        if level50_day is not None and day >= level50_day + 13:
            break

    days_elapsed = day_gold[-1]["day"] if day_gold else 0
    last14 = day_gold[-14:]
    tail_net = sum(row["contract_gold"] + row["offline_gold"] - row["spent_gold"] for row in last14)
    late_net = tail_net if level50_day is not None else None
    earned_total = sum(gold_sources.values())
    capacity = get_inventory_capacity(db, guild)
    final_balance = (_balance_snapshot_live(db, guild, resources.gold, resources) if integrate_item_sources
                     else _balance_snapshot(resources.gold, material_balance, capacity))
    dominant = max(gold_sources, key=gold_sources.get) if gold_sources else "none"
    next_step = _next_purchase(strategy, len(roster), buildings)
    next_purchase_block = None
    if next_step is not None:
        item, building = next_step
        if item == "apprentice_hire":
            quote_gold = get_discounted_hire_cost(
                int(tavern_state.current_apprentice_hire_cost),
                int(get_tavern_apprentice_chances(buildings["tavern"].level, config)["hire_discount_percent"]),
            )
            quote_materials = {name: 0 for name in MATERIALS}
            required_level = guild.level
        else:
            assert building is not None
            quote = get_upgrade_cost(building)
            quote_gold = int(quote["gold"])
            quote_materials = {name: int(quote[name]) for name in BUILDING_MATERIALS}
            quote_materials.update({"leather": 0})
            required_level = _required_level(building)
        next_purchase_block = {
            "item": item if building is None else f"{building.building_template.effect_type}_{building.level + 1}",
            "gold_cost": quote_gold, "gold_balance": int(resources.gold),
            "gold_shortfall": max(0, quote_gold - int(resources.gold)),
            "guild_level_required": required_level, "guild_level_current": guild.level,
            "material_cost": quote_materials,
            "material_shortfalls": {name: max(0, quote_materials[name] - material_balance[name]) for name in MATERIALS},
            "inventory_capacity": capacity, "inventory_used": sum(material_balance.values()),
        }
    target_plan_complete = (
        len(roster) >= int(strategy["roster_target"])
        and buildings["contract_office"].level >= int(strategy.get("office_target", 1))
        and buildings["training_ground"].level >= 1
        and (not strategy.get("include_scouts_objective") or buildings["scouts"].level >= 1)
    )
    failure_events = []
    if level50_day is None:
        failure_events.append("level_50_horizon_timeout")
    if not target_plan_complete:
        failure_events.append("investment_target_incomplete_at_horizon")
    if next_purchase_block and next_purchase_block["material_shortfalls"].get("crystals", 0):
        failure_events.append("unobtainable_crystal_requirement_on_selected_gathering_path")
    if collection_paused_days:
        failure_events.append("warehouse_capacity_paused_gathering")
    return {
        "strategy": strategy["name"], "path_variant": strategy.get("path_variant", "roster_first"),
        "seed": seed, "status": "level_50" if level50_day else "horizon_limit",
        "sink_policy": sink_policy,
        "level_50_day": level50_day, "days_simulated": days_elapsed, "final_guild_level": guild.level,
        "online_hours_per_day": strategy["online_hours"],
        "offline_credited_hours_per_day": daily_offline_seconds(float(strategy["online_hours"])) / 3600,
        "offline_credited_hours_per_day_mean": median([float(row["offline_credited_hours"]) for row in day_gold]) if day_gold else 0,
        "offline_stamina_hours_at_end": offline_stamina_hours,
        "offline_stamina_restored_hours_per_return": offline_stamina_restored(float(strategy["online_hours"])) if strategy["name"] == "offline" else None,
        "starting_gold": 100, "gold_after_minimum_setup": start_gold,
        "purchase_count_after_start": len(purchase_rows) - 3, "purchases": purchase_rows,
        "gold_sources": gold_sources, "dominant_gold_activity": dominant,
        "sink_paid_gold": sink_paid_total, "sink_due_gold": sink_due_total,
        "sink_unpaid_gold": sink_unpaid_total,
        "dominant_activity_share_percent": round(100 * max(gold_sources.values(), default=0) / max(1, earned_total), 2),
        "balances_at_end": final_balance,
        "late_game_last_14_day_net_gold_surplus_deficit": int(late_net) if late_net is not None else None,
        "terminal_last_14_day_net_gold_surplus_deficit": int(tail_net),
        "late_game_status": ("surplus" if late_net > 0 else "deficit" if late_net < 0 else "balanced") if late_net is not None else "level_50_not_reached",
        "actions": actions, "successes": successes, "blocked_windows": blocked_reason_counts,
        "target_plan_complete": target_plan_complete,
        "failure_events": failure_events,
        "modeled_no_route_stall_14d_observed": modeled_no_route_stall(
            day_gold, window_days=SOFTLOCK_OBSERVATION_WINDOW_DAYS),
        "hard_economic_softlock_status": "not_measured",
        "softlock_interpretation": (
            "This integrated slice samples actual seeded home boards, mission success and material/equipment drops, gathers wood/ore/leather with live inventory capacity and consumes materials through live resource-family mappings. It still excludes mission rerolls/skills/professions, market/salvage transactions, completed dungeon reward/drop logic, and regional event progression; whole-game hard softlock remains not measured."
            if integrate_item_sources else
            "The model can detect only a 14-day no-route stall of its finite next purchase path. It cannot establish a whole-game hard economic softlock rate because real mission execution, recruitment RNG, item/material drops and sales, equipment, dungeons, events and other progression routes are abstracted or excluded."
        ),
        "actionless_days": actionless_days,
        "continuous_gathering_capacity_paused_days": collection_paused_days,
        "total_purchase_gold": cumulative_spend,
        "next_purchase_block": next_purchase_block,
        "gold_balance_at_last_day_start": day_gold[-1]["balance_gold"] if day_gold else start_gold,
        "daily_ledger": day_gold,
        "first_gear_drop_day": first_gear_day if integrate_item_sources else None,
        "first_dungeon_gate_open_day": first_dungeon_gate_day if integrate_item_sources else None,
        "first_dungeon_board_offer_day": first_dungeon_offer_day if integrate_item_sources else None,
        "realized_gear_drops": realized_gear_drops if integrate_item_sources else [],
        "material_drop_roll_count": material_drop_roll_count if integrate_item_sources else 0,
        "material_drop_award_count": material_drop_award_count if integrate_item_sources else 0,
        "material_drop_stored_total": material_drop_stored_total if integrate_item_sources else 0,
        "material_drop_discarded_total": material_drop_discarded_total if integrate_item_sources else 0,
        "recovery_actions": recovery_actions if integrate_item_sources else [],
    }


def _distribution(rows: list[dict[str, object]], key: str) -> dict[str, object]:
    values = sorted(float(row[key]) for row in rows if row.get(key) is not None)
    if not values:
        return {"n": 0, "min": None, "p50": None, "max": None}
    return {"n": len(values), "min": values[0], "p50": median(values), "max": values[-1]}


def _median_ci(rows: list[dict[str, object]], key: str, *, seed: int) -> dict[str, object]:
    return bootstrap_median_ci_95(
        [float(row[key]) for row in rows if row.get(key) is not None], seed=seed,
    )


def run_funded_simulation(*, runs_per_strategy: int = 10, seed_start: int = 2026102900,
                          max_days: int = MAX_DAYS,
                          strategy_names: list[str] | None = None,
                          path_variant: str = "roster_first",
                          integrate_item_sources: bool = False,
                          include_scouts_objective: bool = False,
                          sink_policy: dict[str, object] | None = None) -> dict[str, object]:
    """Run trajectories on a disposable on-disk SQLite database."""
    with TemporaryDirectory(prefix="gim-funded-progression-") as temp_dir:
        database_path = Path(temp_dir) / "funded-stage5.sqlite3"
        engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with factory() as db:
                apply_initial_campaign_content(db)
                db.commit()
                if path_variant not in {"roster_first", "office_after_minimum_party"}:
                    raise ValueError(f"Unknown funded path variant: {path_variant}")
                selected = [(index, {**strategy, "path_variant": path_variant,
                                     "include_scouts_objective": include_scouts_objective})
                            for index, strategy in enumerate(STRATEGIES)
                            if strategy_names is None or strategy["name"] in strategy_names]
                if strategy_names is not None and {strat["name"] for _, strat in selected} != set(strategy_names):
                    raise ValueError("Unknown strategy name in strategy_names")
                trajectories = []
                for strategy_index, strategy in selected:
                    for run_index in range(runs_per_strategy):
                        seed = seed_start + strategy_index * 100_000 + run_index
                        trajectories.append(_run_trajectory(
                            db, strategy, seed, run_index, max_days=max_days,
                            sink_policy=sink_policy, integrate_item_sources=integrate_item_sources,
                        ))
                        db.rollback()
                by_strategy = {}
                modeled_milestones = ("apprentice_2", "housing_2", "contract_office_1", "training_ground_1")
                for strategy_index, strategy in selected:
                    rows = [row for row in trajectories if row["strategy"] == strategy["name"]]
                    purchases: dict[str, list[int]] = {}
                    for row in rows:
                        for purchase in row["purchases"]:
                            purchases.setdefault(str(purchase["item"]), []).append(int(purchase["day"]))
                    reached50 = sum(row["level_50_day"] is not None for row in rows)
                    completed = sum(bool(row["target_plan_complete"]) for row in rows)
                    timeouts = sum(row["level_50_day"] is None for row in rows)
                    modeled_stalls = sum(row["modeled_no_route_stall_14d_observed"] is True for row in rows)
                    stall_sample = sum(row["modeled_no_route_stall_14d_observed"] is not None for row in rows)
                    paused_runs = sum(row["continuous_gathering_capacity_paused_days"] > 0 for row in rows)
                    actionless_runs = sum(row["actionless_days"] > 0 for row in rows)
                    milestone_stats = {}
                    for milestone_index, milestone in enumerate(modeled_milestones):
                        entries = [next((purchase for purchase in row["purchases"]
                                         if purchase["item"] == milestone), None) for row in rows]
                        bought = [entry for entry in entries if entry is not None]
                        base_seed = seed_start + strategy_index * 1_000_000 + milestone_index * 100_000
                        milestone_stats[milestone] = {
                            "purchased": len(bought),
                            "purchase_rate_wilson_95": wilson_interval_95(len(bought), len(rows)),
                            "day_median_ci_95": bootstrap_median_ci_95(
                                [float(entry["day"]) for entry in bought], seed=base_seed + 1),
                            "gold_cost_median_ci_95": bootstrap_median_ci_95(
                                [float(entry["gold_cost"]) for entry in bought], seed=base_seed + 2),
                            "material_cost_median_ci_95": {
                                family: bootstrap_median_ci_95(
                                    [float(entry["material_cost"].get(family, 0)) for entry in bought],
                                    seed=base_seed + 3 + material_index,
                                ) for material_index, family in enumerate(MATERIALS)
                            },
                        }
                    gathered_totals = {
                        family: [sum(int(day["materials_gathered"][family]) for day in row["daily_ledger"])
                                 for row in rows] for family in GATHERABLE_MATERIALS
                    }
                    spent_totals = {
                        family: [sum(int(day["materials_spent"][family]) for day in row["daily_ledger"])
                                 for row in rows] for family in MATERIALS
                    }
                    by_strategy[strategy["name"]] = {
                        "policy": strategy,
                        "sink_policy": sink_policy,
                        "trajectories": len(rows),
                        "level_50_reached": reached50,
                        "level_50_reached_wilson_95": wilson_interval_95(reached50, len(rows)),
                        "level_50_day_distribution": _distribution(rows, "level_50_day"),
                        "level_50_day_median_ci_95": _median_ci(rows, "level_50_day", seed=seed_start + strategy_index * 1_000_000 + 1),
                        "offline_credited_hours_per_day_mean_ci_95": bootstrap_median_ci_95(
                            [float(row["offline_credited_hours_per_day_mean"]) for row in rows],
                            seed=seed_start + strategy_index * 1_000_000 + 6),
                        "final_guild_level_distribution": _distribution(rows, "final_guild_level"),
                        "investment_target_completed": completed,
                        "investment_target_completed_wilson_95": wilson_interval_95(completed, len(rows)),
                        "level_50_timeout_wilson_95": wilson_interval_95(timeouts, len(rows)),
                        "modeled_no_route_stall_14d": {
                            "events": modeled_stalls, "observed_n": stall_sample,
                            "rate_wilson_95": wilson_interval_95(modeled_stalls, stall_sample),
                            "definition": "A blocked next mandatory purchase persists for 14 consecutive simulated days with no modeled gold, material or XP route that can recover its shortfalls.",
                            "whole_game_hard_softlock_status": "not_measured",
                        },
                        "capacity_pause_incidence_wilson_95": wilson_interval_95(paused_runs, len(rows)),
                        "actionless_run_incidence_wilson_95": wilson_interval_95(actionless_runs, len(rows)),
                        "modeled_milestones": milestone_stats,
                        "failure_event_counts": {
                            event: sum(event in row["failure_events"] for row in rows)
                            for event in sorted({event for row in rows for event in row["failure_events"]})
                        },
                        "actionless_days_distribution": _distribution(rows, "actionless_days"),
                        "continuous_gathering_capacity_paused_days_distribution": _distribution(
                            rows, "continuous_gathering_capacity_paused_days"),
                        "ending_gold_distribution": _distribution(
                            [{"gold": row["balances_at_end"]["gold"]} for row in rows], "gold"),
                        "ending_gold_median_ci_95": bootstrap_median_ci_95(
                            [float(row["balances_at_end"]["gold"]) for row in rows],
                            seed=seed_start + strategy_index * 1_000_000 + 2),
                        "late_game_last_14_day_net_gold_distribution": _distribution(
                            [{"net": row["late_game_last_14_day_net_gold_surplus_deficit"]} for row in rows], "net"),
                        "late_game_net_14d_median_ci_95": bootstrap_median_ci_95(
                            [float(row["late_game_last_14_day_net_gold_surplus_deficit"]) for row in rows
                             if row["late_game_last_14_day_net_gold_surplus_deficit"] is not None],
                            seed=seed_start + strategy_index * 1_000_000 + 3),
                        "total_purchase_gold_median_ci_95": bootstrap_median_ci_95(
                            [float(row["total_purchase_gold"]) for row in rows],
                            seed=seed_start + strategy_index * 1_000_000 + 4),
                        "materials_gathered_median_ci_95": {
                            family: bootstrap_median_ci_95(values, seed=seed_start + strategy_index * 1_000_000 + 10 + i)
                            for i, (family, values) in enumerate(gathered_totals.items())
                        },
                        "materials_spent_median_ci_95": {
                            family: bootstrap_median_ci_95(values, seed=seed_start + strategy_index * 1_000_000 + 20 + i)
                            for i, (family, values) in enumerate(spent_totals.items())
                        },
                        "warehouse_pause_days_median_ci_95": _median_ci(
                            rows, "continuous_gathering_capacity_paused_days", seed=seed_start + strategy_index * 1_000_000 + 5),
                        "terminal_last_14_day_net_gold_distribution": _distribution(
                            [{"net": row["terminal_last_14_day_net_gold_surplus_deficit"]} for row in rows], "net"),
                        "purchases": {
                            item: {"purchased_in_runs": len(days), "day_distribution": {
                                "min": min(days), "p50": median(days), "max": max(days)}}
                            for item, days in sorted(purchases.items())
                        },
                        "dominant_activity": max(
                            (row["dominant_gold_activity"] for row in rows),
                            key=lambda item: sum(r["dominant_gold_activity"] == item for r in rows),
                        ) if rows else None,
                        "dominant_activity_share_percent_p50": median(
                            [float(row["dominant_activity_share_percent"]) for row in rows]) if rows else 0,
                        "final_material_balances_p50": {
                            family: median([int(row["balances_at_end"]["materials"][family]) for row in rows])
                            for family in MATERIALS
                        },
                        "final_inventory_capacity_p50": median(
                            [int(row["balances_at_end"]["inventory_capacity"]) for row in rows]) if rows else 0,
                        "peak_inventory_use_distribution": _distribution(
                            [{"peak": max((int(day["inventory_peak_used"]) for day in row["daily_ledger"]), default=0)}
                             for row in rows], "peak"),
                        "raw_trajectory_ids": [row["seed"] for row in rows],
                    }
                return {
                    "report_id": "gim-funded-upgrade-trajectories-20261029-confidence-v2",
                    "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "database": "temporary on-disk SQLite created under TemporaryDirectory and removed after run",
                    "source": {
                        "funded_simulator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        "live_catalog_version": PACK_VERSION,
                    },
                    "runs_per_strategy": runs_per_strategy, "seed_start": seed_start,
                    "seed_end": seed_start + max(index for index, _ in selected) * 100_000 + runs_per_strategy - 1,
                    "rules": {
                        "fresh_save_starting_gold": 100,
                        "minimum_setup": "Tavern 1 + Housing 1 + first Apprentice; exact service costs total 70 gold",
                        "upgrade_policy": ("roster_first: start at fresh-save minimum, buy Housing/hire until profile roster target, then Contract Office to target, then Training Ground 1; office_after_minimum_party: first reach profile party size, upgrade Office to target, finish profile roster, then Training Ground 1. All purchases use live service requirements; no discretionary reserve or recurring cost is invented."),
                        "active_income": "Real service-materialized regional home boards; actual snapshot chances, durations, XP, and gold, with current Contract Office reward and Training Ground XP formulas applied per successful/failed action.",
                        "offline_income": "get_passive_gold_rate() service formula, credited daily for min(absent time, OFFLINE_CAP_SECONDS); no ordinary offline materials. A completed 8h credit grants at most one special crystal per return in the live service, but crystals do not fund this policy path.",
                        "offline_stamina": "Persistent balance starts full at 8h. Each day, online hours restore 2h/hour up to the 8h cap; the following absence consumes up to min(absence, 8h cap, current balance). For the 2h/day casual profile, day one credits 8h, then each return restores and credits 4h. Other profiles with at least 4h online restore the full 8h task budget daily. For the offline profile, this daily ledger rule is paired with the existing 8h pre-absence dispatch (one offer/team), then 4h remaining in the current 6h board and 4h in the next board on return. This is a board-window abstraction, not a second-by-second ClockGuard playthrough.",
                        "gathering": "Existing base service rate 1 unit/minute per assigned worker, one worker per wood/ore/leather family, constrained by live get_inventory_capacity() and shared by all materials. Producer keeps three persistent assignments; other profiles temporarily assign available workers to gather materials required by the next gold-affordable building upgrade. No random profession bonus is assumed.",
                        "activity_selection": "Greedy highest expected guild-XP/hour contract on each real regional board, subject to modeled daily player hours, team count, current roster and Office party-size cap.",
                        "statistical_method": "Wilson score 95% intervals for binary rates; deterministic nonparametric percentile bootstrap 95% intervals for medians (3,000 resamples; seed derived from report seed, profile, metric).",
                        "softlock_measurement": "A narrow model-observable 14-day no-route stall checks the daily next-purchase requirement snapshot, live gold inputs credited by the model, gathered-material routes with an available worker and free shared warehouse capacity, and action/XP availability. Whole-game hard economic softlock remains not measured because several real progression and reward paths are omitted.",
                        "modeled_milestones": ["second apprentice hire", "Housing level 2", "Contract Office level 1", "Training Ground level 1"],
                        "not_modeled_milestones": {
                            "first_equipment": "Equipment production/drop and equipment use are not simulated.",
                            "first_dungeon": "Dungeon entry, execution and rewards are excluded.",
                            "first_regional_event": "Portal/rebellion timing and rewards are excluded from funded trajectories.",
                        },
                        "excluded": ["random recruitment attributes and equipment", "market sales and dock arbitrage", "crafting/refinement/salvage", "portal loot", "rebellion rewards", "any recurring upkeep", "other players or multiplayer effects"],
                        "design_choices_left_open": ["whether these roster targets and purchase priorities represent intended player behavior", "whether materials should be actively gathered or sourced from drops", "whether optional upgrades should preserve a cash reserve", "whether to approve any recurring sink", "acceptable confidence-bound thresholds and final Stage 5 sample size"],
                        "infinite_economy_status": "Not demonstrated. With no approved recurring sink, this simulation reports endgame surplus after its finite purchase policy. A sink must remain a separate design decision and was not added.",
                        "infinite_economy_options_analysis": [
                            "Keep current rules and accept accumulating gold as a consequence of no mandatory recurring sink; make optional progression purchases meaningful.",
                            "Consider an optional, explicitly priced recurring service only after a GDD decision and affordability/casual-profile simulation; do not debit resources automatically in this evidence run.",
                            "Use finite optional upgrade/crafting goals as sinks, then measure whether the endgame still accumulates surplus; this does not guarantee a bounded economy if goals are exhausted.",
                        ],
                    },
                    "strategies": by_strategy,
                    "sink_policy": sink_policy,
                    "raw_trajectories": trajectories,
                }
        finally:
            engine.dispose()


def render_markdown(report: dict[str, object]) -> str:
    def ci_text(row: dict[str, object] | None, *, precision: int = 1) -> str:
        if not row or row.get("median") is None:
            return "—"
        return (f"{row['median']:.{precision}f} "
                f"(IC95% {row['lower_95']:.{precision}f}–{row['upper_95']:.{precision}f})")

    def rate_text(row: dict[str, object] | None) -> str:
        if not row or row.get("rate_percent") is None:
            return "—"
        return f"{row['rate_percent']:.1f}% (IC95% {row['lower_percent']:.1f}–{row['upper_percent']:.1f})"

    lines = [
        "# Trajetórias financiadas de progressão econômica",
        "",
        f"Execução `{report['report_id']}` · gerada em {report['generated_at_local']}",
        "",
        f"A simulação parte de campanha nova; N={report['runs_per_strategy']} por perfil, seeds reproduzíveis de {report['seed_start']} a {report['seed_end']}. Cobra cada melhoria quando a próxima etapa está financiada. A estamina offline persistente começa em 8h, regenera 2h por hora online até 8h e é consumida pela ausência: o perfil casual recebe 8h no primeiro dia e 4h nas ausências seguintes. Os custos vêm dos serviços atuais; a renda usa boards regionais materializados pelo serviço e a fórmula do serviço offline. Compras e execução de atividades são simuladas, não executadas pelo serviço final nem em playthrough do cliente. O SQLite temporário é removido ao terminar.",
        "",
        *( [f"**Nota de revisão:** {report['analysis_refresh']['supersedes']} ", ""] if report.get("analysis_refresh", {}).get("supersedes") else [] ),
        "## Cenários",
        "",
        "| Perfil | Presença modelada | Roster alvo | Nível 50 | Dia p50 | Nível final p50 | Ouro final p50 | Saldo líquido 14d após nível 50 p50 | Fonte de ouro dominante | Parcela p50 | Estoque final p50 (madeira/minério/couro/cristais) | Pico/capacidade p50 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|",
    ]
    for name, row in report["strategies"].items():
        timing = row["level_50_day_distribution"]["p50"]
        ending = row["ending_gold_distribution"]["p50"]
        late = row["late_game_last_14_day_net_gold_distribution"]["p50"]
        mats = row["final_material_balances_p50"]
        late_display = f"{late:,.0f}" if late is not None else "— (não chegou ao 50)"
        peak = row["peak_inventory_use_distribution"]["p50"]
        capacity = row["final_inventory_capacity_p50"]
        policy = row["policy"]
        presence = ("8h dispatch + 4h/4h retorno" if name == "offline"
                    else "2h/dia; crédito 8h→4h" if name == "casual"
                    else f"{policy['online_hours']}h/dia")
        lines.append(
            f"| {name} | {presence} | {policy['roster_target']} | {row['level_50_reached']}/{row['trajectories']} | "
            f"{timing if timing is not None else '—'} | {row['final_guild_level_distribution']['p50']:,.0f} | {ending:,.0f} | {late_display} | {row['dominant_activity']} | "
            f"{row['dominant_activity_share_percent_p50']:.1f}% | {mats['wood']:,.0f}/{mats['ore']:,.0f}/{mats['leather']:,.0f}/{mats['crystals']:,.0f} | {peak:,.0f}/{capacity:,.0f} |"
        )
    lines.extend(["", "## Intervalos de confiança de 95%", "", "Wilson score para taxas binárias; bootstrap percentil determinístico (3.000 reamostragens) para medianas. ICs descrevem apenas a variação entre seeds deste modelo.", "", "| Perfil | Crédito offline médio (h/dia; IC95%) | N50 sucesso (IC95%) | Conclui plano (IC95%) | Timeout L50 (IC95%) | Pausa de coleta (IC95%) | Mediana dias até L50 (IC95%) | Mediana ouro líquido 14d late (IC95%) |", "|---|---|---|---|---|---|---|---|"])
    for name, row in report["strategies"].items():
        lines.append(
            f"| {name} | {ci_text(row['offline_credited_hours_per_day_mean_ci_95'])} | "
            f"{rate_text(row['level_50_reached_wilson_95'])} | "
            f"{rate_text(row['investment_target_completed_wilson_95'])} | "
            f"{rate_text(row['level_50_timeout_wilson_95'])} | "
            f"{rate_text(row['capacity_pause_incidence_wilson_95'])} | "
            f"{ci_text(row['level_50_day_median_ci_95'])} | {ci_text(row['late_game_net_14d_median_ci_95'], precision=0)} |"
        )
    lines.extend(["", "## Bloqueio econômico observável no modelo", "", "Definição operacional: uma compra obrigatória permanece bloqueada por 14 dias simulados seguidos e, nesse intervalo, não há fonte de ouro creditada, coleta possível para materiais faltantes (requer trabalhador livre e espaço no Armazém) nem ação que dê XP para cumprir requisito de nível. Conclusão do plano finito encerra a observação. Isso mede uma parada da rota modelada, não todo softlock econômico do jogo; por ausência de execução real, recrutamento RNG, drops/vendas e outras rotas, a taxa geral de hard softlock é **indeterminada / não mensurada**.", "", "| Perfil | Stalls sem rota 14d (observados/N; IC95%) | Hard softlock do jogo | Timeout separado |", "|---|---|---|---:|"])
    for name, row in report["strategies"].items():
        stall = row["modeled_no_route_stall_14d"]
        lines.append(
            f"| {name} | {stall['events']}/{stall['observed_n']}; {rate_text(stall['rate_wilson_95'])} | "
            f"não mensurado | {row['failure_event_counts'].get('level_50_horizon_timeout', 0)}/{row['trajectories']} |"
        )
    lines.extend(["", "## Marcos de progressão medidos e custos", "", "Segundo Aprendiz, Alojamento 2 (primeira melhoria após o setup mínimo), Office 1 e Campo de Treino 1 são observáveis na rota financiada. Custos são cotações determinísticas dos serviços; IC do tempo representa variação entre seeds. Equipamento, primeira masmorra e primeiro evento regional não são modelados por esta simulação.", "", "| Perfil | Marco | Compra/total (IC95%) | Dia mediano (IC95%) | Ouro mediano (IC95%) | Madeira / minério / cristais |", "|---|---|---|---|---|---|"])
    for name, row in report["strategies"].items():
        for milestone, stats in row["modeled_milestones"].items():
            materials = []
            for family in ("wood", "ore", "crystals"):
                cost = stats["material_cost_median_ci_95"][family]
                materials.append(ci_text(cost, precision=0))
            lines.append(
                f"| {name} | {milestone} | {stats['purchased']}/{row['trajectories']}; "
                f"{rate_text(stats['purchase_rate_wilson_95'])} | {ci_text(stats['day_median_ci_95'])} | "
                f"{ci_text(stats['gold_cost_median_ci_95'], precision=0)} | "
                + " / ".join(materials) + " |"
            )
    lines.extend(["", "## Pressão de materiais", "", "Os totais acumulados usam coleta modelada de 1 unidade/minuto e Armazém compartilhado. Intervalos são IC95% bootstrap da mediana por seed; couro não entra nos custos atuais dos prédios-alvo.", "", "| Perfil | Madeira coletada / gasta | Minério coletado / gasto | Couro coletado / gasto | Incidência de pausa do Armazém (IC95%) | Dias pausados p50 (IC95%) | Pico/capacidade p50 |", "|---|---|---|---|---|---|---|"])
    for name, row in report["strategies"].items():
        gathered, spent = row["materials_gathered_median_ci_95"], row["materials_spent_median_ci_95"]
        mats = [f"{ci_text(gathered[f], precision=0)} / {ci_text(spent[f], precision=0)}" for f in GATHERABLE_MATERIALS]
        peak = row["peak_inventory_use_distribution"]["p50"]
        cap = row["final_inventory_capacity_p50"]
        lines.append(f"| {name} | " + " | ".join(mats) + f" | {rate_text(row['capacity_pause_incidence_wilson_95'])} | {ci_text(row['warehouse_pause_days_median_ci_95'], precision=0)} | {peak:,.0f}/{cap:,.0f} |")
    lines.extend(["", "## Compra e desbloqueio", "", "| Estratégia | Item | Comprado em trajetórias | Dia p50 (min–máx) |", "|---|---|---:|---:|"])
    for name, row in report["strategies"].items():
        for item, purchase in row["purchases"].items():
            timing = purchase["day_distribution"]
            lines.append(f"| {name} | {item} | {purchase['purchased_in_runs']}/{row['trajectories']} | {timing['p50']} ({timing['min']}–{timing['max']}) |")
    lines.extend([
        "", "## Leitura e limites", "",
        "O saldo líquido de fim de jogo cobre 14 dias depois de alcançar nível 50; trajetórias que não chegaram ao 50 mantêm o saldo terminal no JSON. O saldo líquido considera contratos regionais e renda passiva menos compras. O produtor mantém até três trabalhadores em madeira/minério/couro; outros perfis atribuem trabalhadores temporariamente quando faltam materiais para a próxima melhoria financiável. Todas as famílias compartilham o limite do Armazém; cristais não são coletáveis por trabalhadores. A parcela dominante compara somente as fontes de ouro incluídas.",
        "",
        "Os preços vêm de `get_upgrade_cost`, `get_discounted_hire_cost` e `next_apprentice_cost`; a renda passiva usa `get_passive_gold_rate`; ofertas e recompensas vêm dos boards regionais seedados. A simulação não altera serviço, preço, chance, regra de offline ou custo recorrente.",
        "",
        "Stage 5 permanece aberto: metas de roster, Office e horários são hipóteses. A taxa de hard economic softlock do jogo não é mensurada; a coluna de stall cobre somente a rota modelada e a janela explícita de 14 dias. Timeouts são exibidos separadamente. O saldo segue positivo após as compras previstas; sem sink recorrente aprovado, ‘sem economia infinita’ não foi demonstrado. Equipamento, primeira masmorra e primeiro evento permanecem fora da trajetória financiada. Opções para discutir sem ativar regra: (1) aceitar acumulação após metas opcionais; (2) deliberar serviço opcional recorrente e testar acessibilidade; (3) ampliar objetivos opcionais de progresso/crafting e medir o saldo após esgotá-los.",
        "",
        "## Reprodução",
        "",
        "```powershell",
        "$env:APP_MODE = 'desktop'",
        f".venv\\Scripts\\python.exe scripts\\balance\\audit_funded_progression.py --runs-per-strategy {report['runs_per_strategy']} --seed-start {report['seed_start']}",
        ".venv\\Scripts\\python.exe -m unittest tests.test_funded_progression_simulation -v",
        "```",
        "",
        "O JSON adjacente contém a configuração, seeds e ledger diário integral de cada trajetória.",
        "",
    ])
    return "\n".join(lines)
