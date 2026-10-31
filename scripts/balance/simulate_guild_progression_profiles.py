"""Deterministic-seed estimate of campaign guild progression through guild level 50.

Recreate a seeded in-memory database and run with:
    .venv-desktop\\Scripts\\python.exe scripts\\balance\\simulate_guild_progression_profiles.py

This is a sensitivity/economy study, not a full client or mercenary simulator. The
profile action windows and roster sizes below are explicit assumptions; rewards,
success rates, durations, and guild XP conversion are read from the live catalog
and current progression services.
"""
from __future__ import annotations

import json
import hashlib
import random
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil, comb, sqrt
from pathlib import Path
import sys
from uuid import uuid5, NAMESPACE_URL

from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.core.game_balance import GUILD_MAX_LEVEL, OFFLINE_BASE_GOLD_PER_HOUR, OFFLINE_CAP_SECONDS, REFINE_BASE_GOLD_COST, REFINE_BASE_ORE_COST
from app.models.building import BuildingTemplate
from app.models.campaign import CampaignMetadata
from app.models.crafting import CraftingRecipe, CraftingRecipeMaterial
from app.models.dock import MerchantOfferTemplate
from app.models.dungeon import DungeonTemplate
from app.models.guild import Guild
from app.models.item import ItemTemplate
from app.models.mission import MissionTemplate
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.regional import RegionalCycle, RegionalOffer, RegionalWorldState
from app.models.tavern import TavernConfig
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_KEY, PACK_VERSION
from app.services.balance_service import TAVERN_MANUAL_REFRESH_COST
from app.services.building_balance_service import (
    building_cost_factor,
    housing_capacity,
    market_values,
    required_guild_level_for_upgrade,
)
from app.services.guild_progression_service import guild_xp_required_for_level
from app.services.guild_progression_service import add_guild_xp
from app.services.progression_service import apply_levelup_attributes
from app.services.salvage_service import SALVAGE_SLOT_RULES
from app.services.tavern_service import get_discounted_hire_cost, next_apprentice_cost
from app.services.economy_pricing_service import effective_dock_unit_price, market_sale_unit_value
from app.services.regional_cycle_service import REGIONS, RANKS, _materialize_cycle


TARGET_LEVEL = 50
SEED = 20261028
CHECKPOINTS = (10, 20, 30, 40, 50)
MONTE_CARLO_RUNS = 100
SENSITIVITY_RUNS = 20
REGIONAL_CASHFLOW_RUNS = 25
REGIONAL_PROGRESSION_RUNS = 1_000
REGIONAL_PROGRESSION_MAX_DAYS = 365
REGIONAL_BOARD_FIXTURE_VERSION = "home-board-first-seed-v1"
OFFLINE_ABSENCE_HOURS = 8.0
OFFLINE_RETURN_ONLINE_HOURS = 8.0


@dataclass(frozen=True)
class Profile:
    name: str
    mode: str
    online_hours_per_day: float
    slots: int
    party_size: int
    gathering_workers: int = 0
    party_selection_policy: str = "fixed"


PROFILES = (
    Profile("ativo", "mission", 12, 3, 3, party_selection_policy="selectable"),
    Profile("casual", "mission", 2, 2, 2, party_selection_policy="selectable"),
    Profile("offline", "mission", 8, 3, 3, party_selection_policy="selectable"),
    # A five-mercenary producer roster keeps three gatherers assigned and uses
    # the remaining two for missions, which is the only current guild-XP path.
    Profile("produtor", "mission", 8, 1, 2, 3, "selectable"),
    # The official combat profile prioritizes contracts per GDD §23.
    Profile("combate", "contract_priority", 8, 3, 3, party_selection_policy="selectable"),
)


def _guild_xp_required_to(target: int) -> int:
    return sum(guild_xp_required_for_level(level) for level in range(1, target))


def _eligible_templates(db, profile: Profile, level: int):
    bands = ("1-20",) if level <= 20 else ("21-50",)
    if profile.mode == "dungeon":
        return list(db.scalars(select(DungeonTemplate).where(
            DungeonTemplate.content_pack == PACK_KEY,
            DungeonTemplate.content_type == "dungeon",
            DungeonTemplate.level_band.in_(bands),
            DungeonTemplate.is_active.is_(True),
            DungeonTemplate.required_guild_level <= level,
            DungeonTemplate.min_party_size <= profile.party_size,
            DungeonTemplate.max_party_size >= profile.party_size,
        )))
    query = select(MissionTemplate).where(
        MissionTemplate.content_pack == PACK_KEY,
        MissionTemplate.level_band.in_(bands),
        MissionTemplate.is_active.is_(True),
        MissionTemplate.required_guild_level <= level,
        MissionTemplate.min_party_size <= profile.party_size,
        MissionTemplate.max_party_size >= profile.party_size,
        MissionTemplate.mission_type != "long_idle",
    )
    if profile.mode == "gathering":
        query = query.where(MissionTemplate.mission_type == "gathering")
    else:
        query = query.where(MissionTemplate.mission_type != "gathering")
    return list(db.scalars(query))


def _expected_guild_xp_per_hour(template, party_size: int) -> float:
    base_xp = max(1, int(template.base_xp_reward))
    duration = max(1, int(template.duration_seconds))
    chance = max(0, min(100, int(template.base_success_chance))) / 100
    success_guild_xp = max(1, base_xp * party_size // 10)
    failed_mercenary_xp = max(1, base_xp // 4)
    failure_guild_xp = max(1, failed_mercenary_xp * party_size // 10)
    expected_guild_xp = chance * success_guild_xp + (1 - chance) * failure_guild_xp
    return expected_guild_xp * 3600 / duration


def _build_profile_catalog(db, profile: Profile) -> dict[int, list[object]]:
    # Catalog eligibility changes by guild-level gate, but content is static
    # during the Monte Carlo run. Cache all 1–50 states once, rather than doing
    # SQL catalog reads for every simulated day/seed.
    return {
        level: sorted(
            _eligible_templates(db, profile, level),
            key=lambda template: (-_expected_guild_xp_per_hour(template, profile.party_size), template.id),
        )
        for level in range(1, TARGET_LEVEL + 1)
    }


def _simulate_profile(
    db, profile: Profile, *, seed: int, catalog: dict[int, list[object]], hours_multiplier: float = 1.0,
    warehouse_guild_bonus_per_level: int = 0,
) -> dict[str, object]:
    rng = random.Random(seed)
    guild_level = 1
    guild_xp = 0
    total_gold = 0
    total_actions = 0
    total_failures = 0
    material_units = {"wood": 0, "ore": 0, "leather": 0}
    capacity_paused_days = 0
    day = 0
    checkpoints: dict[str, int] = {}
    max_days = 365 * 200

    while guild_level < TARGET_LEVEL and day < max_days:
        day += 1
        templates = catalog.get(guild_level, [])
        if not templates:
            return {"profile": profile.name, "status": "missing_catalog", "guild_level": guild_level,
                    "reason": f"No eligible {profile.mode} template at guild level {guild_level}."}

        # Templates were sorted by expected guild XP/hour once per profile/level.
        available_hours = profile.online_hours_per_day * hours_multiplier
        if profile.name == "offline":
            available_hours = min(available_hours, OFFLINE_CAP_SECONDS / 3600)
        slot_minutes = [0.0] * profile.slots
        while min(slot_minutes) < available_hours * 60:
            slot = min(range(profile.slots), key=lambda i: (slot_minutes[i], i))
            template = templates[0]
            duration_minutes = max(1, int(template.duration_seconds)) / 60
            if slot_minutes[slot] + duration_minutes > available_hours * 60:
                slot_minutes[slot] = available_hours * 60
                continue
            slot_minutes[slot] += duration_minutes
            total_actions += 1
            chance = max(0, min(100, int(template.base_success_chance)))
            success = rng.randrange(100) < chance
            earned_merc_xp = int(template.base_xp_reward) if success else max(1, int(template.base_xp_reward) // 4)
            # Mirrors add_guild_xp_from_mercenary_xp: floor(total mercenary XP / 10), min 1.
            guild_xp += max(1, earned_merc_xp * profile.party_size // 10)
            if success:
                total_gold += int(template.base_gold_reward)
            else:
                total_failures += 1
            while guild_level < min(TARGET_LEVEL, GUILD_MAX_LEVEL) and guild_xp >= guild_xp_required_for_level(guild_level):
                guild_xp -= guild_xp_required_for_level(guild_level)
                guild_level += 1
                if guild_level in CHECKPOINTS:
                    checkpoints[str(guild_level)] = day
                if guild_level >= TARGET_LEVEL:
                    break
        if profile.gathering_workers:
            # Current gathering rule: one base unit per worker per minute. The
            # GDD's starting 1,500 capacity is fixed; the unapproved guild bonus
            # is an explicit parameter, set only by a sensitivity scenario.
            capacity = 1500 + max(0, guild_level - 1) * warehouse_guild_bonus_per_level
            used = sum(material_units.values())
            remaining = max(0, capacity - used)
            cycles = min(remaining, int(profile.gathering_workers * available_hours * 60))
            families = ("wood", "ore", "leather")[:profile.gathering_workers]
            for index in range(cycles):
                material_units[families[index % len(families)]] += 1
            if cycles == 0 or cycles < profile.gathering_workers * available_hours * 60:
                capacity_paused_days += 1
        if day % 365 == 0 and guild_level < TARGET_LEVEL:
            # Keep the report finite and make very slow/unreachable profiles visible.
            if day >= 365 * 20:
                break

    reached = guild_level >= TARGET_LEVEL
    return {
        "profile": profile.name,
        "status": "reached_level_50" if reached else "not_reached_within_20_years",
        "seed": seed,
        "guild_level": guild_level,
        "days_to_level_50": day if reached else None,
        "years_to_level_50": round(day / 365, 2) if reached else None,
        "days_to_checkpoints": checkpoints,
        "actions": total_actions,
        "failures": total_failures,
        "gross_gold": total_gold,
        "guild_xp_progress": guild_xp,
        "gathered_material_units": material_units,
        "gathered_material_total": sum(material_units.values()),
        "gathering_capacity_paused_days": capacity_paused_days,
    }


def build_economy_audit(db) -> dict[str, object]:
    missions = list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.content_pack == PACK_KEY,
        MissionTemplate.is_active.is_(True),
        MissionTemplate.mission_type != "gathering",
        MissionTemplate.mission_type != "long_idle",
    )))
    dungeons = list(db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.content_pack == PACK_KEY,
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type == "dungeon",
    )))

    def source_rows(templates):
        by_band = {}
        for item in templates:
            band = item.level_band
            row = by_band.setdefault(band, {"templates": 0, "gold_per_hour_mean": [], "expected_xp_per_run_mean": []})
            row["templates"] += 1
            chance = max(0, min(100, int(item.base_success_chance))) / 100
            row["gold_per_hour_mean"].append(int(item.base_gold_reward) * chance * 3600 / max(1, item.duration_seconds))
            row["expected_xp_per_run_mean"].append(int(item.base_xp_reward) * (chance + (1 - chance) * .25))
        return {
            band: {
                "templates": row["templates"],
                "mean_success_weighted_gold_per_hour": round(sum(row["gold_per_hour_mean"]) / row["templates"], 2),
                "mean_xp_per_run_including_failures": round(sum(row["expected_xp_per_run_mean"]) / row["templates"], 2),
            }
            for band, row in sorted(by_band.items())
        }

    config = db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))
    config = config or TavernConfig(base_apprentice_cost=50, apprentice_cost_threshold=5000,
        apprentice_growth_before_threshold_percent=5, apprentice_growth_after_threshold_percent=3,
        common_apprentice_chance=90, uncommon_apprentice_chance=10)
    hires = []
    hire_cost = config.base_apprentice_cost
    for index in range(10):
        paid = get_discounted_hire_cost(hire_cost, 0)  # Level 1 Tavern has no milestone discount.
        hires.append({"hire_number": index + 1, "gold": paid})
        hire_cost = next_apprentice_cost(hire_cost, config)

    building_rows = []
    for template in db.scalars(select(BuildingTemplate).where(BuildingTemplate.is_active.is_(True)).order_by(BuildingTemplate.effect_type)):
        next_costs = []
        for next_level in range(1, 6):
            if template.effect_type in {"housing", "tavern"} and next_level == 1:
                gold = 10
            else:
                factor = building_cost_factor(next_level)
                gold = ceil(template.base_upgrade_gold_cost * factor)
            next_costs.append({
                "to_level": next_level,
                "required_guild_level": required_guild_level_for_upgrade(next_level, template.required_guild_level),
                "gold": gold,
                "wood": ceil(template.base_upgrade_wood_cost * building_cost_factor(next_level)) if not (template.effect_type in {"housing", "tavern"} and next_level == 1) else 0,
                "ore": ceil(template.base_upgrade_ore_cost * building_cost_factor(next_level)) if not (template.effect_type in {"housing", "tavern"} and next_level == 1) else 0,
                "crystals": ceil(template.base_upgrade_crystals_cost * building_cost_factor(next_level)) if not (template.effect_type in {"housing", "tavern"} and next_level == 1) else 0,
            })
        building_rows.append({"effect_type": template.effect_type,
            "required_guild_level_base": template.required_guild_level,
            "base_cost": {"gold": template.base_upgrade_gold_cost, "wood": template.base_upgrade_wood_cost,
                          "ore": template.base_upgrade_ore_cost, "crystals": template.base_upgrade_crystals_cost},
            "levels_1_to_5_cost": next_costs})

    recipe_rows = []
    for recipe in db.scalars(select(CraftingRecipe).where(CraftingRecipe.is_active.is_(True)).order_by(CraftingRecipe.required_blacksmith_level, CraftingRecipe.id)):
        materials = list(db.scalars(select(CraftingRecipeMaterial).where(CraftingRecipeMaterial.recipe_id == recipe.id)))
        recipe_rows.append({
            "name": recipe.name,
            "blacksmith_level_required": recipe.required_blacksmith_level,
            "gold_cost_per_craft": recipe.gold_cost,
            "output_quantity": recipe.output_quantity,
            "material_costs_per_craft": [{"item": row.item_template.name, "family": row.item_template.material_family,
                                         "tier": row.item_template.tier, "quantity": row.quantity} for row in materials],
            "executable_if_requirements_met": True,
        })

    offers = list(db.scalars(select(MerchantOfferTemplate).where(MerchantOfferTemplate.is_active.is_(True))))
    dock_prices = []
    for offer in offers:
        item = db.get(ItemTemplate, offer.item_template_id)
        if item is None or not item.is_active:
            continue
        at_level_1 = market_sale_unit_value(item.base_sell_value, market_values(1)["value_bonus_percent"])
        at_market_100 = market_sale_unit_value(item.base_sell_value, market_values(100)["value_bonus_percent"])
        effective_unit_price = effective_dock_unit_price(offer.base_price, item.base_sell_value)
        dock_prices.append({
            "item": item.name,
            "item_type": item.item_type,
            "tier": item.tier,
            "dock_min_level": offer.min_dock_level,
            "dock_building_level_required": max(1, (offer.min_dock_level - 1) * 5 + 1),
            "stock_range": [offer.min_stock, offer.max_stock],
            "configured_buy_unit_price": offer.base_price,
            "effective_buy_unit_price": effective_unit_price,
            "market_sell_at_level_1": at_level_1,
            "market_sell_at_level_100": at_market_100,
            "configured_margin_market_level_1": at_level_1 - offer.base_price,
            "configured_margin_market_level_100": at_market_100 - offer.base_price,
            "effective_margin_market_level_1": at_level_1 - effective_unit_price,
            "effective_margin_market_level_100": at_market_100 - effective_unit_price,
        })
    resale_levels = []
    for market_level in (1, 5, 10, 20, 35, 50, 75, 100):
        bonus = market_values(market_level)["value_bonus_percent"]
        sell_values = [market_sale_unit_value(
            row["market_sell_at_level_1"], bonus,
        ) for row in dock_prices]
        configured_margins = [sell - row["configured_buy_unit_price"] for sell, row in zip(sell_values, dock_prices)]
        enforced_margins = [sell - row["effective_buy_unit_price"] for sell, row in zip(sell_values, dock_prices)]
        resale_levels.append({"market_level": market_level, "value_bonus_percent": bonus,
            "configured_positive_margin_pairs": sum(value > 0 for value in configured_margins),
            "enforced_positive_margin_pairs": sum(value > 0 for value in enforced_margins),
            "configured_best_margin_gold": max(configured_margins, default=0),
            "enforced_best_margin_gold": max(enforced_margins, default=0),
            "configured_worst_margin_gold": min(configured_margins, default=0)})
    configured_positive_margins = [row for row in dock_prices if row["configured_margin_market_level_100"] > 0]
    configured_positive_level_1 = [row for row in dock_prices if row["configured_margin_market_level_1"] > 0]
    configured_positive_margins.sort(key=lambda row: row["configured_margin_market_level_100"], reverse=True)
    configured_positive_level_1.sort(key=lambda row: row["configured_margin_market_level_1"], reverse=True)
    effective_positive_level_1 = [row for row in dock_prices if row["effective_margin_market_level_1"] > 0]
    effective_positive_level_100 = [row for row in dock_prices if row["effective_margin_market_level_100"] > 0]

    return {
        "gold_sources": {
            "repeatable_missions_by_band": source_rows(missions),
            "repeatable_dungeons_by_band": source_rows(dungeons),
            "offline_gold_per_hour": OFFLINE_BASE_GOLD_PER_HOUR,
            "offline_cap_hours": OFFLINE_CAP_SECONDS / 3600,
            "reachability": "Repeatable on successful claims; no daily use cap in these services. Offline base gold is separately capped by eligible absence/stamina.",
        },
        "sinks": {
            "tavern": {
                "tavern_level_1_upgrade_gold": 10,
                "first_10_apprentice_hires_level_1_discount_0": hires,
                "first_10_apprentice_hires_total_gold": sum(row["gold"] for row in hires),
                "special_offer_gold_by_rarity": {"rare": config.special_rare_cost, "epic": config.special_epic_cost,
                    "legendary": config.special_legendary_cost, "mythic": config.special_mythic_cost},
                "manual_offer_refresh_gold": TAVERN_MANUAL_REFRESH_COST,
                "availability": "Hire costs are executable after Tavern level 1, subject to housing slots; special hires/refresh require a live offer and enough gold.",
            },
            "buildings": building_rows,
            "crafting": {
                "active_recipe_count": len(recipe_rows),
                "recipes": recipe_rows,
                "availability": "Requires Blacksmith level, current rotating recipe, gold, and each listed material; listed rows are catalog availability, not automatic spending.",
            },
            "refinement": {
                "unlock_blacksmith_level": 10,
                "gold_formula_per_step": f"{REFINE_BASE_GOLD_COST} * (upgrade_level + 1) * max(1, item_tier)",
                "ore_formula_per_step": f"{REFINE_BASE_ORE_COST} * (upgrade_level + 1)",
                "availability": "Requires an owned, unlisted equipment instance, Blacksmith level 10, rarity cap not reached, and gold/ore.",
            },
            "salvage": {
                "slots": [{"slot": slot, **rule} for slot, rule in SALVAGE_SLOT_RULES.items()],
                "material_return_per_item": "random integer 1..3, consumes owned equipment, then adds output subject to capacity",
                "availability": "Requires the corresponding Blacksmith level, free job slot, unlisted equipment, and gold; materials are not guaranteed to be sellable for a profit.",
            },
            "docks": {
                "catalog_offer_count": len(dock_prices),
                "configured_arbitrage_examples_at_market_level_1": configured_positive_level_1[:30],
                "configured_arbitrage_pair_count_market_level_1": len(configured_positive_level_1),
                "configured_arbitrage_examples_at_market_level_100": configured_positive_margins[:30],
                "enforced_positive_margin_pair_count_market_level_1": len(effective_positive_level_1),
                "enforced_positive_margin_pair_count_market_level_100": len(effective_positive_level_100),
                "resale_by_market_level": resale_levels,
                "buy_then_market_sell_at_max_market_bonus": {
                    "market_level": 100,
                    "market_value_bonus_percent": market_values(100)["value_bonus_percent"],
                    "configured_positive_margin_offer_count": len(configured_positive_margins),
                    "effective_positive_margin_offer_count": len(effective_positive_level_100),
                    "best_configured_positive_margin_gold": max((row["configured_margin_market_level_100"] for row in configured_positive_margins), default=0),
                    "best_effective_margin_gold": max((row["effective_margin_market_level_100"] for row in dock_prices), default=0),
                    "result": "Stored offer prices contain positive margins; the Dock service now clamps purchase/display price above max Market resale value." if configured_positive_margins and not effective_positive_level_100 else "Check configured/effective margins in the offer sample.",
                },
                "availability": "A Dock purchase requires its minimum/catalog level, an active rotation that selects the offer, stock, and warehouse room. Market resale requires Market level 1 and sale completion. Display and purchase both normalize legacy active offers to the no-arbitrage floor; future admin/catalog base prices are normalized when a rotation is generated.",
            },
        },
        "economic_findings": {
            "mandatory_sink": "No recurring gold sink is forced by the code after initial progression; listed sinks are optional player actions with unlock/resource gates.",
            "route_infinite_exploit": ("The catalog contained configured positive margins, but the purchase/display code now clamps each Dock price to at least one gold above the maximum Market resale value; regression tests cover creation, stale active rotation, and purchase." if configured_positive_margins and not effective_positive_level_100 else "Review the configured/effective margin rows for an unresolved positive route."),
            "unbounded_activity_gold": "Regional missions/dungeons/bosses are finite within each six-hour board (10/3/1 offers per region), then refresh. With no mandatory recurring sink, repeated participation across cycles can still grow treasury over time; the legacy uncapped-template runner is not evidence of an infinite action inside one board.",
            "stage5_status": "Configured Dock/Market arbitrage is clamped by runtime display/purchase pricing and covered by regression tests. The regional board has finite per-cycle offers, but recurring treasury growth without spending is possible across refreshed cycles. The level-50 board cashflow is a sensitivity, not a complete 1-50 economy pass; Stage 5 remains open.",
        },
    }


