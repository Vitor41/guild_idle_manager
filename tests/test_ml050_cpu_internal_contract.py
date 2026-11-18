import gc
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.database.connection import SessionLocal, configure_database
from app.models.campaign import CampaignMetadata
from app.models.regional import (
    RegionalCpuMercenary,
    RegionalCycle,
    RegionalEvent,
    RegionalEventActivity,
    RegionalEventParticipant,
    RegionalGuildState,
    RegionalOffer,
    RegionalRegionState,
)
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.services import regional_cycle_service
from app.services.regional_cycle_service import advance_regional_world, get_regional_board
from app.services.regional_event_service import record_cpu_event_activity


class CpuInternalContractTests(unittest.TestCase):
    def test_weakest_blocked_cpu_selects_shared_contract_before_strong_cpu_plans(self):
        campaigns = None
        info = None
        with tempfile.TemporaryDirectory(
            prefix="ml050-cpu-internal-", dir=Path(__file__).resolve().parents[1],
        ) as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Contingência CPU", "Guilda Contingência")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    start = campaign.created_at_utc
                    cycle = advance_regional_world(db, campaign, guild, start)
                    home_code = next(
                        code for code, name in regional_cycle_service.REGIONS
                        if name == campaign.home_region
                    )
                    region = db.scalar(select(RegionalRegionState).where(
                        RegionalRegionState.campaign_id == info.campaign_id,
                        RegionalRegionState.region_code == home_code,
                    ))
                    cpu_states = list(db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.region_code == home_code,
                        RegionalGuildState.guild_id.is_(None),
                    ).order_by(RegionalGuildState.id)))
                    strong_cpu = next(state for state in cpu_states if state.profile == "strong")
                    weak_cpu = next(state for state in cpu_states if state.profile == "new")
                    strong_cpu.level = 30
                    weak_cpu.level = 1
                    for state in cpu_states:
                        state.active = state.id in {strong_cpu.id, weak_cpu.id}
                    db.flush()
                    for offer in db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type.in_(regional_cycle_service.PUBLIC_REGIONAL_OFFER_TYPES),
                    )):
                        offer.required_guild_level_snapshot = 999
                    db.flush()

                    strong_cpu_id, weak_cpu_id = strong_cpu.id, weak_cpu.id
                    retry_point = db.begin_nested()
                    prepared_starts = regional_cycle_service._prepare_cpu_region_cycle_start(
                        db, info.campaign_id, cycle, region, [strong_cpu, weak_cpu],
                    )
                    first_internal = db.scalar(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type == "cpu_internal",
                    ))
                    self.assertIsNotNone(first_internal)
                    self.assertEqual(first_internal.required_guild_level_snapshot, 1)
                    first_plan = regional_cycle_service._cpu_plan_for_guild_v6(
                        db, info.campaign_id, cycle, region, strong_cpu,
                        prepared_start=prepared_starts[strong_cpu.id],
                    )[0]
                    first_decisions = json.loads(first_plan.decisions_json)
                    self.assertEqual(len(first_decisions), 1, first_decisions)
                    self.assertTrue(first_decisions[0].get("internal_contract"), first_decisions)
                    first_snapshot_signature = (
                        first_internal.status,
                        first_internal.mission_template_id,
                        first_internal.name_snapshot,
                        first_internal.rank,
                        first_internal.duration_seconds_snapshot,
                        first_internal.gold_reward_snapshot,
                        first_internal.xp_reward_snapshot,
                    )
                    first_decision_signature = {
                        key: value for key, value in first_decisions[0].items()
                        if key != "offer_id"
                    }
                    weak_plan = regional_cycle_service._cpu_plan_for_guild_v6(
                        db, info.campaign_id, cycle, region, weak_cpu,
                        prepared_start=prepared_starts[weak_cpu.id],
                    )[0]
                    weak_decisions = json.loads(weak_plan.decisions_json)
                    self.assertEqual(len(weak_decisions), 1, weak_decisions)
                    self.assertTrue(weak_decisions[0].get("internal_contract"), weak_decisions)
                    self.assertNotEqual(first_decisions[0]["offer_id"], weak_decisions[0]["offer_id"])
                    retry_point.rollback()
                    db.expunge_all()

                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == info.campaign_id,
                        RegionalCycle.cycle_number == 0,
                    ))
                    region = db.scalar(select(RegionalRegionState).where(
                        RegionalRegionState.campaign_id == info.campaign_id,
                        RegionalRegionState.region_code == home_code,
                    ))
                    strong_cpu = db.get(RegionalGuildState, strong_cpu_id)
                    weak_cpu = db.get(RegionalGuildState, weak_cpu_id)
                    cpu_states = [strong_cpu, weak_cpu]
                    prepared_starts = regional_cycle_service._prepare_cpu_region_cycle_start(
                        db, info.campaign_id, cycle, region, cpu_states,
                    )
                    replay_plan = regional_cycle_service._cpu_plan_for_guild_v6(
                        db, info.campaign_id, cycle, region, strong_cpu,
                        prepared_start=prepared_starts[strong_cpu.id],
                    )[0]
                    replay_decisions = json.loads(replay_plan.decisions_json)
                    self.assertEqual(len(replay_decisions), 1, replay_decisions)
                    self.assertEqual(
                        {key: value for key, value in replay_decisions[0].items() if key != "offer_id"},
                        first_decision_signature,
                    )
                    stored = db.scalar(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type == "cpu_internal",
                    ))
                    self.assertEqual(
                        (
                            stored.status,
                            stored.mission_template_id,
                            stored.name_snapshot,
                            stored.rank,
                            stored.duration_seconds_snapshot,
                            stored.gold_reward_snapshot,
                            stored.xp_reward_snapshot,
                        ),
                        first_snapshot_signature,
                    )
                    persisted_snapshot = (
                        stored.status,
                        stored.mission_template_id,
                        stored.name_snapshot,
                        stored.rank,
                        stored.duration_seconds_snapshot,
                        stored.gold_reward_snapshot,
                        stored.xp_reward_snapshot,
                        stored.reserved_by_guild_state_id,
                        stored.claimed_at_utc,
                        stored.resolved_at_utc,
                    )
                    self.assertEqual(stored.status, "cpu_internal")
                    self.assertIsNone(stored.reserved_by_guild_state_id)

                    second_plan = regional_cycle_service._cpu_plan_for_guild_v6(
                        db, info.campaign_id, cycle, region, weak_cpu,
                        prepared_start=prepared_starts[weak_cpu.id],
                    )[0]
                    second_decisions = json.loads(second_plan.decisions_json)
                    self.assertEqual(len(second_decisions), 1, second_decisions)
                    self.assertTrue(second_decisions[0].get("internal_contract"), second_decisions)
                    self.assertNotEqual(replay_decisions[0]["offer_id"], second_decisions[0]["offer_id"])
                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type == "cpu_internal",
                    )), 1)

                    board = get_regional_board(db, campaign, guild, start)
                    self.assertNotIn("cpu_internal", board["offers"])
                    self.assertEqual(
                        persisted_snapshot,
                        (
                            stored.status,
                            stored.mission_template_id,
                            stored.name_snapshot,
                            stored.rank,
                            stored.duration_seconds_snapshot,
                            stored.gold_reward_snapshot,
                            stored.xp_reward_snapshot,
                            stored.reserved_by_guild_state_id,
                            stored.claimed_at_utc,
                            stored.resolved_at_utc,
                        ),
                    )
            finally:
                if campaigns is not None and info is not None:
                    campaigns.close_active_campaign(info.campaign_id)
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_public_viability_at_planner_start_prevents_later_internal_fallback(self):
        campaigns = None
        info = None
        with tempfile.TemporaryDirectory(
            prefix="ml050-cpu-public-cutoff-", dir=Path(__file__).resolve().parents[1],
        ) as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Corte público CPU", "Guilda Corte")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    cycle = advance_regional_world(db, campaign, guild, campaign.created_at_utc)
                    home_code = next(
                        code for code, name in regional_cycle_service.REGIONS
                        if name == campaign.home_region
                    )
                    region = db.scalar(select(RegionalRegionState).where(
                        RegionalRegionState.campaign_id == info.campaign_id,
                        RegionalRegionState.region_code == home_code,
                    ))
                    strong_cpu = db.scalar(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.region_code == home_code,
                        RegionalGuildState.guild_id.is_(None),
                        RegionalGuildState.profile == "strong",
                    ))
                    other_cpus = list(db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.region_code == home_code,
                        RegionalGuildState.guild_id.is_(None),
                    )))
                    for state in other_cpus:
                        state.active = state.id == strong_cpu.id
                    offers = list(db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type.in_(regional_cycle_service.PUBLIC_REGIONAL_OFFER_TYPES),
                    ).order_by(RegionalOffer.id)))
                    for offer in offers:
                        offer.required_guild_level_snapshot = 999
                    public_offer = next(offer for offer in offers if offer.offer_type == "contract")
                    public_offer.required_guild_level_snapshot = 1
                    public_offer.duration_seconds_snapshot = 60
                    public_offer.recommended_power_snapshot = 1
                    public_offer.required_total_power_snapshot = 0
                    public_offer.required_class_code_snapshot = None
                    public_offer.required_tank_count_snapshot = 0
                    public_offer.required_support_count_snapshot = 0
                    public_offer.required_damage_count_snapshot = 0
                    public_offer.required_equipment_tier_snapshot = 0
                    public_offer.min_party_size_snapshot = 1
                    public_offer.max_party_size_snapshot = 1
                    db.flush()

                    prepared_starts = regional_cycle_service._prepare_cpu_region_cycle_start(
                        db, info.campaign_id, cycle, region, [strong_cpu],
                    )
                    prepared_start = prepared_starts[strong_cpu.id]
                    roster = prepared_start["roster"]
                    self.assertTrue(roster, "A fixture precisa de uma equipe CPU ativa.")
                    self.assertEqual(public_offer.status, "available")
                    cycle_start = regional_cycle_service._utc(cycle.starts_at_utc)
                    busy_until = {
                        member.id: cycle_start + timedelta(hours=1)
                        for member in roster
                    }
                    self.assertIsNotNone(regional_cycle_service._cpu_offer_party(
                        public_offer, strong_cpu, roster, busy_until,
                        regional_cycle_service._utc(cycle.ends_at_utc), {},
                        include_synergy_power=True,
                        require_equipment_for_each_member=True,
                        optimize_cpu_value=True,
                    ), "A oferta pública precisa ser viável no início do planejamento.")
                    plan = regional_cycle_service._cpu_plan_for_guild_v6(
                        db, info.campaign_id, cycle, region, strong_cpu,
                        prepared_start=prepared_start,
                    )[0]
                    decisions = json.loads(plan.decisions_json)
                    self.assertEqual(len(decisions), 1, decisions)
                    self.assertEqual(decisions[0]["offer_type"], "contract")
                    self.assertNotIn("internal_contract", decisions[0])
                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type == "cpu_internal",
                    )), 0)
            finally:
                if campaigns is not None and info is not None:
                    campaigns.close_active_campaign(info.campaign_id)
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_previously_materialized_v6_v7_cycles_keep_legacy_cpu_rules(self):
        with tempfile.TemporaryDirectory(
            prefix="ml050-cpu-legacy-version-", dir=Path(__file__).resolve().parents[1],
        ) as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            try:
                for version in (
                    regional_cycle_service.VIGILIA_V6_RULES_VERSION,
                    regional_cycle_service.VIGILIA_V7_RULES_VERSION,
                ):
                    info = campaigns.create_campaign(f"Ciclo {version}", "Guilda Versão")
                    campaigns.activate_campaign(info.campaign_id)
                    with SessionLocal() as db:
                        campaign = db.get(CampaignMetadata, info.campaign_id)
                        guild, _resources = get_current_guild_context(db, info.campaign_id)
                        cycle = advance_regional_world(
                            db, campaign, guild, campaign.created_at_utc,
                        )
                        self.assertEqual(cycle.rules_version, regional_cycle_service.VIGILIA_RULES_VERSION)
                        cycle.rules_version = version
                        db.flush()
                        same_cycle = advance_regional_world(
                            db, campaign, guild, campaign.created_at_utc,
                        )
                        self.assertEqual(same_cycle.id, cycle.id)
                        self.assertEqual(same_cycle.rules_version, version)
                        home_code = next(
                            code for code, name in regional_cycle_service.REGIONS
                            if name == campaign.home_region
                        )
                        region = db.scalar(select(RegionalRegionState).where(
                            RegionalRegionState.campaign_id == info.campaign_id,
                            RegionalRegionState.region_code == home_code,
                        ))
                        cpus = list(db.scalars(select(RegionalGuildState).where(
                            RegionalGuildState.campaign_id == info.campaign_id,
                            RegionalGuildState.region_code == home_code,
                            RegionalGuildState.guild_id.is_(None),
                        )))
                        strong_cpu = next(state for state in cpus if state.profile == "strong")
                        for state in cpus:
                            state.active = state.id == strong_cpu.id
                        for offer in db.scalars(select(RegionalOffer).where(
                            RegionalOffer.cycle_id == cycle.id,
                            RegionalOffer.region_code == home_code,
                            RegionalOffer.offer_type.in_(regional_cycle_service.PUBLIC_REGIONAL_OFFER_TYPES),
                        )):
                            offer.required_guild_level_snapshot = 999
                        db.flush()

                        prepared = regional_cycle_service._prepare_cpu_region_cycle_start(
                            db, info.campaign_id, cycle, region, [strong_cpu],
                        )
                        self.assertEqual(prepared, {})
                        plan = regional_cycle_service._cpu_plan_for_guild(
                            db, info.campaign_id, cycle, region, strong_cpu,
                        )[0]
                        self.assertEqual(plan.actions, 0)
                        self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                            RegionalOffer.cycle_id == cycle.id,
                            RegionalOffer.region_code == home_code,
                            RegionalOffer.offer_type == "cpu_internal",
                        )), 0)
                    campaigns.close_active_campaign(info.campaign_id)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_rosterless_cpu_creates_no_internal_offer_and_internal_work_gets_no_rebellion_credit(self):
        campaigns = None
        info = None
        with tempfile.TemporaryDirectory(
            prefix="ml050-cpu-internal-boundaries-", dir=Path(__file__).resolve().parents[1],
        ) as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                info = campaigns.create_campaign("Limites CPU", "Guilda Limites")
                campaigns.activate_campaign(info.campaign_id)
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    start = campaign.created_at_utc
                    cycle = advance_regional_world(db, campaign, guild, start)
                    home_code = next(
                        code for code, name in regional_cycle_service.REGIONS
                        if name == campaign.home_region
                    )
                    region = db.scalar(select(RegionalRegionState).where(
                        RegionalRegionState.campaign_id == info.campaign_id,
                        RegionalRegionState.region_code == home_code,
                    ))
                    rosterless_cpu = db.scalar(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.region_code == home_code,
                        RegionalGuildState.guild_id.is_(None),
                        RegionalGuildState.profile == "new",
                    ))
                    all_cpus = list(db.scalars(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.region_code == home_code,
                        RegionalGuildState.guild_id.is_(None),
                    )))
                    for state in all_cpus:
                        state.active = state.id == rosterless_cpu.id
                    roster = list(db.scalars(select(RegionalCpuMercenary).where(
                        RegionalCpuMercenary.guild_state_id == rosterless_cpu.id,
                    )))
                    for member in roster:
                        member.active = False
                    for offer in db.scalars(select(RegionalOffer).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type.in_(regional_cycle_service.PUBLIC_REGIONAL_OFFER_TYPES),
                    )):
                        offer.required_guild_level_snapshot = 999
                    db.flush()

                    prepared_starts = regional_cycle_service._prepare_cpu_region_cycle_start(
                        db, info.campaign_id, cycle, region, [rosterless_cpu],
                    )
                    no_roster_plan = regional_cycle_service._cpu_plan_for_guild_v6(
                        db, info.campaign_id, cycle, region, rosterless_cpu,
                        prepared_start=prepared_starts[rosterless_cpu.id],
                    )[0]
                    self.assertEqual(no_roster_plan.actions, 0)
                    self.assertEqual(db.scalar(select(func.count(RegionalOffer.id)).where(
                        RegionalOffer.cycle_id == cycle.id,
                        RegionalOffer.region_code == home_code,
                        RegionalOffer.offer_type == "cpu_internal",
                    )), 0)

                    event = RegionalEvent(
                        campaign_id=info.campaign_id,
                        event_type="rebellion",
                        region_code=home_code,
                        trigger_cycle_number=cycle.cycle_number,
                        rules_version=cycle.rules_version,
                        seed="ml050-internal-rebellion",
                        status="active",
                        created_at_utc=start,
                        priority_ends_at_utc=start + timedelta(hours=1),
                        cpu_started_at_utc=start + timedelta(hours=1),
                        expires_at_utc=start + timedelta(hours=13),
                        summary_json="{}",
                    )
                    db.add(event)
                    db.flush()

                    eligible_cpu = db.scalar(select(RegionalGuildState).where(
                        RegionalGuildState.campaign_id == info.campaign_id,
                        RegionalGuildState.region_code == home_code,
                        RegionalGuildState.guild_id.is_(None),
                        RegionalGuildState.profile == "medium",
                    ))
                    eligible_cpu.active = True
                    prepared_starts = regional_cycle_service._prepare_cpu_region_cycle_start(
                        db, info.campaign_id, cycle, region, [eligible_cpu],
                    )
                    internal_plan = regional_cycle_service._cpu_plan_for_guild_v6(
                        db, info.campaign_id, cycle, region, eligible_cpu,
                        prepared_start=prepared_starts[eligible_cpu.id],
                    )[0]
                    self.assertTrue(any(
                        row.get("internal_contract")
                        for row in json.loads(internal_plan.decisions_json)
                    ))
                    record_cpu_event_activity(
                        db, info.campaign_id, cycle, home_code, internal_plan,
                    )
                    self.assertEqual(db.scalar(select(func.count(RegionalEventActivity.id)).where(
                        RegionalEventActivity.event_id == event.id,
                        RegionalEventActivity.source_type == "cpu_cycle",
                    )), 0)
                    self.assertEqual(db.scalar(select(func.count(RegionalEventParticipant.id)).where(
                        RegionalEventParticipant.event_id == event.id,
                    )), 0)
            finally:
                if campaigns is not None and info is not None:
                    campaigns.close_active_campaign(info.campaign_id)
                configure_database("sqlite:///:memory:")
                gc.collect()


if __name__ == "__main__":
    unittest.main()
