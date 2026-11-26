import gc
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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
from app.services.dungeon_service import DungeonError, validate_dungeon_requirements
from app.models.regional import (
    RegionalCpuCyclePlan,
    RegionalCpuMercenary,
    RegionalCpuResource,
    RegionalCycle,
    RegionalCycleRegion,
    RegionalEventActivity,
    RegionalEvent,
    RegionalEventParticipant,
    RegionalGuildState,
    RegionalOffer,
    RegionalRegionState,
    RegionalRunOutcome,
    RegionalWorldState,
)
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.repositories.mercenary_repository import create_mercenary
from app.services.mission_service import MissionError, claim_mission_loot, start_mission, validate_mission_requirements
from app.services import mission_service, regional_cycle_service
from app.services.regional_cycle_service import (
    CYCLE_SECONDS,
    LEGACY_VIGILIA_RULES_VERSION,
    RANKS,
    VIGILIA_V9_EVENT_RULES_VERSION,
    advance_regional_world,
    cpu_initial_profile_values,
    cpu_roster_cap,
    regional_stage_for_region,
    rival_calm_for_cycle,
    simulate_rank_distribution,
)
from app.core.dependencies import CampaignPlayer
from app.routes.regional_routes import regional_index, templates as regional_templates


class RegionalCycleSimulationTests(unittest.TestCase):
    def test_cpu_busy_until_keeps_the_longer_priority_or_portal_reservation(self):
        cycle_start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        priority_end = cycle_start + timedelta(hours=1)
        roster = [SimpleNamespace(id=value) for value in (101, 102, 103, 104)]
        reservations = {
            101: cycle_start + timedelta(minutes=30),
            102: priority_end,
            103: cycle_start + timedelta(minutes=90),
            104: cycle_start + timedelta(hours=2),
        }
        with patch.object(
            regional_cycle_service,
            "_cpu_pending_portal_reservations",
            return_value=reservations,
        ):
            busy_until = regional_cycle_service._cpu_busy_until_for_roster(
                None, 7, roster, cycle_start, priority_end,
            )

        self.assertEqual(busy_until[101], priority_end)
        self.assertEqual(busy_until[102], priority_end)
        self.assertEqual(busy_until[103], cycle_start + timedelta(minutes=90))
        self.assertEqual(busy_until[104], cycle_start + timedelta(hours=2))

    def test_v9_portal_catchup_matches_7_12_14_hour_visits_and_reserves_party(self):
        fixed_campaign_id = UUID("00000000-0000-4000-8000-000000000091")

        def run_scenario(later_visits):
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    configure_database("sqlite:///:memory:")
                    campaigns = CampaignService(Path(temp_dir) / "saves")
                    with patch("app.services.campaign_service.uuid4", return_value=fixed_campaign_id):
                        info = campaigns.create_campaign("Portal catch-up", "Guilda de teste")
                    campaigns.activate_campaign(info.campaign_id)
                    with SessionLocal() as db:
                        campaign = db.get(CampaignMetadata, info.campaign_id)
                        campaign.created_at_utc = datetime(2026, 11, 1, tzinfo=timezone.utc)
                        db.flush()
                        guild, _resources = get_current_guild_context(db, info.campaign_id)
                        start = regional_cycle_service._utc(campaign.created_at_utc)
                        advance_regional_world(db, campaign, guild, start)
                        with patch("app.services.regional_event_service.create_cycle_portals"):
                            advance_regional_world(
                                db, campaign, guild, start + timedelta(hours=6),
                            )

                        home_code = next(
                            code for code, name in regional_cycle_service.REGIONS
                            if name == campaign.home_region
                        )
                        event = RegionalEvent(
                            campaign_id=info.campaign_id,
                            event_type="portal",
                            region_code=home_code,
                            trigger_cycle_number=0,
                            rules_version=VIGILIA_V9_EVENT_RULES_VERSION,
                            seed="catchup-v9-portal-seed",
                            status="active",
                            created_at_utc=start + timedelta(hours=6),
                            expires_at_utc=start + timedelta(hours=9),
                            summary_json=json.dumps({"portal_boss": {
                                "version": "portal-boss-v1",
                                "template": {
                                    "id": 9191,
                                    "name": "Chefe de teste",
                                    "duration_seconds": 10 * 3600,
                                    "base_success_chance": 65,
                                    "min_party_size": 1,
                                    "max_party_size": 1,
                                    "required_guild_level": 1,
                                    "required_min_mercenary_level": 1,
                                    "required_total_power": 0,
                                    "required_class_code": None,
                                    "required_tank_count": 0,
                                    "required_support_count": 0,
                                    "required_damage_count": 0,
                                    "required_equipment_tier": 0,
                                },
                            }}),
                        )
                        db.add(event)
                        db.commit()

                        for visit_hour in later_visits:
                            advance_regional_world(
                                db, campaign, guild, start + timedelta(hours=visit_hour),
                            )
                            if visit_hour in {12, 14}:
                                pending_activities = list(db.scalars(select(RegionalEventActivity).where(
                                    RegionalEventActivity.event_id == event.id,
                                    RegionalEventActivity.source_type == "cpu_portal",
                                    RegionalEventActivity.status == "in_progress",
                                ).order_by(RegionalEventActivity.guild_state_id)))
                                self.assertTrue(pending_activities)
                                for pending in pending_activities:
                                    self.assertEqual(
                                        regional_cycle_service._utc(pending.started_at_utc),
                                        start + timedelta(hours=7),
                                    )
                                    self.assertEqual(
                                        regional_cycle_service._utc(pending.due_at_utc),
                                        start + timedelta(hours=17),
                                    )
                                if visit_hour == 14:
                                    region = db.scalar(select(RegionalRegionState).where(
                                        RegionalRegionState.campaign_id == info.campaign_id,
                                        RegionalRegionState.region_code == home_code,
                                    ))
                                    prior_snapshot = db.scalar(
                                        select(RegionalCycleRegion)
                                        .join(RegionalCycle, RegionalCycle.id == RegionalCycleRegion.cycle_id)
                                        .where(
                                            RegionalCycle.campaign_id == info.campaign_id,
                                            RegionalCycle.cycle_number == 1,
                                            RegionalCycleRegion.region_code == home_code,
                                        )
                                    )
                                    self.assertEqual(region.security, prior_snapshot.security_after)
                                    self.assertEqual(region.threat, prior_snapshot.threat_after)

                        activities = list(db.scalars(select(RegionalEventActivity).where(
                            RegionalEventActivity.event_id == event.id,
                            RegionalEventActivity.source_type == "cpu_portal",
                            RegionalEventActivity.status == "resolved",
                        ).order_by(RegionalEventActivity.guild_state_id)))
                        self.assertTrue(activities)
                        participants = list(db.scalars(select(RegionalEventParticipant).where(
                            RegionalEventParticipant.event_id == event.id,
                        ).order_by(RegionalEventParticipant.guild_state_id)))
                        self.assertEqual(
                            [row.guild_state_id for row in activities],
                            [row.guild_state_id for row in participants],
                        )
                        self.assertEqual(len({row.guild_state_id for row in activities}), len(activities))
                        for activity, participant in zip(activities, participants):
                            self.assertEqual(
                                regional_cycle_service._utc(activity.due_at_utc),
                                start + timedelta(hours=17),
                            )
                            self.assertEqual(activity.resolved_at_utc, activity.due_at_utc)
                            self.assertEqual(participant.status, "resolved")
                            self.assertIsNotNone(participant.success)

                        next_cycle = db.scalar(select(RegionalCycle).where(
                            RegionalCycle.campaign_id == info.campaign_id,
                            RegionalCycle.cycle_number == 2,
                        ))
                        for activity in activities:
                            later_plan = db.scalar(select(RegionalCpuCyclePlan).where(
                                RegionalCpuCyclePlan.cycle_id == next_cycle.id,
                                RegionalCpuCyclePlan.guild_state_id == activity.guild_state_id,
                            ))
                            if later_plan is not None:
                                portal_ids = set(json.loads(activity.snapshot_json)["mercenary_ids"])
                                for decision in json.loads(later_plan.decisions_json or "[]"):
                                    if portal_ids.intersection(decision.get("mercenary_ids", [])):
                                        self.assertGreaterEqual(
                                            regional_cycle_service._utc(datetime.fromisoformat(
                                                decision["started_at_utc"]
                                            )),
                                            regional_cycle_service._utc(activity.due_at_utc),
                                        )

                        plans = list(db.execute(
                            select(RegionalCpuCyclePlan, RegionalCycle)
                            .join(RegionalCycle, RegionalCycle.id == RegionalCpuCyclePlan.cycle_id)
                            .where(RegionalCpuCyclePlan.campaign_id == info.campaign_id)
                            .order_by(RegionalCycle.cycle_number, RegionalCpuCyclePlan.guild_state_id)
                        ))
                        plan_snapshot = [(
                            cycle.cycle_number, plan.guild_state_id, plan.seed,
                            plan.roster_snapshot_json,
                            plan.resources_before_json, plan.resources_after_json,
                            plan.decisions_json, plan.outcomes_json,
                        ) for plan, cycle in plans]
                        origin_cycle_ids = {
                            db.get(RegionalCpuCyclePlan, activity.source_run_id).cycle_id
                            for activity in activities
                        }
                        history_rows = list(db.execute(
                            select(RegionalCycleRegion, RegionalCycle)
                            .join(RegionalCycle, RegionalCycle.id == RegionalCycleRegion.cycle_id)
                            .where(
                                RegionalCycleRegion.cycle_id.in_(origin_cycle_ids),
                                RegionalCycleRegion.region_code == event.region_code,
                            )
                            .order_by(RegionalCycle.cycle_number)
                        ))
                        history_snapshot = []
                        for history, origin_cycle in history_rows:
                            summary = json.loads(history.summary_json)
                            activity_summary = summary["cpu_activity"]
                            origin_plans = list(db.scalars(
                                select(RegionalCpuCyclePlan)
                                .join(RegionalGuildState,
                                      RegionalGuildState.id == RegionalCpuCyclePlan.guild_state_id)
                                .where(
                                    RegionalCpuCyclePlan.cycle_id == origin_cycle.id,
                                    RegionalGuildState.region_code == event.region_code,
                                )
                            ))
                            self.assertEqual(
                                activity_summary["started"],
                                sum(plan.started_actions for plan in origin_plans),
                            )
                            self.assertEqual(
                                activity_summary["resolved"],
                                sum(plan.resolved_actions for plan in origin_plans),
                            )
                            self.assertEqual(
                                activity_summary["pending"],
                                activity_summary["started"] - activity_summary["resolved"],
                            )
                            self.assertEqual(
                                summary["successes"], sum(plan.successes for plan in origin_plans),
                            )
                            self.assertEqual(
                                summary["failures"], sum(plan.failures for plan in origin_plans),
                            )
                            history_snapshot.append((origin_cycle.cycle_number, history.summary_json))
                        resource_snapshot = list(db.execute(select(
                            RegionalCpuResource.guild_state_id,
                            RegionalCpuResource.resource_code,
                            RegionalCpuResource.amount,
                        ).where(
                            RegionalCpuResource.campaign_id == info.campaign_id,
                        ).order_by(
                            RegionalCpuResource.guild_state_id,
                            RegionalCpuResource.resource_code,
                        )))
                        region = db.scalar(select(RegionalRegionState).where(
                            RegionalRegionState.campaign_id == info.campaign_id,
                            RegionalRegionState.region_code == home_code,
                        ))
                        result = (
                            event.id, event.status, event.summary_json,
                            tuple((activity.guild_state_id, activity.source_run_id,
                                   activity.status, activity.snapshot_json,
                                   participant.status, participant.success)
                                  for activity, participant in zip(activities, participants)),
                            round(region.security, 4), round(region.threat, 4),
                            plan_snapshot, history_snapshot, resource_snapshot,
                        )
                        before_retry = (region.security, region.threat, event.summary_json)
                        advance_regional_world(
                            db, campaign, guild, start + timedelta(hours=18),
                        )
                        self.assertEqual(
                            (region.security, region.threat, event.summary_json), before_retry,
                        )
                        return result
                finally:
                    configure_database("sqlite:///:memory:")
                    gc.collect()

        incremental = run_scenario([7, 12, 14, 18])
        batch = run_scenario([18])
        self.assertEqual(incremental, batch)

    def test_v9_public_planner_defers_portal_effects_until_due_for_success_and_failure(self):
        def run_case(success: bool) -> None:
            configure_database("sqlite:///:memory:")
            campaigns = None
            info = None
            try:
                temp_dir = tempfile.TemporaryDirectory()
                try:
                    campaigns = CampaignService(Path(temp_dir.name) / "saves")
                    fixed_id = UUID("00000000-0000-4000-8000-000000000091")
                    with patch("app.services.campaign_service.uuid4", return_value=fixed_id):
                        info = campaigns.create_campaign("CPU portal effects", "Guilda de teste")
                    campaigns.activate_campaign(info.campaign_id)
                    with SessionLocal() as db:
                        from app.services.regional_event_service import (
                            V9_EVENT_RULES_VERSION,
                            build_portal_boss_snapshot,
                        )

                        campaign = db.get(CampaignMetadata, info.campaign_id)
                        guild, _resources = get_current_guild_context(db, info.campaign_id)
                        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
                        campaign.created_at_utc = start
                        db.flush()
                        advance_regional_world(db, campaign, guild, start)
                        cycle = db.scalar(select(RegionalCycle).where(
                            RegionalCycle.campaign_id == info.campaign_id,
                            RegionalCycle.cycle_number == 0,
                        ))
                        home_code = next(
                            code for code, name in regional_cycle_service.REGIONS
                            if name == campaign.home_region
                        )
                        cpu = db.scalar(select(RegionalGuildState).where(
                            RegionalGuildState.campaign_id == info.campaign_id,
                            RegionalGuildState.region_code == home_code,
                            RegionalGuildState.profile == "strong",
                        ))
                        for other_cpu in db.scalars(select(RegionalGuildState).where(
                            RegionalGuildState.campaign_id == info.campaign_id,
                            RegionalGuildState.guild_id.is_(None),
                        )):
                            if other_cpu.id != cpu.id:
                                other_cpu.active = False
                        cpu.archetype = "exploration"
                        cpu_baseline = (cpu.influence, cpu.reputation)
                        cpu_resources = {
                            row.resource_code: row for row in db.scalars(select(RegionalCpuResource).where(
                                RegionalCpuResource.guild_state_id == cpu.id,
                            ))
                        }
                        cpu_resources["gold"].amount = 0  # Avoid unrelated cycle-start hiring.
                        resource_baseline = {
                            code: row.amount for code, row in cpu_resources.items()
                        }
                        roster = list(db.scalars(select(RegionalCpuMercenary).where(
                            RegionalCpuMercenary.guild_state_id == cpu.id,
                            RegionalCpuMercenary.active.is_(True),
                        )))
                        self.assertTrue(roster)
                        for member in roster:
                            member.profession_code = "woodcutter"
                        wood_before = cpu_resources["wood"].amount

                        template = DungeonTemplate(
                            name="Chefe CPU diferido", description="Portal de teste",
                            content_type="boss", level_band="1-20", recommended_level=1,
                            biome="portal", difficulty="normal", duration_seconds=10 * 3600,
                            base_gold_reward=500, base_xp_reward=500, base_success_chance=65,
                            min_party_size=1, max_party_size=5, required_guild_level=1,
                            required_min_mercenary_level=1, required_total_power=0,
                            required_tank_count=0, required_support_count=0,
                            required_damage_count=0, required_equipment_tier=0, is_active=True,
                        )
                        db.add(template)
                        db.flush()
                        portal = RegionalEvent(
                            campaign_id=info.campaign_id,
                            event_type="portal",
                            region_code=home_code,
                            trigger_cycle_number=0,
                            rules_version=V9_EVENT_RULES_VERSION,
                            seed=f"public-planner-{success}",
                            status="active",
                            dungeon_template_id=template.id,
                            created_at_utc=start,
                            expires_at_utc=start + timedelta(hours=3),
                            summary_json=json.dumps({
                                "portal_boss": {"template": build_portal_boss_snapshot(template)},
                            }, sort_keys=True),
                        )
                        db.add(portal)
                        for offer in db.scalars(select(RegionalOffer).where(
                            RegionalOffer.cycle_id == cycle.id,
                            RegionalOffer.region_code == home_code,
                        )):
                            offer.status = "cpu_completed"
                        db.flush()
                        plan_seed = regional_cycle_service._seed_text(
                            info.campaign_id, cycle.cycle_number, cpu.id,
                            cycle.rules_version, "cpu-plan",
                        )
                        original_rng = regional_cycle_service._rng

                        class ForcedOutcomeRng:
                            def randint(self, low, high):
                                return low if success else high

                        def controlled_rng(*parts):
                            if parts == (plan_seed,):
                                return ForcedOutcomeRng()
                            return original_rng(*parts)

                        with patch.object(regional_cycle_service, "_rng", side_effect=controlled_rng):
                            with patch("app.services.regional_event_service.create_cycle_portals"):
                                advance_regional_world(
                                    db, campaign, guild, start + timedelta(hours=6),
                                )

                        plan = db.scalar(select(RegionalCpuCyclePlan).where(
                            RegionalCpuCyclePlan.cycle_id == cycle.id,
                            RegionalCpuCyclePlan.guild_state_id == cpu.id,
                        ))
                        decision = next(row for row in json.loads(plan.decisions_json)
                                        if row.get("offer_type") == "portal")
                        self.assertEqual(decision["result_success_snapshot"], success)
                        self.assertEqual(plan.started_actions, 1)
                        self.assertEqual(plan.resolved_actions, 0)
                        self.assertEqual((plan.successes, plan.failures), (0, 0))
                        self.assertEqual(json.loads(plan.outcomes_json), [])
                        self.assertEqual((cpu.influence, cpu.reputation), cpu_baseline)
                        self.assertEqual(
                            {code: row.amount for code, row in cpu_resources.items()},
                            resource_baseline,
                        )
                        self.assertEqual(cpu_resources["wood"].amount, wood_before)

                        region = db.scalar(select(RegionalRegionState).where(
                            RegionalRegionState.campaign_id == info.campaign_id,
                            RegionalRegionState.region_code == home_code,
                        ))
                        cycle_region = db.scalar(select(RegionalCycleRegion).where(
                            RegionalCycleRegion.cycle_id == cycle.id,
                            RegionalCycleRegion.region_code == home_code,
                        ))
                        pending_state = (
                            cpu.influence, cpu.reputation, cpu_resources["wood"].amount,
                            cpu_resources["gold"].amount, cpu_resources["xp"].amount,
                            region.security, region.threat, region.influence,
                            plan.successes, plan.failures, plan.resolved_actions,
                            plan.gold_earned, plan.xp_earned,
                            plan.outcomes_json,
                        )
                        self.assertEqual(region.security, cycle_region.security_after)
                        self.assertEqual(region.threat, cycle_region.threat_after)
                        self.assertEqual(region.influence, cycle_region.influence_after)

                        with patch("app.services.regional_event_service.create_cycle_portals"):
                            advance_regional_world(
                                db, campaign, guild, start + timedelta(hours=9),
                            )
                        self.assertEqual((
                            cpu.influence, cpu.reputation, cpu_resources["wood"].amount,
                            cpu_resources["gold"].amount, cpu_resources["xp"].amount,
                            region.security, region.threat, region.influence,
                            plan.successes, plan.failures, plan.resolved_actions,
                            plan.gold_earned, plan.xp_earned,
                            plan.outcomes_json,
                        ), pending_state)
                        activity = db.scalar(select(RegionalEventActivity).where(
                            RegionalEventActivity.event_id == portal.id,
                            RegionalEventActivity.guild_state_id == cpu.id,
                            RegionalEventActivity.source_type == "cpu_portal",
                        ))
                        self.assertEqual(activity.status, "in_progress")
                        self.assertEqual(
                            regional_cycle_service._utc(activity.due_at_utc),
                            start + timedelta(hours=11),
                        )

                        with patch("app.services.regional_event_service.create_cycle_portals"):
                            advance_regional_world(
                                db, campaign, guild, start + timedelta(hours=11),
                            )
                        impact = regional_cycle_service.regional_outcome_impact("C")
                        self.assertEqual(activity.status, "resolved")
                        self.assertEqual(activity.successes, int(success))
                        self.assertEqual(activity.failures, int(not success))
                        self.assertEqual(plan.resolved_actions, 1)
                        self.assertEqual((plan.successes, plan.failures), (int(success), int(not success)))
                        self.assertEqual(len(json.loads(plan.outcomes_json)), 1)
                        effects_snapshot = decision["planner_effects_snapshot"]
                        for resource_code in ("gold", "xp"):
                            resource = cpu_resources[resource_code]
                            self.assertEqual(
                                resource.amount,
                                min(resource.capacity, resource_baseline[resource_code]
                                    + effects_snapshot[f"{resource_code}_resource_delta"]),
                            )
                        expected_influence = min(100, cpu_baseline[0] + (3 if success else 1))
                        expected_reputation = (
                            min(100, cpu_baseline[1] + 3) if success
                            else max(0, cpu_baseline[1] - 1)
                        )
                        self.assertEqual((cpu.influence, cpu.reputation),
                                         (expected_influence, expected_reputation))
                        self.assertEqual(
                            cpu_resources["wood"].amount,
                            wood_before + int(success),
                        )
                        self.assertEqual(
                            (region.security, region.threat),
                            (cycle_region.security_after + (impact if success else -impact),
                             cycle_region.threat_after + (-impact if success else impact)),
                        )
                        resolved_state = (
                            cpu.influence, cpu.reputation, cpu_resources["wood"].amount,
                            cpu_resources["gold"].amount, cpu_resources["xp"].amount,
                            region.security, region.threat, region.influence,
                            plan.successes, plan.failures, plan.resolved_actions,
                            plan.gold_earned, plan.xp_earned,
                            plan.outcomes_json, activity.status, activity.resolved_at_utc,
                        )
                        with patch("app.services.regional_event_service.create_cycle_portals"):
                            advance_regional_world(
                                db, campaign, guild, start + timedelta(hours=11),
                            )
                        self.assertEqual((
                            cpu.influence, cpu.reputation, cpu_resources["wood"].amount,
                            cpu_resources["gold"].amount, cpu_resources["xp"].amount,
                            region.security, region.threat, region.influence,
                            plan.successes, plan.failures, plan.resolved_actions,
                            plan.gold_earned, plan.xp_earned,
                            plan.outcomes_json, activity.status, activity.resolved_at_utc,
                        ), resolved_state)
                finally:
                    if campaigns is not None and info is not None:
                        campaigns.close_active_campaign(info.campaign_id)
                    temp_dir.cleanup()
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

        for expected_success in (True, False):
            with self.subTest(success=expected_success):
                run_case(expected_success)

    def test_contract_candidates_follow_guild_bands_and_keep_100_plus_ceiling(self):
        from random import Random

        expected_bands = (
            (1, (1, 10)),
            (9, (1, 10)),
            (10, (5, 20)),
            (14, (5, 20)),
            (15, (10, 25)),
            (24, (15, 30)),
            (25, (20, 35)),
            (29, (20, 35)),
            (30, (25, 40)),
            (49, (40, 55)),
            (50, (45, 60)),
            (99, (90, 105)),
        )
        with tempfile.TemporaryDirectory(
            prefix="ml050-contract-bands-", dir=Path(__file__).resolve().parents[1],
        ) as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Faixas ML-050", "Guilda Faixas")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    regional_cycle_service.ensure_campaign_world(db, campaign, guild)
                    cpu_levels = set(db.scalars(select(RegionalCpuMercenary.level).where(
                        RegionalCpuMercenary.campaign_id == info.campaign_id,
                        RegionalCpuMercenary.active.is_(True),
                    )))
                    self.assertTrue({1, 2, 3, 5}.issubset(cpu_levels), cpu_levels)

                    for guild_level, band in expected_bands:
                        with self.subTest(guild_level=guild_level):
                            self.assertEqual(
                                regional_cycle_service._contract_recommended_level_band(guild_level),
                                band,
                            )
                            pool = regional_cycle_service._contract_candidates(db, guild_level, 1)
                            roster_independent_pool = regional_cycle_service._contract_candidates(
                                db, guild_level, 350,
                            )
                            self.assertTrue(pool, f"no seeded contracts for guild level {guild_level}")
                            self.assertEqual(
                                [row.id for row in pool],
                                [row.id for row in roster_independent_pool],
                            )
                            self.assertTrue(all(
                                band[0] <= int(row.recommended_level) <= band[1]
                                and int(row.required_min_mercenary_level) <= band[1]
                                for row in pool
                            ))
                            templates = regional_cycle_service._select_contract_templates(
                                roster_independent_pool, 10, Random(guild_level), guild_level, 350,
                            )
                            rank_sequence = ["E", "D", "C", "B", "A", "S", "E", "D", "C", "B"]
                            paired = regional_cycle_service._pair_contract_templates_with_ranks(
                                templates, rank_sequence,
                            )
                            self.assertEqual({rank for _template, rank in paired}, set(RANKS))
                            self.assertTrue(all(
                                band[0] <= int(template.recommended_level) <= band[1]
                                for template, _rank in paired
                            ))

                    self.assertIsNone(regional_cycle_service._contract_recommended_level_band(100))
                    guild_100_roster_1 = regional_cycle_service._contract_candidates(db, 100, 1)
                    guild_100_roster_350 = regional_cycle_service._contract_candidates(db, 100, 350)
                    self.assertTrue(guild_100_roster_1)
                    self.assertTrue(guild_100_roster_350)
                    self.assertLessEqual(max(row.recommended_level for row in guild_100_roster_1), 100)
                    self.assertLessEqual(max(row.required_min_mercenary_level for row in guild_100_roster_1), 100)
                    self.assertLessEqual(max(row.recommended_level for row in guild_100_roster_350), 350)
                    self.assertLessEqual(max(row.required_min_mercenary_level for row in guild_100_roster_350), 350)
                    self.assertGreater(
                        max(row.recommended_level for row in guild_100_roster_350),
                        max(row.recommended_level for row in guild_100_roster_1),
                    )
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_contract_cutover_preserves_existing_in_progress_offer_snapshot(self):
        with tempfile.TemporaryDirectory(
            prefix="ml050-contract-cutover-", dir=Path(__file__).resolve().parents[1],
        ) as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Virada ML-050", "Guilda Virada")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    start = campaign.created_at_utc
                    advance_regional_world(db, campaign, guild, start)
                    first_cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 0,
                    ))
                    offer = db.scalar(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == first_cycle.id,
                        RegionalOffer.offer_type == "contract",
                    ).order_by(RegionalOffer.slot).limit(1))
                    self.assertIsNotNone(offer)
                    offer.status = "in_progress"
                    frozen = (
                        offer.name_snapshot,
                        offer.rank,
                        offer.recommended_level_snapshot,
                        offer.recommended_power_snapshot,
                        offer.duration_seconds_snapshot,
                        offer.gold_reward_snapshot,
                        offer.xp_reward_snapshot,
                        offer.success_chance_snapshot,
                    )
                    guild.level = 15
                    db.flush()

                    advance_regional_world(db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS))
                    next_cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 1,
                    ))
                    next_offers = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == next_cycle.id,
                        RegionalOffer.region_code == offer.region_code,
                        RegionalOffer.offer_type == "contract",
                    ).order_by(RegionalOffer.slot)))
                    self.assertEqual(len(next_offers), 10)
                    self.assertTrue(all(10 <= row.recommended_level_snapshot <= 25 for row in next_offers))
                    self.assertEqual(offer.status, "in_progress")
                    self.assertEqual((
                        offer.name_snapshot,
                        offer.rank,
                        offer.recommended_level_snapshot,
                        offer.recommended_power_snapshot,
                        offer.duration_seconds_snapshot,
                        offer.gold_reward_snapshot,
                        offer.xp_reward_snapshot,
                        offer.success_chance_snapshot,
                    ), frozen)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_ml050_short_cpu_trace_contract_dungeon_idle(self):
        with tempfile.TemporaryDirectory(
            prefix="ml050-short-cpu-trace-", dir=Path(__file__).resolve().parents[1],
        ) as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                with patch(
                    "app.services.campaign_service.uuid4",
                    return_value=UUID("00000000-0000-4000-8000-000000000050"),
                ):
                    info = campaigns.create_campaign("Traço curto ML-050", "Guilda Traço")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    home_code = next(
                        code for code, name in regional_cycle_service.REGIONS
                        if name == campaign.home_region
                    )
                    start = campaign.created_at_utc
                    advance_regional_world(db, campaign, guild, start)

                    cpu_states = list(db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.guild_id.is_(None),
                    )))
                    cpu = next(
                        state for state in cpu_states
                        if state.region_code == home_code and state.profile == "strong"
                    )
                    for state in cpu_states:
                        state.active = state.id == cpu.id
                    cpu.archetype = "contracts"
                    cpu.level = 50
                    roster = list(db.scalars(select(RegionalCpuMercenary).where(
                        RegionalCpuMercenary.guild_state_id == cpu.id,
                        RegionalCpuMercenary.active.is_(True),
                    ).order_by(RegionalCpuMercenary.slot)))
                    self.assertTrue(roster)
                    for member in roster:
                        member.level = 5

                    cycle_zero = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 0,
                    ))
                    offers_zero = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle_zero.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type == "contract",
                    )))
                    self.assertEqual(len(offers_zero), 10)
                    self.assertTrue(all(1 <= offer.recommended_level_snapshot <= 10
                                        for offer in offers_zero))

                    guild.level = 49
                    advance_regional_world(
                        db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS),
                    )
                    plan_zero = db.scalar(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.cycle_id == cycle_zero.id,
                        RegionalCpuCyclePlan.guild_state_id == cpu.id,
                    ))
                    decisions_zero = json.loads(plan_zero.decisions_json)
                    self.assertTrue(decisions_zero, "CPU roster should take an eligible low-band offer")
                    self.assertIn("contract", [row["offer_type"] for row in decisions_zero])

                    cycle_one = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 1,
                    ))
                    offers_one = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle_one.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type == "contract",
                    )))
                    self.assertEqual(len(offers_one), 10)
                    self.assertTrue(all(40 <= offer.recommended_level_snapshot <= 55
                                        for offer in offers_one))
                    # Adversarially make the high-band contracts require a guild
                    # level above this rival's level; the real planner must fall back
                    # to any feasible dungeon/boss rather than stalling on contracts.
                    for offer in offers_one:
                        offer.required_guild_level_snapshot = 51
                    fallback_offers = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle_one.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type.in_(("dungeon", "boss")),
                    )))
                    self.assertTrue(fallback_offers)
                    for offer in fallback_offers:
                        offer.required_guild_level_snapshot = 1
                        offer.required_total_power_snapshot = 0
                        offer.required_tank_count_snapshot = 0
                        offer.required_support_count_snapshot = 0
                        offer.required_damage_count_snapshot = 0
                        offer.min_party_size_snapshot = 1
                        offer.max_party_size_snapshot = 1

                    cpu.archetype = "exploration"
                    cpu.level = 50
                    db.flush()
                    fallback_id = fallback_offers[0].id

                    def force_one_eligible_fallback(
                        offer, state, party_roster, available_at, cycle_end, class_roles, **_kwargs,
                    ):
                        if offer.id != fallback_id or not party_roster:
                            return None
                        member = party_roster[0]
                        start_at = max(
                            available_at.get(member.id, cycle_end),
                            cycle_end - timedelta(seconds=CYCLE_SECONDS) + timedelta(hours=1),
                        )
                        if start_at + timedelta(seconds=offer.duration_seconds_snapshot) > cycle_end:
                            return None
                        return start_at, [member]

                    with patch.object(
                        regional_cycle_service, "_cpu_offer_party",
                        side_effect=force_one_eligible_fallback,
                    ):
                        advance_regional_world(
                            db, campaign, guild, start + timedelta(seconds=2 * CYCLE_SECONDS),
                        )
                    plan_one = db.scalar(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.cycle_id == cycle_one.id,
                        RegionalCpuCyclePlan.guild_state_id == cpu.id,
                    ))
                    decisions_one = json.loads(plan_one.decisions_json)
                    self.assertTrue(decisions_one, "CPU should substitute an eligible exploration offer")
                    self.assertIn(
                        decisions_one[0]["offer_type"], {"dungeon", "boss"}, decisions_one,
                    )
                    self.assertEqual(decisions_one[0]["offer_id"], fallback_id)

                    for member in roster:
                        member.active = False
                    cpu_gold = db.scalar(select(RegionalCpuResource).where(
                        RegionalCpuResource.guild_state_id == cpu.id,
                        RegionalCpuResource.resource_code == "gold",
                    ))
                    cpu_gold.amount = 0
                    db.flush()
                    cycle_two = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 2,
                    ))
                    advance_regional_world(
                        db, campaign, guild, start + timedelta(seconds=3 * CYCLE_SECONDS),
                    )
                    plan_two = db.scalar(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.cycle_id == cycle_two.id,
                        RegionalCpuCyclePlan.guild_state_id == cpu.id,
                    ))
                    self.assertEqual(plan_two.actions, 0)
                    self.assertEqual(json.loads(plan_two.decisions_json), [])
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_cpu_offer_policy_ranks_expected_xp_rate_before_rank(self):
        from app.services.regional_cycle_service import _cpu_offer_preference

        strong_expected = SimpleNamespace(
            offer_type="contract", rank="E", success_chance_snapshot=90,
            recommended_power_snapshot=100, gold_reward_snapshot=50,
            xp_reward_snapshot=50, duration_seconds_snapshot=900,
            cpu_failure_risk_snapshot=0, id=1,
        )
        high_rank_low_value = SimpleNamespace(
            offer_type="contract", rank="S", success_chance_snapshot=45,
            recommended_power_snapshot=100, gold_reward_snapshot=5,
            xp_reward_snapshot=5, duration_seconds_snapshot=3600,
            cpu_failure_risk_snapshot=0, id=2,
        )
        best = _cpu_offer_preference(strong_expected, "contracts", 100, 2, 0)
        weaker = _cpu_offer_preference(high_rank_low_value, "contracts", 100, 2, 0)
        self.assertLess(best, weaker)

    def test_cpu_offer_policy_does_not_treat_gold_as_xp(self):
        from app.services.regional_cycle_service import _cpu_offer_preference

        xp_contract = SimpleNamespace(
            offer_type="contract", rank="E", success_chance_snapshot=80,
            recommended_power_snapshot=100, gold_reward_snapshot=0,
            xp_reward_snapshot=100, duration_seconds_snapshot=900,
            cpu_failure_risk_snapshot=0, id=1,
        )
        gold_contract = SimpleNamespace(
            offer_type="contract", rank="S", success_chance_snapshot=80,
            recommended_power_snapshot=100, gold_reward_snapshot=10000,
            xp_reward_snapshot=1, duration_seconds_snapshot=900,
            cpu_failure_risk_snapshot=0, id=2,
        )

        self.assertLess(
            _cpu_offer_preference(xp_contract, "contracts", 100, 1, 0),
            _cpu_offer_preference(gold_contract, "contracts", 100, 1, 0),
        )

    def test_cpu_boss_equipment_requirement_applies_to_every_party_member(self):
        from app.services.regional_cycle_service import _cpu_offer_party

        start = datetime(2026, 11, 9)
        offer = SimpleNamespace(
            required_guild_level_snapshot=1,
            min_party_size_snapshot=2,
            max_party_size_snapshot=2,
            required_min_mercenary_level_snapshot=99,
            required_class_code_snapshot=None,
            required_total_power_snapshot=0,
            required_tank_count_snapshot=0,
            required_support_count_snapshot=0,
            required_damage_count_snapshot=0,
            required_equipment_tier_snapshot=2,
        )
        party = [
            SimpleNamespace(
                id=1, slot=1, level=1, class_code="warrior", power=20,
                vitality=0, agility=0, intelligence=0, luck=0, armor=0,
                equipment_bonus_json='{"equipment_tier": 2}',
            ),
            SimpleNamespace(
                id=2, slot=2, level=1, class_code="mage", power=20,
                vitality=0, agility=0, intelligence=0, luck=0, armor=0,
                equipment_bonus_json='{"equipment_tier": 1}',
            ),
        ]
        choice = _cpu_offer_party(
            offer, SimpleNamespace(level=1), party,
            {1: start, 2: start}, start + timedelta(hours=4), {},
        )
        self.assertIsNone(choice)
        party[1].equipment_bonus_json = '{"equipment_tier": 2}'
        choice = _cpu_offer_party(
            offer, SimpleNamespace(level=1), party,
            {1: start, 2: start}, start + timedelta(hours=4), {},
        )
        self.assertIsNotNone(choice)

    def test_v7_cpu_party_prefers_later_team_when_expected_xp_rate_is_better(self):
        from app.services.regional_cycle_service import _cpu_offer_party

        start = datetime(2026, 11, 9)
        offer = SimpleNamespace(
            required_guild_level_snapshot=1,
            min_party_size_snapshot=1,
            max_party_size_snapshot=1,
            required_min_mercenary_level_snapshot=1,
            required_class_code_snapshot=None,
            required_total_power_snapshot=0,
            required_tank_count_snapshot=0,
            required_support_count_snapshot=0,
            required_damage_count_snapshot=0,
            required_equipment_tier_snapshot=0,
            success_chance_snapshot=50,
            cpu_failure_risk_snapshot=0,
            recommended_power_snapshot=100,
            xp_reward_snapshot=100,
            duration_seconds_snapshot=3600,
        )
        roster = [
            SimpleNamespace(
                id=1, slot=1, level=1, class_code="warrior", power=20,
                vitality=0, agility=0, intelligence=0, luck=0, armor=0,
                equipment_bonus_json="{}",
            ),
            SimpleNamespace(
                id=2, slot=2, level=1, class_code="mage", power=100,
                vitality=0, agility=0, intelligence=0, luck=0, armor=0,
                equipment_bonus_json="{}",
            ),
        ]
        choice = _cpu_offer_party(
            offer, SimpleNamespace(level=1), roster,
            {1: start, 2: start + timedelta(minutes=30)},
            start + timedelta(hours=4), {}, optimize_cpu_value=True,
        )

        self.assertIsNotNone(choice)
        self.assertEqual(choice[0], start + timedelta(minutes=30))
        self.assertEqual([member.id for member in choice[1]], [2])

    def test_v7_cpu_party_skips_team_that_cannot_finish_before_deadline(self):
        from app.services.regional_cycle_service import _cpu_offer_party

        start = datetime(2026, 11, 9)
        offer = SimpleNamespace(
            required_guild_level_snapshot=1,
            min_party_size_snapshot=1,
            max_party_size_snapshot=1,
            required_min_mercenary_level_snapshot=1,
            required_class_code_snapshot=None,
            required_total_power_snapshot=0,
            required_tank_count_snapshot=0,
            required_support_count_snapshot=0,
            required_damage_count_snapshot=0,
            required_equipment_tier_snapshot=0,
            success_chance_snapshot=50,
            cpu_failure_risk_snapshot=0,
            recommended_power_snapshot=100,
            xp_reward_snapshot=100,
            duration_seconds_snapshot=3600,
        )
        mercenary = SimpleNamespace(
            id=1, slot=1, level=1, class_code="warrior", power=100,
            vitality=0, agility=0, intelligence=0, luck=0, armor=0,
            equipment_bonus_json="{}",
        )

        choice = _cpu_offer_party(
            offer, SimpleNamespace(level=1), [mercenary],
            {1: start + timedelta(hours=3, minutes=30)},
            start + timedelta(hours=4), {}, optimize_cpu_value=True,
        )

        self.assertIsNone(choice)

    def test_v7_cpu_portal_party_filters_start_deadline_before_ranking(self):
        from app.services.regional_cycle_service import _cpu_offer_party

        start = datetime(2026, 11, 9)
        portal_deadline = start + timedelta(hours=3)
        offer = SimpleNamespace(
            required_guild_level_snapshot=1,
            min_party_size_snapshot=1,
            max_party_size_snapshot=1,
            required_min_mercenary_level_snapshot=1,
            required_class_code_snapshot=None,
            required_total_power_snapshot=0,
            required_tank_count_snapshot=0,
            required_support_count_snapshot=0,
            required_damage_count_snapshot=0,
            required_equipment_tier_snapshot=0,
            success_chance_snapshot=50,
            cpu_failure_risk_snapshot=0,
            recommended_power_snapshot=100,
            xp_reward_snapshot=100,
            duration_seconds_snapshot=3600,
        )
        roster = [
            SimpleNamespace(
                id=1, slot=1, level=1, class_code="warrior", power=20,
                vitality=0, agility=0, intelligence=0, luck=0, armor=0,
                equipment_bonus_json="{}",
            ),
            SimpleNamespace(
                id=2, slot=2, level=1, class_code="mage", power=500,
                vitality=0, agility=0, intelligence=0, luck=0, armor=0,
                equipment_bonus_json="{}",
            ),
        ]
        choice = _cpu_offer_party(
            offer, SimpleNamespace(level=1), roster,
            {1: start + timedelta(hours=1), 2: portal_deadline},
            start + timedelta(hours=6), {}, optimize_cpu_value=True,
            latest_start_before=portal_deadline,
        )

        self.assertIsNotNone(choice)
        self.assertEqual(choice[0], start + timedelta(hours=1))
        self.assertEqual([member.id for member in choice[1]], [1])

        late_only = _cpu_offer_party(
            offer, SimpleNamespace(level=1), [roster[1]],
            {2: portal_deadline}, start + timedelta(hours=6), {},
            optimize_cpu_value=True, latest_start_before=portal_deadline,
        )
        self.assertIsNone(late_only)

    def test_open_v6_cycle_keeps_targeted_pressure_and_cpu_rotation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            with patch(
                "app.services.campaign_service.uuid4",
                return_value=UUID("00000000-0000-4000-8000-000000000071"),
            ):
                created = campaigns.create_campaign("Ciclo v6 aberto", "Guilda v6")
            campaigns.activate_campaign(created.campaign_id)
            try:
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, created.campaign_id)
                    guild, _resources = get_current_guild_context(db, created.campaign_id)
                    start = campaign.created_at_utc
                    advance_regional_world(db, campaign, guild, start)
                    regional_cycle_service.get_regional_board(db, campaign, guild, start)
                    cycle_zero = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == created.campaign_id,
                        RegionalCycle.cycle_number == 0,
                    ))
                    cycle_zero.rules_version = regional_cycle_service.VIGILIA_V6_RULES_VERSION
                    db.flush()

                    first_cycle_order = []
                    original_plan = regional_cycle_service._cpu_plan_for_guild

                    def record_first_order(db_session, campaign_id, cycle, region, state):
                        if cycle.id == cycle_zero.id:
                            first_cycle_order.append((region.region_code, state.slot))
                        return original_plan(db_session, campaign_id, cycle, region, state)

                    with patch.object(
                        regional_cycle_service, "_cpu_plan_for_guild", side_effect=record_first_order,
                    ):
                        advance_regional_world(
                            db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS),
                        )
                    snapshots = list(db.scalars(select(RegionalCycleRegion).where(
                        RegionalCycleRegion.cycle_id == cycle_zero.id,
                    )))
                    target_regions = {
                        json.loads(row.summary_json)["gradual_pressure"]["target_region"]
                        for row in snapshots
                    }
                    self.assertEqual(len(target_regions), 1)
                    self.assertLessEqual(sum(
                        json.loads(row.summary_json)["gradual_pressure"]["targeted"]
                        for row in snapshots
                    ), 1)
                    expected_first_order = [
                        (region_code, slot)
                        for region_code in sorted({row[0] for row in first_cycle_order})
                        for slot in sorted(slot for code, slot in first_cycle_order if code == region_code)
                    ]
                    self.assertEqual(first_cycle_order, expected_first_order)

                    cycle_one_time = start + timedelta(seconds=CYCLE_SECONDS)
                    regional_cycle_service.get_regional_board(db, campaign, guild, cycle_one_time)
                    cycle_one = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == created.campaign_id,
                        RegionalCycle.cycle_number == 1,
                    ))
                    cycle_one.rules_version = regional_cycle_service.VIGILIA_V6_RULES_VERSION
                    db.flush()
                    second_cycle_order = []
                    risk_by_region = {}

                    def record_second_order(db_session, campaign_id, cycle, region, state):
                        if cycle.id == cycle_one.id:
                            second_cycle_order.append((region.region_code, state.slot))
                            risk_by_region.setdefault(
                                region.region_code,
                                float(region.threat) + 100.0 - float(region.security),
                            )
                        return original_plan(db_session, campaign_id, cycle, region, state)

                    with patch.object(
                        regional_cycle_service, "_cpu_plan_for_guild", side_effect=record_second_order,
                    ):
                        advance_regional_world(
                            db, campaign, guild, start + timedelta(seconds=2 * CYCLE_SECONDS),
                        )
                    expected_second_order = []
                    for region_code in sorted(
                        risk_by_region,
                        key=lambda code: (-risk_by_region[code], code),
                    ):
                        slots = sorted(slot for code, slot in second_cycle_order if code == region_code)
                        rotation = 1 % len(slots)
                        expected_second_order.extend(
                            (region_code, slot) for slot in slots[rotation:] + slots[:rotation]
                        )
                    self.assertEqual(second_cycle_order, expected_second_order)
            finally:
                campaigns.close_active_campaign(created.campaign_id)

    def test_cpu_throughput_scales_with_roster_and_pressure_selects_highest_risk(self):
        strong = RegionalGuildState(
            region_code="vale-fronteira", slot=1, name="Forte", profile="strong", archetype="balanced",
            level=50,
        )
        self.assertEqual(cpu_roster_cap(strong, 1), 20)
        strong.level = 100
        self.assertEqual(cpu_roster_cap(strong, 1), 20)
        new = RegionalGuildState(
            region_code="vale-fronteira", slot=4, name="Nova", profile="new", archetype="balanced",
            level=1,
        )
        self.assertEqual(cpu_roster_cap(new, 1), 2)
        self.assertEqual(regional_cycle_service.cpu_failure_risk_for_region(25, 50), 0)
        self.assertEqual(regional_cycle_service.cpu_failure_risk_for_region(85, 25), 15)
        self.assertEqual(regional_cycle_service.cpu_failure_risk_for_region(100, 0), 15)
        self.assertGreater(
            regional_cycle_service.regional_gradual_pressure(85, 25),
            regional_cycle_service.regional_gradual_pressure(25, 50),
        )
        self.assertLessEqual(
            regional_cycle_service.regional_gradual_pressure(100, 0),
            regional_cycle_service.REGIONAL_GRADUAL_PRESSURE_MAX,
        )
        self.assertGreater(
            regional_cycle_service.regional_gradual_security_pressure(85, 25),
            regional_cycle_service.regional_gradual_security_pressure(25, 50),
        )
        self.assertLessEqual(
            regional_cycle_service.regional_gradual_security_pressure(100, 0),
            regional_cycle_service.REGIONAL_GRADUAL_SECURITY_PRESSURE_MAX,
        )
        regions = [
            SimpleNamespace(region_code=f"r{i}", threat=20 + i * 10, security=60 - i * 5)
            for i in range(5)
        ]
        self.assertEqual(
            regional_cycle_service.regional_pressure_target_code("pressure-risk-test", 0, regions),
            "r4",
        )
        self.assertEqual(
            regional_cycle_service.regional_pressure_target_code("pressure-risk-test", 19, regions, {"r4"}),
            "r3",
        )
        ties = [SimpleNamespace(region_code="a", threat=90, security=20),
                SimpleNamespace(region_code="b", threat=90, security=20)]
        self.assertEqual(
            regional_cycle_service.regional_pressure_target_code("pressure-tie-test", 0, ties),
            regional_cycle_service.regional_pressure_target_code("pressure-tie-test", 0, ties),
        )

    def test_cpu_portal_entry_starts_before_deadline_and_may_resolve_after(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            with patch(
                "app.services.campaign_service.uuid4",
                return_value=UUID("00000000-0000-4000-8000-000000000091"),
            ):
                created = campaigns.create_campaign("Portal CPU", "Guilda Portal")
            campaigns.activate_campaign(created.campaign_id)
            with SessionLocal() as db:
                from app.services.regional_event_service import build_portal_boss_snapshot

                campaign = db.get(CampaignMetadata, created.campaign_id)
                guild, _resources = get_current_guild_context(db, created.campaign_id)
                start = campaign.created_at_utc
                advance_regional_world(db, campaign, guild, start)
                cycle = db.scalar(select(RegionalCycle).where(
                    RegionalCycle.campaign_id == created.campaign_id,
                    RegionalCycle.cycle_number == 0,
                ))
                region_code = next(code for code, name in regional_cycle_service.REGIONS
                                   if name == campaign.home_region)
                cpu = db.scalar(select(RegionalGuildState).where(
                    RegionalGuildState.campaign_id == created.campaign_id,
                    RegionalGuildState.region_code == region_code,
                    RegionalGuildState.profile == "strong",
                ))
                for other_cpu in db.scalars(select(RegionalGuildState).where(
                    RegionalGuildState.campaign_id == created.campaign_id,
                    RegionalGuildState.guild_id.is_(None),
                )):
                    if other_cpu.id != cpu.id:
                        other_cpu.active = False
                cpu.archetype = "exploration"
                template = DungeonTemplate(
                    name="Chefe de teste do portal", description="Encontro regional", content_type="boss",
                    level_band="1-20", recommended_level=1, biome="portal", difficulty="normal",
                    duration_seconds=1800, base_gold_reward=500, base_xp_reward=500,
                    base_success_chance=65, min_party_size=1, max_party_size=5,
                    required_guild_level=1, required_min_mercenary_level=1,
                    required_total_power=0, required_tank_count=0, required_support_count=0,
                    required_damage_count=0, required_equipment_tier=0, is_active=True,
                )
                db.add(template)
                db.flush()
                plan_seed = regional_cycle_service._seed_text(
                    created.campaign_id, 0, cpu.id, cycle.rules_version, "cpu-plan",
                )
                portal_seed = next(
                    f"portal-test-{seed_index}"
                    for seed_index in range(10_000)
                    if regional_cycle_service._rng(
                        f"portal-test-{seed_index}", plan_seed, "cpu-portal-entry",
                    ).random() < 0.25
                )
                portal = regional_cycle_service.RegionalEvent(
                    campaign_id=created.campaign_id,
                    event_type="portal",
                    region_code=region_code,
                    trigger_cycle_number=0,
                    rules_version="regional-events-v3",
                    seed=portal_seed,
                    status="active",
                    dungeon_template_id=template.id,
                    created_at_utc=start,
                    expires_at_utc=start + timedelta(hours=1, minutes=15),
                    summary_json=json.dumps({
                        "portal_boss": {
                            "template": build_portal_boss_snapshot(template),
                        },
                    }, sort_keys=True),
                )
                db.add(portal)
                for offer in db.scalars(select(RegionalOffer).where(
                    RegionalOffer.cycle_id == cycle.id,
                    RegionalOffer.region_code == region_code,
                )):
                    offer.status = "cpu_completed"
                db.commit()

                advance_regional_world(db, campaign, guild, start + timedelta(seconds=CYCLE_SECONDS))

                plan = db.scalar(select(RegionalCpuCyclePlan).where(
                    RegionalCpuCyclePlan.cycle_id == cycle.id,
                    RegionalCpuCyclePlan.guild_state_id == cpu.id,
                ))
                decisions = json.loads(plan.decisions_json)
                portal_decisions = [item for item in decisions if item["offer_type"] == "portal"]
                self.assertEqual(
                    len(portal_decisions), 1,
                    (
                        [item["offer_type"] for item in decisions], plan.planned_actions,
                        plan.eligible_actions, portal.status,
                        regional_cycle_service._utc(cycle.starts_at_utc),
                        regional_cycle_service._utc(portal.created_at_utc),
                        regional_cycle_service._utc(portal.expires_at_utc),
                    ),
                )
                decision = portal_decisions[0]
                self.assertEqual(decision["event_id"], portal.id)
                self.assertEqual(decision["duration_seconds"], template.duration_seconds)
                self.assertEqual(plan.actions, len(decisions))
                start_at = regional_cycle_service._utc(datetime.fromisoformat(decision["started_at_utc"]))
                end_at = regional_cycle_service._utc(datetime.fromisoformat(decision["resolved_at_utc"]))
                self.assertEqual((end_at - start_at).total_seconds(), template.duration_seconds)
                self.assertGreaterEqual(
                    start_at,
                    regional_cycle_service._utc(datetime.fromisoformat(
                        decision["player_priority_ends_at_utc"],
                    )),
                )
                self.assertLess(start_at, regional_cycle_service._utc(portal.expires_at_utc))
                self.assertGreater(end_at, regional_cycle_service._utc(portal.expires_at_utc))
                occupied: dict[int, datetime] = {}
                for item in sorted(decisions, key=lambda row: row["started_at_utc"]):
                    item_start = regional_cycle_service._utc(datetime.fromisoformat(item["started_at_utc"]))
                    item_end = regional_cycle_service._utc(datetime.fromisoformat(item["resolved_at_utc"]))
                    for slot in item["mercenary_slots"]:
                        self.assertLessEqual(occupied.get(slot, item_start), item_start)
                        occupied[slot] = item_end
                portal_outcome = next(row for row in json.loads(plan.outcomes_json)
                                      if row["offer_id"] == decision["offer_id"])
                self.assertEqual((portal_outcome["gold"], portal_outcome["xp"]), (0, 0))
                participant = db.scalar(select(regional_cycle_service.RegionalEventParticipant).where(
                    regional_cycle_service.RegionalEventParticipant.event_id == portal.id,
                    regional_cycle_service.RegionalEventParticipant.guild_state_id == cpu.id,
                ))
                self.assertIsNotNone(participant)
                self.assertEqual(participant.status, "resolved")
                self.assertEqual(regional_cycle_service._utc(participant.resolved_at_utc), end_at)
                offline_return = start + timedelta(seconds=2 * CYCLE_SECONDS)
                advance_regional_world(db, campaign, guild, offline_return)
                self.assertEqual(portal.status, "resolved")
                advance_regional_world(db, campaign, guild, offline_return)
                self.assertEqual(db.scalar(select(func.count(RegionalEventActivity.id)).where(
                    RegionalEventActivity.event_id == portal.id,
                    RegionalEventActivity.source_type == "cpu_portal",
                )), 1)
            configure_database("sqlite:///:memory:")

    def test_portal_expiry_request_does_not_change_pending_cpu_cycle(self):
        def run_scenario(*, visit_player: bool, collect_at_t4: bool) -> tuple[object, ...]:
            configure_database("sqlite:///:memory:")
            with tempfile.TemporaryDirectory() as temp_dir:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                with patch(
                    "app.services.campaign_service.uuid4",
                    return_value=UUID("00000000-0000-4000-8000-000000000092"),
                ):
                    created = campaigns.create_campaign("Portal deadline", "Guilda Portal")
                campaigns.activate_campaign(created.campaign_id)
                with SessionLocal() as db:
                    from app.services.regional_event_service import (
                        attach_event_activity,
                        build_portal_boss_snapshot,
                        expire_due_events,
                        record_event_activity_result,
                        resolve_portal_participant,
                    )
                    from app.routes.regional_routes import _portal_action_blocker

                    campaign = db.get(CampaignMetadata, created.campaign_id)
                    guild, _resources = get_current_guild_context(db, created.campaign_id)
                    origin = campaign.created_at_utc
                    # Processing cycle 0 creates the boundary at which the
                    # cycle 1 portal appears. Hold the random event roll fixed
                    # so each half of this paired test uses the same event.
                    with patch("app.services.regional_event_service.create_cycle_portals"):
                        advance_regional_world(
                            db, campaign, guild, origin + timedelta(seconds=CYCLE_SECONDS),
                        )
                    cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == created.campaign_id,
                        RegionalCycle.cycle_number == 1,
                    ))
                    region_code = next(
                        code for code, name in regional_cycle_service.REGIONS
                        if name == campaign.home_region
                    )
                    cpu = db.scalar(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == created.campaign_id,
                        RegionalGuildState.region_code == region_code,
                        RegionalGuildState.profile == "strong",
                    ))
                    for other_cpu in db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == created.campaign_id,
                        RegionalGuildState.guild_id.is_(None),
                    )):
                        if other_cpu.id != cpu.id:
                            other_cpu.active = False
                    cpu.archetype = "exploration"
                    template = DungeonTemplate(
                        name="Chefe de portal pareado", description="Encontro regional",
                        content_type="boss", level_band="1-20", recommended_level=1,
                        biome="portal", difficulty="normal", duration_seconds=1800,
                        base_gold_reward=500, base_xp_reward=500, base_success_chance=65,
                        min_party_size=1, max_party_size=5, required_guild_level=1,
                        required_min_mercenary_level=1, required_total_power=0,
                        required_tank_count=0, required_support_count=0,
                        required_damage_count=0, required_equipment_tier=0, is_active=True,
                    )
                    db.add(template)
                    db.flush()
                    plan_seed = regional_cycle_service._seed_text(
                        created.campaign_id, cycle.cycle_number, cpu.id,
                        cycle.rules_version, "cpu-plan",
                    )
                    portal_seed = next(
                        f"portal-race-{seed_index}"
                        for seed_index in range(10_000)
                        if regional_cycle_service._rng(
                            f"portal-race-{seed_index}", plan_seed, "cpu-portal-entry",
                        ).random() < 0.25
                    )
                    portal = RegionalEvent(
                        campaign_id=created.campaign_id, event_type="portal",
                        region_code=region_code, trigger_cycle_number=0,
                        rules_version="regional-events-v4", seed=portal_seed,
                        status="active", dungeon_template_id=template.id,
                        created_at_utc=cycle.starts_at_utc,
                        expires_at_utc=cycle.starts_at_utc + timedelta(hours=3),
                        summary_json=json.dumps({
                            "portal_boss": {"template": build_portal_boss_snapshot(template)},
                        }, sort_keys=True),
                    )
                    db.add(portal)
                    db.flush()
                    player_state = regional_cycle_service.get_current_player_regional_guild(
                        db, created.campaign_id, guild.id,
                    )
                    player_source_run_id = 987654321
                    player_activity = None
                    if visit_player:
                        player_activity = attach_event_activity(
                            db, portal, player_state, "dungeon", player_source_run_id,
                        )
                        self.assertEqual(player_activity.status, "in_progress")
                    for offer in db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == region_code,
                    )):
                        offer.status = "cpu_completed"
                    db.commit()

                    deadline = portal.expires_at_utc
                    original_deadline = regional_cycle_service._utc(deadline)
                    # This GET/expire/commit can run at T+3 while the CPU plan
                    # for the just-opened cycle is still pending.
                    expire_due_events(db, created.campaign_id, deadline)
                    db.commit()
                    db.refresh(portal)
                    self.assertEqual(portal.status, "in_progress" if visit_player else "active")
                    self.assertEqual(regional_cycle_service._utc(portal.expires_at_utc), original_deadline)
                    self.assertIn(
                        "prazo",
                        _portal_action_blocker(db, campaign, portal, player_state, original_deadline).lower(),
                    )

                    if collect_at_t4:
                        self.assertIsNotNone(player_activity)
                        player_activity = record_event_activity_result(
                            db, "dungeon", player_source_run_id, True,
                            original_deadline + timedelta(hours=1),
                        )
                        self.assertIsNotNone(player_activity)
                        resolve_portal_participant(
                            db, player_activity, True, original_deadline + timedelta(hours=1),
                        )
                        db.flush()
                        db.refresh(portal)
                        self.assertEqual(
                            portal.status, "in_progress",
                            "player collection at T+4 must not finalize before the T+6 CPU plan",
                        )

                    close_time = cycle.ends_at_utc
                    advance_regional_world(db, campaign, guild, close_time)
                    plan = db.scalar(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.cycle_id == cycle.id,
                        RegionalCpuCyclePlan.guild_state_id == cpu.id,
                    ))
                    portal_decisions = [
                        row for row in json.loads(plan.decisions_json)
                        if row.get("offer_type") == "portal"
                    ]
                    self.assertEqual(len(portal_decisions), 1)
                    decision = portal_decisions[0]
                    self.assertLess(
                        regional_cycle_service._utc(datetime.fromisoformat(decision["started_at_utc"])),
                        original_deadline,
                    )
                    self.assertGreater(
                        regional_cycle_service._utc(datetime.fromisoformat(decision["resolved_at_utc"])),
                        regional_cycle_service._utc(datetime.fromisoformat(decision["started_at_utc"])),
                    )
                    self.assertEqual(portal.status, "in_progress" if visit_player else "active")
                    if player_activity is not None and player_activity.status == "in_progress":
                        player_activity = record_event_activity_result(
                            db, "dungeon", player_source_run_id, True, close_time,
                        )
                        self.assertIsNotNone(player_activity)
                        resolve_portal_participant(db, player_activity, True, close_time)
                    expire_due_events(db, created.campaign_id, close_time)
                    db.commit()
                    activity = db.scalar(select(RegionalEventActivity).where(
                        RegionalEventActivity.event_id == portal.id,
                        RegionalEventActivity.source_type == "cpu_portal",
                    ))
                    self.assertIsNotNone(activity)
                    activity_count = db.scalar(select(func.count(RegionalEventActivity.id)).where(
                        RegionalEventActivity.event_id == portal.id,
                        RegionalEventActivity.source_type == "cpu_portal",
                    ))
                    self.assertEqual(activity_count, 1)
                    self.assertEqual(portal.status, "resolved")
                    player_participant = db.scalar(select(RegionalEventParticipant).where(
                        RegionalEventParticipant.event_id == portal.id,
                        RegionalEventParticipant.guild_state_id == player_state.id,
                    ))
                    cpu_participant = db.scalar(select(RegionalEventParticipant).where(
                        RegionalEventParticipant.event_id == portal.id,
                        RegionalEventParticipant.guild_state_id == cpu.id,
                    ))
                    self.assertEqual(cpu_participant.status, "resolved")
                    if visit_player:
                        self.assertEqual(player_participant.status, "resolved")
                        player_activity = db.scalar(select(RegionalEventActivity).where(
                            RegionalEventActivity.event_id == portal.id,
                            RegionalEventActivity.source_run_id == player_source_run_id,
                        ))
                        self.assertEqual(player_activity.status, "resolved")
                    else:
                        self.assertIsNone(player_participant)
                    final_summary = json.loads(portal.summary_json)
                    self.assertEqual(final_summary["aggregate"]["entries"], 2 if visit_player else 1)
                    self.assertEqual(final_summary["aggregate"]["successes"],
                                     activity.successes + (player_activity.successes if player_activity else 0))
                    self.assertEqual(final_summary["aggregate"]["failures"],
                                     activity.failures + (player_activity.failures if player_activity else 0))
                    cycle_start_utc = regional_cycle_service._utc(cycle.starts_at_utc)
                    decision_start = regional_cycle_service._utc(
                        datetime.fromisoformat(decision["started_at_utc"]),
                    )
                    decision_end = regional_cycle_service._utc(
                        datetime.fromisoformat(decision["resolved_at_utc"]),
                    )
                    result = (
                        round((decision_start - cycle_start_utc).total_seconds(), 3),
                        round((decision_end - cycle_start_utc).total_seconds(), 3),
                        activity.successes, activity.failures, activity.contribution,
                        activity_count, portal.status,
                        final_summary["aggregate"]["entries"],
                        final_summary["aggregate"]["successes"],
                        final_summary["aggregate"]["failures"],
                        (regional_cycle_service._utc(portal.expires_at_utc) - cycle_start_utc).total_seconds(),
                    )
                    final_summary_json = portal.summary_json
                    advance_regional_world(db, campaign, guild, close_time)
                    expire_due_events(db, created.campaign_id, close_time)
                    db.commit()
                    self.assertEqual(portal.summary_json, final_summary_json)
                    self.assertEqual(db.scalar(select(func.count(RegionalEventActivity.id)).where(
                        RegionalEventActivity.event_id == portal.id,
                        RegionalEventActivity.source_type == "cpu_portal",
                    )), 1)
                configure_database("sqlite:///:memory:")
                gc.collect()
                return result

        unvisited_at_expiry = run_scenario(visit_player=False, collect_at_t4=False)
        visited_and_collected_at_t4 = run_scenario(visit_player=True, collect_at_t4=True)
        visited_and_collected_after_cpu = run_scenario(visit_player=True, collect_at_t4=False)
        self.assertEqual(unvisited_at_expiry[2] + unvisited_at_expiry[3], 1)
        self.assertEqual(unvisited_at_expiry[5:8], (1, "resolved", 1))
        self.assertEqual(visited_and_collected_at_t4, visited_and_collected_after_cpu)

    def test_offline_catchup_resolves_cpu_rebellion_without_opening_regional_board(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Rebelião offline", "Guilda Offline")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    start = campaign.created_at_utc
                    advance_regional_world(db, campaign, guild, start)
                    cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 0,
                    ))
                    region_code = next(
                        code for code, name in regional_cycle_service.REGIONS
                        if name == campaign.home_region
                    )
                    event = RegionalEvent(
                        campaign_id=info.campaign_id,
                        event_type="rebellion",
                        region_code=region_code,
                        trigger_cycle_number=0,
                        rules_version=cycle.rules_version,
                        seed="offline-rebellion-seed",
                        status="active",
                        created_at_utc=start,
                        priority_ends_at_utc=start + timedelta(hours=1),
                        cpu_started_at_utc=start + timedelta(hours=1),
                        expires_at_utc=start + timedelta(hours=13),
                        summary_json=json.dumps({"player_decision": "no_response_delegated_to_cpu"}),
                    )
                    db.add(event)
                    db.commit()

                    return_time = start + timedelta(seconds=3 * CYCLE_SECONDS)
                    advance_regional_world(db, campaign, guild, return_time)

                    activities = list(db.scalars(select(RegionalEventActivity).where(
                        RegionalEventActivity.event_id == event.id,
                        RegionalEventActivity.source_type == "cpu_cycle",
                    )))
                    self.assertGreater(len(activities), 0)
                    self.assertTrue(all(activity.status == "resolved" for activity in activities))
                    self.assertEqual(event.status, "resolved")
                    activity_ids = {activity.id for activity in activities}
                    summary = event.summary_json

                    advance_regional_world(db, campaign, guild, return_time)

                    repeated = list(db.scalars(select(RegionalEventActivity).where(
                        RegionalEventActivity.event_id == event.id,
                        RegionalEventActivity.source_type == "cpu_cycle",
                    )))
                    self.assertEqual({activity.id for activity in repeated}, activity_ids)
                    self.assertEqual(event.summary_json, summary)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_requirement_overrides_remain_defensive_in_services(self):
        class Stub:
            level = 1
            required_guild_level = 1

        with self.assertRaisesRegex(MissionError, "Nível da guilda insuficiente"):
            validate_mission_requirements(None, Stub(), Stub(), required_guild_level=5)
        with self.assertRaisesRegex(DungeonError, "Nível da guilda insuficiente"):
            validate_dungeon_requirements(None, Stub(), Stub(), required_guild_level=5)

    def test_cpu_action_cadence_is_above_initial_baseline(self):
        states = [
            RegionalGuildState(region_code="sample", slot=slot, name=f"Rival {slot}", profile=profile, archetype="balanced")
            for slot, profile in enumerate(("strong", "medium", "new", "new"))
        ]
        expected_actions = sum(
            regional_cycle_service.regional_cpu_action_probability("cadence-test", state)
            * (2 if state.profile == "strong" else 1)
            for state in states
        )

        self.assertGreater(expected_actions, 1.25)
        self.assertGreaterEqual(expected_actions, 1.38)
        self.assertLessEqual(expected_actions, 1.48)

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
                    advance_regional_world(db, campaign, guild, campaign.created_at_utc)
                    regional_cycle_service.get_regional_board(db, campaign, guild, campaign.created_at_utc)
                    for cycle_index in range(1, 101):
                        current_time = campaign.created_at_utc + timedelta(seconds=cycle_index * CYCLE_SECONDS)
                        advance_regional_world(db, campaign, guild, current_time)
                        regional_cycle_service.get_regional_board(db, campaign, guild, current_time)

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
                        planned = sum(plan.planned_actions for plan in plans)
                        eligible = sum(plan.eligible_actions for plan in plans)
                        started = sum(plan.started_actions for plan in plans)
                        resolved = sum(plan.resolved_actions for plan in plans)
                        pending_portal_actions = db.scalar(
                            select(func.count(func.distinct(RegionalEventActivity.source_run_id)))
                            .join(RegionalCpuCyclePlan,
                                  RegionalCpuCyclePlan.id == RegionalEventActivity.source_run_id)
                            .join(RegionalCycle, RegionalCycle.id == RegionalCpuCyclePlan.cycle_id)
                            .where(
                                RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                                RegionalCycle.cycle_number < horizon,
                                RegionalEventActivity.source_type == "cpu_portal",
                                RegionalEventActivity.status == "in_progress",
                            )
                        )
                        self.assertGreaterEqual(planned, eligible)
                        self.assertGreaterEqual(eligible, started)
                        self.assertEqual(started, actions)
                        self.assertEqual(resolved + pending_portal_actions, actions)
                        self.assertGreaterEqual(started / max(1, eligible), 0.70)
                        by_profile = {}
                        by_region = {}
                        by_guild = {}
                        for plan in plans:
                            state = db.get(RegionalGuildState, plan.guild_state_id)
                            bucket = by_profile.setdefault(state.profile, {
                                "actions": 0, "successes": 0, "failures": 0, "gold": 0, "xp": 0,
                                "hires": 0, "hire_gold_spent": 0,
                                "guild_ids": set(), "roster_slots": 0, "roster_observations": 0,
                            })
                            bucket["actions"] += plan.actions
                            bucket["successes"] += plan.successes
                            bucket["failures"] += plan.failures
                            bucket["gold"] += plan.gold_earned
                            bucket["xp"] += plan.xp_earned
                            bucket["hires"] += plan.hired_count
                            bucket["hire_gold_spent"] += plan.hire_gold_spent
                            bucket["guild_ids"].add(state.id)
                            bucket["roster_slots"] += len(json.loads(plan.roster_snapshot_json))
                            bucket["roster_observations"] += 1
                            regional = by_region.setdefault(state.region_code, {
                                "planned": 0, "eligible": 0, "started": 0, "resolved": 0,
                                "successes": 0, "failures": 0, "hires": 0,
                                "hire_gold_spent": 0,
                            })
                            for metric, value in (
                                ("planned", plan.planned_actions), ("eligible", plan.eligible_actions),
                                ("started", plan.started_actions), ("resolved", plan.resolved_actions),
                                ("successes", plan.successes), ("failures", plan.failures),
                                ("hires", plan.hired_count), ("hire_gold_spent", plan.hire_gold_spent),
                            ):
                                regional[metric] += value or 0
                            guild_metrics = by_guild.setdefault(f"{state.region_code}:{state.slot}", {
                                "name": state.name, "profile": state.profile, "archetype": state.archetype,
                                "planned": 0, "eligible": 0, "started": 0, "resolved": 0,
                                "successes": 0, "failures": 0, "hires": 0,
                                "hire_gold_spent": 0, "gold_earned": 0, "xp_earned": 0,
                            })
                            for metric, value in (
                                ("planned", plan.planned_actions), ("eligible", plan.eligible_actions),
                                ("started", plan.started_actions), ("resolved", plan.resolved_actions),
                                ("successes", plan.successes), ("failures", plan.failures),
                                ("hires", plan.hired_count), ("hire_gold_spent", plan.hire_gold_spent),
                                ("gold_earned", plan.gold_earned), ("xp_earned", plan.xp_earned),
                            ):
                                guild_metrics[metric] += value or 0
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
                            "regions": by_region,
                            "guilds": by_guild,
                        }
                        self.assertGreater(actions, 0)
                        self.assertGreaterEqual(successes, 0)
                        self.assertLessEqual(successes, actions)
                        self.assertEqual(set(by_profile), {"strong", "medium", "new"})
                        self.assertGreater(by_profile["strong"]["success_rate"], 0)
                        self.assertGreater(by_profile["medium"]["success_rate"], 0)
                        self.assertGreater(by_profile["new"]["success_rate"], 0)

                    all_plans = list(db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                    )))
                    pending_portal_activities = list(db.scalars(select(RegionalEventActivity).join(
                        RegionalEvent, RegionalEvent.id == RegionalEventActivity.event_id,
                    ).where(
                        RegionalEventActivity.source_type == "cpu_portal",
                        RegionalEventActivity.status == "in_progress",
                        RegionalEvent.campaign_id == first.campaign_id,
                    )))
                    pending_by_plan = {row.source_run_id: row for row in pending_portal_activities}
                    self.assertTrue(all(
                        regional_cycle_service._utc(row.due_at_utc) > regional_cycle_service._utc(now)
                        for row in pending_portal_activities
                    ), "an overdue CPU portal activity must be resolved during catch-up")
                    self.assertEqual(db.execute(
                        select(RegionalEventActivity.event_id, RegionalEventActivity.guild_state_id)
                        .join(RegionalEvent, RegionalEvent.id == RegionalEventActivity.event_id)
                        .where(
                            RegionalEvent.campaign_id == first.campaign_id,
                            RegionalEventActivity.source_type == "cpu_portal",
                            RegionalEventActivity.status.in_(("in_progress", "resolved")),
                        )
                        .group_by(RegionalEventActivity.event_id, RegionalEventActivity.guild_state_id)
                        .having(func.count(RegionalEventActivity.id) > 1)
                    ).all(), [], "a guild can have at most one started or resolved entry per event")
                    plans_by_id = {plan.id: plan for plan in all_plans}
                    for plan in all_plans:
                        decisions = json.loads(plan.decisions_json or "[]")
                        outcomes = json.loads(plan.outcomes_json or "[]")
                        self.assertEqual(len(decisions), plan.actions)
                        self.assertEqual(len(outcomes), plan.resolved_actions)
                        self.assertLessEqual(plan.resolved_actions, plan.started_actions)
                        self.assertEqual(
                            plan.resolved_actions + int(plan.id in pending_by_plan),
                            plan.started_actions,
                        )
                        portal_outcomes = [row for row in outcomes if row.get("event_id") is not None]
                        self.assertLessEqual(len(portal_outcomes), 1)

                    resolved_portal_activities = list(db.scalars(select(RegionalEventActivity).join(
                        RegionalEvent, RegionalEvent.id == RegionalEventActivity.event_id,
                    ).where(
                        RegionalEventActivity.source_type == "cpu_portal",
                        RegionalEventActivity.status == "resolved",
                        RegionalEvent.campaign_id == first.campaign_id,
                    )))
                    for activity in resolved_portal_activities:
                        plan = plans_by_id[activity.source_run_id]
                        event_outcomes = [row for row in json.loads(plan.outcomes_json or "[]")
                                          if row.get("event_id") == activity.event_id]
                        self.assertEqual(len(event_outcomes), 1)
                        self.assertEqual(
                            event_outcomes[0]["success"],
                            bool(activity.successes),
                        )

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
                    self.assertTrue(all(
                        0 <= offer.cpu_failure_risk_snapshot <= regional_cycle_service.CPU_FAILURE_RISK_CAP_PP
                        for offer in all_regional_offers
                    ))
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
                            if decision.get("offer_type") == "portal":
                                continue
                            bucket = by_rank[decision["rank"]]
                            result = outcome_by_offer[decision["offer_id"]]
                            bucket["cpu_actions"] += 1
                            bucket["cpu_successes"] += int(result["success"])
                            bucket["expected_chance_points"] += decision.get(
                                "chance", decision.get("success_chance", 0),
                            )
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
                                ordered_groups = sorted(groups, key=lambda row: row["slot"])
                                if ordered_groups:
                                    rotation = cycle_number % len(ordered_groups)
                                    ordered_groups = ordered_groups[rotation:] + ordered_groups[:rotation]
                                for group in ordered_groups:
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
                        recommended_band = regional_cycle_service._contract_recommended_level_band(guild_level)
                        if recommended_band is None:
                            challenge_ceiling = max(20, guild_level, roster_level)
                            self.assertTrue(all(row.recommended_level <= challenge_ceiling for row in pool))
                        else:
                            minimum_recommended, maximum_recommended = recommended_band
                            challenge_ceiling = maximum_recommended
                            self.assertTrue(all(
                                minimum_recommended <= row.recommended_level <= maximum_recommended
                                for row in pool
                            ))
                        self.assertTrue(pool)
                        self.assertLessEqual(max(row.required_min_mercenary_level for row in pool), challenge_ceiling)
                        candidate_pool_metrics[stage_name] = {
                            "guild_level": guild_level,
                            "roster_level": roster_level,
                            "recommended_band": list(recommended_band) if recommended_band else None,
                            "legacy_100_plus_ceiling": challenge_ceiling if recommended_band is None else None,
                            "templates": len(pool),
                            "max_recommended_level": max(row.recommended_level for row in pool),
                            "max_required_mercenary_level": max(row.required_min_mercenary_level for row in pool),
                        }
                    guild_only_pool = regional_cycle_service._contract_candidates(db, 50, 50)
                    self.assertTrue(all(45 <= row.recommended_level <= 60 for row in guild_only_pool))
                    candidate_pool_metrics["guild_50_roster_50"] = {
                        "guild_level": 50,
                        "roster_level": 50,
                        "recommended_band": [45, 60],
                        "templates": len(guild_only_pool),
                        "max_recommended_level": max(row.recommended_level for row in guild_only_pool),
                        "max_required_mercenary_level": max(
                            row.required_min_mercenary_level for row in guild_only_pool
                        ),
                    }
                    guild_100_pool = regional_cycle_service._contract_candidates(db, 100, 350)
                    self.assertTrue(guild_100_pool)
                    self.assertLessEqual(max(row.recommended_level for row in guild_100_pool), 350)
                    self.assertLessEqual(max(row.required_min_mercenary_level for row in guild_100_pool), 350)
                    candidate_pool_metrics["guild_100_roster_350_legacy_rule"] = {
                        "guild_level": 100,
                        "roster_level": 350,
                        "recommended_band": None,
                        "legacy_100_plus_ceiling": 350,
                        "templates": len(guild_100_pool),
                        "max_recommended_level": max(row.recommended_level for row in guild_100_pool),
                        "max_required_mercenary_level": max(row.required_min_mercenary_level for row in guild_100_pool),
                    }
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
                        self.assertGreater(
                            contracts_at_stage["S"]["avg_level"], contracts_at_stage["E"]["avg_level"],
                        )
                    self.assertTrue(early_s_levels)
                    self.assertTrue(all(1 <= level <= 10 for level in early_s_levels))
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
                        self.assertGreaterEqual(row.security, 0)
                        self.assertLessEqual(row.security, 100)
                        self.assertGreaterEqual(row.threat, 0)
                        self.assertLessEqual(row.threat, 100)
                        final_snapshot = db.scalar(select(RegionalCycleRegion).join(
                            RegionalCycle, RegionalCycle.id == RegionalCycleRegion.cycle_id,
                        ).where(
                            RegionalCycleRegion.campaign_id == first.campaign_id,
                            RegionalCycleRegion.region_code == row.region_code,
                            RegionalCycle.cycle_number == 99,
                        ))
                        self.assertAlmostEqual(row.security, final_snapshot.security_after)
                        self.assertAlmostEqual(row.threat, final_snapshot.threat_after)
                    rebellion_candidates = [
                        row["first_rebellion_eligible_cycle"]
                        for row in candidate_cpu_pressure.values()
                        if row["first_rebellion_eligible_cycle"] is not None
                    ]
                    event_history = list(db.scalars(select(regional_cycle_service.RegionalEvent).where(
                        regional_cycle_service.RegionalEvent.campaign_id == first.campaign_id,
                        regional_cycle_service.RegionalEvent.trigger_cycle_number < 100,
                    )))
                    active_rebellions = [event for event in event_history
                                         if event.event_type == "rebellion"
                                         and event.status in {"active", "in_progress"}]
                    self.assertLessEqual(len(active_rebellions), 1)
                    events_by_horizon = {}
                    for horizon in (10, 50, 100):
                        counts = {}
                        for event in event_history:
                            if event.trigger_cycle_number >= horizon:
                                continue
                            key = f"{event.event_type}:{event.status}"
                            counts[key] = counts.get(key, 0) + 1
                        events_by_horizon[horizon] = counts
                    ranking = []
                    for position, state in enumerate(sorted(
                        guild_states,
                        key=lambda row: (
                            -(row.influence * 0.50 + row.reputation * 0.25
                              + min(100, row.event_wins * 10) * 0.25),
                            row.name.casefold(),
                        ),
                    ), start=1):
                        ranking.append({
                            "position": position, "region": state.region_code, "slot": state.slot,
                            "name": state.name, "profile": state.profile,
                            "score": round(state.influence * 0.50 + state.reputation * 0.25
                                           + min(100, state.event_wins * 10) * 0.25, 2),
                        })
                    home_code = next(code for code, name in regional_cycle_service.REGIONS
                                     if name == campaign.home_region)
                    all_cpu_plans = list(db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                    )))
                    plan_cycle = {plan.id: db.get(RegionalCycle, plan.cycle_id).cycle_number
                                  for plan in all_cpu_plans}
                    phase_progression = {}
                    for phase, first_cycle, after_cycle in (
                        ("vigílias_1_3", 0, 3), ("vigílias_4_20", 3, 20),
                        ("vigílias_21_50", 20, 50), ("vigílias_51_100", 50, 100),
                    ):
                        phase_plans = [plan for plan in all_cpu_plans
                                       if first_cycle <= plan_cycle[plan.id] < after_cycle]
                        phases = {}
                        for plan in phase_plans:
                            state = db.get(RegionalGuildState, plan.guild_state_id)
                            bucket = phases.setdefault(state.profile, {
                                "actions": 0, "successes": 0, "failures": 0,
                                "hires": 0, "roster_size_sum": 0, "roster_observations": 0,
                            })
                            bucket["actions"] += plan.resolved_actions or 0
                            bucket["successes"] += plan.successes
                            bucket["failures"] += plan.failures
                            bucket["hires"] += plan.hired_count
                            bucket["roster_size_sum"] += len(json.loads(plan.roster_snapshot_json))
                            bucket["roster_observations"] += 1
                        for bucket in phases.values():
                            bucket["avg_roster_size"] = round(
                                bucket.pop("roster_size_sum") / max(1, bucket.pop("roster_observations")), 2,
                            )
                        home_actions = sum(
                            plan.resolved_actions or 0
                            for plan in phase_plans
                            if db.get(RegionalGuildState, plan.guild_state_id).region_code == home_code
                        )
                        opened_crises = sum(
                            1 for event in event_history
                            if first_cycle <= event.trigger_cycle_number < after_cycle
                            and event.status not in {"not_triggered", "suppressed"}
                        )
                        phase_progression[phase] = {
                            "cycles": after_cycle - first_cycle,
                            "cpu_actions_per_cycle_global": round(
                                sum(plan.resolved_actions or 0 for plan in phase_plans)
                                / max(1, after_cycle - first_cycle), 2,
                            ),
                            "cpu_actions_per_cycle_home_region": round(
                                home_actions / max(1, after_cycle - first_cycle), 2,
                            ),
                            "profiles": phases,
                            "opened_crises": opened_crises,
                        }
                    legacy_baseline_by_region = {}
                    for state in guild_states:
                        if state.guild_id is not None or state.profile == "player" or not state.active:
                            continue
                        probability = regional_cycle_service.regional_cpu_action_probability(
                            first.campaign_id, state, "vigilia-v4",
                        )
                        expected_actions = 1.0 + (probability if state.profile == "strong" else 0.0)
                        legacy_baseline_by_region[state.region_code] = (
                            legacy_baseline_by_region.get(state.region_code, 0.0) + expected_actions
                        )
                    first_strong_hire_cycle = min(
                        (plan_cycle[plan.id] for plan in all_cpu_plans
                         if db.get(RegionalGuildState, plan.guild_state_id).profile == "strong"
                         and plan.hired_count > 0),
                        default=None,
                    )
                    print("REGIONAL_SIMULATION_METRICS=" + json.dumps({
                        "cycles": summaries,
                        "phase_progression_1_100": phase_progression,
                        "legacy_vigilias_v4_baseline": {
                            "global_expected_actions_per_cycle": round(sum(legacy_baseline_by_region.values()), 2),
                            "home_region_expected_actions_per_cycle": round(
                                legacy_baseline_by_region.get(home_code, 0.0), 2,
                            ),
                            "region_actions_per_cycle": legacy_baseline_by_region,
                        },
                        "first_strong_hire_cycle_zero_based": first_strong_hire_cycle,
                        "events_by_horizon": events_by_horizon,
                        "ranking_after_100_cycles": ranking,
                        "cpu_roster_cap_projection": {
                            profile: {
                                f"level_{level}": regional_cycle_service.cpu_roster_cap(
                                    RegionalGuildState(
                                        profile=profile, region_code=regional_cycle_service.REGIONS[0][0],
                                        level=level,
                                    ),
                                    1,
                                )
                                for level in (
                                    int(cpu_initial_profile_values(profile, 1)["guild_level"]), 50, 100,
                                )
                            }
                            for profile in ("strong", "medium", "new")
                        },
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

                    for plan in db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                    )):
                        busy_until = {}
                        for decision in sorted(
                            json.loads(plan.decisions_json),
                            key=lambda item: item["started_at_utc"],
                        ):
                            start_at = regional_cycle_service._utc(
                                regional_cycle_service.datetime.fromisoformat(decision["started_at_utc"]),
                            )
                            player_priority_ends_at = regional_cycle_service._utc(
                                regional_cycle_service.datetime.fromisoformat(
                                    decision["player_priority_ends_at_utc"],
                                ),
                            )
                            end_at = regional_cycle_service._utc(
                                regional_cycle_service.datetime.fromisoformat(decision["resolved_at_utc"]),
                            )
                            self.assertGreaterEqual(start_at, player_priority_ends_at)
                            self.assertEqual(
                                (end_at - start_at).total_seconds(), decision["duration_seconds"],
                            )
                            for slot in decision["mercenary_slots"]:
                                self.assertLessEqual(busy_until.get(slot, start_at), start_at)
                                busy_until[slot] = end_at
                            if decision["offer_type"] == "portal":
                                event = db.get(regional_cycle_service.RegionalEvent, decision["event_id"])
                                self.assertIsNotNone(event)
                                self.assertLess(start_at, regional_cycle_service._utc(event.expires_at_utc))
                                self.assertLessEqual(len(decision["mercenary_slots"]), 5)
                            else:
                                offer = offer_by_id[decision["offer_id"]]
                                self.assertEqual(offer.status, "cpu_completed")

                    for region_cycle in db.scalars(select(RegionalCycleRegion).where(
                        RegionalCycleRegion.campaign_id == first.campaign_id,
                    )):
                        activity = json.loads(region_cycle.summary_json)["cpu_activity"]
                        pressure = json.loads(region_cycle.summary_json)["gradual_pressure"]
                        self.assertEqual(
                            activity["started"],
                            activity["resolved"] + activity["pending"],
                        )
                        self.assertGreaterEqual(activity["pending"], 0)
                        self.assertLessEqual(activity["started"], activity["eligible"])
                        self.assertLessEqual(activity["eligible"], activity["planned"])
                        self.assertGreater(activity["started"], 0)
                        if pressure["targeted"]:
                            self.assertGreaterEqual(
                                region_cycle.security_after,
                                regional_cycle_service.REGIONAL_ACTIVE_SECURITY_FLOOR,
                            )
                    previous_pressure_target = None
                    pressure_window = regional_cycle_service.REGIONAL_PRESSURE_WINDOW_CYCLES
                    for cycle_number in range(100):
                        pressure_cycle = db.scalar(select(RegionalCycle).where(
                            RegionalCycle.campaign_id == first.campaign_id,
                            RegionalCycle.cycle_number == cycle_number,
                        ))
                        pressure_rows = list(db.scalars(select(RegionalCycleRegion).where(
                            RegionalCycleRegion.cycle_id == pressure_cycle.id,
                        )))
                        target_regions = {
                            json.loads(row.summary_json)["gradual_pressure"]["target_region"]
                            for row in pressure_rows
                        }
                        self.assertEqual(len(target_regions), 1)
                        pressure_target = next(iter(target_regions))
                        if cycle_number % pressure_window:
                            self.assertEqual(pressure_target, previous_pressure_target)
                        elif previous_pressure_target is not None:
                            self.assertNotEqual(pressure_target, previous_pressure_target)
                        previous_pressure_target = pressure_target
                        targets = [
                            row.region_code for row in pressure_rows
                            if json.loads(row.summary_json)["gradual_pressure"]["targeted"]
                        ]
                        self.assertLessEqual(len(targets), 1)
                        simultaneously_vulnerable = sum(
                            row.threat_after >= 85 and row.security_after <= 25
                            for row in pressure_rows
                        )
                        self.assertLessEqual(simultaneously_vulnerable, 1)
                    strong_ids = set(db.scalars(select(RegionalGuildState.id).where(
                        RegionalGuildState.campaign_id == first.campaign_id,
                        RegionalGuildState.profile == "strong",
                    )))
                    first_strong_hire = db.scalar(
                        select(func.min(RegionalCycle.cycle_number))
                        .join(RegionalCpuCyclePlan, RegionalCpuCyclePlan.cycle_id == RegionalCycle.id)
                        .where(
                            RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                            RegionalCpuCyclePlan.guild_state_id.in_(strong_ids),
                            RegionalCpuCyclePlan.hired_count > 0,
                        )
                    )
                    self.assertIn(first_strong_hire, {2, 3})

                    home_code = next(
                        code for code, name in regional_cycle_service.REGIONS
                        if name == campaign.home_region
                    )
                    max_cpu_completed_in_home_cycle = 0
                    for cycle_number in range(100):
                        home_board = [offer for offer in all_regional_offers
                                      if offer.region_code == home_code
                                      and offer.cycle_number == cycle_number]
                        self.assertEqual(len(home_board), 14)
                        max_cpu_completed_in_home_cycle = max(
                            max_cpu_completed_in_home_cycle,
                            sum(offer.status == "cpu_completed" for offer in home_board),
                        )
                    self.assertGreater(max_cpu_completed_in_home_cycle, 8)

                    regular_cpu_actions = sum(
                        decision["offer_type"] != "portal"
                        for plan in db.scalars(select(RegionalCpuCyclePlan).where(
                            RegionalCpuCyclePlan.campaign_id == first.campaign_id,
                        ))
                        for decision in json.loads(plan.decisions_json)
                    )
                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.campaign_id == first.campaign_id,
                        RegionalOffer.status == "cpu_completed",
                    )), regular_cpu_actions)

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
                    self.assertTrue(all(len(snapshots) == 61 for snapshots in per_region.values()))
                    for cycle_number in range(61):
                        cycle_snapshots = [
                            row for snapshots in per_region.values() for row in snapshots
                            if row.cycle_id == db.scalar(select(RegionalCycle.id).where(
                                RegionalCycle.campaign_id == second.campaign_id,
                                RegionalCycle.cycle_number == cycle_number,
                            ))
                        ]
                        target_regions = {
                            json.loads(row.summary_json)["gradual_pressure"]["target_region"]
                            for row in cycle_snapshots
                        }
                        self.assertEqual(len(target_regions), 1)
                        self.assertLessEqual(
                            sum(row.threat_after >= 85 and row.security_after <= 25
                                for row in cycle_snapshots),
                            1,
                        )
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
                    with patch.object(regional_cycle_service, "_cpu_offer_party", return_value=None):
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
                        # Baseline, gradual pressure and calm remain separate ledger entries.
                        first_security_pressure = first_summary["gradual_pressure"]["security_applied"]
                        self.assertAlmostEqual(
                            first_snapshot.security_after,
                            first_snapshot.security_before - 1 - first_security_pressure + 0.25,
                        )
                        self.assertAlmostEqual(
                            first_snapshot.threat_after,
                            first_snapshot.threat_before + 1 + first_summary["gradual_pressure"]["threat_applied"] - 0.25,
                        )

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
                        expired_security_pressure = expired_summary["gradual_pressure"]["security_applied"]
                        self.assertAlmostEqual(
                            expired_snapshot.security_after,
                            expired_snapshot.security_before - 1 - expired_security_pressure,
                        )
                        self.assertAlmostEqual(
                            expired_snapshot.threat_after,
                            expired_snapshot.threat_before + 1 + expired_summary["gradual_pressure"]["threat_applied"],
                        )
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
                    completed_public_offers = db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.cycle_id == cycle_zero.id,
                        RegionalOffer.status == "cpu_completed",
                    ))
                    cycle_plans = list(db.scalars(select(RegionalCpuCyclePlan).where(
                        RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    )))
                    internal_actions = sum(
                        bool(decision.get("internal_contract"))
                        for plan in cycle_plans
                        for decision in json.loads(plan.decisions_json or "[]")
                        if isinstance(decision, dict)
                    )
                    # The cycle-start region preflight found public work for every
                    # active CPU cohort in this retry fixture; exhaustion later in
                    # the sequential plans must not create a retroactive fallback.
                    self.assertEqual(internal_actions, 0)
                    self.assertEqual(
                        db.scalar(select(func.sum(RegionalCpuCyclePlan.actions)).where(
                            RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                        )) - internal_actions,
                        completed_public_offers,
                    )
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
                        rank="A",
                        name_snapshot=template.name,
                        description_snapshot=template.description,
                        level_band_snapshot="1-20",
                        recommended_level_snapshot=1,
                        recommended_power_snapshot=1,
                        min_party_size_snapshot=1,
                        max_party_size_snapshot=1,
                        required_guild_level_snapshot=1,
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
                    template.min_party_size = 2
                    template.max_party_size = 3
                    template.required_guild_level = 99
                    template.required_min_mercenary_level = 99
                    offer.required_min_mercenary_level_snapshot = 99
                    run = start_mission(
                        db, guild, str(template.id), [str(mercenary.id)], commit=False,
                        regional_duration_seconds=offer.duration_seconds_snapshot,
                        regional_party_bounds=(offer.min_party_size_snapshot, offer.max_party_size_snapshot),
                        regional_required_guild_level=offer.required_guild_level_snapshot,
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
                    self.assertEqual(resources.crystals, 1)
                    self.assertEqual(resources.crystal_reserve, 1)
                    self.assertIn("Cristais x1", json.loads(resolved.result_details)["items"])
                    result = db.scalar(select(RegionalRunOutcome).where(
                        RegionalRunOutcome.source_run_id == run.id,
                    ))
                    self.assertEqual(result.rank, "A")
                    self.assertEqual(result.gold_earned, 321)
                    self.assertEqual(result.xp_earned, resolved.xp_reward)
                    self.assertEqual(offer.status, "completed")
                    region = db.scalar(select(regional_cycle_service.RegionalRegionState).where(
                        regional_cycle_service.RegionalRegionState.campaign_id == info.campaign_id,
                        regional_cycle_service.RegionalRegionState.region_code == home_code,
                    ))
                    self.assertAlmostEqual(region.security, 50.12)
                    self.assertAlmostEqual(region.threat, 24.88)

                    failed_offer = RegionalOffer(
                        campaign_id=info.campaign_id,
                        cycle_id=active_cycle.id,
                        cycle_number=active_cycle.cycle_number,
                        region_code=home_code,
                        offer_type="contract",
                        slot=12,
                        mission_template_id=template.id,
                        rank="A",
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
                        regional_party_bounds=(failed_offer.min_party_size_snapshot, failed_offer.max_party_size_snapshot),
                        regional_required_guild_level=failed_offer.required_guild_level_snapshot,
                    )
                    failed_run.regional_offer_id = failed_offer.id
                    failed_run.rank_snapshot = failed_offer.rank
                    failed_run.ends_at = failed_run.started_at - timedelta(seconds=1)
                    db.flush()
                    with patch("app.services.mission_service.randint", return_value=100):
                        failed_result = claim_mission_loot(db, guild, resources, failed_run.id)
                    self.assertFalse(failed_result.success)
                    self.assertEqual(resources.crystals, 1)
                    self.assertEqual(resources.crystal_reserve, 1)
                    self.assertAlmostEqual(region.security, 50.0)
                    self.assertAlmostEqual(region.threat, 25.0)

                    low_rank_offer = RegionalOffer(
                        campaign_id=info.campaign_id,
                        cycle_id=active_cycle.id,
                        cycle_number=active_cycle.cycle_number,
                        region_code=home_code,
                        offer_type="contract",
                        slot=13,
                        mission_template_id=template.id,
                        rank="C",
                        name_snapshot=template.name,
                        description_snapshot=template.description,
                        level_band_snapshot="1-20",
                        recommended_level_snapshot=1,
                        recommended_power_snapshot=1,
                        min_party_size_snapshot=1,
                        max_party_size_snapshot=1,
                        required_guild_level_snapshot=1,
                        duration_seconds_snapshot=5400,
                        gold_reward_snapshot=321,
                        xp_reward_snapshot=123,
                        success_chance_snapshot=95,
                        status="in_progress",
                        reserved_by_guild_state_id=player_state.id,
                    )
                    db.add(low_rank_offer)
                    db.flush()
                    low_rank_run = start_mission(
                        db, guild, str(template.id), [str(mercenary.id)], commit=False,
                        regional_duration_seconds=low_rank_offer.duration_seconds_snapshot,
                        regional_party_bounds=(low_rank_offer.min_party_size_snapshot, low_rank_offer.max_party_size_snapshot),
                        regional_required_guild_level=low_rank_offer.required_guild_level_snapshot,
                    )
                    low_rank_run.regional_offer_id = low_rank_offer.id
                    low_rank_run.rank_snapshot = low_rank_offer.rank
                    low_rank_run.ends_at = low_rank_run.started_at - timedelta(seconds=1)
                    db.flush()
                    with patch("app.services.mission_service.randint", return_value=1):
                        low_rank_result = claim_mission_loot(db, guild, resources, low_rank_run.id)
                    self.assertTrue(low_rank_result.success)
                    self.assertEqual(resources.crystals, 1)
                    self.assertEqual(resources.crystal_reserve, 1)
                    self.assertAlmostEqual(region.security, 50.08)
                    self.assertAlmostEqual(region.threat, 24.92)
                    self.assertEqual(regional_cycle_service.REGION_BASELINE_PRESSURE, 1)
                    with patch.object(regional_cycle_service, "_cpu_offer_party", return_value=None):
                        advance_regional_world(
                            db, campaign, guild, campaign.created_at_utc + timedelta(seconds=CYCLE_SECONDS),
                        )
                    cycle_summary = db.scalar(select(RegionalCycleRegion).where(
                        RegionalCycleRegion.cycle_id == active_cycle.id,
                        RegionalCycleRegion.region_code == home_code,
                    ))
                    summary = json.loads(cycle_summary.summary_json)
                    self.assertFalse(summary["baseline"]["applied"])
                    self.assertEqual(summary["player_actions"], 3)
                    self.assertEqual(summary["player_successes"], 2)
                    self.assertEqual(summary["player_failures"], 1)
                    self.assertAlmostEqual(cycle_summary.security_before, 50)
                    self.assertTrue(summary["rival_calm"]["active"])
                    self.assertTrue(summary["rival_calm"]["applied"])
                    self.assertAlmostEqual(summary["rival_calm"]["security"], 0.25)
                    gradual_threat_pressure = summary["gradual_pressure"]["threat_applied"]
                    gradual_security_pressure = summary["gradual_pressure"]["security_applied"]
                    self.assertAlmostEqual(cycle_summary.security_after, 50.33 - gradual_security_pressure)
                    self.assertAlmostEqual(cycle_summary.threat_before, 25)
                    self.assertAlmostEqual(cycle_summary.threat_after, 24.67 + gradual_threat_pressure)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()


if __name__ == "__main__":
    unittest.main()