def _profile_investment_policy(db, profile: Profile, catalog: dict[int, list[object]]) -> dict[str, object]:
    """Cost staffing and housing; building bonuses are not access prerequisites."""
    templates = {row.effect_type: row for row in db.scalars(select(BuildingTemplate).where(BuildingTemplate.is_active.is_(True)))}
    roster_size = profile.slots * profile.party_size + profile.gathering_workers
    housing_level = next((level for level in range(1, 101) if housing_capacity(level) >= roster_size), 100)
    required_levels = {"tavern": 1, "housing": housing_level}

    building_costs = []
    gold_total = 0
    material_totals = {"wood": 0, "ore": 0, "crystals": 0}
    for effect_type, target_level in sorted(required_levels.items()):
        building = templates.get(effect_type)
        if building is None:
            building_costs.append({"effect_type": effect_type, "target_level": target_level, "available": False})
            continue
        for level in range(1, target_level + 1):
            special_first = effect_type in {"housing", "tavern"} and level == 1
            factor = building_cost_factor(level)
            costs = {
                "gold": 10 if special_first else ceil(building.base_upgrade_gold_cost * factor),
                "wood": 0 if special_first else ceil(building.base_upgrade_wood_cost * factor),
                "ore": 0 if special_first else ceil(building.base_upgrade_ore_cost * factor),
                "crystals": 0 if special_first else ceil(building.base_upgrade_crystals_cost * factor),
            }
            gold_total += costs["gold"]
            for resource in material_totals:
                material_totals[resource] += costs[resource]
        building_costs.append({
            "effect_type": effect_type,
            "target_level": target_level,
            "available": True,
            "gold": sum(10 if effect_type in {"housing", "tavern"} and level == 1 else ceil(building.base_upgrade_gold_cost * building_cost_factor(level))
                        for level in range(1, target_level + 1)),
            "materials": {
                resource: sum(
                    0 if effect_type in {"housing", "tavern"} and level == 1
                    else ceil(getattr(building, f"base_upgrade_{resource}_cost") * building_cost_factor(level))
                    for level in range(1, target_level + 1)
                )
                for resource in material_totals
            },
        })

    config = db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))
    config = config or TavernConfig(base_apprentice_cost=50, apprentice_cost_threshold=5000,
        apprentice_growth_before_threshold_percent=5, apprentice_growth_after_threshold_percent=3)
    hires = []
    hire_cost = config.base_apprentice_cost
    for number in range(roster_size):
        paid = get_discounted_hire_cost(hire_cost, 0)
        hires.append(paid)
        hire_cost = next_apprentice_cost(hire_cost, config)
    hire_total = sum(hires)
    return {
        "policy": "Pay one Tavern upgrade, housing capacity for the profile roster, and recruit enough mercenaries. Contract Office and Explorers provide optional bonuses and do not gate mission, contract, dungeon, or boss access. Materials are shown as required stock; the simulation does not model how the profile acquires/uses them.",
        "roster_size": roster_size,
        "building_costs": building_costs,
        "building_gold": gold_total,
        "building_materials": material_totals,
        "hire_costs": hires,
        "hire_gold": hire_total,
        "total_setup_gold": gold_total + hire_total,
        "starting_gold": 100,
        "net_after_setup_before_activity": 100 - gold_total - hire_total,
    }


