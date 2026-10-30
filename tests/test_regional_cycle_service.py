import gc
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.database.connection import SessionLocal, configure_database
from app.models.campaign import CampaignMetadata
from app.models.guild import Guild
from app.models.mercenary import MercenaryClass
from app.models.dungeon import DungeonTemplate
from app.models.mission import MissionTemplate
from app.models.regional import (
    RegionalCpuCyclePlan,
    RegionalCpuMercenary,
    RegionalCpuResource,
    RegionalCycle,
    RegionalCycleRegion,
    RegionalGuildState,
    RegionalOffer,
    RegionalRunOutcome,
    RegionalWorldState,
)
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.repositories.mercenary_repository import create_mercenary
from app.services.mission_service import claim_mission_loot, start_mission
from app.services import mission_service, regional_cycle_service
from app.services.regional_cycle_service import (
    CYCLE_SECONDS,
    LEGACY_VIGILIA_RULES_VERSION,
    RANKS,
    advance_regional_world,
    cpu_initial_profile_values,
    regional_stage_for_region,
    rival_calm_for_cycle,
    simulate_rank_distribution,
)
from app.core.dependencies import CampaignPlayer
from app.routes.regional_routes import regional_index, templates as regional_templates


class RegionalCycleSimulationTests(unittest.TestCase):
    def test_seeded_cpu_simulation_100_cycles_and_campaign_isolation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                with patch(
                    "app.services.campaign_service.uuid4",
                    side_effect=[UUID("00000000-0000-4000-8000-000000000001"), UUID("00000000-0000-4000-8000-000000000002")],
                ):
                    first = campaigns.create_campaign("Simulação Vigília", "Guilda Simulada")
                    second = campaigns.create_campaign("Isolamento Vigília", "Outra Guilda")
                campaigns.activate_campaign(first.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, first.campaign_id)
                    guild, _resources = get_current_guild_context(db, first.campaign_id)
                    self.assertIsNotNone(campaign)
                    self.assertIsNotNone(guild)
                    now = campaign.created_at_utc + timedelta(seconds=100 * CYCLE_SECONDS)
                    advance_regional_world(db, campaign, guild, now)

                    region_count = db.scalar(select(func.count(RegionalCycle.id)).where(
                        RegionalCycle.campaign_id == first.campaign_id,
                        RegionalCycle.status == "completed",
                    ))
                    self.assertEqual(region_count, 100)
                    guild_states = list(db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == first.campaign_id,
                    )))
                    self.assertEqual(sum(state.guild_id is not None for state in guild_states), 1)
                    self.assertEqual(len(guild_states), 25)

                    summaries = {}
                    for horizon in (10, 50, 100):
                        plans = list(db.scalars(
                            select(RegionalCpuCyclePlan)
                            .join(RegionalCycle, RegionalCycle.id == RegionalCpuCyclePlan.cycle_id)
                            .where(
                                RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                                RegionalCycle.cycle_number < horizon,
                            )
                        ))
                        successes = sum(plan.successes for plan in plans)
                        actions = sum(plan.actions for plan in plans)
                        by_profile = {}
                        for plan in plans:
                            state = db.get(RegionalGuildState, plan.guild_state_id)
                            bucket = by_profile.setdefault(state.profile, {
                                "actions": 0, "successes": 0, "gold": 0, "xp": 0,
                                "guild_ids": set(), "roster_slots": 0, "roster_observations": 0,
                            })
                            bucket["actions"] += plan.actions
                            bucket["successes"] += plan.successes
                            bucket["gold"] += plan.gold_earned
                            bucket["xp"] += plan.xp_earned
                            bucket["guild_ids"].add(state.id)
                            bucket["roster_slots"] += len(json.loads(plan.roster_snapshot_json))
                            bucket["roster_observations"] += 1
                        for bucket in by_profile.values():
                            bucket["guild_count"] = len(bucket["guild_ids"])
                            del bucket["guild_ids"]
                            bucket["success_rate"] = round(bucket["successes"] / max(1, bucket["actions"]), 4)
                            bucket["gold_per_action"] = round(bucket["gold"] / max(1, bucket["actions"]), 2)
                            bucket["gold_per_guild"] = round(bucket["gold"] / max(1, bucket["guild_count"]), 2)
                            bucket["avg_roster_size"] = round(
                                bucket["roster_slots"] / max(1, bucket["roster_observations"]), 2,
                            )
                            del bucket["roster_slots"]
                            del bucket["roster_observations"]
                        summaries[horizon] = {
                            "cycles": horizon,
                            "actions": actions,
                            "successes": successes,
                            "success_rate": round(successes / actions, 4) if actions else 0,
                            "gold_earned": sum(plan.gold_earned for plan in plans),
                            "xp_earned": sum(plan.xp_earned for plan in plans),
                            "profiles": by_profile,
                        }
                        self.assertGreater(actions, 0)
                        self.assertGreaterEqual(successes, 0)
                        self.assertLessEqual(successes, actions)
                        self.assertEqual(set(by_profile), {"strong", "medium", "new"})
                        self.assertGreater(by_profile["strong"]["success_rate"], 0)
                        self.assertGreater(by_profile["medium"]["success_rate"], 0)
                        self.assertGreater(by_profile["new"]["success_rate"], 0)

                    contracts = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.campaign_id == first.campaign_id,
                        RegionalOffer.cycle_number < 100,
                        RegionalOffer.offer_type == "contract",
                    )))
                    self.assertEqual(len(contracts), 100 * 5 * 10)
                    for cycle_number in range(100):
                        for region_code in {offer.region_code for offer in contracts}:
                            cycle_ranks = [offer.rank for offer in contracts
                                           if offer.cycle_number == cycle_number and offer.region_code == region_code]
                            self.assertEqual(len(cycle_ranks), 10)
                            self.assertLessEqual(max(cycle_ranks.count(rank) for rank in set(cycle_ranks)), 3)

                    all_regional_offers = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.campaign_id == first.campaign_id,
                        RegionalOffer.cycle_number < 100,
                    )))
                    offer_by_id = {offer.id: offer for offer in all_regional_offers}
                    by_rank = {rank: {
                        "offers": 0, "level": 0, "power": 0, "chance": 0,
                        "gold": 0, "xp": 0, "duration_seconds": 0,
                        "cpu_actions": 0, "cpu_successes": 0, "cpu_gold": 0, "cpu_xp": 0,
                        "expected_chance_points": 0,
                    } for rank in RANKS}
                    for offer in all_regional_offers:
                        bucket = by_rank[offer.rank]
                        bucket["offers"] += 1
                        bucket["level"] += offer.recommended_level_snapshot
                        bucket["power"] += offer.recommended_power_snapshot
                        bucket["chance"] += offer.success_chance_snapshot
                        bucket["gold"] += offer.gold_reward_snapshot
                        bucket["xp"] += offer.xp_reward_snapshot
                        bucket["duration_seconds"] += offer.duration_seconds_snapshot
                    for plan in db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                    )):
                        decisions = json.loads(plan.decisions_json)
                        outcomes = json.loads(plan.outcomes_json)
                        outcome_by_offer = {outcome["offer_id"]: outcome for outcome in outcomes}
                        for decision in decisions:
                            bucket = by_rank[decision["rank"]]
                            result = outcome_by_offer[decision["offer_id"]]
                            bucket["cpu_actions"] += 1
                            bucket["cpu_successes"] += int(result["success"])
                            bucket["expected_chance_points"] += decision["chance"]
                            bucket["cpu_gold"] += result["gold"]
                            bucket["cpu_xp"] += result["xp"]
                    for bucket in by_rank.values():
                        for metric in ("level", "power", "chance", "gold", "xp", "duration_seconds"):
                            bucket[f"avg_{metric}"] = round(bucket[metric] / max(1, bucket["offers"]), 2)
                        bucket["cpu_success_rate"] = round(
                            bucket["cpu_successes"] / max(1, bucket["cpu_actions"]), 4,
                        )
                        bucket["expected_success_rate"] = round(
                            bucket["expected_chance_points"] / max(1, bucket["cpu_actions"] * 100), 4,
                        )
                        bucket["success_rate_minus_expected"] = round(
                            bucket["cpu_success_rate"] - bucket["expected_success_rate"], 4,
                        )
                    by_type_and_rank = {}
                    for offer_type in ("contract", "dungeon", "boss"):
                        typed = {}
                        for rank in RANKS:
                            offers = [row for row in all_regional_offers
                                      if row.offer_type == offer_type and row.rank == rank]
                            typed[rank] = {
                                "offers": len(offers),
                                "avg_level": round(sum(row.recommended_level_snapshot for row in offers)
                                                   / max(1, len(offers)), 2),
                                "avg_power": round(sum(row.recommended_power_snapshot for row in offers)
                                                   / max(1, len(offers)), 2),
                                "avg_chance": round(sum(row.success_chance_snapshot for row in offers)
                                                    / max(1, len(offers)), 2),
                                "avg_gold": round(sum(row.gold_reward_snapshot for row in offers)
                                                  / max(1, len(offers)), 2),
                                "avg_xp": round(sum(row.xp_reward_snapshot for row in offers)
                                                / max(1, len(offers)), 2),
                                "avg_duration_seconds": round(sum(row.duration_seconds_snapshot for row in offers)
                                                               / max(1, len(offers)), 2),
                            }
                        by_type_and_rank[offer_type] = typed
                    cpu_resources = list(db.scalars(select(regional_cycle_service.RegionalCpuResource).where(
                        regional_cycle_service.RegionalCpuResource.campaign_id == first.campaign_id,
                    )))
                    self.assertTrue(all(resource.amount >= 0 for resource in cpu_resources))
                    profile_progression = {}
                    for state in guild_states:
                        values = profile_progression.setdefault(state.profile, {
                            "guilds": 0, "avg_level": 0, "avg_power": 0,
                            "avg_reputation": 0, "avg_influence": 0,
                        })
                        values["guilds"] += 1
                        values["avg_level"] += state.level
                        values["avg_power"] += state.power
                        values["avg_reputation"] += state.reputation
                        values["avg_influence"] += state.influence
                    for values in profile_progression.values():
                        count = max(1, values["guilds"])
                        for key in ("avg_level", "avg_power", "avg_reputation", "avg_influence"):
                            values[key] = round(values[key] / count, 2)
                    region_states = list(db.scalars(select(regional_cycle_service.RegionalRegionState).where(
                        regional_cycle_service.RegionalRegionState.campaign_id == first.campaign_id,
                    )))
                    region_trajectory = {
                        "regions": len(region_states),
                        "security_min_max": [
                            min((row.security for row in region_states), default=0),
                            max((row.security for row in region_states), default=0),
                        ],
                        "threat_min_max": [
                            min((row.threat for row in region_states), default=0),
                            max((row.threat for row in region_states), default=0),
                        ],
                        "influence_min_max": [
                            min((row.influence for row in region_states), default=0),
                            max((row.influence for row in region_states), default=0),
                        ],
                    }
                    candidate_cpu_actions = {}
                    for plan in db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                    )):
                        cycle_number = db.get(RegionalCycle, plan.cycle_id).cycle_number
                        state = db.get(RegionalGuildState, plan.guild_state_id)
                        if state.profile == "player":
                            continue
                        guild_effect = {
                            "slot": state.slot,
                            "archetype": state.archetype,
                            "successes_by_rank": {rank: 0 for rank in RANKS},
                            "failures_by_rank": {rank: 0 for rank in RANKS},
                        }
                        for outcome in json.loads(plan.outcomes_json):
                            target = "successes_by_rank" if outcome["success"] else "failures_by_rank"
                            guild_effect[target][outcome["rank"]] += 1
                        candidate_cpu_actions.setdefault((cycle_number, state.region_code), []).append(guild_effect)

                    def simulate_region_pressure(
                        impact_base: float, impact_per_rank: float, include_cpu: bool,
                    ):
                        results = {}
                        def impact(counts):
                            return sum(
                                count * (impact_base + impact_per_rank * (RANKS.index(rank) + 1))
                                for rank, count in counts.items()
                            )

                        for region in region_states:
                            security, threat = 50, 25
                            strong_rival_present = any(
                                state.region_code == region.region_code
                                and state.profile == "strong"
                                and state.active
                                for state in guild_states
                            )
                            first_portal_eligible = None
                            first_rebellion_eligible = None
                            portal_hazards = []
                            for cycle_number in range(100):
                                groups = candidate_cpu_actions.get(
                                    (cycle_number, region.region_code), [],
                                ) if include_cpu else []
                                cycle_actions = sum(
                                    sum(group["successes_by_rank"].values())
                                    + sum(group["failures_by_rank"].values())
                                    for group in groups
                                )
                                if cycle_actions == 0:
                                    threat = max(0, min(100, threat + 1))
                                    security = max(0, min(100, security - 1))
                                for group in sorted(groups, key=lambda row: row["slot"]):
                                    success_impact = impact(group["successes_by_rank"])
                                    failure_impact = impact(group["failures_by_rank"])
                                    threat = round(max(0, min(100, threat - success_impact + failure_impact)), 4)
                                    security = round(max(0, min(100, security + success_impact - failure_impact)), 4)
                                if (
                                    strong_rival_present
                                    and cycle_number < regional_cycle_service.RIVAL_CALM_WINDOW_CYCLES
                                ):
                                    security = round(min(100, security + regional_cycle_service.RIVAL_CALM_IMPACT_PER_CYCLE), 4)
                                    threat = round(max(0, threat - regional_cycle_service.RIVAL_CALM_IMPACT_PER_CYCLE), 4)
                                if threat >= 70:
                                    first_portal_eligible = first_portal_eligible or cycle_number
                                    portal_hazards.append(min(0.25, 0.05 + (threat - 70) * (0.20 / 30)))
                                if threat >= 85 and security <= 25 and first_rebellion_eligible is None:
                                    first_rebellion_eligible = cycle_number
                            no_portal_probability = 1.0
                            for chance in portal_hazards:
                                no_portal_probability *= 1 - chance
                            results[region.region_code] = {
                                "first_portal_eligible_cycle": first_portal_eligible,
                                "portal_eligible_cycles": len(portal_hazards),
                                "expected_portal_rolls": round(sum(portal_hazards), 3),
                                "portal_roll_probability_ignoring_active_event_suppression": round(
                                    1 - no_portal_probability, 4,
                                ),
                                "first_rebellion_eligible_cycle": first_rebellion_eligible,
                                "final_security": security,
                                "final_threat": threat,
                            }
                        return results

                    candidate_idle_without_cpu = simulate_region_pressure(0, 0, False)
                    candidate_cpu_pressure = simulate_region_pressure(0.02, 0.02, True)
                    pressure_sweep = {}
                    for impact_scale in (0.01, 0.015, 0.02, 0.025, 0.03):
                        result = simulate_region_pressure(impact_scale, impact_scale, True)
                        rebellion_cycles = [
                            row["first_rebellion_eligible_cycle"]
                            for row in result.values()
                            if row["first_rebellion_eligible_cycle"] is not None
                        ]
                        portal_cycles = [
                            row["first_portal_eligible_cycle"]
                            for row in result.values()
                            if row["first_portal_eligible_cycle"] is not None
                        ]
                        pressure_sweep[f"impact_base_and_rank_scale_{impact_scale}"] = {
                            "rebellion_regions_by_cycle_100": len(rebellion_cycles),
                            "portal_regions_by_cycle_100": len(portal_cycles),
                            "first_rebellion_cycle_min_max": [
                                min(rebellion_cycles, default=None), max(rebellion_cycles, default=None),
                            ],
                            "first_portal_cycle_min_max": [
                                min(portal_cycles, default=None), max(portal_cycles, default=None),
                            ],
                            "expected_portal_rolls": round(sum(
                                row["expected_portal_rolls"] for row in result.values()
                            ), 3),
                        }

                    rank_template_stats = {
                        offer_type: {rank: {"count": 0, "level": 0, "power": 0,
                                           "mercenary_requirement": 0, "guild_requirement": 0}
                                     for rank in RANKS}
                        for offer_type in ("contract_early", "contract_mid", "contract_late", "dungeon", "boss")
                    }
                    contract_stages = (
                        ("early", 1, 1, 0.0), ("mid", 25, 25, 0.5), ("late", 50, 350, 1.0),
                    )
                    contract_pools = {
                        stage_name: regional_cycle_service._contract_candidates(db, guild_level, roster_level)
                        for stage_name, guild_level, roster_level, _stage_value in contract_stages
                    }
                    candidate_pool_metrics = {}
                    for stage_name, guild_level, roster_level, _stage_value in contract_stages:
                        pool = contract_pools[stage_name]
                        challenge_ceiling = max(20, guild_level, roster_level)
                        self.assertGreaterEqual(len(pool), 10)
                        self.assertLessEqual(max(row.recommended_level for row in pool), challenge_ceiling)
                        self.assertLessEqual(max(row.required_min_mercenary_level for row in pool), challenge_ceiling)
                        candidate_pool_metrics[stage_name] = {
                            "guild_level": guild_level,
                            "roster_level": roster_level,
                            "challenge_ceiling": challenge_ceiling,
                            "templates": len(pool),
                            "max_recommended_level": max(row.recommended_level for row in pool),
                            "max_required_mercenary_level": max(row.required_min_mercenary_level for row in pool),
                        }
                    guild_only_pool = regional_cycle_service._contract_candidates(db, 50, 50)
                    self.assertLessEqual(max(row.recommended_level for row in guild_only_pool), 50)
                    candidate_pool_metrics["guild_50_roster_50"] = {
                        "guild_level": 50,
                        "roster_level": 50,
                        "challenge_ceiling": 50,
                        "templates": len(guild_only_pool),
                        "max_recommended_level": max(row.recommended_level for row in guild_only_pool),
                        "max_required_mercenary_level": max(
                            row.required_min_mercenary_level for row in guild_only_pool
                        ),
                    }
                    self.assertGreaterEqual(candidate_pool_metrics["late"]["max_recommended_level"], 301)
                    late_high_rank_counts = {"offers": 0, "eligible": 0}
                    early_s_levels = []
                    early_startability = {
                        "boards": 0,
                        "startable_offers": 0,
                        "power_at_or_above_recommendation": 0,
                        "startable_count_histogram": [0] * 11,
                        "boards_with_at_least_two_startable": 0,
                        "by_seed": {},
                    }
                    dungeon_pool = list(db.scalars(select(DungeonTemplate).where(
                        DungeonTemplate.is_active.is_(True),
                        DungeonTemplate.content_type == "dungeon",
                        DungeonTemplate.level_band.is_not(None),
                    ).order_by(DungeonTemplate.id)))
                    boss_pool = sorted(list(db.scalars(select(DungeonTemplate).where(
                        DungeonTemplate.is_active.is_(True),
                        DungeonTemplate.content_type == "boss",
                    ).order_by(DungeonTemplate.id))), key=regional_cycle_service._template_rank_order)

                    def add_template_rank(offer_type, template, rank):
                        bucket = rank_template_stats[offer_type][rank]
                        bucket["count"] += 1
                        bucket["level"] += int(template.recommended_level or 1)
                        bucket["mercenary_requirement"] += int(template.required_min_mercenary_level or 1)
                        bucket["guild_requirement"] += int(template.required_guild_level or 1)
                        if isinstance(template, MissionTemplate):
                            bucket["power"] += max(1, int(template.recommended_power or 0))
                        else:
                            bucket["power"] += max(
                                1, int(template.required_total_power or template.recommended_level * 10),
                            )

                    correlation_seeds = (1842, 5271, 9013, 17021, 42893)
                    for seed in correlation_seeds:
                      seed_startability = {"boards": 0, "startable_offers": 0, "power_at_or_above_recommendation": 0}
                      for sample_cycle in range(2_000):
                        for stage_name, guild_level, roster_level, stage_value in contract_stages:
                            contract_rng = regional_cycle_service._rng(
                                "rank-template-correlation", seed, stage_name, sample_cycle,
                            )
                            contract_templates = regional_cycle_service._select_contract_templates(
                                contract_pools[stage_name], 10, contract_rng, guild_level, roster_level,
                            )
                            if stage_name == "early":
                                # Representative first playable roster: one level-1
                                # mercenary with conservative starter-class power 14,
                                # guild level 1, no buildings, and office level 0.
                                startable_templates = [template for template in contract_templates if (
                                    template.required_guild_level <= 1
                                    and template.required_min_mercenary_level <= 1
                                    and (
                                        template.required_building_type is None
                                        or template.required_building_level <= 0
                                    )
                                    and template.min_party_size <= 1 <= template.max_party_size
                                )]
                                startable_count = len(startable_templates)
                                early_startability["boards"] += 1
                                early_startability["startable_offers"] += startable_count
                                early_startability["power_at_or_above_recommendation"] += sum(
                                    int(template.recommended_power or 0) <= 14
                                    for template in startable_templates
                                )
                                early_startability["startable_count_histogram"][startable_count] += 1
                                early_startability["boards_with_at_least_two_startable"] += int(startable_count >= 2)
                                seed_startability["boards"] += 1
                                seed_startability["startable_offers"] += startable_count
                                seed_startability["power_at_or_above_recommendation"] += sum(
                                    int(template.recommended_power or 0) <= 14
                                    for template in startable_templates
                                )
                            contract_ranks = regional_cycle_service._roll_contract_rank_set(
                                contract_rng, regional_cycle_service.rank_weights_for_stage(stage_value),
                            )
                            for template, rank in regional_cycle_service._pair_contract_templates_with_ranks(
                                contract_templates, contract_ranks,
                            ):
                                add_template_rank(f"contract_{stage_name}", template, rank)
                                if stage_name == "early" and rank == "S":
                                    early_s_levels.append(template.recommended_level)
                                if stage_name == "late" and rank in {"B", "A", "S"}:
                                    late_high_rank_counts["offers"] += 1
                                    eligible = (
                                        template.required_guild_level <= guild_level
                                        and template.required_min_mercenary_level <= roster_level
                                        and template.required_building_level <= 100
                                        and template.min_party_size <= 5
                                    )
                                    late_high_rank_counts["eligible"] += int(eligible)
                        rng = regional_cycle_service._rng("rank-template-correlation", seed, "other", sample_cycle)
                        dungeon_templates = regional_cycle_service._select_templates(dungeon_pool, 3, rng)
                        dungeon_ranks = sorted((regional_cycle_service._roll_rank(
                            rng, regional_cycle_service._rank_weight_payload(0.0)["dungeon"],
                        ) for _ in dungeon_templates), key=RANKS.index)
                        for template, rank in zip(
                            sorted(dungeon_templates, key=regional_cycle_service._template_rank_order),
                            dungeon_ranks,
                        ):
                            add_template_rank("dungeon", template, rank)
                        boss_rank = regional_cycle_service._roll_rank(
                            rng, regional_cycle_service._rank_weight_payload(0.0)["boss"],
                        )
                        boss_index = round(
                            RANKS.index(boss_rank) * (len(boss_pool) - 1) / (len(RANKS) - 1),
                        )
                        add_template_rank("boss", boss_pool[boss_index], boss_rank)
                      early_startability["by_seed"][str(seed)] = {
                          "boards": seed_startability["boards"],
                          "avg_startable_offers": round(
                              seed_startability["startable_offers"] / max(1, seed_startability["boards"]), 3,
                          ),
                          "avg_power_at_or_above_recommendation": round(
                              seed_startability["power_at_or_above_recommendation"] / max(1, seed_startability["boards"]), 3,
                          ),
                      }

                    rank_template_correlation = {}
                    for offer_type, ranks in rank_template_stats.items():
                        rank_template_correlation[offer_type] = {}
                        for rank, totals in ranks.items():
                            count = max(1, totals["count"])
                            rank_template_correlation[offer_type][rank] = {
                                "offers": totals["count"],
                                "avg_level": round(totals["level"] / count, 2),
                                "avg_power": round(totals["power"] / count, 2),
                                "avg_required_mercenary_level": round(totals["mercenary_requirement"] / count, 2),
                                "avg_required_guild_level": round(totals["guild_requirement"] / count, 2),
                            }
                        for metric in ("avg_level", "avg_power"):
                            values = [rank_template_correlation[offer_type][rank][metric] for rank in RANKS]
                            self.assertEqual(values, sorted(values), f"{offer_type} {metric} rank order")
                    early_contracts = rank_template_correlation["contract_early"]
                    mid_contracts = rank_template_correlation["contract_mid"]
                    late_contracts = rank_template_correlation["contract_late"]
                    self.assertEqual(regional_cycle_service.rank_weights_for_stage(0.0)["S"], 1)
                    for contracts_at_stage in (early_contracts, mid_contracts, late_contracts):
                        self.assertGreaterEqual(
                            contracts_at_stage["S"]["avg_level"], contracts_at_stage["E"]["avg_level"] + 5,
                        )
                    self.assertTrue(early_s_levels)
                    self.assertGreaterEqual(
                        sum(early_s_levels) / len(early_s_levels), 10,
                        "early S contracts should average into aspirational content",
                    )
                    early_startability["avg_startable_offers_per_board"] = round(
                        early_startability["startable_offers"] / max(1, early_startability["boards"]), 3,
                    )
                    early_startability["percent_boards_with_at_least_two_startable"] = round(
                        100 * early_startability["boards_with_at_least_two_startable"]
                        / max(1, early_startability["boards"]), 2,
                    )
                    self.assertGreaterEqual(early_startability["avg_startable_offers_per_board"], 2.5)
                    self.assertGreaterEqual(early_startability["percent_boards_with_at_least_two_startable"], 75)
                    self.assertGreaterEqual(min(
                        count for count, frequency in enumerate(early_startability["startable_count_histogram"])
                        if frequency
                    ), 2)
                    early_startability["power_is_a_success_recommendation_not_a_start_gate"] = True
                    self.assertGreater(mid_contracts["S"]["avg_level"], early_contracts["S"]["avg_level"])
                    self.assertGreater(late_contracts["S"]["avg_level"], mid_contracts["S"]["avg_level"])
                    self.assertGreater(late_high_rank_counts["offers"], 0)
                    self.assertEqual(late_high_rank_counts["eligible"], late_high_rank_counts["offers"])
                    rank_template_correlation["late_high_rank_eligibility"] = late_high_rank_counts
                    rank_template_correlation["candidate_pool_by_stage"] = candidate_pool_metrics
                    rank_template_correlation["early_startability"] = early_startability

                    boss_offers = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.campaign_id == first.campaign_id,
                        RegionalOffer.cycle_number < 100,
                        RegionalOffer.offer_type == "boss",
                    )))
                    boss_counts = {rank: sum(offer.rank == rank for offer in boss_offers)
                                   for rank in "EDCBAS"}
                    rank_curves = {
                        label: simulate_rank_distribution(stage, seed=1842, cycles=10_000)
                        for label, stage in (("early", 0.0), ("mid", 0.5), ("late", 1.0))
                    }
                    self.assertLess(rank_curves["early"]["rank_percentages"]["S"], 2.0)
                    def mean_rank(counts):
                        total = sum(counts.values())
                        return sum(index * counts[rank] for index, rank in enumerate(RANKS)) / max(1, total)

                    for curve in rank_curves.values():
                        self.assertLessEqual(curve["max_contract_rank_slots_in_cycle"], 3)
                        self.assertGreater(
                            mean_rank(curve["dungeon_rank_counts"]),
                            mean_rank(curve["uncapped_regional_rank_counts"]),
                        )
                        self.assertGreater(
                            mean_rank(curve["boss_rank_counts"]),
                            mean_rank(curve["dungeon_rank_counts"]),
                        )
                    self.assertLess(
                        rank_curves["early"]["b_to_s_per_cycle"],
                        rank_curves["mid"]["b_to_s_per_cycle"],
                    )
                    self.assertLess(
                        rank_curves["mid"]["b_to_s_per_cycle"],
                        rank_curves["late"]["b_to_s_per_cycle"],
                    )
                    self.assertGreaterEqual(rank_curves["late"]["b_to_s_per_cycle"], 5)
                    self.assertLessEqual(rank_curves["late"]["b_to_s_per_cycle"], 6)
                    self.assertEqual(
                        rank_curves,
                        {
                            label: simulate_rank_distribution(stage, seed=1842, cycles=10_000)
                            for label, stage in (("early", 0.0), ("mid", 0.5), ("late", 1.0))
                        },
                    )
                    self.assertEqual(
                        [regional_cycle_service.regional_outcome_impact(rank) for rank in RANKS],
                        sorted(regional_cycle_service.regional_outcome_impact(rank) for rank in RANKS),
                    )
                    self.assertEqual(
                        [regional_cycle_service.regional_outcome_impact(rank) for rank in RANKS],
                        sorted(regional_cycle_service.regional_outcome_impact(rank) for rank in RANKS),
                    )
                    self.assertGreater(
                        min(regional_cycle_service.regional_outcome_impact(rank) for rank in RANKS), 0,
                    )
                    self.assertEqual(
                        len({regional_cycle_service.regional_outcome_impact(rank) for rank in RANKS}), 6,
                    )
                    for row in region_states:
                        candidate = candidate_cpu_pressure[row.region_code]
                        self.assertEqual(row.security, candidate["final_security"])
                        self.assertEqual(row.threat, candidate["final_threat"])
                    rebellion_candidates = [
                        row["first_rebellion_eligible_cycle"]
                        for row in candidate_cpu_pressure.values()
                        if row["first_rebellion_eligible_cycle"] is not None
                    ]
                    print("REGIONAL_SIMULATION_METRICS=" + json.dumps({
                        "cycles": summaries,
                        "rank_curves_10000_each": rank_curves,
                        "boss_ranks_500": boss_counts,
                        "boss_percentages": {
                            rank: round(count * 100 / max(1, len(boss_offers)), 2)
                            for rank, count in boss_counts.items()
                        },
                        "offers_and_cpu_outcomes_by_rank": by_rank,
                        "offer_snapshots_by_type_and_rank": by_type_and_rank,
                        "cpu_profile_progression_100_cycles": profile_progression,
                        "regional_state_100_cycles": region_trajectory,
                        "no_actions_baseline1_pressure": candidate_idle_without_cpu,
                        "cpu_only_pressure_by_region_base_1_impact_0_02_plus_0_02_per_rank": candidate_cpu_pressure,
                        "impact_parameter_sweep_baseline_1_when_no_actions": pressure_sweep,
                        "regional_impact_by_rank": {
                            rank: regional_cycle_service.regional_outcome_impact(rank) for rank in RANKS
                        },
                        "rank_template_correlation_10000_cycles_each": rank_template_correlation,
                        "cpu_resources_negative_values": sum(resource.amount < 0 for resource in cpu_resources),
                    }, ensure_ascii=False, sort_keys=True))

                    render_app = FastAPI()
                    render_app.state.app_mode = "desktop"
                    render_app.mount(
                        "/static",
                        StaticFiles(directory=Path(__file__).resolve().parents[1] / "app" / "static"),
                        name="static",
                    )
                    request = Request({
                        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                        "method": "GET", "scheme": "http", "path": "/regional",
                        "raw_path": b"/regional", "query_string": b"",
                        "headers": [(b"host", b"localhost")], "server": ("localhost", 8000),
                        "client": ("127.0.0.1", 12345), "app": render_app,
                    })
                    rendered = regional_index(
                        request, db, CampaignPlayer(first.campaign_id, guild.name), campaign,
                    )
                    html = rendered.template.render(rendered.context)
                    self.assertIn(guild.name, html)
                    self.assertIn("regional-vigil.webp", html)
                    self.assertIn("Ler relatório", html)
                    self.assertIn("Portais e rebeliões", html)

                    duplicate_reservations = db.execute(
                        select(RegionalCpuCyclePlan.cycle_id, RegionalCpuCyclePlan.decisions_json)
                        .where(RegionalCpuCyclePlan.campaign_id == first.campaign_id)
                    ).all()
                    for cycle_id in {row[0] for row in duplicate_reservations}:
                        decisions = []
                        for plan in db.scalars(select(RegionalCpuCyclePlan).where(
                            RegionalCpuCyclePlan.cycle_id == cycle_id,
                        )):
                            decisions.extend(json.loads(plan.decisions_json))
                        offer_ids = [decision["offer_id"] for decision in decisions]
                        self.assertEqual(len(offer_ids), len(set(offer_ids)))

                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.campaign_id == first.campaign_id,
                        RegionalOffer.status == "cpu_completed",
                    )), sum(plan.actions for plan in db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                    ))))

                campaigns.activate_campaign(second.campaign_id)
                with SessionLocal() as db:
                    self.assertEqual(db.scalar(select(func.count(RegionalWorldState.campaign_id))), 0)
                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id))), 0)
                    self.assertEqual(db.scalar(select(func.count(RegionalCpuCyclePlan.id))), 0)
                    second_campaign = db.get(CampaignMetadata, second.campaign_id)
                    second_guild, _second_resources = get_current_guild_context(db, second.campaign_id)
                    advance_regional_world(db, second_campaign, second_guild, second_campaign.created_at_utc)
                    for state in db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == second.campaign_id,
                        RegionalGuildState.guild_id.is_(None),
                    )):
                        state.active = False
                    db.commit()
                    no_action_now = second_campaign.created_at_utc + timedelta(seconds=61 * CYCLE_SECONDS)
                    advance_regional_world(db, second_campaign, second_guild, no_action_now)
                    no_action_rows = list(db.scalars(select(RegionalCycleRegion).where(
                        RegionalCycleRegion.campaign_id == second.campaign_id,
                    ).order_by(RegionalCycleRegion.cycle_id, RegionalCycleRegion.region_code)))
                    per_region = {}
                    for row in no_action_rows:
                        per_region.setdefault(row.region_code, []).append(row)
                    for snapshots in per_region.values():
                        rebellion_cycles = [
                            row.cycle_id for row in snapshots
                            if row.threat_after >= 85 and row.security_after <= 25
                        ]
                        self.assertEqual(len(snapshots), 61)
                        self.assertEqual(rebellion_cycles[0], snapshots[59].cycle_id)
                    snapshot_count = len(no_action_rows)
                    advance_regional_world(db, second_campaign, second_guild, no_action_now)
                    self.assertEqual(db.scalar(select(func.count(RegionalCycleRegion.id)).where(
                        RegionalCycleRegion.campaign_id == second.campaign_id,
                    )), snapshot_count)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_region_stage_scales_cpu_profiles_and_temporary_strong_rival_calm_expires(self):
        first_region, last_region = regional_cycle_service.REGIONS[0][0], regional_cycle_service.REGIONS[-1][0]
        first_stage = regional_stage_for_region(first_region)
        last_stage = regional_stage_for_region(last_region)
        self.assertEqual((first_stage, last_stage), (1, 5))
        first_values = {
            profile: cpu_initial_profile_values(profile, first_stage)
            for profile in ("strong", "medium", "new")
        }
        last_values = {
            profile: cpu_initial_profile_values(profile, last_stage)
            for profile in ("strong", "medium", "new")
        }
        for stage_values in (first_values, last_values):
            self.assertGreater(stage_values["strong"]["guild_level"], stage_values["medium"]["guild_level"])
            self.assertGreater(stage_values["medium"]["guild_level"], stage_values["new"]["guild_level"])
            self.assertGreater(stage_values["strong"]["mercenary_level"], stage_values["medium"]["mercenary_level"])
            self.assertGreater(stage_values["medium"]["mercenary_level"], stage_values["new"]["mercenary_level"])
            for stat in ("attributes", "gold", "material", "capacity"):
                value = lambda profile: sum(stage_values[profile][stat]) if stat == "attributes" else stage_values[profile][stat]
                self.assertGreater(value("strong"), value("medium"))
                self.assertGreater(value("medium"), value("new"))
        self.assertGreater(last_values["strong"]["guild_level"], first_values["strong"]["guild_level"])
        self.assertGreater(last_values["strong"]["mercenary_level"], first_values["strong"]["mercenary_level"])
        self.assertGreater(sum(last_values["strong"]["attributes"]), sum(first_values["strong"]["attributes"]))
        self.assertGreater(last_values["strong"]["gold"], first_values["strong"]["gold"])
        self.assertGreater(last_values["strong"]["capacity"], first_values["strong"]["capacity"])

        calm = rival_calm_for_cycle(0, regional_cycle_service.VIGILIA_RULES_VERSION, True, True)
        self.assertEqual(calm, rival_calm_for_cycle(0, regional_cycle_service.VIGILIA_RULES_VERSION, True, True))
        self.assertTrue(calm["active"])
        self.assertTrue(calm["applied"])
        self.assertFalse(rival_calm_for_cycle(0, LEGACY_VIGILIA_RULES_VERSION, True, True)["active"])

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Bandas CPU", "Guilda de Teste")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    start = campaign.created_at_utc
                    regional_cycle_service.ensure_campaign_world(db, campaign, guild)
                    cpu_guilds = list(db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.guild_id.is_(None),
                    )))
                    by_region_profile = {}
                    for state in cpu_guilds:
                        by_region_profile.setdefault((state.region_code, state.profile), []).append(state)
                    self.assertEqual(len(cpu_guilds), 24)
                    home_code = next(
                        code for code, name in regional_cycle_service.REGIONS if name == campaign.home_region
                    )
                    for region_code, _region_name in regional_cycle_service.REGIONS:
                        expected_new = 2 if region_code == home_code else 3
                        self.assertEqual(len(by_region_profile[(region_code, "new")]), expected_new)
                    for region_code, _region_name in regional_cycle_service.REGIONS:
                        strong = by_region_profile[(region_code, "strong")][0]
                        medium = by_region_profile[(region_code, "medium")][0]
                        new = by_region_profile[(region_code, "new")][0]
                        self.assertGreater(strong.level, medium.level)
                        self.assertGreater(medium.level, new.level)
                        self.assertGreater(strong.power, medium.power)
                        self.assertGreater(medium.power, new.power)
                    first_strong = by_region_profile[(first_region, "strong")][0]
                    last_strong = by_region_profile[(last_region, "strong")][0]
                    self.assertGreater(last_strong.level, first_strong.level)
                    self.assertGreater(last_strong.power, first_strong.power)
                    cpu_resources = {
                        (row.guild_state_id, row.resource_code): row
                        for row in db.scalars(select(RegionalCpuResource).where(
                            RegionalCpuResource.campaign_id == info.campaign_id,
                        ))
                    }
                    self.assertGreater(
                        cpu_resources[(last_strong.id, "gold")].amount,
                        cpu_resources[(first_strong.id, "gold")].amount,
                    )
                    self.assertGreater(
                        cpu_resources[(last_strong.id, "gold")].capacity,
                        cpu_resources[(first_strong.id, "gold")].capacity,
                    )

                    advance_regional_world(db, campaign, guild, start)
                    with patch.object(regional_cycle_service, "regional_cpu_action_probability", return_value=0.0):
                        advance_regional_world(db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS))
                        cycle_zero = db.scalar(select(RegionalCycle).where(
                            RegionalCycle.campaign_id == info.campaign_id,
                            RegionalCycle.cycle_number == 0,
                        ))
                        first_snapshot = db.scalar(select(RegionalCycleRegion).where(
                            RegionalCycleRegion.cycle_id == cycle_zero.id,
                            RegionalCycleRegion.region_code == home_code,
                        ))
                        first_summary = json.loads(first_snapshot.summary_json)
                        self.assertTrue(first_summary["baseline"]["applied"])
                        self.assertEqual(first_snapshot.cpu_actions, 0)
                        self.assertTrue(first_summary["rival_calm"]["active"])
                        self.assertTrue(first_summary["rival_calm"]["applied"])
                        self.assertEqual(first_summary["rival_calm"]["source_guild_state_id"],
                                         by_region_profile[(home_code, "strong")][0].id)
                        # One baseline delta (-1/+1) plus one independent calm offset (+0.25/-0.25).
                        self.assertAlmostEqual(first_snapshot.security_after, first_snapshot.security_before - 0.75)
                        self.assertAlmostEqual(first_snapshot.threat_after, first_snapshot.threat_before + 0.75)

                        advance_regional_world(db, campaign, guild, start + timedelta(seconds=5 * CYCLE_SECONDS))
                        cycle_four = db.scalar(select(RegionalCycle).where(
                            RegionalCycle.campaign_id == info.campaign_id,
                            RegionalCycle.cycle_number == 4,
                        ))
                        expired_snapshot = db.scalar(select(RegionalCycleRegion).where(
                            RegionalCycleRegion.cycle_id == cycle_four.id,
                            RegionalCycleRegion.region_code == home_code,
                        ))
                        expired_summary = json.loads(expired_snapshot.summary_json)
                        self.assertTrue(expired_summary["baseline"]["applied"])
                        self.assertFalse(expired_summary["rival_calm"]["active"])
                        self.assertFalse(expired_summary["rival_calm"]["applied"])
                        self.assertTrue(expired_summary["rival_calm"]["expired_before_this_cycle"])
                        self.assertAlmostEqual(expired_snapshot.security_after, expired_snapshot.security_before - 1)
                        self.assertAlmostEqual(expired_snapshot.threat_after, expired_snapshot.threat_before + 1)
                        before_repeat = expired_snapshot.summary_json
                        advance_regional_world(db, campaign, guild, start + timedelta(seconds=5 * CYCLE_SECONDS))
                        self.assertEqual(expired_snapshot.summary_json, before_repeat)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_cycle_resolves_before_expiry_retry_is_idempotent_and_catches_up_24h(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Retry Vigília", "Guilda Retry")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    start = campaign.created_at_utc
                    advance_regional_world(db, campaign, guild, start)
                    player_state = regional_cycle_service.get_current_player_regional_guild(
                        db, info.campaign_id, guild.id,
                    )
                    cycle_zero = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 0,
                    ))
                    player_offer = db.scalar(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle_zero.id,
                    ).order_by(RegionalOffer.id))
                    player_offer.status = "in_progress"
                    player_offer.reserved_by_guild_state_id = player_state.id
                    db.commit()
                    process_cycle = regional_cycle_service._process_cycle

                    def fail_after_processing(*args, **kwargs):
                        process_cycle(*args, **kwargs)
                        raise RuntimeError("simulated failure before cycle commit")

                    with patch.object(regional_cycle_service, "_process_cycle", side_effect=fail_after_processing):
                        with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                            advance_regional_world(db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS))

                    self.assertEqual(cycle_zero.status, "open")
                    self.assertEqual(db.scalar(select(func.count(RegionalCycleRegion.id)).where(
                        RegionalCycleRegion.cycle_id == cycle_zero.id,
                    )), 0)
                    self.assertEqual(db.scalar(select(func.count(RegionalCpuCyclePlan.id)).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    )), 0)
                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.cycle_id == cycle_zero.id,
                        RegionalOffer.status == "available",
                    )), 69)

                    advance_regional_world(db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS))
                    plans_after_retry = db.scalar(select(func.count(RegionalCpuCyclePlan.id)).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    ))
                    self.assertGreater(plans_after_retry, 0)
                    self.assertEqual(db.scalar(select(func.sum(RegionalCpuCyclePlan.actions)).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    )), db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.cycle_id == cycle_zero.id,
                        RegionalOffer.status == "cpu_completed",
                    )))
                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.cycle_id == cycle_zero.id,
                        RegionalOffer.status == "available",
                    )), 0)
                    decisions = []
                    for plan in db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    )):
                        decisions.extend(json.loads(plan.decisions_json))
                    self.assertNotIn(player_offer.id, [decision["offer_id"] for decision in decisions])
                    self.assertEqual(player_offer.status, "in_progress")
                    advance_regional_world(db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS))
                    self.assertEqual(db.scalar(select(func.count(RegionalCpuCyclePlan.id)).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    )), plans_after_retry)

                    advance_regional_world(db, campaign, guild, start + timedelta(seconds=4 * CYCLE_SECONDS))
                    completed = db.scalar(select(func.count(RegionalCycle.id)).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.status == "completed",
                    ))
                    self.assertEqual(completed, 4)
                    self.assertEqual(db.scalar(select(func.count(RegionalCycle.id)).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 4,
                    )), 1)
                    plans_after_catchup = db.scalar(select(func.count(RegionalCpuCyclePlan.id)).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    ))
                    advance_regional_world(db, campaign, guild, start + timedelta(seconds=4 * CYCLE_SECONDS))
                    self.assertEqual(db.scalar(select(func.count(RegionalCpuCyclePlan.id)).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    )), plans_after_catchup)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_regional_run_uses_frozen_duration_chance_and_rewards(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Snapshot Vigília", "Guilda Snapshot")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, resources = get_current_guild_context(db, info.campaign_id)
                    active_cycle = advance_regional_world(db, campaign, guild, campaign.created_at_utc)
                    home_code = next(code for code, name in regional_cycle_service.REGIONS
                                     if name == campaign.home_region)
                    player_state = regional_cycle_service.get_current_player_regional_guild(
                        db, info.campaign_id, guild.id,
                    )
                    for cpu_state in db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.guild_id.is_(None),
                    )):
                        if cpu_state.profile != "strong":
                            cpu_state.active = False
                    template = MissionTemplate(
                        name="Contrato Snapshot de teste",
                        description="Oferta de teste para conferir os dados congelados.",
                        display_order=999999,
                        difficulty="normal",
                        level_band="1-20",
                        mission_type="standard",
                        recommended_level=1,
                        recommended_power=1,
                        duration_seconds=900,
                        base_gold_reward=11,
                        base_xp_reward=7,
                        base_success_chance=50,
                        min_party_size=1,
                        max_party_size=1,
                        required_guild_level=1,
                        required_min_mercenary_level=1,
                        required_building_level=0,
                        is_active=True,
                    )
                    db.add(template)
                    db.flush()
                    offer = RegionalOffer(
                        campaign_id=info.campaign_id,
                        cycle_id=active_cycle.id,
                        cycle_number=active_cycle.cycle_number,
                        region_code=home_code,
                        offer_type="contract",
                        slot=11,
                        mission_template_id=template.id,
                        rank="S",
                        name_snapshot=template.name,
                        description_snapshot=template.description,
                        level_band_snapshot="1-20",
                        recommended_level_snapshot=1,
                        recommended_power_snapshot=1,
                        duration_seconds_snapshot=5400,
                        gold_reward_snapshot=321,
                        xp_reward_snapshot=123,
                        success_chance_snapshot=95,
                        status="in_progress",
                        reserved_by_guild_state_id=player_state.id,
                    )
                    db.add(offer)
                    apprentice = db.scalar(select(MercenaryClass).where(MercenaryClass.code == "apprentice"))
                    mercenary = create_mercenary(db, guild.id, apprentice, "Snapshot Runner")
                    db.flush()
                    run = start_mission(
                        db, guild, str(template.id), [str(mercenary.id)], commit=False,
                        regional_duration_seconds=offer.duration_seconds_snapshot,
                    )
                    run.regional_offer_id = offer.id
                    run.rank_snapshot = offer.rank
                    self.assertEqual((run.ends_at - run.started_at).total_seconds(), 5400)

                    template.duration_seconds = 90000
                    template.base_gold_reward = 90000
                    template.base_xp_reward = 90000
                    template.base_success_chance = 5
                    run.ends_at = run.started_at - timedelta(seconds=1)
                    db.flush()
                    with patch(
                        "app.services.mission_service.get_party_chance_details",
                        wraps=mission_service.get_party_chance_details,
                    ) as chance_details, patch(
                        "app.services.mission_service.randint", return_value=1,
                    ):
                        resolved = claim_mission_loot(db, guild, resources, run.id)
                    self.assertEqual(chance_details.call_args.args[2], 95)
                    self.assertTrue(resolved.success)
                    self.assertEqual(resolved.gold_reward, 321)
                    self.assertGreaterEqual(resolved.xp_reward, 123)
                    self.assertLess(resolved.xp_reward, 500)
                    result = db.scalar(select(RegionalRunOutcome).where(
                        RegionalRunOutcome.source_run_id == run.id,
                    ))
                    self.assertEqual(result.rank, "S")
                    self.assertEqual(result.gold_earned, 321)
                    self.assertEqual(result.xp_earned, resolved.xp_reward)
                    self.assertEqual(offer.status, "completed")
                    region = db.scalar(select(regional_cycle_service.RegionalRegionState).where(
                        regional_cycle_service.RegionalRegionState.campaign_id == info.campaign_id,
                        regional_cycle_service.RegionalRegionState.region_code == home_code,
                    ))
                    self.assertAlmostEqual(region.security, 50.14)
                    self.assertAlmostEqual(region.threat, 24.86)

                    failed_offer = RegionalOffer(
                        campaign_id=info.campaign_id,
                        cycle_id=active_cycle.id,
                        cycle_number=active_cycle.cycle_number,
                        region_code=home_code,
                        offer_type="contract",
                        slot=12,
                        mission_template_id=template.id,
                        rank="C",
                        name_snapshot=template.name,
                        description_snapshot=template.description,
                        level_band_snapshot="1-20",
                        recommended_level_snapshot=1,
                        recommended_power_snapshot=1,
                        duration_seconds_snapshot=5400,
                        gold_reward_snapshot=321,
                        xp_reward_snapshot=123,
                        success_chance_snapshot=5,
                        status="in_progress",
                        reserved_by_guild_state_id=player_state.id,
                    )
                    db.add(failed_offer)
                    db.flush()
                    failed_run = start_mission(
                        db, guild, str(template.id), [str(mercenary.id)], commit=False,
                        regional_duration_seconds=failed_offer.duration_seconds_snapshot,
                    )
                    failed_run.regional_offer_id = failed_offer.id
                    failed_run.rank_snapshot = failed_offer.rank
                    failed_run.ends_at = failed_run.started_at - timedelta(seconds=1)
                    db.flush()
                    with patch("app.services.mission_service.randint", return_value=100):
                        failed_result = claim_mission_loot(db, guild, resources, failed_run.id)
                    self.assertFalse(failed_result.success)
                    self.assertAlmostEqual(region.security, 50.06)
                    self.assertAlmostEqual(region.threat, 24.94)
                    self.assertEqual(regional_cycle_service.REGION_BASELINE_PRESSURE, 1)
                    with patch.object(regional_cycle_service, "regional_cpu_action_probability", return_value=0.0):
                        advance_regional_world(
                            db, campaign, guild, campaign.created_at_utc + timedelta(seconds=CYCLE_SECONDS),
                        )
                    cycle_summary = db.scalar(select(RegionalCycleRegion).where(
                        RegionalCycleRegion.cycle_id == active_cycle.id,
                        RegionalCycleRegion.region_code == home_code,
                    ))
                    summary = json.loads(cycle_summary.summary_json)
                    self.assertFalse(summary["baseline"]["applied"])
                    self.assertEqual(summary["player_actions"], 2)
                    self.assertEqual(summary["player_successes"], 1)
                    self.assertEqual(summary["player_failures"], 1)
                    self.assertAlmostEqual(cycle_summary.security_before, 50)
                    self.assertTrue(summary["rival_calm"]["active"])
                    self.assertTrue(summary["rival_calm"]["applied"])
                    self.assertAlmostEqual(summary["rival_calm"]["security"], 0.25)
                    self.assertAlmostEqual(cycle_summary.security_after, 50.31)
                    self.assertAlmostEqual(cycle_summary.threat_before, 25)
                    self.assertAlmostEqual(cycle_summary.threat_after, 24.69)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()


if __name__ == "__main__":
    unittest.main()
