import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import delete, func, select

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.models.campaign import CampaignMetadata
from app.models.dungeon import DungeonTemplate
from app.models.guild import Guild
from app.models.item import ItemTemplate
from app.models.regional import (
    RegionalCycle,
    RegionalEvent,
    RegionalEventActivity,
    RegionalEventParticipant,
    RegionalGuildState,
    RegionalOffer,
    RegionalRegionState,
    RegionalRunOutcome,
    RegionalWorldState,
)
from app.services.regional_event_service import (
    PORTAL_TTL,
    REBELLION_CHANCE,
    REBELLION_TTL,
    _resolve_rebellion_summary,
    active_rebellion,
    evaluate_open_rebellion,
    attach_event_activity,
    build_portal_loot_snapshot,
    create_cycle_portals,
    expire_due_events,
    record_rebellion_decision,
    record_event_activity_result,
    record_cpu_event_activity,
    resolve_portal_participant,
)
from app.services.regional_cycle_service import REGIONS, regional_outcome_impact
from app.services.regional_cycle_service import record_player_offer_result
from scripts.balance.simulate_regional_event_incidence import portal_roll, rebellion_roll


def _as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class RegionalEventServiceTests(unittest.TestCase):
    def setUp(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(bind=get_engine())
        self.campaign_id = str(uuid4())
        self.now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
        with SessionLocal() as db:
            db.add(CampaignMetadata(
                campaign_id=self.campaign_id,
                campaign_name="Eventos",
                created_at_utc=self.now,
            ))
            self.guild_state = RegionalGuildState(
                campaign_id=self.campaign_id,
                region_code="vale-fronteira",
                slot=0,
                guild_id=None,
                name="Guilda de QA",
                profile="player",
                archetype="player",
            )
            db.add(self.guild_state)
            db.flush()
            self.guild_state_id = self.guild_state.id
            db.commit()

    def tearDown(self):
        configure_database("sqlite:///:memory:")

    def _rebellion(self, db, *, created_at=None, status="active", participant_status="accepted", decision="accept"):
        started = created_at or self.now
        event = RegionalEvent(
            campaign_id=self.campaign_id,
            event_type="rebellion",
            region_code="vale-fronteira",
            trigger_cycle_number=1,
            rules_version="regional-events-v1",
            seed="a" * 64,
            status=status,
            created_at_utc=started,
            priority_ends_at_utc=started + timedelta(hours=1),
            expires_at_utc=started + timedelta(hours=13),
            player_decision=decision,
            summary_json="{}",
        )
        db.add(event)
        db.flush()
        db.add(RegionalEventParticipant(
            event_id=event.id,
            guild_state_id=self.guild_state_id,
            status=participant_status,
        ))
        db.flush()
        return event

    def test_portal_generation_respects_threat_threshold_chance_curve_and_cycle_idempotency(self):
        class FixedRng:
            def __init__(self, roll=0.0):
                self.roll = roll

            def random(self):
                return self.roll

            def randrange(self, _stop):
                return 0

        with SessionLocal() as db:
            cycle = RegionalCycle(
                campaign_id=self.campaign_id, cycle_number=4,
                starts_at_utc=self.now, ends_at_utc=self.now + timedelta(hours=6),
                seed="portal-generation", rules_version="vigilia-v2",
            )
            below = RegionalRegionState(
                campaign_id=self.campaign_id, region_code="a-below", region_name="Abaixo",
                security=50, threat=69.99,
            )
            threshold = RegionalRegionState(
                campaign_id=self.campaign_id, region_code="b-threshold", region_name="Limiar",
                security=50, threat=70,
            )
            capped = RegionalRegionState(
                campaign_id=self.campaign_id, region_code="c-capped", region_name="Teto",
                security=50, threat=100,
            )
            boss = DungeonTemplate(
                name="Chefe de portal", description="Especial",
                content_type="boss", level_band="21-50", recommended_level=30,
                biome="portal", difficulty="legendary", duration_seconds=3600,
                base_gold_reward=100, base_xp_reward=100, base_success_chance=50,
                is_active=True,
            )
            db.add_all([cycle, below, threshold, capped, boss])
            db.flush()
            db.add(ItemTemplate(
                name="Relíquia do Portal", description="Equipamento raro",
                item_type="equipment", rarity="rare", level_band="21-50",
                equipment_slot="main_hand", required_level=21, tier=3, base_sell_value=1,
                rng_bonus_min=1, rng_bonus_max=2, is_active=True,
            ))
            db.flush()
            rolls = iter((0.049, 0.249))

            def fixed_rng(*parts):
                return FixedRng(next(rolls)) if len(parts) == 1 else FixedRng()

            with patch("app.services.regional_event_service._rng", side_effect=fixed_rng):
                create_cycle_portals(db, self.campaign_id, cycle, [below, threshold, capped])
                db.flush()
                events = list(db.scalars(select(RegionalEvent).where(
                    RegionalEvent.campaign_id == self.campaign_id,
                    RegionalEvent.event_type == "portal",
                ).order_by(RegionalEvent.region_code)))
                self.assertEqual([event.region_code for event in events], ["b-threshold", "c-capped"])
                summaries = [json.loads(event.summary_json) for event in events]
                self.assertEqual([row["chance"] for row in summaries], [0.05, 0.25])
                self.assertTrue(all(row["deadline_policy"] == "continues_offline" for row in summaries))
                self.assertEqual(
                    _as_utc(events[0].expires_at_utc),
                    _as_utc(cycle.ends_at_utc + PORTAL_TTL),
                )

                create_cycle_portals(db, self.campaign_id, cycle, [below, threshold, capped])
                db.flush()
                self.assertEqual(db.scalar(select(RegionalEvent.id).where(
                    RegionalEvent.campaign_id == self.campaign_id,
                    RegionalEvent.event_type == "portal",
                ).order_by(RegionalEvent.id.desc()).limit(1)), events[-1].id)
                self.assertEqual(db.scalar(select(func.count()).select_from(RegionalEvent).where(
                    RegionalEvent.campaign_id == self.campaign_id,
                    RegionalEvent.event_type == "portal",
                )), 2)

    def test_incidence_audit_portal_roll_matches_production_seeded_service(self):
        from app.services.regional_cycle_service import REGIONS

        with SessionLocal() as db:
            cycle = RegionalCycle(
                campaign_id=self.campaign_id, cycle_number=27,
                starts_at_utc=self.now, ends_at_utc=self.now + timedelta(hours=6),
                seed="portal-audit-parity", rules_version="vigilia-v2",
            )
            regions = [RegionalRegionState(
                campaign_id=self.campaign_id, region_code=code, region_name=name,
                security=50, threat=100,
            ) for code, name in REGIONS]
            boss = DungeonTemplate(
                name="Parity portal boss", description="Parity fixture",
                content_type="boss", level_band="21-50", recommended_level=30,
                biome="portal", difficulty="legendary", duration_seconds=3600,
                base_gold_reward=0, base_xp_reward=0, base_success_chance=50,
                is_active=True,
            )
            db.add_all([cycle, *regions, boss])
            db.flush()
            db.add(ItemTemplate(
                name="Parity portal item", description="Parity fixture",
                item_type="equipment", rarity="rare", level_band="21-50",
                equipment_slot="main_hand", required_level=21, tier=3, base_sell_value=0,
                rng_bonus_min=0, rng_bonus_max=0, is_active=True,
            ))
            db.flush()
            expected = sorted(
                code for code, _name in REGIONS
                if portal_roll(self.campaign_id, cycle.cycle_number, code, 100)
            )
            create_cycle_portals(db, self.campaign_id, cycle, regions)
            actual = list(db.scalars(select(RegionalEvent.region_code).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "portal",
                RegionalEvent.trigger_cycle_number == cycle.cycle_number,
            ).order_by(RegionalEvent.region_code)))
            self.assertEqual(actual, expected)
            self.assertFalse(portal_roll(self.campaign_id, cycle.cycle_number, "below", 69.99))

    def test_rebellion_generation_rolls_only_eligible_regions_once_per_cycle(self):
        with SessionLocal() as db:
            campaign = db.get(CampaignMetadata, self.campaign_id)
            cycle = RegionalCycle(
                campaign_id=self.campaign_id, cycle_number=7,
                starts_at_utc=self.now, ends_at_utc=self.now + timedelta(hours=6),
                seed="rebellion-generation", rules_version="vigilia-v2",
            )
            eligible = RegionalRegionState(
                campaign_id=self.campaign_id, region_code="a-eligible", region_name="Elegível",
                security=25, threat=85,
            )
            safe = RegionalRegionState(
                campaign_id=self.campaign_id, region_code="b-safe", region_name="Segura",
                security=25.01, threat=100,
            )
            low_threat = RegionalRegionState(
                campaign_id=self.campaign_id, region_code="c-low", region_name="Ameaça baixa",
                security=10, threat=84.99,
            )
            db.add_all([cycle, eligible, safe, low_threat])
            db.flush()
            with patch("app.services.regional_event_service._rng") as rng_factory:
                rng_factory.return_value.random.return_value = REBELLION_CHANCE - 0.0001
                event = evaluate_open_rebellion(db, campaign, cycle, guild_id=999, now=self.now)
                self.assertIsNotNone(event)
                self.assertEqual(event.region_code, "a-eligible")
                self.assertEqual(json.loads(event.summary_json)["chance_per_eligible_region_cycle"], REBELLION_CHANCE)
                self.assertEqual(rng_factory.call_count, 1)

                repeated = evaluate_open_rebellion(db, campaign, cycle, guild_id=999, now=self.now)
                self.assertEqual(repeated.id, event.id)
                self.assertEqual(db.scalar(select(func.count()).select_from(RegionalEvent).where(
                    RegionalEvent.campaign_id == self.campaign_id,
                    RegionalEvent.event_type == "rebellion",
                )), 3)

    def test_rebellion_global_limit_suppresses_extra_regions_and_replays_identically(self):
        with SessionLocal() as db:
            campaign = db.get(CampaignMetadata, self.campaign_id)
            cycle = RegionalCycle(
                campaign_id=self.campaign_id, cycle_number=11,
                starts_at_utc=self.now, ends_at_utc=self.now + timedelta(hours=6),
                seed="global-limit", rules_version="vigilia-v2",
            )
            regions = [RegionalRegionState(
                campaign_id=self.campaign_id,
                region_code=f"region-{index}", region_name=f"Região {index}",
                security=25, threat=85,
            ) for index in range(3)]
            db.add_all([cycle, *regions])
            db.flush()
            candidate_rolls = iter((0.01, 0.015, 0.99))
            with patch("app.services.regional_event_service._rng") as rng_factory:
                rng_factory.side_effect = lambda *_parts: SimpleNamespace(
                    random=lambda: next(candidate_rolls),
                )
                event = evaluate_open_rebellion(db, campaign, cycle, guild_id=999, now=self.now)
            self.assertEqual(event.region_code, "region-0")
            first_rows = list(db.scalars(select(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
            ).order_by(RegionalEvent.region_code)))
            self.assertEqual([row.status for row in first_rows], ["active", "suppressed", "not_triggered"])
            self.assertTrue(all(
                json.loads(row.summary_json)["simultaneous_candidates"] == 2
                for row in first_rows
            ))
            active_now = list(db.scalars(select(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
                RegionalEvent.status.in_(("active", "in_progress")),
            )))
            self.assertEqual(len(active_now), 1)
            original = [(row.region_code, row.status, row.seed, row.summary_json) for row in first_rows]
            next_cycle = RegionalCycle(
                campaign_id=self.campaign_id, cycle_number=12,
                starts_at_utc=self.now + timedelta(hours=6),
                ends_at_utc=self.now + timedelta(hours=12),
                seed="global-limit-next-cycle", rules_version="vigilia-v2",
            )
            db.add(next_cycle)
            db.flush()
            still_active = evaluate_open_rebellion(
                db, campaign, next_cycle, guild_id=999, now=self.now + timedelta(hours=6),
            )
            self.assertEqual(still_active.id, event.id)
            self.assertEqual(db.scalar(select(func.count()).select_from(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
                RegionalEvent.trigger_cycle_number == 12,
            )), 0)

            # Re-run the identical starting state after clearing only its event ledger.
            db.execute(delete(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
            ))
            db.flush()
            replay_rolls = iter((0.01, 0.015, 0.99))
            with patch("app.services.regional_event_service._rng") as rng_factory:
                rng_factory.side_effect = lambda *_parts: SimpleNamespace(
                    random=lambda: next(replay_rolls),
                )
                replay = evaluate_open_rebellion(db, campaign, cycle, guild_id=999, now=self.now)
            self.assertEqual(replay.region_code, event.region_code)
            replay_rows = list(db.scalars(select(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
            ).order_by(RegionalEvent.region_code).execution_options(populate_existing=True)))
            self.assertEqual(
                [(row.region_code, row.status, row.seed, row.summary_json) for row in replay_rows],
                original,
            )

    def test_rebellion_seed_replay_produces_same_results_from_same_start_state(self):
        with SessionLocal() as db:
            campaign = db.get(CampaignMetadata, self.campaign_id)
            cycle = RegionalCycle(
                campaign_id=self.campaign_id, cycle_number=19,
                starts_at_utc=self.now, ends_at_utc=self.now + timedelta(hours=6),
                seed="seed-replay", rules_version="vigilia-v2",
            )
            regions = [RegionalRegionState(
                campaign_id=self.campaign_id,
                region_code=f"replay-{index}", region_name=f"Replay {index}",
                security=25, threat=85,
            ) for index in range(5)]
            db.add_all([cycle, *regions])
            db.flush()

            first_event = evaluate_open_rebellion(db, campaign, cycle, guild_id=999, now=self.now)
            first_rows = list(db.scalars(select(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
            ).order_by(RegionalEvent.region_code)))
            first_signature = [
                (row.region_code, row.status, row.seed, row.summary_json) for row in first_rows
            ]
            expected_candidates = [
                f"replay-{index}" for index in range(5)
                if rebellion_roll(self.campaign_id, cycle.cycle_number, f"replay-{index}", 85, 25)
            ]
            actual_candidates = [
                row.region_code for row in first_rows if row.status in {"active", "suppressed"}
            ]
            self.assertEqual(actual_candidates, expected_candidates)
            db.execute(delete(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
            ))
            db.flush()

            replay_event = evaluate_open_rebellion(db, campaign, cycle, guild_id=999, now=self.now)
            replay_rows = list(db.scalars(select(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "rebellion",
            ).order_by(RegionalEvent.region_code).execution_options(populate_existing=True)))
            replay_signature = [
                (row.region_code, row.status, row.seed, row.summary_json) for row in replay_rows
            ]
            self.assertEqual(replay_signature, first_signature)
            self.assertEqual(
                replay_event.region_code if replay_event is not None else None,
                first_event.region_code if first_event is not None else None,
            )

    def test_concurrent_portal_and_rebellion_triggers_are_campaign_idempotent(self):
        class FixedRng:
            def random(self):
                return 0.0

            def randrange(self, _stop):
                return 0

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = (Path(temp_dir) / "concurrent-events.db").resolve().as_posix()
            configure_database(f"sqlite:///{database_path}")
            Base.metadata.create_all(bind=get_engine())
            campaign_id = str(uuid4())
            cycle_start = self.now
            with SessionLocal() as db:
                campaign = CampaignMetadata(
                    campaign_id=campaign_id,
                    campaign_name="Concorrência regional",
                    created_at_utc=cycle_start,
                )
                cycle1 = RegionalCycle(
                    campaign_id=campaign_id, cycle_number=1,
                    starts_at_utc=cycle_start, ends_at_utc=cycle_start + timedelta(hours=6),
                    seed="portal-race", rules_version="vigilia-v2",
                )
                cycle2 = RegionalCycle(
                    campaign_id=campaign_id, cycle_number=2,
                    starts_at_utc=cycle_start + timedelta(hours=6),
                    ends_at_utc=cycle_start + timedelta(hours=12),
                    seed="rebellion-race", rules_version="vigilia-v2",
                )
                regions = [RegionalRegionState(
                    campaign_id=campaign_id,
                    region_code=f"race-{index}",
                    region_name=f"Região {index}",
                    threat=100,
                    security=25,
                ) for index in range(5)]
                boss = DungeonTemplate(
                    name="Chefe portal concorrente", description="Fixture de corrida",
                    content_type="boss", level_band="21-50", recommended_level=30,
                    biome="portal", difficulty="legendary", duration_seconds=3600,
                    base_gold_reward=100, base_xp_reward=100, base_success_chance=50,
                    is_active=True,
                )
                item = ItemTemplate(
                    name="Relíquia concorrente", description="Fixture de loot",
                    item_type="equipment", rarity="rare", level_band="21-50",
                    equipment_slot="main_hand", required_level=21, tier=3, base_sell_value=1,
                    rng_bonus_min=1, rng_bonus_max=2, is_active=True,
                )
                db.add_all([campaign, cycle1, cycle2, *regions, boss, item])
                db.commit()

            barrier = Barrier(2)

            def create_portals_concurrently():
                with SessionLocal() as db:
                    cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == campaign_id,
                        RegionalCycle.cycle_number == 1,
                    ))
                    regions = list(db.scalars(select(RegionalRegionState).where(
                        RegionalRegionState.campaign_id == campaign_id,
                    )))
                    barrier.wait(timeout=5)
                    create_cycle_portals(db, campaign_id, cycle, regions)
                    db.commit()
                    return True

            with patch("app.services.regional_event_service._rng", side_effect=lambda *_args: FixedRng()):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    portal_results = [
                        executor.submit(create_portals_concurrently) for _ in range(2)
                    ]
                    self.assertEqual([future.result(timeout=10) for future in portal_results], [True, True])

            barrier = Barrier(2)

            def evaluate_rebellion_concurrently():
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, campaign_id)
                    cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == campaign_id,
                        RegionalCycle.cycle_number == 2,
                    ))
                    barrier.wait(timeout=5)
                    event = evaluate_open_rebellion(
                        db, campaign, cycle, guild_id=999, now=cycle.starts_at_utc,
                    )
                    db.commit()
                    return event.id if event is not None else None

            with patch("app.services.regional_event_service._rng", side_effect=lambda *_args: FixedRng()):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    rebellion_results = [
                        executor.submit(evaluate_rebellion_concurrently) for _ in range(2)
                    ]
                    rebellion_ids = [future.result(timeout=10) for future in rebellion_results]

            self.assertIsNotNone(rebellion_ids[0])
            self.assertEqual(rebellion_ids, [rebellion_ids[0], rebellion_ids[0]])
            with SessionLocal() as db:
                portal_rows = list(db.scalars(select(RegionalEvent).where(
                    RegionalEvent.campaign_id == campaign_id,
                    RegionalEvent.event_type == "portal",
                )))
                rebellion_rows = list(db.scalars(select(RegionalEvent).where(
                    RegionalEvent.campaign_id == campaign_id,
                    RegionalEvent.event_type == "rebellion",
                    RegionalEvent.trigger_cycle_number == 2,
                )))
                self.assertEqual(len(portal_rows), 5)
                self.assertEqual(len({row.region_code for row in portal_rows}), 5)
                self.assertEqual(len(rebellion_rows), 5)
                self.assertEqual(sum(row.status == "active" for row in rebellion_rows), 1)
                self.assertEqual(sum(row.status == "suppressed" for row in rebellion_rows), 4)
                self.assertEqual(db.scalar(select(func.count(RegionalEvent.id)).where(
                    RegionalEvent.campaign_id == campaign_id,
                    RegionalEvent.event_type == "rebellion",
                    RegionalEvent.status.in_(("active", "in_progress")),
                )), 1)
            configure_database("sqlite:///:memory:")

    def test_regular_regional_outcome_does_not_count_as_rebellion_activity(self):
        with SessionLocal() as db:
            campaign = db.get(CampaignMetadata, self.campaign_id)
            cycle = RegionalCycle(
                campaign_id=self.campaign_id,
                cycle_number=1,
                starts_at_utc=self.now,
                ends_at_utc=self.now + timedelta(hours=6),
                seed="b" * 64,
                rules_version="vigilia-v2",
            )
            db.add(cycle)
            db.flush()
            offer = RegionalOffer(
                campaign_id=self.campaign_id,
                cycle_id=cycle.id,
                cycle_number=1,
                region_code="vale-fronteira",
                offer_type="contract",
                slot=1,
                rank="S",
                name_snapshot="Contrato normal",
                level_band_snapshot="1-20",
                recommended_level_snapshot=1,
                recommended_power_snapshot=1,
                duration_seconds_snapshot=3600,
                gold_reward_snapshot=10,
                xp_reward_snapshot=10,
                success_chance_snapshot=90,
                status="completed",
            )
            db.add(offer)
            db.flush()
            db.add(RegionalRunOutcome(
                campaign_id=self.campaign_id,
                guild_state_id=self.guild_state_id,
                offer_id=offer.id,
                source_type="mission",
                source_run_id=777,
                offer_cycle_number=1,
                applied_cycle_number=1,
                rank="S",
                success=True,
                contribution=6,
            ))
            event = self._rebellion(db)
            db.flush()
            payload = {}
            _resolve_rebellion_summary(db, event, payload)
            participant = db.scalar(select(RegionalEventParticipant).where(
                RegionalEventParticipant.event_id == event.id,
            ))
            self.assertEqual(payload["result"], "failure")
            self.assertEqual(payload["aggregate"]["successes"], 0)
            self.assertEqual(payload["aggregate"]["player_successes"], 0)
            self.assertEqual(participant.contribution, 0)
            self.assertFalse(participant.success)

    def test_only_event_linked_activities_contribute_and_multiple_runs_are_allowed(self):
        with SessionLocal() as db:
            event = self._rebellion(db)
            activity_a = attach_event_activity(db, event, db.get(RegionalGuildState, self.guild_state_id), "mission", 9001)
            activity_b = attach_event_activity(db, event, db.get(RegionalGuildState, self.guild_state_id), "dungeon", 9002)
            self.assertNotEqual(activity_a.id, activity_b.id)
            record_event_activity_result(db, "mission", 9001, True, self.now + timedelta(hours=2))
            record_event_activity_result(db, "dungeon", 9002, True, self.now + timedelta(hours=3))
            payload = {}
            _resolve_rebellion_summary(db, event, payload)
            participant = db.scalar(
                select(RegionalEventParticipant).where(RegionalEventParticipant.event_id == event.id)
            )
            self.assertEqual(payload["aggregate"]["player_successes"], 2)
            self.assertEqual(payload["result"], "success")
            self.assertEqual(participant.contribution, 2)
            self.assertTrue(participant.success)

    def test_rebellion_run_started_before_deadline_counts_when_it_finishes_after(self):
        with SessionLocal() as db:
            event = self._rebellion(db)
            activity = attach_event_activity(
                db, event, db.get(RegionalGuildState, self.guild_state_id), "mission", 9050,
            )
            deadline = _as_utc(event.expires_at_utc)
            expire_due_events(db, self.campaign_id, deadline)
            self.assertEqual(event.status, "in_progress")
            self.assertIs(active_rebellion(db, self.campaign_id), event)
            self.assertTrue(json.loads(event.summary_json)["started_activities_may_finish"])
            next_cycle = RegionalCycle(
                campaign_id=self.campaign_id,
                cycle_number=2,
                starts_at_utc=deadline,
                ends_at_utc=deadline + timedelta(hours=6),
                seed="g" * 64,
                rules_version="vigilia-v2",
            )
            db.add(next_cycle)
            db.flush()
            self.assertIs(
                evaluate_open_rebellion(
                    db, db.get(CampaignMetadata, self.campaign_id), next_cycle, 999, deadline,
                ),
                event,
            )
            with self.assertRaisesRegex(ValueError, "evento já foi encerrado"):
                attach_event_activity(
                    db, event, db.get(RegionalGuildState, self.guild_state_id), "dungeon", 9051,
                )

            completed_at = deadline + timedelta(hours=2)
            completed = record_event_activity_result(db, "mission", 9050, True, completed_at)
            self.assertIs(completed, activity)
            self.assertEqual(event.status, "resolved")
            self.assertIsNone(active_rebellion(db, self.campaign_id))
            summary = json.loads(event.summary_json)
            self.assertEqual(summary["aggregate"]["player_successes"], 1)
            self.assertEqual(summary["activities_completed_after_deadline"], 1)
            self.assertEqual(summary["activities"][0]["source_run_id"], 9050)
            self.assertEqual(summary["activities"][0]["resolved_at_utc"], completed_at.isoformat())

    def test_portal_stays_open_for_other_guilds_until_deadline_and_keeps_started_run(self):
        with SessionLocal() as db:
            region = RegionalRegionState(
                campaign_id=self.campaign_id,
                region_code="vale-fronteira",
                region_name="Vale da Fronteira",
                security=50,
                threat=80,
            )
            db.add(region)
            first_guild = Guild(campaign_id=self.campaign_id, name="Guilda do Jogador")
            db.add(first_guild)
            db.flush()
            first_state = db.get(RegionalGuildState, self.guild_state_id)
            first_state.guild_id = first_guild.id
            second_state = RegionalGuildState(
                campaign_id=self.campaign_id,
                region_code=region.region_code,
                slot=1,
                guild_id=None,
                name="Guilda CPU",
                profile="strong",
                archetype="security",
            )
            db.add(second_state)
            db.flush()
            event = RegionalEvent(
                campaign_id=self.campaign_id,
                event_type="portal",
                region_code=region.region_code,
                trigger_cycle_number=1,
                rules_version="regional-events-v1",
                seed="c" * 64,
                status="active",
                created_at_utc=self.now,
                expires_at_utc=self.now + timedelta(hours=3),
                summary_json="{}",
            )
            db.add(event)
            db.flush()
            first_activity = attach_event_activity(db, event, first_state, "dungeon", 9100)
            repeated_start = attach_event_activity(db, event, first_state, "dungeon", 9100)
            self.assertEqual(repeated_start.id, first_activity.id)
            with self.assertRaisesRegex(ValueError, "já usou sua entrada"):
                attach_event_activity(db, event, first_state, "dungeon", 9101)
            first_completed = record_event_activity_result(
                db, "dungeon", 9100, True, self.now + timedelta(hours=2),
            )
            resolve_portal_participant(db, first_completed, True, self.now + timedelta(hours=2))
            db.flush()
            self.assertEqual(first_activity.status, "resolved")
            self.assertEqual(event.status, "active")
            self.assertIsNone(event.resolved_at_utc)

            second_activity = attach_event_activity(
                db, event, second_state, "dungeon", 9102,
            )
            expire_due_events(db, self.campaign_id, event.expires_at_utc)
            self.assertEqual(event.status, "in_progress")
            self.assertTrue(json.loads(event.summary_json)["started_activities_may_finish"])
            with self.assertRaisesRegex(ValueError, "evento já foi encerrado"):
                attach_event_activity(db, event, second_state, "dungeon", 9103)

            second_completed = record_event_activity_result(
                db, "dungeon", 9102, False, self.now + timedelta(hours=4),
            )
            resolve_portal_participant(db, second_completed, False, self.now + timedelta(hours=4))
            db.flush()
            self.assertEqual(second_activity.status, "resolved")
            self.assertEqual(event.status, "resolved")
            self.assertEqual(_as_utc(event.resolved_at_utc), self.now + timedelta(hours=4))
            portal_summary = json.loads(event.summary_json)
            self.assertEqual(portal_summary["aggregate"], {"entries": 2, "successes": 1, "failures": 1})
            self.assertEqual(portal_summary["activities_completed_after_deadline"], 1)
            self.assertEqual(
                {row["guild_state_id"]: row["success"] for row in portal_summary["participant_results"]},
                {first_state.id: True, second_state.id: False},
            )
            self.assertEqual(region.threat, 80)
            self.assertEqual(region.security, 50)
            repeated = record_event_activity_result(
                db, "dungeon", 9100, True, self.now + timedelta(hours=4, minutes=1),
            )
            self.assertIsNone(repeated)

    def test_cpu_portal_entry_is_deterministic_linked_once_and_separate_from_player(self):
        with SessionLocal() as db:
            region = RegionalRegionState(
                campaign_id=self.campaign_id,
                region_code="vale-fronteira",
                region_name="Vale da Fronteira",
                security=50,
                threat=80,
            )
            cpu_state = RegionalGuildState(
                campaign_id=self.campaign_id,
                region_code="vale-fronteira",
                slot=1,
                guild_id=None,
                name="Guilda CPU",
                profile="strong",
                archetype="security",
            )
            cycle = RegionalCycle(
                campaign_id=self.campaign_id,
                cycle_number=2,
                starts_at_utc=self.now + timedelta(minutes=30),
                ends_at_utc=self.now + timedelta(hours=6, minutes=30),
                seed="d" * 64,
                rules_version="vigilia-v2",
            )
            event = RegionalEvent(
                campaign_id=self.campaign_id,
                event_type="portal",
                region_code="vale-fronteira",
                trigger_cycle_number=1,
                rules_version="regional-events-v3",
                seed="portal-cpu-test",
                status="active",
                created_at_utc=self.now,
                expires_at_utc=self.now + timedelta(hours=3),
                summary_json="{}",
            )
            db.add_all([region, cpu_state, cycle, event])
            db.flush()
            plan = SimpleNamespace(
                id=9201,
                seed="cpu-plan-test",
                guild_state_id=cpu_state.id,
                actions=2,
                successes=1,
                failures=1,
            )

            with patch("app.services.regional_event_service.PORTAL_CPU_PARTICIPATION_CHANCE", 1.0):
                security_delta, threat_delta = record_cpu_event_activity(
                    db, self.campaign_id, cycle, event.region_code, plan,
                )
                repeated_delta = record_cpu_event_activity(
                    db, self.campaign_id, cycle, event.region_code, plan,
                )

            participant = db.scalar(select(RegionalEventParticipant).where(
                RegionalEventParticipant.event_id == event.id,
                RegionalEventParticipant.guild_state_id == cpu_state.id,
            ))
            activities = list(db.scalars(select(RegionalEventActivity).where(
                RegionalEventActivity.event_id == event.id,
                RegionalEventActivity.source_type == "cpu_portal",
            )))
            self.assertIsNotNone(participant)
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities[0].source_run_id, plan.id)
            self.assertEqual(activities[0].successes + activities[0].failures, 1)
            self.assertEqual(participant.contribution, 3 if participant.success else 1)
            self.assertEqual(event.status, "active")
            self.assertEqual(repeated_delta, (0.0, 0.0))
            self.assertNotEqual((security_delta, threat_delta), (0.0, 0.0))
            self.assertEqual(_as_utc(activities[0].resolved_at_utc), cycle.starts_at_utc + timedelta(hours=2))
            expire_due_events(db, self.campaign_id, event.expires_at_utc)
            self.assertEqual(event.status, "resolved")
            self.assertEqual(_as_utc(event.resolved_at_utc), self.now + timedelta(hours=3))

    def test_portal_loot_snapshot_is_versioned_high_rarity_and_not_guaranteed(self):
        with SessionLocal() as db:
            template = DungeonTemplate(
                name="Chefe do Portal de teste", description="Chefe especial",
                content_type="boss", level_band="21-50", recommended_level=30,
                biome="portal", difficulty="legendary", duration_seconds=3600,
                base_gold_reward=100, base_xp_reward=100, base_success_chance=50,
                is_active=True,
            )
            db.add(template)
            db.flush()
            for rarity, slot in (("rare", "main_hand"), ("epic", "chest"), ("legendary", "ring")):
                db.add(ItemTemplate(
                    name=f"Portal {rarity}", description="Loot do portal",
                    item_type="equipment", rarity=rarity, level_band="21-50",
                    equipment_slot=slot, required_level=21, tier=3, base_sell_value=1,
                    rng_bonus_min=1, rng_bonus_max=2, is_active=True,
                ))
            db.flush()
            snapshot = build_portal_loot_snapshot(db, template, "f" * 64)
            self.assertEqual(snapshot["version"], "portal-loot-v1")
            self.assertEqual(snapshot["roll_model"], "one_100_point_roll;exclusive_rarity_bands;no_guaranteed_equipment")
            self.assertEqual([entry["rarity"] for entry in snapshot["entries"]], ["rare", "epic", "legendary"])
            self.assertEqual([entry["chance_percent"] for entry in snapshot["entries"]], [20, 6, 1])
            self.assertEqual(sum(entry["chance_percent"] for entry in snapshot["entries"]), 27)
            for entry in snapshot["entries"]:
                item_snapshot = entry["item_snapshot"]
                self.assertEqual(item_snapshot["id"], entry["item_template_id"])
                self.assertIn("equipment_slot", item_snapshot)
                self.assertIn("bonus_power", item_snapshot)
                self.assertIn("rng_bonus_max", item_snapshot)

    def test_visitor_rebellion_run_updates_target_and_home_influence_with_event_score(self):
        with SessionLocal() as db:
            guild = Guild(campaign_id=self.campaign_id, name="Guilda Visitante")
            db.add(guild)
            db.flush()
            player_state = db.get(RegionalGuildState, self.guild_state_id)
            player_state.guild_id = guild.id
            db.add_all([
                RegionalWorldState(campaign_id=self.campaign_id, last_materialized_cycle=1),
                RegionalRegionState(
                    campaign_id=self.campaign_id, region_code="vale-fronteira",
                    region_name="Vale da Fronteira", security=50, threat=40, influence=0,
                ),
                RegionalRegionState(
                    campaign_id=self.campaign_id, region_code="bosque-ambar",
                    region_name="Bosque de Âmbar", security=40, threat=80, influence=0,
                ),
            ])
            event = self._rebellion(db)
            event.region_code = "bosque-ambar"
            cycle = RegionalCycle(
                campaign_id=self.campaign_id,
                cycle_number=1,
                starts_at_utc=self.now,
                ends_at_utc=self.now + timedelta(hours=6),
                seed="d" * 64,
                rules_version="vigilia-v2",
            )
            db.add(cycle)
            db.flush()
            offer = RegionalOffer(
                campaign_id=self.campaign_id,
                cycle_id=cycle.id,
                cycle_number=1,
                region_code="bosque-ambar",
                offer_type="contract",
                slot=2,
                rank="S",
                name_snapshot="Defesa visitante",
                level_band_snapshot="1-20",
                recommended_level_snapshot=1,
                recommended_power_snapshot=1,
                duration_seconds_snapshot=3600,
                gold_reward_snapshot=10,
                xp_reward_snapshot=10,
                success_chance_snapshot=90,
                status="in_progress",
            )
            db.add(offer)
            db.flush()
            activity = attach_event_activity(db, event, player_state, "mission", 9200)
            target = db.scalar(select(RegionalRegionState).where(
                RegionalRegionState.region_code == "bosque-ambar",
            ))
            home = db.scalar(select(RegionalRegionState).where(
                RegionalRegionState.region_code == "vale-fronteira",
            ))
            target_before = (target.security, target.threat)
            record_player_offer_result(
                db, guild, source_type="mission", source_run_id=9200,
                offer_id=offer.id, success=True, gold_earned=10, xp_earned=10,
            )
            record_event_activity_result(db, "mission", 9200, True, self.now + timedelta(hours=2))
            payload = {}
            _resolve_rebellion_summary(db, event, payload)
            self.assertGreater(target.security, target_before[0])
            self.assertLess(target.threat, target_before[1])
            self.assertEqual(player_state.influence, 6)
            self.assertEqual(home.influence, 6)
            self.assertEqual(activity.contribution, 6)
            self.assertEqual(payload["aggregate"]["player_successes"], 1)
            self.assertEqual(payload["activities"][0]["contribution"], 6)

    def test_no_response_gets_full_twelve_hour_cpu_window_after_priority(self):
        with SessionLocal() as db:
            event = self._rebellion(db, participant_status="invited", decision=None)
            expire_due_events(db, self.campaign_id, self.now + timedelta(minutes=59))
            db.refresh(event)
            self.assertIsNone(event.cpu_started_at_utc)
            self.assertEqual(event.status, "active")

            cpu_start = self.now + timedelta(hours=1)
            expire_due_events(db, self.campaign_id, cpu_start)
            db.refresh(event)
            self.assertEqual(event.player_decision, "delegated_cpu")
            self.assertEqual(_as_utc(event.cpu_started_at_utc), cpu_start)
            self.assertEqual(_as_utc(event.expires_at_utc), cpu_start + REBELLION_TTL)
            self.assertEqual(event.status, "active")

            expire_due_events(db, self.campaign_id, cpu_start + timedelta(hours=12) - timedelta(seconds=1))
            db.refresh(event)
            self.assertEqual(event.status, "active")
            expire_due_events(db, self.campaign_id, cpu_start + timedelta(hours=12))
            db.refresh(event)
            self.assertEqual(event.status, "resolved")
            self.assertEqual(json.loads(event.summary_json)["result"], "failure")

    def test_first_cpu_cycle_after_priority_is_linked_to_rebellion(self):
        with SessionLocal() as db:
            event = self._rebellion(db, participant_status="invited", decision=None)
            cycle = RegionalCycle(
                campaign_id=self.campaign_id,
                cycle_number=2,
                starts_at_utc=self.now + timedelta(hours=1),
                ends_at_utc=self.now + timedelta(hours=7),
                seed="f" * 64,
                rules_version="vigilia-v2",
            )
            db.add(cycle)
            db.flush()
            expire_due_events(db, self.campaign_id, cycle.starts_at_utc)
            plan = SimpleNamespace(
                id=701,
                guild_state_id=self.guild_state_id,
                actions=3,
                successes=2,
                failures=1,
            )
            record_cpu_event_activity(db, self.campaign_id, cycle, event.region_code, plan)
            activity = db.scalar(select(RegionalEventActivity).where(
                RegionalEventActivity.event_id == event.id,
                RegionalEventActivity.source_type == "cpu_cycle",
                RegionalEventActivity.source_run_id == plan.id,
            ))
            self.assertIsNotNone(activity)
            self.assertEqual(activity.contribution, 3)
            self.assertEqual(activity.successes, 2)
            self.assertEqual(activity.failures, 1)

    def test_cpu_cycle_started_before_rebellion_deadline_is_kept_in_final_summary(self):
        with SessionLocal() as db:
            event = self._rebellion(db)
            event.cpu_started_at_utc = self.now
            cycle = RegionalCycle(
                campaign_id=self.campaign_id,
                cycle_number=2,
                starts_at_utc=self.now + timedelta(hours=12),
                ends_at_utc=self.now + timedelta(hours=18),
                seed="e" * 64,
                rules_version="vigilia-v2",
            )
            db.add(cycle)
            db.flush()
            plan = SimpleNamespace(
                id=702,
                guild_state_id=self.guild_state_id,
                actions=3,
                successes=2,
                failures=1,
            )
            record_cpu_event_activity(db, self.campaign_id, cycle, event.region_code, plan)
            activity = db.scalar(select(RegionalEventActivity).where(
                RegionalEventActivity.event_id == event.id,
                RegionalEventActivity.source_type == "cpu_cycle",
                RegionalEventActivity.source_run_id == plan.id,
            ))
            deadline = _as_utc(event.expires_at_utc)
            self.assertGreater(_as_utc(activity.resolved_at_utc), deadline)
            expire_due_events(db, self.campaign_id, deadline)
            self.assertEqual(event.status, "resolved")
            summary = json.loads(event.summary_json)
            self.assertEqual(summary["aggregate"]["cpu_successes"], 2)
            self.assertEqual(summary["aggregate"]["cpu_failures"], 1)
            self.assertEqual(summary["activities_completed_after_deadline"], 1)

    def test_explicit_decline_starts_cpu_twelve_hour_window_immediately(self):
        with SessionLocal() as db:
            event = self._rebellion(db, participant_status="invited", decision=None)
            click_time = self.now + timedelta(minutes=59)
            record_rebellion_decision(db, event, self.guild_state_id, "decline", click_time)
            deadline = click_time + REBELLION_TTL
            self.assertEqual(_as_utc(event.cpu_started_at_utc), click_time)
            self.assertEqual(_as_utc(event.expires_at_utc), deadline)
            expire_due_events(db, self.campaign_id, deadline - timedelta(seconds=1))
            self.assertEqual(event.status, "active")
            expire_due_events(db, self.campaign_id, deadline)
            self.assertEqual(event.status, "resolved")

    def test_accept_keeps_one_hour_priority_then_full_twelve_hour_activity_window(self):
        with SessionLocal() as db:
            event = self._rebellion(db)
            participant = db.scalar(select(RegionalEventParticipant).where(
                RegionalEventParticipant.event_id == event.id,
            ))
            participant.status = "invited"
            event.player_decision = None
            event.cpu_started_at_utc = None
            event.expires_at_utc = self.now + timedelta(hours=13)
            record_rebellion_decision(
                db, event, self.guild_state_id, "accept", self.now + timedelta(minutes=10),
            )
            self.assertEqual(event.cpu_started_at_utc, self.now + timedelta(hours=1))
            self.assertEqual(event.expires_at_utc, self.now + timedelta(hours=13))
            expire_due_events(db, self.campaign_id, self.now + timedelta(hours=13) - timedelta(seconds=1))
            self.assertEqual(event.status, "active")
            expire_due_events(db, self.campaign_id, self.now + timedelta(hours=13))
            self.assertEqual(event.status, "resolved")


if __name__ == "__main__":
    unittest.main()