def _endgame_daily_gold(profile: Profile, template, seed: int) -> int:
    rng = random.Random(f"endgame:{profile.name}:{seed}")
    hours = min(profile.online_hours_per_day, OFFLINE_CAP_SECONDS / 3600) if profile.name == "offline" else profile.online_hours_per_day
    runs_per_slot = int(hours * 3600 // max(1, int(template.duration_seconds)))
    chance = max(0, min(100, int(template.base_success_chance)))
    return sum(
        int(template.base_gold_reward)
        for _slot in range(profile.slots)
        for _run in range(runs_per_slot)
        if rng.randrange(100) < chance
    )


def _create_abstract_roster(db, guild: Guild, profile: Profile) -> list[Mercenary]:
    """Create the profile's assumed available common Apprentices; no gear or class evolution."""
    apprentice = db.scalar(select(MercenaryClass).where(
        MercenaryClass.code == "apprentice", MercenaryClass.is_active.is_(True),
    ))
    if apprentice is None:
        raise RuntimeError("The seeded catalog has no active Apprentice class for the regional simulation.")
    roster_size = profile.slots * profile.party_size + profile.gathering_workers
    roster = [Mercenary(
        guild_id=guild.id, class_id=apprentice.id, mercenary_class=apprentice,
        name=f"Sim {profile.name} {index + 1}", level=1, xp=0,
        status="available", rarity="common", hire_cost=0,
        power=apprentice.base_power, vitality=apprentice.base_vitality,
        agility=apprentice.base_agility, intelligence=apprentice.base_intelligence,
        luck=apprentice.base_luck,
    ) for index in range(roster_size)]
    db.add_all(roster)
    db.flush()
    return roster


def _sync_abstract_roster(roster: list[Mercenary], guild_level: int) -> None:
    """Assume each active common Apprentice gains one level with each guild level."""
    for mercenary in roster:
        while mercenary.level < guild_level:
            mercenary.level += 1
            apply_levelup_attributes(mercenary)


def _sample_real_home_board(db, campaign, guild, cycle_number: int) -> tuple[list[dict[str, object]], int, float]:
    """Materialize one actual home-region board for this guild roster and cycle seed."""
    world = RegionalWorldState(campaign_id=campaign.campaign_id)
    cycle = _materialize_cycle(db, campaign, guild, world, cycle_number, region_scope=(REGIONS[0],))
    offer_rows = db.execute(select(RegionalOffer, MissionTemplate, DungeonTemplate)
        .outerjoin(MissionTemplate, RegionalOffer.mission_template_id == MissionTemplate.id)
        .outerjoin(DungeonTemplate, RegionalOffer.dungeon_template_id == DungeonTemplate.id)
        .where(
        RegionalOffer.cycle_id == cycle.id,
        RegionalOffer.region_code == REGIONS[0][0],
        ).order_by(RegionalOffer.offer_type, RegionalOffer.slot)).all()
    offers = [row[0] for row in offer_rows]
    snapshot = []
    for offer, mission, dungeon in offer_rows:
        template = mission or dungeon
        snapshot.append({
            "offer_type": offer.offer_type, "rank": offer.rank, "name": offer.name_snapshot,
            "duration_seconds": offer.duration_seconds_snapshot,
            "gold_reward": offer.gold_reward_snapshot, "xp_reward": offer.xp_reward_snapshot,
            "success_chance_percent": offer.success_chance_snapshot,
            "min_party_size": offer.min_party_size_snapshot,
            "max_party_size": offer.max_party_size_snapshot,
            "recommended_power": offer.recommended_power_snapshot,
            "required_guild_level": int(template.required_guild_level or 1),
            "required_min_mercenary_level": int(template.required_min_mercenary_level or 1),
            "required_building_type": template.required_building_type,
            "required_building_level": int(template.required_building_level or 0),
            "required_total_power": int(getattr(template, "required_total_power", 0) or 0),
            "required_class_code": getattr(template, "required_class_code", None),
            "required_tank_count": int(getattr(template, "required_tank_count", 0) or 0),
            "required_support_count": int(getattr(template, "required_support_count", 0) or 0),
            "required_damage_count": int(getattr(template, "required_damage_count", 0) or 0),
            "required_equipment_tier": int(getattr(template, "required_equipment_tier", 0) or 0),
            "mission_template_id": mission.id if mission else None,
            "item_drops": ([
                {
                    "item_template_id": int(drop.item_template_id),
                    "item_name": drop.item_template.name,
                    "item_type": drop.item_template.item_type,
                    "material_family": drop.item_template.material_family,
                    "drop_chance_percent": int(drop.drop_chance),
                    "quantity_min": int(drop.min_quantity),
                    "quantity_max": int(drop.max_quantity),
                }
                for drop in mission.item_drops if drop.is_active and drop.item_template
            ] if mission else []),
        })
    player_power_snapshot = int(cycle.player_power_snapshot)
    rank_stage = float(json.loads(cycle.rank_weights_json).get("stage", 0.0))
    db.execute(delete(RegionalOffer).where(RegionalOffer.cycle_id == cycle.id))
    db.delete(cycle)
    db.flush()
    return snapshot, player_power_snapshot, rank_stage


def _selected_party_size(profile: Profile, offer: dict[str, object]) -> int:
    capacity = max(1, int(profile.party_size))
    if profile.party_selection_policy == "selectable":
        return min(capacity, int(offer["max_party_size"]))
    return capacity


def _party_fits_offer(profile: Profile, offer: dict[str, object]) -> bool:
    selected_size = _selected_party_size(profile, offer)
    return int(offer["min_party_size"]) <= selected_size <= int(offer["max_party_size"])


def _cycle_outcome(
    profile: Profile, offers: list[dict[str, object]], seed: int, *,
    action_hours: float | None = None, max_actions_per_team: int | None = None,
    guild: Guild | None = None, player_power_snapshot: int = 0, roster_size: int | None = None,
    eligibility_guild_level: int | None = None, eligibility_mercenary_level: int | None = None,
    reward_bonus_percent: int = 0, training_bonus_percent: int = 0,
    track_item_drops: bool = False,
) -> dict[str, object]:
    """Greedily fill each team's activity window from the finite offer board."""
    rng = random.Random(f"board:{profile.name}:{seed}")
    available = list(offers)
    active_hours_per_cycle = min(6.0, action_hours if action_hours is not None else profile.online_hours_per_day / 4.0)
    guild_level = guild.level if guild is not None else (eligibility_guild_level or GUILD_MAX_LEVEL)
    mercenary_level = (int(eligibility_mercenary_level) if eligibility_mercenary_level is not None
                       else guild.level if guild is not None else GUILD_MAX_LEVEL)
    total_gold = total_guild_xp = actions = successes = blocked_team_windows = 0
    blocked_window_reasons = {"board_empty": 0, "claimed_by_other_team": 0, "no_contract": 0,
                              "party_size": 0, "guild_level": 0, "mercenary_level": 0,
                              "duration": 0, "other_gate": 0}
    team_remaining = [int(active_hours_per_cycle * 3600)] * profile.slots
    team_actions = [0] * profile.slots
    item_drop_events: list[dict[str, object]] = []
    item_drop_rolls: list[dict[str, object]] = []

    def classify_blocked_window(remaining: int) -> str:
        board_contracts = [offer for offer in offers if offer["offer_type"] == "contract"]
        available_offer_identities = {id(offer) for offer in available}
        claimed_eligible_contract = any(
            id(offer) not in available_offer_identities
            and _party_fits_offer(profile, offer)
            and int(offer.get("required_guild_level", 1)) <= guild_level
            and int(offer.get("required_min_mercenary_level", 1)) <= mercenary_level
            and offer["duration_seconds"] <= remaining
            for offer in board_contracts
        )
        if claimed_eligible_contract:
            return "claimed_by_other_team"
        if not offers or not available:
            return "board_empty"
        if not board_contracts:
            return "no_contract"
        if not any(_party_fits_offer(profile, offer) for offer in board_contracts):
            return "party_size"
        if not any(_party_fits_offer(profile, offer)
                   and int(offer.get("required_guild_level", 1)) <= guild_level
                   for offer in board_contracts):
            return "guild_level"
        if not any(_party_fits_offer(profile, offer)
                   and int(offer.get("required_guild_level", 1)) <= guild_level
                   and int(offer.get("required_min_mercenary_level", 1)) <= mercenary_level
                   for offer in board_contracts):
            return "mercenary_level"
        if not any(_party_fits_offer(profile, offer)
                   and int(offer.get("required_guild_level", 1)) <= guild_level
                   and int(offer.get("required_min_mercenary_level", 1)) <= mercenary_level
                   and offer["duration_seconds"] <= remaining
                   for offer in board_contracts):
            return "duration"
        return "other_gate"

    # Dispatch offers across parallel slots in turns, avoiding an outcome that
    # depends on filling one team's entire queue before the others can claim.
    next_team = 0
    while any(remaining > 0 for remaining in team_remaining):
        team_index = next_team
        next_team = (next_team + 1) % profile.slots
        remaining = team_remaining[team_index]
        if remaining <= 0:
            continue
        if max_actions_per_team is not None and team_actions[team_index] >= max_actions_per_team:
            team_remaining[team_index] = 0
            continue
        eligible = [offer for offer in available
            if _party_fits_offer(profile, offer)
            and offer["duration_seconds"] <= remaining
            and int(offer.get("required_guild_level", 1)) <= guild_level
            and int(offer.get("required_min_mercenary_level", 1)) <= mercenary_level]
        if profile.mode == "dungeon":
            combat_eligible = []
            for offer in eligible:
                if offer["offer_type"] == "dungeon":
                    # Production advanced-party checks apply to bosses only;
                    # normal dungeons use their content party/level requirements.
                    combat_eligible.append(offer)
                elif (offer["offer_type"] == "boss"
                      and int(player_power_snapshot * _selected_party_size(profile, offer)
                              / max(1, roster_size or profile.party_size))
                      >= int(offer.get("required_total_power", 0))
                      and not offer.get("required_class_code")
                      and int(offer.get("required_tank_count", 0)) == 0
                      and int(offer.get("required_support_count", 0)) == 0
                      and int(offer.get("required_damage_count", 0)) == 0
                      and int(offer.get("required_equipment_tier", 0)) == 0):
                    combat_eligible.append(offer)
            eligible = combat_eligible or [offer for offer in eligible if offer["offer_type"] == "contract"]
        else:
            eligible = [offer for offer in eligible if offer["offer_type"] == "contract"]
        if not eligible:
            if team_actions[team_index] == 0:
                blocked_team_windows += 1
                blocked_window_reasons[classify_blocked_window(remaining)] += 1
            team_remaining[team_index] = 0
            continue
        eligible.sort(key=lambda offer: (
            -({"E": 0, "D": 1, "C": 2, "B": 3, "A": 4, "S": 5}.get(offer["rank"], 0)
              if profile.mode == "contract_priority" else 0),
            -(offer["success_chance_percent"] * max(1, offer["xp_reward"] * _selected_party_size(profile, offer) // 10)
              + (100 - offer["success_chance_percent"]) * max(1, (offer["xp_reward"] // 4) * _selected_party_size(profile, offer) // 10))
            / max(1, offer["duration_seconds"]),
            offer["offer_type"], offer["name"],
        ))
        offer = eligible[0]
        action_party_size = _selected_party_size(profile, offer)
        available.remove(offer)
        team_remaining[team_index] -= offer["duration_seconds"]
        success = rng.randrange(100) < offer["success_chance_percent"]
        xp_per_mercenary = (
            int(offer["xp_reward"]) * (100 + max(0, int(reward_bonus_percent))) // 100
            if success else int(offer["xp_reward"]) // 4
        )
        xp_per_mercenary += xp_per_mercenary * max(0, int(training_bonus_percent)) // 100
        guild_xp_gain = max(1, xp_per_mercenary * action_party_size // 10)
        total_guild_xp += guild_xp_gain
        if guild is not None:
            add_guild_xp(guild, guild_xp_gain)
        if success:
            total_gold += int(offer["gold_reward"]) * (100 + max(0, int(reward_bonus_percent))) // 100
            successes += 1
            if track_item_drops:
                drop_rng = random.Random(
                    f"mission-drop:{profile.name}:{seed}:{team_index}:{team_actions[team_index]}:{offer.get('mission_template_id')}"
                )
                for drop in offer.get("item_drops", []):
                    awarded = drop_rng.randrange(100) < int(drop["drop_chance_percent"])
                    quantity = (drop_rng.randint(int(drop["quantity_min"]), int(drop["quantity_max"]))
                                if awarded else 0)
                    item_drop_rolls.append({
                        "mission_template_id": offer.get("mission_template_id"),
                        "mission_name": offer["name"], "item_template_id": int(drop["item_template_id"]),
                        "item_name": str(drop["item_name"]), "item_type": str(drop["item_type"]),
                        "material_family": drop.get("material_family"),
                        "drop_chance_percent": int(drop["drop_chance_percent"]),
                        "awarded": awarded, "quantity_requested": quantity,
                    })
                    if awarded:
                        item_drop_events.append({
                            "mission_template_id": offer.get("mission_template_id"),
                            "mission_name": offer["name"], "item_template_id": int(drop["item_template_id"]),
                            "item_name": str(drop["item_name"]), "item_type": str(drop["item_type"]),
                            "material_family": drop.get("material_family"), "quantity_requested": quantity,
                            "drop_chance_percent": int(drop["drop_chance_percent"]),
                        })
        actions += 1
        team_actions[team_index] += 1
    return {"gold": total_gold, "guild_xp": total_guild_xp, "actions": actions,
            "successes": successes, "blocked_team_windows": blocked_team_windows,
            "blocked_window_reasons": blocked_window_reasons, "item_drop_events": item_drop_events,
            "item_drop_rolls": item_drop_rolls}


def build_controlled_activity_audit(db, *, sample_cycles: int = 100) -> dict[str, object]:
    """Compare activity hours on identical real boards at fixed guild/party/slot state."""
    control_profile = Profile("controlled_fixed", "mission", 8, 3, 3)
    selectable_profile = Profile("controlled_selectable", "mission", 8, 3, 3, party_selection_policy="selectable")
    hours_grid = (0.5, 2.0, 3.0, 6.0)
    level_rows = {}
    for level in (1, 10, 20, 30, 40, 50):
        candidate_conditions = (
            MissionTemplate.is_active.is_(True),
            ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
            MissionTemplate.required_min_mercenary_level <= max(1, level * 2),
            MissionTemplate.recommended_level <= max(20, level * 3),
        )
        candidate_pool_count = db.scalar(select(func.count(MissionTemplate.id)).where(*candidate_conditions)) or 0
        full_active_pool_count = db.scalar(select(func.count(MissionTemplate.id)).where(
            MissionTemplate.is_active.is_(True),
            ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
        )) or 0
        fallback_to_full_active_pool = int(candidate_pool_count) < 10
        selection_pool_count = int(full_active_pool_count if fallback_to_full_active_pool else candidate_pool_count)
        selection_pool_conditions = (
            (MissionTemplate.is_active.is_(True), ~MissionTemplate.mission_type.in_(("gathering", "long_idle")))
            if fallback_to_full_active_pool else candidate_conditions
        )
        candidate_pool_accessibility = {}
        for party_size in (2, 3):
            fixed_accessible_count = db.scalar(select(func.count(MissionTemplate.id)).where(
                *selection_pool_conditions,
                MissionTemplate.required_guild_level <= level,
                MissionTemplate.required_min_mercenary_level <= level,
                MissionTemplate.min_party_size <= party_size,
                MissionTemplate.max_party_size >= party_size,
            )) or 0
            selectable_accessible_count = db.scalar(select(func.count(MissionTemplate.id)).where(
                *selection_pool_conditions,
                MissionTemplate.required_guild_level <= level,
                MissionTemplate.required_min_mercenary_level <= level,
                MissionTemplate.min_party_size <= party_size,
                MissionTemplate.max_party_size >= MissionTemplate.min_party_size,
            )) or 0
            draw_size = min(10, selection_pool_count)
            def probability_zero(accessible_count):
                if draw_size <= 0:
                    return 1.0
                if selection_pool_count - int(accessible_count) < draw_size:
                    return 0.0
                return comb(selection_pool_count - int(accessible_count), draw_size) / comb(selection_pool_count, draw_size)
            candidate_pool_accessibility[str(party_size)] = {
                "fixed_exact": {
                    "eligible_templates_in_selection_pool": int(fixed_accessible_count),
                    "probability_no_eligible_contract_in_random_ten": round(probability_zero(fixed_accessible_count), 4),
                },
                "selectable_within_capacity": {
                    "eligible_templates_in_selection_pool": int(selectable_accessible_count),
                    "probability_no_eligible_contract_in_random_ten": round(probability_zero(selectable_accessible_count), 4),
                },
                "selection_pool_size": selection_pool_count,
            }
        campaign_id = str(uuid5(NAMESPACE_URL, f"guild-board-control:{level}"))
        campaign = CampaignMetadata(
            campaign_id=campaign_id, campaign_name=f"Controle guilda {level}",
            schema_version=5, content_version=PACK_VERSION, home_region=REGIONS[0][1],
        )
        guild = Guild(campaign_id=campaign_id, name=f"Controle {level}", level=level)
        db.add_all([campaign, guild])
        db.flush()
        roster = _create_abstract_roster(db, guild, control_profile)
        _sync_abstract_roster(roster, level)
        samples = {hours: {"actions": [], "blocked": [], "selectable_actions": [], "selectable_blocked": [], "eligible_contracts": [],
                           "merc_level_locked_contracts": [], "guild_level_locked_contracts": [],
                           "party_incompatible_contracts": [], "too_long_contracts": []}
                   for hours in hours_grid}
        party_size_samples = {size: {"actions": [], "eligible_contracts": []} for size in (2, 3)}
        rank_samples = {rank: {"offered": [], "eligible_group_3_fixed": [], "eligible_group_3_selectable": []}
                        for rank in RANKS}
        for cycle_number in range(sample_cycles):
            board, power, _rank_stage = _sample_real_home_board(db, campaign, guild, cycle_number)
            contracts = [offer for offer in board if offer["offer_type"] == "contract"]
            guild_ok = [offer for offer in contracts if offer["required_guild_level"] <= level]
            merc_ok = [offer for offer in guild_ok if offer["required_min_mercenary_level"] <= level]
            party_ok = [offer for offer in merc_ok
                        if offer["min_party_size"] <= control_profile.party_size <= offer["max_party_size"]]
            selectable_party_ok = [offer for offer in merc_ok
                        if offer["min_party_size"] <= min(control_profile.party_size, offer["max_party_size"])
                        <= offer["max_party_size"]]
            for rank in RANKS:
                rank_samples[rank]["offered"].append(sum(offer["rank"] == rank for offer in contracts))
                rank_samples[rank]["eligible_group_3_fixed"].append(sum(
                    offer["rank"] == rank and offer["min_party_size"] <= control_profile.party_size <= offer["max_party_size"]
                    and offer["required_guild_level"] <= level
                    and offer["required_min_mercenary_level"] <= level
                    for offer in contracts
                ))
                rank_samples[rank]["eligible_group_3_selectable"].append(sum(
                    offer["rank"] == rank and offer["min_party_size"] <= min(control_profile.party_size, offer["max_party_size"])
                    <= offer["max_party_size"]
                    and offer["required_guild_level"] <= level
                    and offer["required_min_mercenary_level"] <= level
                    for offer in contracts
                ))
            for hours in hours_grid:
                outcome = _cycle_outcome(
                    control_profile, board, 20261028 + cycle_number,
                    action_hours=hours, player_power_snapshot=power,
                    roster_size=len(roster), eligibility_guild_level=level,
                    eligibility_mercenary_level=level,
                )
                row = samples[hours]
                row["actions"].append(outcome["actions"])
                row["blocked"].append(outcome["blocked_team_windows"])
                selectable_outcome = _cycle_outcome(
                    selectable_profile, board, 20261028 + cycle_number,
                    action_hours=hours, player_power_snapshot=power,
                    roster_size=len(roster), eligibility_guild_level=level,
                    eligibility_mercenary_level=level,
                )
                row["selectable_actions"].append(selectable_outcome["actions"])
                row["selectable_blocked"].append(selectable_outcome["blocked_team_windows"])
                row["eligible_contracts"].append(len(party_ok))
                row["merc_level_locked_contracts"].append(len(guild_ok) - len(merc_ok))
                row["guild_level_locked_contracts"].append(len(contracts) - len(guild_ok))
                row["party_incompatible_contracts"].append(len(merc_ok) - len(party_ok))
                row["too_long_contracts"].append(sum(
                    offer["min_party_size"] <= control_profile.party_size <= offer["max_party_size"]
                    and offer["duration_seconds"] > hours * 3600 for offer in party_ok
                ))
            for party_size in (2, 3):
                eligible_for_party = [offer for offer in contracts
                    if offer["required_guild_level"] <= level
                    and offer["required_min_mercenary_level"] <= level
                    and offer["min_party_size"] <= min(party_size, offer["max_party_size"])
                    <= offer["max_party_size"]]
                party_profile = Profile(f"controlled_party_{party_size}", "mission", 8, 3, party_size,
                                        party_selection_policy="selectable")
                outcome = _cycle_outcome(
                    party_profile, board, 20261028 + cycle_number,
                    action_hours=3.0, player_power_snapshot=power,
                    roster_size=len(roster), eligibility_guild_level=level,
                    eligibility_mercenary_level=level,
                )
                party_size_samples[party_size]["actions"].append(outcome["actions"])
                party_size_samples[party_size]["eligible_contracts"].append(len(eligible_for_party))
        def summary(values):
            ordered = sorted(float(value) for value in values)
            if not ordered:
                return {"n": 0, "p10": None, "p50": None, "p90": None}
            return {"n": len(ordered), "p10": round(ordered[int((len(ordered) - 1) * .1)], 2),
                    "p50": round(ordered[int((len(ordered) - 1) * .5)], 2),
                    "p90": round(ordered[int((len(ordered) - 1) * .9)], 2)}
        level_rows[str(level)] = {
            "boards": sample_cycles,
            "mission_candidate_pool_before_fallback": int(candidate_pool_count),
            "full_active_mission_pool": int(full_active_pool_count),
            "fallback_to_full_active_pool": fallback_to_full_active_pool,
            "candidate_pool_accessibility": candidate_pool_accessibility,
            "fixed_party_size": control_profile.party_size,
            "fixed_parallel_slots": control_profile.slots,
            "fixed_assumed_mercenary_level": level,
            "contract_offer_gates_per_board": {
                "eligible_for_roster": summary(samples[hours_grid[0]]["eligible_contracts"]),
                "guild_level_locked": summary(samples[hours_grid[0]]["guild_level_locked_contracts"]),
                "mercenary_level_locked": summary(samples[hours_grid[0]]["merc_level_locked_contracts"]),
                "party_incompatible_after_level_gates": summary(samples[hours_grid[0]]["party_incompatible_contracts"]),
            },
            "hours_sensitivity_same_boards": {
                str(hours): {
                    "daily_actions_if_board_pattern_repeats_4x": summary([value * 4 for value in row["actions"]]),
                    "fixed_exact_actions_per_board": summary(row["actions"]),
                    "selectable_subset_actions_per_board": summary(row["selectable_actions"]),
                    "fixed_exact_blocked_team_windows_per_board": summary(row["blocked"]),
                    "selectable_subset_blocked_team_windows_per_board": summary(row["selectable_blocked"]),
                    "offers_too_long_for_one_team_window": summary(row["too_long_contracts"]),
                }
                for hours, row in samples.items()
            },
            "party_size_sensitivity_same_boards": {
                str(size): {
                    "roster_size_across_3_disjoint_teams": 3 * size,
                    "actions_per_board": summary(row["actions"]),
                    "eligible_contracts_per_board": summary(row["eligible_contracts"]),
                }
                for size, row in party_size_samples.items()
            },
            "rank_accessibility_per_board": {
                rank: {
                    "offered": summary(row["offered"]),
                    "eligible_for_fixed_group_3": summary(row["eligible_group_3_fixed"]),
                    "eligible_for_selectable_capacity_3": summary(row["eligible_group_3_selectable"]),
                }
                for rank, row in rank_samples.items()
            },
        }
    return {
        "method": "At each guild level, reuse the same materialized home-region boards for every hours and party policy. Fix three parallel team slots and roster capacity 3 mercenaries per slot (9 distinct roster members); compare fixed exact group size 3 against selectable group size min(capacity, offer max), provided it meets the offer minimum. XP uses the selected size. Separately compare selectable capacities 2 and 3 with 3 team slots and 3h per board.",
        "sample_cycles_per_level": sample_cycles,
        "levels": level_rows,
        "interpretation_limit": "Controlled activity sensitivity. Every parallel slot owns a disjoint roster slice of capacity party_size; members are not reused across simultaneous tasks. Selected members per task can be fewer than capacity in selectable mode. Synthetic mercenary levels remain synchronized to guild level; real guild rosters can have independently leveled mercenaries.",
    }


def apply_candidate_upkeep(balance: int, rate: float) -> tuple[int, int]:
    charge = min(max(0, int(balance)), ceil(max(0.0, float(balance)) * max(0.0, float(rate))))
    return int(balance) - charge, charge


def _offline_cycle_window(cycle_in_day: int) -> tuple[float, int | None, str]:
    """8h assigned absence, then 8h online after return; cycles still advance."""
    if cycle_in_day == 0:
        return OFFLINE_ABSENCE_HOURS, 1, "pre_absence_dispatch"
    return_cycle = int(OFFLINE_ABSENCE_HOURS // 6)
    return_offset = OFFLINE_ABSENCE_HOURS % 6
    first_online_window = min(6.0 - return_offset, OFFLINE_RETURN_ONLINE_HOURS)
    remaining_online = max(0.0, OFFLINE_RETURN_ONLINE_HOURS - first_online_window)
    if cycle_in_day == return_cycle:
        return first_online_window, None, "post_return_online"
    if cycle_in_day == return_cycle + 1 and remaining_online > 0:
        return min(6.0, remaining_online), None, "post_return_online"
    return 0.0, 0, "unattended"


def _endgame_cashflow(db, profile: Profile, seed_start: int) -> dict[str, object]:
    """Project finite-board cash flow at level 50; setup and gear are explicit exclusions."""
    rate_rows = {"no_spend": [], "upkeep_2_percent": [], "upkeep_5_percent": [], "upkeep_10_percent": []}
    board_sizes = []
    sample_count = REGIONAL_CASHFLOW_RUNS
    horizon_days = 14
    for index in range(sample_count):
        seed = seed_start + index
        campaign_id = str(uuid5(NAMESPACE_URL, f"guild-board-economy:{profile.name}:{seed}"))
        campaign = CampaignMetadata(
            campaign_id=campaign_id, campaign_name=f"Economia {profile.name}",
            schema_version=5, content_version=PACK_VERSION, home_region=REGIONS[0][1],
        )
        guild = Guild(campaign_id=campaign_id, name=f"Guilda {profile.name}", level=TARGET_LEVEL)
        db.add_all([campaign, guild])
        db.flush()
        roster = _create_abstract_roster(db, guild, profile)
        _sync_abstract_roster(roster, guild.level)
        assumed_roster_size = profile.slots * profile.party_size + profile.gathering_workers
        passive_rate = OFFLINE_BASE_GOLD_PER_HOUR + (TARGET_LEVEL - 1) + assumed_roster_size * 2
        daily_income = []
        daily_actions = []
        cycle_income_rows = []
        board_power_snapshots = []
        rank_stages = []
        for day in range(horizon_days):
            day_gold = day_actions = 0
            cycle_income = []
            for cycle_in_day in range(4):
                offline_window = _offline_cycle_window(cycle_in_day) if profile.name == "offline" else None
                if offline_window is not None and offline_window[2] == "unattended":
                    # The world advances, but there is no human choice window.
                    _sync_abstract_roster(roster, guild.level)
                    board, player_power, rank_stage = _sample_real_home_board(db, campaign, guild, day * 4 + cycle_in_day)
                    board_sizes.append(len(board))
                    board_power_snapshots.append(player_power)
                    rank_stages.append(rank_stage)
                    cycle_income.append(0)
                    continue
                _sync_abstract_roster(roster, guild.level)
                board, player_power, rank_stage = _sample_real_home_board(db, campaign, guild, day * 4 + cycle_in_day)
                board_sizes.append(len(board))
                board_power_snapshots.append(player_power)
                rank_stages.append(rank_stage)
                if profile.name == "offline":
                    action_hours, max_actions, _window_kind = offline_window
                    result = _cycle_outcome(
                        profile, board, seed + day * 7919 + cycle_in_day * 104729,
                        action_hours=action_hours, max_actions_per_team=max_actions,
                        player_power_snapshot=player_power, roster_size=assumed_roster_size,
                    )
                else:
                    result = _cycle_outcome(
                        profile, board, seed + day * 7919 + cycle_in_day * 104729,
                        player_power_snapshot=player_power, roster_size=assumed_roster_size,
                    )
                day_gold += result["gold"]
                day_actions += result["actions"]
                cycle_income.append(result["gold"])
            if profile.name == "offline":
                passive_gold = passive_rate * min(OFFLINE_ABSENCE_HOURS, OFFLINE_CAP_SECONDS / 3600)
                day_gold += passive_gold
                # An 8h absence starting with cycle 0 ends inside cycle 1.
                cycle_income[int(OFFLINE_ABSENCE_HOURS // 6)] += passive_gold
            daily_income.append(day_gold)
            daily_actions.append(day_actions)
            cycle_income_rows.append(cycle_income)
        no_spend_balance = 0
        candidate_balances = {0.02: 0, 0.05: 0, 0.10: 0}
        paid = {rate: 0 for rate in candidate_balances}
        no_spend_horizon = 0
        for day, income in enumerate(daily_income):
            no_spend_balance += income
            no_spend_horizon += income
            for rate, balance in tuple(candidate_balances.items()):
                for cycle_gold in cycle_income_rows[day]:
                    balance, charge = apply_candidate_upkeep(balance, rate)
                    paid[rate] += charge
                    balance += cycle_gold
                candidate_balances[rate] = balance
        rate_rows["no_spend"].append({
            "after_horizon_endgame_days": no_spend_horizon,
            "gross_horizon_gold": no_spend_horizon,
            "daily_actions_mean": sum(daily_actions) / horizon_days,
        })
        for rate, key in ((0.02, "upkeep_2_percent"), (0.05, "upkeep_5_percent"), (0.10, "upkeep_10_percent")):
            rate_rows[key].append({
                "after_horizon_endgame_days": candidate_balances[rate],
                "maintenance_paid_horizon_days": paid[rate],
            })

    def dist(values):
        values = sorted(float(value) for value in values)
        return {"n": len(values), "p10": round(values[int((len(values) - 1) * .1)], 2),
                "p50": round(values[int((len(values) - 1) * .5)], 2), "p90": round(values[int((len(values) - 1) * .9)], 2)} if values else {"n": 0, "p10": None, "p50": None, "p90": None}

    return {
        "board_source": "Real regional_cycle_service._materialize_cycle offer snapshots at guild level 50, home region only.",
        "home_region": REGIONS[0][1],
        "horizon_days": horizon_days,
        "trajectories": sample_count,
        "finite_board_offers_per_vigilia": {"contract": 10, "dungeon": 3, "boss": 1},
        "sampled_board_offer_count": dist(board_sizes),
        "player_power_snapshot": dist(board_power_snapshots),
        "rank_progression_stage_snapshot": dist(rank_stages),
        "activity_model": ("Cada Vigília materializa um board regional novo com seed distinta e roster abstrato de Aprendizes comuns sincronizado ao nível da guilda para calcular os pesos de rank. Perfis online escolhem ofertas em cada board conforme XP esperado por hora, grupo e duração. Para o perfil offline, inicia-se uma oferta por equipe antes da ausência de 8h; a duração pode usar toda a estamina, mesmo se exceder a duração do board, pois a run já começou. Após o retorno, há uma janela online de 8h distribuída em 4h restantes do ciclo 1 e 4h do ciclo 2; boards sem interação avançam sem escolhas. A estamina recarrega à taxa de 2h por hora online até 8h. O ouro passivo offline usa a fórmula de produção com roster presumido e Armazém nível 0 e entra no retorno. A chance usa snapshots sem bônus de equipamento ou poder do grupo."),
        "starting_treasury_after_setup": 0,
        "progression_sinks": "Full profile setup is treated as already paid before the level-50 horizon; its gold/material bill is listed separately. The endgame projection isolates recurring cashflow and does not model equipment or ongoing building upgrades.",
        "endgame_daily_gross_gold": dist([row["gross_horizon_gold"] / horizon_days for row in rate_rows["no_spend"]]),
        "no_spend_gold_balance": {
            "after_horizon_endgame_days": dist([row["after_horizon_endgame_days"] for row in rate_rows["no_spend"]]),
            "daily_actions_mean": dist([row["daily_actions_mean"] for row in rate_rows["no_spend"]]),
        },
        "candidate_upkeep_sensitivity": {
            "not_live_or_approved_rule": True,
            "formula": "At the start of each eligible six-hour Vigília, charge min(current_treasury, ceil(current_treasury * rate)); then add success-weighted board gold (and modeled passive offline gold when applicable).",
            "rates": {key: {"treasury_after_horizon_endgame_days": dist([row["after_horizon_endgame_days"] for row in values]),
                            "upkeep_paid_horizon_days": dist([row["maintenance_paid_horizon_days"] for row in values])}
                      for key, values in rate_rows.items() if key != "no_spend"},
        },
        "interpretation": "No-spend is the deliberate non-spender control. Candidate upkeep rates are sensitivities only; no maintenance is implemented or approved. 2% per eligible Vigília is the separately confirmed rebellion spawn chance, not an approved upkeep rate. Boards reroll deterministically by cycle. The abstract level-synced roster affects rank weights, but cashflow remains an endgame sensitivity without gear, class evolution or combat-power chance bonuses.",
    }


def _simulate_regional_progression(
    db, profile: Profile, catalog: dict[int, list[object]], seed_start: int, *,
    sample_runs: int | None = None, max_days: int | None = None,
    vary_board_seeds: bool = False, starting_gold: int = 100,
    setup_gold_override: int | None = None, gold_reward_multiplier: float = 1.0,
    board_seed_pool_size: int | None = None,
) -> dict[str, object]:
    """Simulate level 1–50 with a newly materialized, finite regional board every Vigília."""
    setup = _profile_investment_policy(db, profile, catalog)
    trajectories = []
    checkpoints = (10, 20, 30, 40, 50)
    run_count = REGIONAL_PROGRESSION_RUNS if sample_runs is None else max(1, int(sample_runs))
    day_limit = REGIONAL_PROGRESSION_MAX_DAYS if max_days is None else max(1, int(max_days))
    # Hold the materialized service boards fixed across repetitions. Seeds still
    # vary team choice and mission outcomes, while this versioned fixture avoids
    # rematerializing millions of equivalent board rows for a large Monte Carlo.
    board_fixture: dict[tuple[int, int, int], tuple[list[dict[str, object]], int, float]] = {}
    for seed_index in range(run_count):
        seed = seed_start + seed_index
        campaign_id = str(uuid5(NAMESPACE_URL, f"guild-board-progression:{profile.name}:{seed}"))
        campaign = CampaignMetadata(
            campaign_id=campaign_id, campaign_name=f"Progressão {profile.name}",
            schema_version=5, content_version=PACK_VERSION, home_region=REGIONS[0][1],
        )
        guild = Guild(campaign_id=campaign_id, name=f"Guilda {profile.name}", level=1)
        db.add_all([campaign, guild])
        db.flush()
        roster = _create_abstract_roster(db, guild, profile)
        roster_size = profile.slots * profile.party_size + profile.gathering_workers
        gross_gold = actions = successes = blocked_team_windows = eligible_team_windows = cycles_simulated = 0
        gross_gold_at_checkpoints: dict[int, int | None] = {level: None for level in checkpoints}
        blocked_window_reasons = {"board_empty": 0, "claimed_by_other_team": 0, "no_contract": 0,
                                  "party_size": 0, "guild_level": 0, "mercenary_level": 0,
                                  "duration": 0, "other_gate": 0}
        offline_pre_absence_actions = post_return_online_actions = 0
        board_power_snapshots = []
        rank_stages = []
        level_days: dict[int, int | None] = {level: None for level in checkpoints}
        if guild.level >= 10:
            level_days[10] = 0
        for day in range(day_limit):
            for cycle_in_day in range(4):
                cycle_number = day * 4 + cycle_in_day
                offline_window = _offline_cycle_window(cycle_in_day) if profile.name == "offline" else None
                _sync_abstract_roster(roster, guild.level)
                pool_size = max(1, int(board_seed_pool_size or run_count))
                fixture_variant = (seed_index % pool_size) if vary_board_seeds else 0
                fixture_key = (fixture_variant, guild.level, cycle_number)
                if fixture_key not in board_fixture:
                    board_fixture[fixture_key] = _sample_real_home_board(db, campaign, guild, cycle_number)
                board, player_power, rank_stage = board_fixture[fixture_key]
                board_power_snapshots.append(player_power)
                rank_stages.append(rank_stage)
                cycles_simulated += 1
                if offline_window is not None and offline_window[2] == "unattended":
                    continue
                eligible_team_windows += profile.slots
                if profile.name == "offline":
                    action_hours, max_actions, _window_kind = offline_window
                    result = _cycle_outcome(
                        profile, board, seed + cycle_number * 7919,
                        action_hours=action_hours, max_actions_per_team=max_actions, guild=guild,
                        player_power_snapshot=player_power, roster_size=roster_size,
                    )
                else:
                    result = _cycle_outcome(
                        profile, board, seed + cycle_number * 7919, guild=guild,
                        player_power_snapshot=player_power, roster_size=roster_size,
                    )
                gross_gold += int(result["gold"] * max(0.0, gold_reward_multiplier))
                actions += result["actions"]
                successes += result["successes"]
                blocked_team_windows += result["blocked_team_windows"]
                for reason, count in result["blocked_window_reasons"].items():
                    blocked_window_reasons[reason] += count
                if profile.name == "offline":
                    if cycle_in_day == 0:
                        offline_pre_absence_actions += result["actions"]
                    else:
                        post_return_online_actions += result["actions"]
            if profile.name == "offline":
                passive_rate = OFFLINE_BASE_GOLD_PER_HOUR + max(0, guild.level - 1) + roster_size * 2
                gross_gold += passive_rate * min(8, OFFLINE_CAP_SECONDS / 3600)
            for level in checkpoints:
                if level_days[level] is None and guild.level >= level:
                    level_days[level] = day + 1
                    gross_gold_at_checkpoints[level] = gross_gold
            if guild.level >= TARGET_LEVEL:
                break
        reached = guild.level >= TARGET_LEVEL
        trajectories.append({
            "seed": seed,
            "level_50_days": next((level_days[level] for level in (50,) if level_days[level] is not None), None),
            "level_checkpoint_days": level_days,
            "final_level": guild.level,
            "cycles_simulated": cycles_simulated,
            "actions": actions,
            "simulated_days": day + 1,
            "successes": successes,
            "blocked_team_windows": blocked_team_windows,
            "eligible_team_windows": eligible_team_windows,
            "productive_team_windows": eligible_team_windows - blocked_team_windows,
            "actions_per_simulated_day": actions / max(1, day + 1),
            "productive_team_window_share": (eligible_team_windows - blocked_team_windows) / max(1, eligible_team_windows),
            "blocked_window_reasons": blocked_window_reasons,
            "offline_pre_absence_actions": offline_pre_absence_actions,
            "post_return_online_actions": post_return_online_actions,
            "average_board_player_power": (sum(board_power_snapshots) / len(board_power_snapshots)) if board_power_snapshots else 0,
            "average_rank_progression_stage": (sum(rank_stages) / len(rank_stages)) if rank_stages else 0,
            "gross_gold": gross_gold,
            "gross_gold_at_level_checkpoints": gross_gold_at_checkpoints,
            "cash_balance_at_level_checkpoints": {
                str(level): (starting_gold - int(setup["total_setup_gold"] if setup_gold_override is None else setup_gold_override)
                             + int(gold_at_level)) if gold_at_level is not None else None
                for level, gold_at_level in gross_gold_at_checkpoints.items()
            },
            "starting_gold": starting_gold,
            "setup_gold_applied": int(setup["total_setup_gold"] if setup_gold_override is None else setup_gold_override),
            "gold_reward_multiplier": gold_reward_multiplier,
            "net_gold_after_profile_setup": starting_gold + gross_gold - int(setup["total_setup_gold"] if setup_gold_override is None else setup_gold_override),
            "reached_level_50": reached,
            "roster_capacity_assumed": roster_size,
        })

    def dist(values):
        clean = sorted(float(value) for value in values if value is not None)
        return {"n": len(clean), "p10": round(clean[int((len(clean) - 1) * .1)], 2),
                "p50": round(clean[int((len(clean) - 1) * .5)], 2),
                "p90": round(clean[int((len(clean) - 1) * .9)], 2)} if clean else {
                    "n": 0, "p10": None, "p50": None, "p90": None,
                }

    reached_count = sum(row["reached_level_50"] for row in trajectories)
    sample_n = max(1, len(trajectories))
    z = 1.959963984540054
    p = reached_count / sample_n
    denominator = 1 + z * z / sample_n
    center = (p + z * z / (2 * sample_n)) / denominator
    margin = z * sqrt((p * (1 - p) + z * z / (4 * sample_n)) / sample_n) / denominator
    return {
        "trajectories": len(trajectories),
        "seed_start": seed_start,
        "seed_end": seed_start + run_count - 1,
        "board_fixture_version": REGIONAL_BOARD_FIXTURE_VERSION,
        "board_fixture_policy": (f"Boards are materialized once per guild level, cycle and seed-pool slot (pool size {max(1, int(board_seed_pool_size or run_count))}); trajectories share one of the distinct boards while team choice and mission outcome RNG vary by seed. Confidence intervals are conditional on this board pool." if vary_board_seeds else "Boards are materialized once per guild level and cycle using the first trajectory seed; all trajectories reuse those boards while team choice and mission outcome RNG vary by seed. Confidence intervals are conditional on this fixed board fixture."),
        "max_days": day_limit,
        "finite_offers_per_home_region_cycle": {"contract": 10, "dungeon": 3, "boss": 1},
        "profile_setup_costs": setup,
        "level_50_days": dist([row["level_50_days"] for row in trajectories]),
        "level_50_reached_percent": round(100 * reached_count / sample_n, 1),
        "level_50_reached_wilson_95_ci_percent": [round(100 * max(0.0, center - margin), 2), round(100 * min(1.0, center + margin), 2)],
        "final_level": dist([row["final_level"] for row in trajectories]),
        "gross_gold": dist([row["gross_gold"] for row in trajectories]),
        "net_gold_after_profile_setup": dist([row["net_gold_after_profile_setup"] for row in trajectories]),
        "actions": dist([row["actions"] for row in trajectories]),
        "actions_per_simulated_day": dist([row["actions_per_simulated_day"] for row in trajectories]),
        "blocked_team_windows": dist([row["blocked_team_windows"] for row in trajectories]),
        "eligible_team_windows": dist([row["eligible_team_windows"] for row in trajectories]),
        "productive_team_windows": dist([row["productive_team_windows"] for row in trajectories]),
        "productive_team_window_share": dist([row["productive_team_window_share"] for row in trajectories]),
        "blocked_window_reasons": {
            key: dist([row["blocked_window_reasons"][key] for row in trajectories])
            for key in ("board_empty", "claimed_by_other_team", "no_contract", "party_size", "guild_level",
                        "mercenary_level", "duration", "other_gate")
        },
        "offline_pre_absence_actions": dist([row["offline_pre_absence_actions"] for row in trajectories]),
        "post_return_online_actions": dist([row["post_return_online_actions"] for row in trajectories]),
        "average_board_player_power": dist([row["average_board_player_power"] for row in trajectories]),
        "average_rank_progression_stage": dist([row["average_rank_progression_stage"] for row in trajectories]),
        "checkpoint_days": {
            str(level): dist([row["level_checkpoint_days"][level] for row in trajectories])
            for level in checkpoints
        },
        "activity_model": (
            "Cada ciclo de seis horas é materializado pelo serviço regional de produção, com uma seed determinística distinta; cada oferta da região natal pode ser reivindicada uma vez por board. A elegibilidade respeita snapshots de tamanho de grupo e duração, quantidade de equipes e janelas de atividade do perfil. O formulário real aceita um subconjunto de mercenários disponíveis, e o serviço valida o tamanho efetivamente enviado contra mínimos e máximos. A rota principal do simulador envia o maior subconjunto que cabe na capacidade fixa da equipe e no máximo da oferta; XP da guilda usa esse tamanho efetivo. Cada equipe possui um segmento disjunto do roster total (`equipes × capacidade`), sem reutilizar mercenários em runs simultâneas. Um roster sintético de Aprendizes comuns acompanha o nível da guilda e recebe os atributos pela função real de progressão; o poder total alimenta o estágio de pesos de rank de produção. No perfil offline, começa-se até uma oferta por equipe antes de uma ausência elegível de 8h. Ao retornar, há 8h online: 4h restantes do ciclo atual e 4h no ciclo seguinte; os demais boards avançam sem ações. Isso reflete a recarga de 2h de estamina por hora online até 8h, sem simular o relógio segundo a segundo. O ouro passivo cobre só as 8h offline, pela fórmula de produção, com roster presumido e Armazém nível 0. "
            "A chance de sucesso permanece no snapshot da oferta, sem ajustes por poder do grupo, equipamento ou habilidades. O sucesso concede o XP e ouro do snapshot; falha concede 25% do XP e nenhum ouro; XP da guilda usa a conversão de produção."
        ),
        "limitations": "O roster é sintético: apenas Aprendizes comuns disponíveis, capacidade fixa por perfil, nenhum mercenário dispensado, níveis sincronizados ao nível da guilda e nenhuma evolução de classe, equipamento, habilidade ou progressão independente por XP. O custo de setup é subtraído do ouro líquido, mas tratado como pré-pago; não se verifica se a guilda consegue financiar contratações e construções ao longo do tempo. Aquisição/consumo de recursos, decisões de mercado e agenda humana dentro das janelas online ficam fora do modelo. Esta é uma projeção de progressão por board regional, não uma validação ponta a ponta do jogo.",
        "trajectory_samples": trajectories,
    }


def run(db) -> dict[str, object]:
    generated_at_local = datetime.now(timezone(timedelta(hours=-3)))
    report_run_id = f"gim-balance-{generated_at_local.strftime('%Y%m%dT%H%M%S%z')}-{SEED}"
    source_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    dirty_tree = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())
    catalogs = {profile.name: _build_profile_catalog(db, profile) for profile in PROFILES}
    base_results = {
        profile.name: [
            _simulate_profile(db, profile, seed=SEED + index, catalog=catalogs[profile.name])
            for index in range(MONTE_CARLO_RUNS)
        ]
        for profile in PROFILES
    }

    def distribution(rows: list[dict[str, object]], key: str) -> dict[str, object]:
        values = sorted(float(row[key]) for row in rows if row.get(key) is not None)
        if not values:
            return {"n": 0, "p10": None, "p50": None, "p90": None, "min": None, "max": None}
        at = lambda percentile: values[min(len(values) - 1, int((len(values) - 1) * percentile))]
        return {"n": len(values), "p10": round(at(.1), 2), "p50": round(at(.5), 2),
                "p90": round(at(.9), 2), "min": round(values[0], 2), "max": round(values[-1], 2)}

    summaries = {}
    for profile in PROFILES:
        rows = base_results[profile.name]
        summaries[profile.name] = {
            "level_50_days": distribution(rows, "days_to_level_50"),
            "actions": distribution(rows, "actions"),
            "gross_gold": distribution(rows, "gross_gold"),
            "failures": distribution(rows, "failures"),
            "reached_level_50_rate_percent": round(100 * sum(row["status"] == "reached_level_50" for row in rows) / len(rows), 2),
            "producer_material_units": distribution(rows, "gathered_material_total"),
        }

    sensitivity = []
    sensitivity_seeds = (SEED + index for index in range(SENSITIVITY_RUNS))
    seed_list = list(sensitivity_seeds)
    for profile in PROFILES:
        for label, multiplier in (("metade_horas", .5), ("base", 1.0), ("uma_vez_e_meia_horas", 1.5)):
            if label == "base":
                selected = base_results[profile.name][:SENSITIVITY_RUNS]
            else:
                selected = [
                    _simulate_profile(db, profile, seed=seed, catalog=catalogs[profile.name], hours_multiplier=multiplier)
                    for seed in seed_list
                ]
            sensitivity.append({
                "profile": profile.name,
                "scenario": label,
                "requested_hours_multiplier": multiplier,
                "effective_hours_per_day": min(profile.online_hours_per_day * multiplier, 8) if profile.name == "offline" else profile.online_hours_per_day * multiplier,
                "level_50_days": distribution(selected, "days_to_level_50"),
                "gross_gold": distribution(selected, "gross_gold"),
            })

    producer = next(profile for profile in PROFILES if profile.name == "produtor")
    warehouse_sensitivity = {}
    for bonus in (0, 10):
        rows = [
            _simulate_profile(db, producer, seed=seed, catalog=catalogs[producer.name], warehouse_guild_bonus_per_level=bonus)
            for seed in seed_list
        ]
        warehouse_sensitivity[str(bonus)] = {
            "scenario_only_capacity_bonus_per_guild_level": bonus,
            "gathered_units": distribution(rows, "gathered_material_total"),
        }

    regional_board_progression = {}
    for profile_index, profile in enumerate(PROFILES):
        regional_board_progression[profile.name] = _simulate_regional_progression(
            db, profile, catalogs[profile.name], SEED + 200_000 + profile_index * REGIONAL_PROGRESSION_RUNS,
        )

    regional_endgame_economy = {}
    for profile_index, profile in enumerate(PROFILES):
        setup = _profile_investment_policy(db, profile, catalogs[profile.name])
        cashflow = _endgame_cashflow(db, profile, SEED + 100_000 + profile_index * SENSITIVITY_RUNS)
        regional_endgame_economy[profile.name] = {"profile_setup_costs": setup, **cashflow}

    return {
        "title": "Guild progression profile simulation",
        "generated_local_date": generated_at_local.date().isoformat(),
        "generated_at_local": generated_at_local.isoformat(timespec="seconds"),
        "report_run_id": report_run_id,
        "source_git_head": source_head,
        "source_worktree_dirty": dirty_tree,
        "seed_start": SEED,
        "monte_carlo_runs_per_profile": MONTE_CARLO_RUNS,
        "sensitivity_runs_per_cell": SENSITIVITY_RUNS,
        "regional_progression_runs_per_profile": REGIONAL_PROGRESSION_RUNS,
        "target_guild_level": TARGET_LEVEL,
        "guild_xp_required_level_1_to_50": _guild_xp_required_to(TARGET_LEVEL),
        "profile_assumptions": [
            {"name": p.name, "activity": p.mode, "hours_per_day": p.online_hours_per_day,
             "party_selection_policy": p.party_selection_policy,
             "selection_policy": ("Prioriza contratos de maior rank; usa XP esperado/h como desempate." if p.name == "combate" else "Maior XP esperado/h dentro das ofertas elegíveis."),
             "party_selection_policy": p.party_selection_policy,
             "parallel_slots": p.slots, "party_size": p.party_size,
             "gathering_workers": p.gathering_workers,
             "roster_size": p.slots * p.party_size + p.gathering_workers}
            for p in PROFILES
        ],
        "rules": {
            "catalog": PACK_KEY,
            "catalog_version": PACK_VERSION,
            "guild_xp": "current guild progression conversion: floor(total mercenary XP / 10), minimum 1 per claim",
            "success": f"Legacy upper-bound runner: {MONTE_CARLO_RUNS} seeds/profile; each action rolls active template base success chance; failed claims grant 25% base XP and no gold",
            "duration_rewards": "Legacy upper-bound runner uses live seeded template duration, XP and gold values and repeats templates inside each daily slot window; this is not the regional board loop",
            "template_choice": "Legacy upper-bound runner picks highest expected guild XP/hour among eligible active templates; optimistic and not board-limited",
            "regional_party_selection": "The regional UI accepts a user-selected set of available mercenary IDs; the service validates selected count against offer min/max, guild office cap, and individual minimum mercenary level. Main regional projection uses the largest valid subset within each team’s fixed roster capacity; exact capacity is retained as a controlled sensitivity. Guild XP uses the selected member count. Team slots own disjoint roster slices.",
            "economy_scope": "Regional board progression sample subtracts a pre-paid setup bundle from earned gold; separate level-50 cashflow/no-spend and candidate-maintenance sensitivities remain scenario analyses, not complete economy proof",
            "offline_scope": "Progressão regional assume até uma oferta iniciada por equipe antes de ausência elegível de 8h, limitada pela estamina; após retorno, modela 8h online (4h restantes no ciclo atual e 4h no próximo). Boards sem janela/interação avançam sem escolhas. Ouro passivo usa a fórmula atual, roster presumido e teto ClockGuard de 8h. A recarga de 2h por hora online até 8h é representada como faixa diária, não como estado segundo a segundo.",
            "producer_scope": "3 gathering assignments each produce 1 unit/minute; base capacity is only the GDD initial 1,500; +10 per guild level is reported only as sensitivity; no consumption is applied",
            "limits": "regional rank weights use a synthetic common-Apprentice roster scaled with guild level; no gear, class evolution, independent XP-based leveling, resource-gated affordability, or live market behavior; interpret as a regional-board model, not end-to-end forecast",
        },
        "profiles": summaries,
        "regional_board_progression": regional_board_progression,
        "controlled_activity_audit": build_controlled_activity_audit(db),
        "sensitivities": sensitivity,
        "producer_capacity_sensitivity": warehouse_sensitivity,
        "regional_board_endgame_economy": regional_endgame_economy,
        "economy_audit": build_economy_audit(db),
    }


def render_markdown(report: dict[str, object]) -> str:
    audit = report["economy_audit"]
    controlled = report["controlled_activity_audit"]
    lines = [
        "# Guild progression to level 50 — profile simulation",
        "",
        f"Progressão por board regional: **{report['regional_progression_runs_per_profile']} sementes por perfil**; a fixture compartilhada materializa cada Vigília de 6h com 10 contratos, 3 masmorras e 1 chefe na região natal uma vez por combinação nível/ciclo. XP da guilda do nível 1 ao 50: **{report['guild_xp_required_level_1_to_50']:,}**.",
        f"Execução regional: `{report.get('regional_progression_execution', {}).get('report_run_id', report['report_run_id'])}`; início {report.get('regional_progression_execution', {}).get('started_at_local', report['generated_at_local'])}, concluída {report.get('regional_progression_execution', {}).get('completed_at_local', report.get('diagnostics_generated_at_local', report['generated_at_local']))} (America/Sao_Paulo). Execução-base preservada: `{report.get('base_execution', {}).get('report_run_id', report['report_run_id'])}` em {report.get('base_execution', {}).get('generated_at_local', report['generated_at_local'])}.",
        f"Fonte simulada: HEAD-base `{report.get('diagnostics_source', {}).get('git_head', report['source_git_head'])}`, worktree sujo `{report.get('diagnostics_source', {}).get('worktree_dirty', report['source_worktree_dirty'])}`, SHA-256 do simulador no início da rodada `{report.get('diagnostics_source', {}).get('simulator_sha256_at_simulation_run', report.get('diagnostics_source', {}).get('simulator_sha256', 'indisponível'))}`; catálogo `{report['rules']['catalog']}` v{report['rules']['catalog_version']}; fixture regional `{report.get('regional_board_fixture_version', REGIONAL_BOARD_FIXTURE_VERSION)}`.",
        "",
        "| Perfil | Premissas | Dias até 50 p10 / p50 / p90 | Atingiu 50 (IC 95%) | Ações/dia p50 | Janelas produtivas p50 | Fração produtiva p50 | Nível final p50 | Poder médio p50 | Estágio de rank p50 | Janelas sem início p50 | Ouro líquido após setup p50 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    assumptions = {item["name"]: item for item in report["profile_assumptions"]}
    for name, row in report["regional_board_progression"].items():
        assumption = assumptions[name]
        teams_label = "equipe" if assumption["parallel_slots"] == 1 else "equipes"
        detail = f"{assumption['hours_per_day']} h/dia, {assumption['parallel_slots']} {teams_label}, capacidade {assumption['party_size']} mercenários/equipe"
        if assumption["party_selection_policy"] == "selectable":
            detail += ", escolhe subconjunto válido por oferta"
        if name == "offline":
            detail = f"1 despacho/equipe pré-ausência; 8h online após retorno, ausência de 8h, {assumption['parallel_slots']} {teams_label}, capacidade {assumption['party_size']}"
        if name == "combate":
            detail += ", prioriza contratos de maior rank"
        if assumption["gathering_workers"]:
            detail += f", {assumption['gathering_workers']} coletores"
        timeline = row["level_50_days"]
        timeline_label = f"{timeline['p10']} / {timeline['p50']} / {timeline['p90']} (n={timeline['n']})"
        lines.append(
            f"| {name} | {detail} | {timeline_label} | "
            f"{row['level_50_reached_percent']:.1f}% ({row['level_50_reached_wilson_95_ci_percent'][0]:.2f}–{row['level_50_reached_wilson_95_ci_percent'][1]:.2f}) | "
            f"{row['actions_per_simulated_day']['p50']:,.2f} | "
            f"{row['productive_team_windows']['p50']:,.0f} | "
            f"{row['productive_team_window_share']['p50']:.1%} | "
            f"{row['final_level']['p50']:,.0f} | "
            f"{row['average_board_player_power']['p50']:,.0f} | "
            f"{row['average_rank_progression_stage']['p50']:.3f} | "
            f"{row['blocked_team_windows']['p50']:,.0f} | "
            f"{row['net_gold_after_profile_setup']['p50']:,.0f} |"
        )
    lines.extend([
        "",
        f"A progressão da tabela usa boards finitos e resultados regionais reais; `n` na coluna de dias informa trajetórias. O IC de Wilson de 95% para a taxa de chegada é condicional à fixture de boards descrita abaixo. ‘Ações/dia’ divide as ações por dias simulados; ‘janelas produtivas’ conta equipes que iniciaram ao menos uma tarefa; ‘fração produtiva’ divide isso por todas as janelas de equipe com interação. ‘Ouro líquido após setup’ soma ouro inicial e recompensas e subtrai o custo total de contratação/construções necessário ao roster assumido. O custo é tratado como pré-pago; a simulação ainda não comprova que a guilda consegue financiá-lo no tempo indicado. O resultado econômico não passa Stage 5.",
        "",
        "## Método da progressão regional",
        "",
        report["regional_board_progression"]["ativo"]["activity_model"],
        "",
        "Cadência: o dia de 24h contém quatro boards/Vigílias de 6h. Nos perfis online, as horas diárias declaradas são distribuídas entre os quatro boards (ativo 3h por board; casual 30 min; produtor e combate 2h). Cada equipe tem capacidade fixa `party_size` e reserva mercenários distintos: por exemplo, 3 equipes × capacidade 3 = 9 mercenários, sem reutilizar indivíduos entre runs paralelas. No modelo principal, o formulário permite escolher qualquer quantidade válida para a oferta e o simulador envia o maior subconjunto permitido pela capacidade e pelo máximo do template, desde que atinja o mínimo; XP da guilda usa esse tamanho real da equipe enviada. O tamanho fixo exato permanece como sensibilidade controlada. A mesma lista finita é compartilhada pelas equipes e uma oferta só pode ser reivindicada uma vez. No offline, o ciclo 0 permite um despacho por equipe antes da ausência de 8h; após o retorno há 8h online, divididas em 4h no ciclo 1 e 4h no ciclo 2; o ciclo 3 avança sem escolhas. Assim, o despacho pré-ausência é uma ação de agenda e não mais 8h de jogo ativo por dia.",
        "Uma janela sem início significa que a equipe não conseguiu iniciar sequer uma oferta no começo da sua janela de ação por tamanho do grupo, nível mínimo da guilda, nível mínimo dos mercenários, duração maior que o tempo disponível ou ausência de contrato no board após o filtro do perfil. Janelas sem interação (offline) não entram no denominador. Estes gates são a elegibilidade aplicada pelo serviço às ofertas; a frequência observada depende também da lista finita sorteada, do perfil e da cadência assumida, e não prova um bloqueio independente no jogo. O estágio de rank deriva do poder do roster sintético e do nível da guilda pelo serviço regional.",
        "### Causa das janelas sem início (p50 por trajetória)",
        "",
        "| Perfil | Nível guilda | Nível mercenário | Grupo incompatível | Duração excede janela | Contrato tomado por outra equipe | Sem contrato | Board vazio | Outros gates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    reason_labels = ("guild_level", "mercenary_level", "party_size", "duration",
                     "claimed_by_other_team", "no_contract", "board_empty", "other_gate")
    for name, row in report["regional_board_progression"].items():
        reasons = row["blocked_window_reasons"]
        lines.append("| " + name + " | " + " | ".join(f"{reasons[key]['p50']:,.0f}" for key in reason_labels) + " |")
    lines.extend([
        "",
        "As causas são classificadas pela primeira etapa que elimina as ofertas. Cada coluna mostra a mediana própria por seed; medianas de causas separadas não precisam somar à mediana de todas as janelas bloqueadas.",
    ])
    lines.extend([
        "",
        f"No perfil offline, a mediana registra {report['regional_board_progression']['offline']['offline_pre_absence_actions']['p50']:,.0f} ações pré-ausência e {report['regional_board_progression']['offline']['post_return_online_actions']['p50']:,.0f} ações online após o retorno.",
        "",
        "### Sensibilidade controlada de horas por janela",
        "",
        f"Auditoria controlada distinta `{report.get('controlled_activity_audit_execution', {}).get('audit_id', 'audit-na')}`: {controlled['sample_cycles_per_level']} boards por nível (6 níveis; 600 boards no total), gerada em {report.get('controlled_activity_audit_execution', {}).get('generated_at_local', report.get('diagnostics_generated_at_local', report['generated_at_local']))}; SHA-256 do simulador `{report.get('controlled_activity_audit_execution', {}).get('simulator_sha256', 'indisponível')}`.",
        "A matriz mantém o mesmo board e três equipes paralelas com capacidade fixa de 3 mercenários distintos cada (3×3 = 9 no roster). Compara a política realista de seleção livre no formulário, com grupo efetivo min(capacidade, máximo da oferta), contra a sensibilidade de tamanho exato 3; em ambos o grupo atende ao mínimo da oferta. XP usa o número efetivamente enviado. Varia também o tempo por equipe e, em separado, a capacidade 2 vs 3, que corresponde a 6 vs 9 mercenários totais entre três equipes distintas. Nenhum mercenário é compartilhado entre equipes simultâneas. O valor diário repete a distribuição de boards em quatro Vigílias, portanto serve para comparar cadências, não é uma previsão independente.",
        "",
        "| Nível | Pool serviço / ativo | Fallback? | Templates aptos exato 3 / selecionável | P(zero elegível) exato 3 / selecionável | Ações/board p50 selecionável em 0,5 / 2 / 3 / 6h | Ações/board p50 tamanho exato 3 | Ações/board p50 capacidade 2 / 3 (3h, 3 equipes) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for level, row in controlled["levels"].items():
        gates = row["contract_offer_gates_per_board"]
        action_values = [row["hours_sensitivity_same_boards"][str(hours)]["selectable_subset_actions_per_board"]["p50"]
                         for hours in (0.5, 2.0, 3.0, 6.0)]
        fixed_action_values = [row["hours_sensitivity_same_boards"][str(hours)]["fixed_exact_actions_per_board"]["p50"]
                               for hours in (0.5, 2.0, 3.0, 6.0)]
        party_values = [row["party_size_sensitivity_same_boards"][str(size)]["actions_per_board"]["p50"]
                        for size in (2, 3)]
        lines.append(
            f"| {level} | {row['mission_candidate_pool_before_fallback']} / {row['full_active_mission_pool']} | "
            f"{'sim' if row['fallback_to_full_active_pool'] else 'não'} | "
            f"{row['candidate_pool_accessibility']['3']['fixed_exact']['eligible_templates_in_selection_pool']} / "
            f"{row['candidate_pool_accessibility']['3']['selectable_within_capacity']['eligible_templates_in_selection_pool']} | "
            f"{row['candidate_pool_accessibility']['3']['fixed_exact']['probability_no_eligible_contract_in_random_ten']:.1%} / "
            f"{row['candidate_pool_accessibility']['3']['selectable_within_capacity']['probability_no_eligible_contract_in_random_ten']:.1%} | "
            + " / ".join(f"{value:,.1f}" for value in action_values) + " | "
            + " / ".join(f"{value:,.1f}" for value in fixed_action_values) + " | "
            + " / ".join(f"{value:,.1f}" for value in party_values) + " |"
        )
    lines.extend([
        "",
        f"### Acesso a ofertas por rank (p50 por board, {controlled['sample_cycles_per_level']} boards por nível)",
        "",
        "Cada célula mostra contratos acessíveis com tamanho exato 3 / selecionável dentro da capacidade 3 / total de contratos daquele rank.",
        "",
        "| Nível da guilda | E | D | C | B | A | S |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for level, row in controlled["levels"].items():
        rank_values = [
            f"{row['rank_accessibility_per_board'][rank]['eligible_for_fixed_group_3']['p50']:,.0f} / "
            f"{row['rank_accessibility_per_board'][rank]['eligible_for_selectable_capacity_3']['p50']:,.0f} / "
            f"{row['rank_accessibility_per_board'][rank]['offered']['p50']:,.0f}"
            for rank in ("E", "D", "C", "B", "A", "S")
        ]
        lines.append("| " + level + " | " + " | ".join(rank_values) + " |")
    lines.extend([
        "",
        "O materializador regional filtra candidatos com nível mínimo de mercenário até 2× o nível da guilda e nível recomendado até max(20, 3× guilda); se restarem menos de 10 candidatos, o serviço recua para o catálogo ativo completo. A seleção tira 10 templates uniformemente do pool final. A chance teórica de zero contrato apto é hipergeométrica sobre esse pool; a tabela também mostra a frequência empírica em boards realmente materializados. O início da missão valida nível da guilda e nível individual dos mercenários. Como o runner assume mercenários exatamente no nível da guilda, ofertas acima desse nível ficam bloqueadas no modelo; jogadores com mercenários mais evoluídos podem iniciá-las. Os ranks são rolados com distribuição por Vigília e depois associados em ordem crescente de desafio aos templates ordenados por nível recomendado, poder e nível mínimo de mercenário. O rank pode, portanto, correlacionar-se à dificuldade e às travas, embora não seja um gate de início em si. A matriz não modela evolução individual, equipamento nem a progressão real de mercenários.",
        "Rank não é gate de início, mas a associação ordenada pode deixar os ranks mais altos concentrados nos templates de maior requisito. A categoria ‘contrato tomado por outra equipe’ identifica quando outra equipe já reivindicou uma oferta que serviria à janela seguinte, porque os 10 contratos do board são compartilhados. A comparação ativo/casual também muda grupo (3 contra 2), slots (3 contra 2) e horas por board (3h contra 0,5h), então a trajetória não isola horas. Não reduzi RNG, requisitos ou progressão: os resultados identificam um possível problema de configuração/acesso a conteúdo que precisa de decisão de balanceamento antes de considerar o Stage 5 aprovado.",
    ])
    lines.extend([
        f"Cada perfil usa {report['regional_progression_runs_per_profile']} trajetórias. A fixture `{report.get('regional_board_fixture_version', REGIONAL_BOARD_FIXTURE_VERSION)}` fixa os boards de cada combinação nível/ciclo a partir da primeira seed e varia as decisões/resultados por seed; a incerteza reportada é condicional a esses boards. Limite da trajetória: {REGIONAL_PROGRESSION_MAX_DAYS} dias. {report['regional_board_progression']['ativo']['limitations']}",
        "",
        "## Comparação antiga de templates (teto otimista; não é aceite)",
        "",
        f"O runner antigo repetia templates sem limite do board. Foram simuladas {report['monte_carlo_runs_per_profile']:,} seeds por perfil; estes prazos não representam a disponibilidade regional e não devem ser usados para balancear nem aprovar Stage 5.",
        "",
        "| Perfil | Dias até 50 p10 / p50 / p90 | Ouro bruto p50 |",
        "|---|---:|---:|",
    ])
    for name, row in report["profiles"].items():
        timeline = row["level_50_days"]
        lines.append(f"| {name} | {timeline['p10']} / {timeline['p50']} / {timeline['p90']} | {row['gross_gold']['p50']:,.0f} |")
    lines.extend([
        "",
        "## Método",
        "",
        "O runner legado e as sensibilidades de horas abaixo existem apenas como referência histórica. O aceite de progressão usa a tabela regional; o fluxo econômico steady-state separado materializa boards novos a cada Vigília.",
        "",
        "## Sensibilidade de horas",
        "",
        "| Perfil | Horas | Dias até 50 p10 / p50 / p90 | Ouro bruto p50 |",
        "|---|---:|---:|---:|",
    ])
    for row in report["sensitivities"]:
        if row["scenario"] == "base":
            continue
        days = row["level_50_days"]
        lines.append(f"| {row['profile']} | {row['effective_hours_per_day']:g} h/dia ({row['scenario']}) | {days['p10']} / {days['p50']} / {days['p90']} | {row['gross_gold']['p50']:,.0f} |")
    capacity = report["producer_capacity_sensitivity"]
    lines.extend([
        "",
        "## Produção e capacidade do perfil produtor",
        "",
        f"Capacidade-base do GDD: 1.500 unidades compartilhadas; mediana coletada até o nível 50: **{report['profiles']['produtor']['producer_material_units']['p50']:,.0f}**. O bônus por nível ainda não tem valor aprovado. Sensibilidade isolada em {report['sensitivity_runs_per_cell']} seeds: sem bônus = {capacity['0']['gathered_units']['p50']:,.0f}; cenário hipotético +10/unidade de nível = {capacity['10']['gathered_units']['p50']:,.0f}. O +10 aparece só como cenário, não como regra. Coleta para quando a capacidade sem consumo enche.",
        "",
        "## Fontes e sinks no conteúdo seedado",
        "",
        f"- Missões repetíveis: renda média ponderada por sucesso varia de **{min(row['mean_success_weighted_gold_per_hour'] for row in audit['gold_sources']['repeatable_missions_by_band'].values()):,.2f}** a **{max(row['mean_success_weighted_gold_per_hour'] for row in audit['gold_sources']['repeatable_missions_by_band'].values()):,.2f} ouro/h** entre faixas; masmorras: **{min(row['mean_success_weighted_gold_per_hour'] for row in audit['gold_sources']['repeatable_dungeons_by_band'].values()):,.2f}** a **{max(row['mean_success_weighted_gold_per_hour'] for row in audit['gold_sources']['repeatable_dungeons_by_band'].values()):,.2f} ouro/h**. O offline acrescenta {audit['gold_sources']['offline_gold_per_hour']} ouro/h até {audit['gold_sources']['offline_cap_hours']:g}h, sujeito ao ClockGuard.",
        f"- Taverna: primeiros 10 Aprendizes custam **{audit['sinks']['tavern']['first_10_apprentice_hires_total_gold']:,} ouro** após a melhoria inicial de 10; especiais custam {audit['sinks']['tavern']['special_offer_gold_by_rarity']}. Refresh manual custa {audit['sinks']['tavern']['manual_offer_refresh_gold']}.",
        f"- Construções: tabela completa de ouro, madeira, minério, cristais e faixas 1–5 está no JSON; a fórmula usa os custos-base seedados e `building_cost_factor`. São gastos opcionais executáveis após os requisitos e estoque necessários.",
        f"- Ferreiro: {audit['sinks']['crafting']['active_recipe_count']} receitas ativas. Custos exatos por receita e materiais estão no JSON; crafting requer receita na rotação e materiais. Refino abre no nível {audit['sinks']['refinement']['unlock_blacksmith_level']} do Ferreiro, com fórmulas `{audit['sinks']['refinement']['gold_formula_per_step']}` ouro e `{audit['sinks']['refinement']['ore_formula_per_step']}` minério. Salvage cobra {', '.join(f"slot {row['slot']}: nível {row['required_level']}, {row['unit_cost']} ouro/unidade" for row in audit['sinks']['salvage']['slots'])} e consome equipamento; retorno é 1–3 materiais aleatórios.",
        f"- Docas→Mercado: o catálogo tem {audit['sinks']['docks']['catalog_offer_count']} pares; {audit['sinks']['docks']['configured_arbitrage_pair_count_market_level_1']} configurações seedadas tinham margem positiva no Mercado nível 1 e {audit['sinks']['docks']['buy_then_market_sell_at_max_market_bonus']['configured_positive_margin_offer_count']} no nível 100. Com o piso aplicado pelo serviço, a margem efetiva positiva é {audit['sinks']['docks']['enforced_positive_margin_pair_count_market_level_1']} no nível 1 e {audit['sinks']['docks']['enforced_positive_margin_pair_count_market_level_100']} no nível 100.",
        "",
        "## Fluxo econômico por board regional no nível 50",
        "",
        "Este complemento usa 25 seeds por perfil e snapshots criados pelo serviço regional real no nível 50, na região natal: 10 contratos, 3 masmorras e 1 chefe por Vigília de 6h, em horizonte de 14 dias/56 ciclos. Cada Vigília rerrola um board com seed determinística distinta. Perfis online podem escolher ofertas em cada board, respeitando grupo e duração. No perfil offline, inicia-se uma oferta por equipe antes da ausência de 8h; após o retorno há 8h online em janelas de 4h no ciclo atual e 4h no seguinte. O ClockGuard limita a ausência a 8h; a recarga online (2h por hora) restaura a estamina até o teto, e boards sem interação não recebem escolhas. O ouro passivo credita no retorno. A chance usa o snapshot sem bônus de poder, equipamento ou evolução de mercenários. O caixa de 14 dias é uma amostra separada do caminho 1–50.",
        "",
        "A configuração do perfil (contratações e construções requeridas) é tratada como já paga antes do horizonte; o custo total aparece na tabela. O tesouro inicia em zero após essa configuração. ‘Sem gasto’ é o controle deliberado. As taxas de manutenção são apenas sensibilidades de gasto candidato, cobradas por Vigília; nenhuma está implementada ou aprovada. A confirmação de 2% por Vigília elegível refere-se à chance de surgimento de rebelião, não à manutenção.",
        "",
        "| Perfil | Ofertas por board | Ações/dia p50 | Setup ouro | Ouro/dia p50 | Saldo sem gasto em 14 dias p50 | Saldo após manutenção 2% / 5% / 10% em 14 dias p50 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for name, row in report["regional_board_endgame_economy"].items():
        no_spend = row["no_spend_gold_balance"]
        maintenance = row["candidate_upkeep_sensitivity"]["rates"]
        balances = [maintenance[key]["treasury_after_horizon_endgame_days"]["p50"]
                    for key in ("upkeep_2_percent", "upkeep_5_percent", "upkeep_10_percent")]
        lines.append(
            f"| {name} | 10 + 3 + 1 | {no_spend['daily_actions_mean']['p50']:,.1f} | "
            f"{row['profile_setup_costs']['total_setup_gold']:,} | "
            f"{row['endgame_daily_gross_gold']['p50']:,.0f} | "
            f"{no_spend['after_horizon_endgame_days']['p50']:,.0f} | "
            f"{balances[0]:,.0f} / {balances[1]:,.0f} / {balances[2]:,.0f} |"
        )
    lines.extend([
        "",
        "## Conclusão econômica e limites",
        "",
        f"Foi confirmado e corrigido o risco no serviço: **{audit['sinks']['docks']['configured_arbitrage_examples_at_market_level_1'][0]['item']}** tinha preço configurado {audit['sinks']['docks']['configured_arbitrage_examples_at_market_level_1'][0]['configured_buy_unit_price']} e podia ser vendido no Mercado nível 1 por {audit['sinks']['docks']['configured_arbitrage_examples_at_market_level_1'][0]['market_sell_at_level_1']} (+{audit['sinks']['docks']['configured_arbitrage_examples_at_market_level_1'][0]['configured_margin_market_level_1']}). O serviço agora publica/cobra pelo menos {audit['sinks']['docks']['configured_arbitrage_examples_at_market_level_1'][0]['effective_buy_unit_price']}, um ouro acima da revenda máxima (nível 100: {audit['sinks']['docks']['configured_arbitrage_examples_at_market_level_1'][0]['market_sell_at_level_100']}); a regressão cobre rotação nova, rotação aberta e compra. Estoque continua finito por rotação. O board regional também limita tentativas a 10 contratos, 3 masmorras e 1 chefe por região a cada 6h; após renovação, a atividade positiva pode se repetir no tempo. Sem gasto recorrente obrigatório, o saldo pode crescer, sem que isso seja arbitragem nem ilimitado dentro de um único board. A estabilidade ainda não passa Stage 5.",
        "",
        "A simulação não modela equipamento/poder, evolução dos mercenários, bônus, custos pagos ao longo da trajetória, restrições reais de roster/desbloqueio, consumo e venda de materiais, drops de itens ou decisões econômicas. Valores por ação são do conteúdo live, mas a escolha do maior XP esperado/hora e os prazos são otimistas. O perfil produtor usa três trabalhadores e uma equipe de missões de dois. O inventário começa em 1.500; qualquer bônus por nível de guilda aparece apenas na sensibilidade, pois o GDD deixa o valor pendente. O gerador não declara aceite final.",
        "",
        "## Reprodução",
        "",
        "```powershell",
        "$env:APP_MODE='desktop'",
        ".\\.venv-desktop\\Scripts\\python.exe scripts\\balance\\simulate_guild_progression_profiles.py",
        "```",
        "",
        f"Catálogo: `{PACK_KEY}` v{report['rules']['catalog_version']}. Amostras: progressão regional {report['regional_progression_runs_per_profile']:,} trajetórias por perfil; auditoria controlada {controlled['sample_cycles_per_level']} boards por nível ({len(controlled['levels'])} níveis); runner legado {report['monte_carlo_runs_per_profile']:,} seeds por perfil; sensibilidades gerais {report['sensitivity_runs_per_cell']:,} seeds por célula; sensibilidade de capacidade do produtor {report['sensitivity_runs_per_cell']:,} seeds por célula; fluxo econômico endgame {report['regional_board_endgame_economy']['ativo']['trajectories']:,} trajetórias por perfil.",
        "",
    ])
    tables = [
        "### Ouro por faixa e tipo de atividade",
        "",
        "| Faixa | Fonte | Templates ativos | Ouro esperado/h (média) | XP esperado por run |",
        "|---|---|---:|---:|---:|",
    ]
    for source_name, source_key in (("Missões", "repeatable_missions_by_band"), ("Masmorras", "repeatable_dungeons_by_band")):
        for band, row in audit["gold_sources"][source_key].items():
            tables.append(f"| {band} | {source_name} | {row['templates']} | {row['mean_success_weighted_gold_per_hour']:,.2f} | {row['mean_xp_per_run_including_failures']:,.2f} |")
    tables.extend([
        "",
        "### Custo efetivo da primeira melhoria de cada construção",
        "",
        "| Construção | Nível de guilda exigido | Ouro | Madeira | Minério | Cristais |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for building in audit["sinks"]["buildings"]:
        cost = building["levels_1_to_5_cost"][0]
        tables.append(f"| {building['effect_type']} | {cost['required_guild_level']} | {cost['gold']} | {cost['wood']} | {cost['ore']} | {cost['crystals']} |")
    recipe_costs = [row["gold_cost_per_craft"] for row in audit["sinks"]["crafting"]["recipes"]]
    tables.extend([
        "",
        f"Crafting tem {len(recipe_costs)} receitas seedadas, com custo de **{min(recipe_costs, default=0)}–{max(recipe_costs, default=0)} ouro** cada; desbloqueio de Ferreiro, rotação e materiais exigidos por receita estão no JSON.",
        "",
        "### Recompra no Mercado por nível",
        "",
        "A coluna de ofertas compara preço seedado bruto / preço efetivo após piso do serviço; margem efetiva usa o preço efetivamente mostrado e cobrado.",
        "",
        "| Nível Mercado | Bônus | Ofertas com margem positiva (configurada / efetiva) | Melhor margem/unidade (configurada / efetiva) |",
        "|---:|---:|---:|---:|",
    ])
    for row in audit["sinks"]["docks"]["resale_by_market_level"]:
        tables.append(f"| {row['market_level']} | {row['value_bonus_percent']}% | {row['configured_positive_margin_pairs']} / {row['enforced_positive_margin_pairs']} | {row['configured_best_margin_gold']} / {row['enforced_best_margin_gold']} |")
    conclusion_index = lines.index("## Conclusão econômica e limites")
    lines[conclusion_index:conclusion_index] = tables + [""]
    return "\n".join(lines)


if __name__ == "__main__":
    configure_database("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    with SessionLocal() as session:
        apply_initial_campaign_content(session)
        session.commit()
    report_path = ROOT / "reports" / "guild_progression_profiles_1_50.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path = ROOT / "reports" / "guild_progression_profiles_1_50.md"
    if "--refresh-diagnostics" in sys.argv:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        refresh_started = datetime.now(timezone(timedelta(hours=-3)))
        if "base_execution" not in report:
            report["base_execution"] = {
                "report_run_id": report.get("report_run_id"),
                "generated_at_local": report.get("generated_at_local"),
                "git_head_base": report.get("source_git_head"),
            }
        refresh_run_id = f"gim-regional-{REGIONAL_PROGRESSION_RUNS}-{refresh_started.strftime('%Y%m%dT%H%M%S%z')}-{SEED}"
        report["report_run_id"] = refresh_run_id
        report["generated_at_local"] = refresh_started.isoformat(timespec="seconds")
        report["generated_local_date"] = refresh_started.date().isoformat()
        report["regional_progression_execution"] = {
            "report_run_id": refresh_run_id,
            "started_at_local": report["generated_at_local"],
            "trajectories_per_profile": REGIONAL_PROGRESSION_RUNS,
            "seed_start_by_profile": {
                profile.name: SEED + 200_000 + profile_index * REGIONAL_PROGRESSION_RUNS
                for profile_index, profile in enumerate(PROFILES)
            },
            "board_fixture_version": REGIONAL_BOARD_FIXTURE_VERSION,
        }
        diagnostic_source_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        diagnostic_source_dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip())
        diagnostic_simulator_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        catalogs = {profile.name: _build_profile_catalog(session, profile) for profile in PROFILES}
        report["profile_assumptions"] = [
            {"name": p.name, "activity": p.mode, "hours_per_day": p.online_hours_per_day,
             "selection_policy": ("Prioriza contratos de maior rank; usa XP esperado/h como desempate."
                                  if p.name == "combate" else "Maior XP esperado/h dentro das ofertas elegíveis."),
             "party_selection_policy": p.party_selection_policy,
             "parallel_slots": p.slots, "party_size": p.party_size,
             "gathering_workers": p.gathering_workers,
             "roster_size": p.slots * p.party_size + p.gathering_workers}
            for p in PROFILES
        ]
        report["regional_board_progression"] = {
            profile.name: _simulate_regional_progression(
                session, profile, catalogs[profile.name], SEED + 200_000 + profile_index * REGIONAL_PROGRESSION_RUNS,
                sample_runs=REGIONAL_PROGRESSION_RUNS,
            )
            for profile_index, profile in enumerate(PROFILES)
        }
        report["regional_board_endgame_economy"] = {
            profile.name: {
                "profile_setup_costs": _profile_investment_policy(session, profile, catalogs[profile.name]),
                **_endgame_cashflow(session, profile, SEED + 100_000 + profile_index * SENSITIVITY_RUNS),
            }
            for profile_index, profile in enumerate(PROFILES)
        }
        report["controlled_activity_audit"] = build_controlled_activity_audit(session)
        report["regional_progression_runs_per_profile"] = REGIONAL_PROGRESSION_RUNS
        report["regional_board_fixture_version"] = REGIONAL_BOARD_FIXTURE_VERSION
        report["diagnostics_source"] = {
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "worktree_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()),
            "simulator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "catalog": PACK_KEY,
            "catalog_version": PACK_VERSION,
            "board_fixture_version": REGIONAL_BOARD_FIXTURE_VERSION,
            "trajectory_seed_start_by_profile": {
                profile.name: SEED + 200_000 + profile_index * REGIONAL_PROGRESSION_RUNS
                for profile_index, profile in enumerate(PROFILES)
            },
        }
        refresh_completed = datetime.now(timezone(timedelta(hours=-3)))
        report["execution_completed_at_local"] = refresh_completed.isoformat(timespec="seconds")
        report["diagnostics_generated_at_local"] = report["execution_completed_at_local"]
        report["regional_progression_execution"]["completed_at_local"] = report["execution_completed_at_local"]
        report["regional_progression_execution"]["source_snapshot_identity"] = (
            f"{diagnostic_source_head}+simulator-sha256:{diagnostic_simulator_hash}+"
            f"{PACK_KEY}@{PACK_VERSION}+{REGIONAL_BOARD_FIXTURE_VERSION}"
        )
        relevant_source_files = (
            "app/services/regional_cycle_service.py", "app/services/guild_progression_service.py",
            "app/services/progression_service.py", "app/core/game_balance.py",
            "app/seeds/campaign_content.py", "app/seeds/massive_content.py",
        )
        report["diagnostics_source"] = {
            "git_head_base": diagnostic_source_head,
            "worktree_dirty": diagnostic_source_dirty,
            "simulator_sha256_at_simulation_run": diagnostic_simulator_hash,
            "relevant_source_sha256": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in relevant_source_files
            },
            "source_snapshot_identity": report["regional_progression_execution"]["source_snapshot_identity"],
            "catalog": PACK_KEY,
            "catalog_version": PACK_VERSION,
            "board_fixture_version": REGIONAL_BOARD_FIXTURE_VERSION,
            "trajectory_seed_start_by_profile": report["regional_progression_execution"]["seed_start_by_profile"],
        }
        report["controlled_activity_audit_execution"] = {
            "audit_id": f"gim-controlled-activity-{refresh_started.strftime('%Y%m%dT%H%M%S%z')}",
            "generated_at_local": report["execution_completed_at_local"],
            "sample_cycles_per_level": report["controlled_activity_audit"]["sample_cycles_per_level"],
            "total_materialized_boards": report["controlled_activity_audit"]["sample_cycles_per_level"] * len(report["controlled_activity_audit"]["levels"]),
            "simulator_sha256": diagnostic_simulator_hash,
            "catalog": PACK_KEY,
            "catalog_version": PACK_VERSION,
        }
    else:
        report = run(session)
        report["diagnostics_generated_at_local"] = report["generated_at_local"]
    output = json.dumps(report, ensure_ascii=False, indent=2)
    report_path.write_text(output + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Relatórios salvos em: {report_path} e {markdown_path}")
    print(f"Execução: {report['report_run_id']}; diagnósticos: {report.get('diagnostics_generated_at_local', report['generated_at_local'])}")
