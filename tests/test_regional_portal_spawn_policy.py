import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select
from sqlalchemy import create_engine

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.models.campaign import CampaignMetadata
from app.models.dungeon import DungeonTemplate
from app.models.item import ItemTemplate
from app.models.regional import (
    RegionalCycle,
    RegionalEvent,
    RegionalPortalSpawnState,
    RegionalRegionState,
)
from app.services.portal_spawn_rules import (
    CURRENT_PORTAL_SPAWN_RULES_VERSION,
    PortalSpawnRules,
    get_portal_spawn_rules,
)
from app.services.regional_cycle_service import VIGILIA_RULES_VERSION
from app.services.regional_event_service import create_cycle_portals


class FixedRng:
    def __init__(self, roll: float = 0.0):
        self.roll = roll

    def random(self):
        return self.roll

    def randrange(self, stop):
        return 0 if stop else 0


class RegionalPortalSpawnPolicyTests(unittest.TestCase):
    def setUp(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(bind=get_engine())
        self.now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        self.campaign_id = str(uuid4())
        with SessionLocal() as db:
            db.add(CampaignMetadata(
                campaign_id=self.campaign_id,
                campaign_name="Portal policy",
                created_at_utc=self.now,
            ))
            self.region = RegionalRegionState(
                campaign_id=self.campaign_id,
                region_code="vale-norte",
                region_name="Vale do Norte",
                threat=0,
                security=100,
            )
            db.add(self.region)
            self._add_content(db)
            db.commit()
            self.region_id = self.region.id

    def tearDown(self):
        configure_database("sqlite:///:memory:")

    @staticmethod
    def _add_content(db, *, boss_name="Chefe Portal", band="1-20", loot=True):
        boss = DungeonTemplate(
            name=boss_name,
            description="Encontro sintético",
            content_type="boss",
            level_band=band,
            recommended_level=1,
            biome="portal",
            difficulty="normal",
            duration_seconds=3600,
            base_gold_reward=10,
            base_xp_reward=10,
            base_success_chance=50,
            is_active=True,
        )
        db.add(boss)
        if loot:
            db.add(ItemTemplate(
                name=f"Loot {boss_name}",
                description="Item sintético",
                item_type="equipment",
                rarity="rare",
                level_band=band,
                equipment_slot="main_hand",
                required_level=1,
                tier=1,
                base_sell_value=1,
                rng_bonus_min=1,
                rng_bonus_max=2,
                is_active=True,
            ))
        return boss

    def _cycle(self, number: int, ends_at: datetime, campaign_id: str | None = None):
        return RegionalCycle(
            campaign_id=campaign_id or self.campaign_id,
            cycle_number=number,
            starts_at_utc=ends_at - timedelta(hours=6),
            ends_at_utc=ends_at,
            seed=f"cycle-{number}",
            rules_version=VIGILIA_RULES_VERSION,
            player_level_snapshot=1,
            portal_spawn_rules_version=CURRENT_PORTAL_SPAWN_RULES_VERSION,
        )

    def _region(self, db, region_code="vale-norte", campaign_id=None):
        return db.scalar(select(RegionalRegionState).where(
            RegionalRegionState.campaign_id == (campaign_id or self.campaign_id),
            RegionalRegionState.region_code == region_code,
        ))

    @staticmethod
    def _utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    def test_formula_covers_base_bonus_and_caps(self):
        rules = get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION)
        self.assertEqual(rules.chance_percentages(0, 0), (8, 0, 8))
        self.assertEqual(rules.chance_percentages(1, 0), (9, 0, 9))
        self.assertEqual(rules.chance_percentages(12, 0), (20, 0, 20))
        self.assertEqual(rules.chance_percentages(99, 99), (20, 5, 25))
        self.assertEqual(rules.chance_percentages(0, 5), (8, 5, 13))
        self.assertEqual(rules.chance_percentages(1, 5), (9, 5, 14))
        self.assertEqual(rules.chance_percentages(12, 5), (20, 5, 25))
        self.assertIsNone(get_portal_spawn_rules("unknown-version"))

    def test_configuration_rejects_invalid_probability_and_timing(self):
        with self.assertRaises(ValueError):
            PortalSpawnRules(version="bad", base_chance_pp=98, base_chance_cap_pp=98,
                             explorer_bonus_cap_pp=2)
        with self.assertRaises(ValueError):
            PortalSpawnRules(version="bad", cooldown_hours=0)
        with self.assertRaises(ValueError):
            PortalSpawnRules(version="bad", max_failure_stacks=1)

    def test_failed_roll_persists_one_stack_and_retry_after_reload_is_idempotent(self):
        with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.99)):
            with SessionLocal() as db:
                cycle = self._cycle(1, self.now + timedelta(hours=6))
                db.add(cycle)
                db.flush()
                region = self._region(db)
                create_cycle_portals(db, self.campaign_id, cycle, [region])
                create_cycle_portals(db, self.campaign_id, cycle, [region])
                db.commit()
            with SessionLocal() as db:
                state = db.scalar(select(RegionalPortalSpawnState).where(
                    RegionalPortalSpawnState.campaign_id == self.campaign_id,
                    RegionalPortalSpawnState.region_code == "vale-norte",
                ))
                self.assertEqual(state.failure_stacks, 1)
                self.assertEqual(state.last_evaluated_cycle_number, 1)
                self.assertEqual(state.last_result, "rolled_failure")
                self.assertEqual(db.scalar(select(RegionalEvent.id).where(
                    RegionalEvent.campaign_id == self.campaign_id,
                    RegionalEvent.event_type == "portal",
                )), None)
                cycle = db.get(RegionalCycle, 1)
                create_cycle_portals(db, self.campaign_id, cycle, [self._region(db)])
                db.commit()
                self.assertEqual(state.failure_stacks, 1)

    def test_success_resets_stack_sets_twelve_hour_window_and_exact_24_hour_cooldown(self):
        with SessionLocal() as db:
            db.add(RegionalPortalSpawnState(
                campaign_id=self.campaign_id,
                region_code="vale-norte",
                failure_stacks=4,
                rules_version=CURRENT_PORTAL_SPAWN_RULES_VERSION,
                created_at_utc=self.now,
                updated_at_utc=self.now,
            ))
            first = self._cycle(1, self.now + timedelta(hours=6))
            db.add(first)
            db.flush()
            region = self._region(db)
            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.0)):
                create_cycle_portals(db, self.campaign_id, first, [region])
                db.commit()

        with SessionLocal() as db:
            event = db.scalar(select(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "portal",
            ))
            state = db.scalar(select(RegionalPortalSpawnState).where(
                RegionalPortalSpawnState.campaign_id == self.campaign_id,
            ))
            self.assertEqual(self._utc(event.expires_at_utc), self.now + timedelta(hours=18))
            self.assertEqual(json.loads(event.summary_json)["chance_percent"], 12)
            self.assertEqual(state.failure_stacks, 0)
            self.assertEqual(self._utc(state.cooldown_until_utc), self.now + timedelta(hours=30))

            before_boundary = self._cycle(2, self.now + timedelta(hours=29, minutes=59))
            db.add(before_boundary)
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.0)):
                create_cycle_portals(db, self.campaign_id, before_boundary, [self._region(db)])
            self.assertEqual(state.last_result, "cooldown")

            boundary = self._cycle(3, self.now + timedelta(hours=30))
            db.add(boundary)
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.0)):
                create_cycle_portals(db, self.campaign_id, boundary, [self._region(db)])
            db.commit()
            self.assertEqual(state.last_result, "spawned")
            self.assertEqual(self._utc(state.last_portal_spawned_at_utc), self._utc(boundary.ends_at_utc))

    def test_migrated_state_backfills_cooldown_from_last_portal_origin(self):
        with SessionLocal() as db:
            old_portal = RegionalEvent(
                campaign_id=self.campaign_id,
                event_type="portal",
                region_code="vale-norte",
                trigger_cycle_number=4,
                rules_version="regional-events-v5",
                seed="old-portal",
                status="expired",
                created_at_utc=self.now,
                expires_at_utc=self.now + timedelta(hours=3),
                summary_json="{\"existing_snapshot\":true}",
            )
            db.add(old_portal)
            cycle = self._cycle(5, self.now + timedelta(hours=23))
            db.add(cycle)
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.0)):
                create_cycle_portals(db, self.campaign_id, cycle, [self._region(db)])
            state = db.scalar(select(RegionalPortalSpawnState).where(
                RegionalPortalSpawnState.campaign_id == self.campaign_id,
            ))
            self.assertEqual(state.failure_stacks, 0)
            self.assertEqual(self._utc(state.last_portal_spawned_at_utc), self.now)
            self.assertEqual(self._utc(state.cooldown_until_utc), self.now + timedelta(hours=24))
            self.assertEqual(state.last_result, "cooldown")
            db.commit()

        with SessionLocal() as db:
            old_portal = db.scalar(select(RegionalEvent).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "portal",
            ))
            self.assertEqual(old_portal.summary_json, "{\"existing_snapshot\":true}")
            cycle = self._cycle(6, self.now + timedelta(hours=24))
            db.add(cycle)
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.0)):
                create_cycle_portals(db, self.campaign_id, cycle, [self._region(db)])
            db.commit()
            self.assertEqual(self._utc(old_portal.expires_at_utc), self.now + timedelta(hours=3))

    def test_missing_boss_or_loot_records_block_without_consuming_failure(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(bind=get_engine())
        no_loot_campaign = str(uuid4())
        with SessionLocal() as db:
            db.add(CampaignMetadata(
                campaign_id=no_loot_campaign,
                campaign_name="Sem loot",
                created_at_utc=self.now,
            ))
            no_loot_region = RegionalRegionState(
                campaign_id=no_loot_campaign,
                region_code="regiao-sem-loot",
                region_name="Sem loot",
                threat=100,
                security=0,
            )
            self._add_content(db, boss_name="Chefe sem loot", loot=False)
            db.add(no_loot_region)
            cycle = self._cycle(1, self.now + timedelta(hours=6), no_loot_campaign)
            db.add(cycle)
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=AssertionError("no eligible roll")):
                create_cycle_portals(db, no_loot_campaign, cycle, [no_loot_region])
            state = db.scalar(select(RegionalPortalSpawnState).where(
                RegionalPortalSpawnState.campaign_id == no_loot_campaign,
            ))
            self.assertEqual(state.failure_stacks, 0)
            self.assertEqual(state.last_result, "content_unavailable")
            self.assertEqual(state.last_evaluated_cycle_number, 1)

    def test_missing_boss_records_block_without_calling_rng(self):
        with SessionLocal() as db:
            db.query(DungeonTemplate).delete()
            cycle = self._cycle(1, self.now + timedelta(hours=6))
            db.add(cycle)
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=AssertionError("no eligible roll")):
                create_cycle_portals(db, self.campaign_id, cycle, [self._region(db)])
            state = db.scalar(select(RegionalPortalSpawnState).where(
                RegionalPortalSpawnState.campaign_id == self.campaign_id,
            ))
            self.assertEqual(state.failure_stacks, 0)
            self.assertEqual(state.last_result, "content_unavailable")

    def test_state_isolated_by_campaign_and_region(self):
        other_campaign = str(uuid4())
        with SessionLocal() as db:
            db.add(CampaignMetadata(
                campaign_id=other_campaign,
                campaign_name="Outra campanha",
                created_at_utc=self.now,
            ))
            same_campaign_other_region = RegionalRegionState(
                campaign_id=self.campaign_id,
                region_code="vale-sul",
                region_name="Vale do Sul",
            )
            other_campaign_region = RegionalRegionState(
                campaign_id=other_campaign,
                region_code="vale-norte",
                region_name="Vale do Norte",
            )
            db.add_all([same_campaign_other_region, other_campaign_region])
            db.add_all([
                RegionalPortalSpawnState(
                    campaign_id=self.campaign_id,
                    region_code="vale-norte",
                    failure_stacks=2,
                    rules_version=CURRENT_PORTAL_SPAWN_RULES_VERSION,
                ),
                RegionalPortalSpawnState(
                    campaign_id=self.campaign_id,
                    region_code="vale-sul",
                    failure_stacks=0,
                    rules_version=CURRENT_PORTAL_SPAWN_RULES_VERSION,
                ),
                RegionalPortalSpawnState(
                    campaign_id=other_campaign,
                    region_code="vale-norte",
                    failure_stacks=5,
                    rules_version=CURRENT_PORTAL_SPAWN_RULES_VERSION,
                ),
            ])
            first = self._cycle(1, self.now + timedelta(hours=6))
            other = self._cycle(1, self.now + timedelta(hours=6), other_campaign)
            db.add_all([first, other])
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.99)):
                create_cycle_portals(db, self.campaign_id, first, [self._region(db), same_campaign_other_region])
                create_cycle_portals(db, other_campaign, other, [other_campaign_region])
            db.commit()
            states = {
                (state.campaign_id, state.region_code): state.failure_stacks
                for state in db.scalars(select(RegionalPortalSpawnState))
            }
            self.assertEqual(states[(self.campaign_id, "vale-norte")], 3)
            self.assertEqual(states[(self.campaign_id, "vale-sul")], 1)
            self.assertEqual(states[(other_campaign, "vale-norte")], 6)

    def test_parameter_version_change_clamps_saved_stack_deterministically(self):
        next_rules = PortalSpawnRules(
            version="portal-spawn-v2-test",
            base_chance_pp=8,
            failure_increment_pp=1,
            base_chance_cap_pp=10,
            explorer_bonus_cap_pp=5,
            cooldown_hours=24,
            entry_window_hours=12,
            max_failure_stacks=2,
        )
        with SessionLocal() as db:
            db.add(RegionalPortalSpawnState(
                campaign_id=self.campaign_id,
                region_code="vale-norte",
                failure_stacks=12,
                rules_version=CURRENT_PORTAL_SPAWN_RULES_VERSION,
            ))
            cycle = self._cycle(1, self.now + timedelta(hours=6))
            cycle.portal_spawn_rules_version = next_rules.version
            db.add(cycle)
            db.flush()
            with patch(
                "app.services.portal_spawn_rules.PORTAL_SPAWN_RULES",
                {next_rules.version: next_rules},
            ), patch(
                "app.services.regional_event_service._rng",
                side_effect=lambda *_: FixedRng(0.99),
            ):
                create_cycle_portals(db, self.campaign_id, cycle, [self._region(db)])
            state = db.scalar(select(RegionalPortalSpawnState).where(
                RegionalPortalSpawnState.campaign_id == self.campaign_id,
            ))
            self.assertEqual(state.rules_version, next_rules.version)
            self.assertEqual(state.failure_stacks, 2)
            self.assertEqual(state.last_result, "rolled_failure")
            db.commit()

    def test_rollback_removes_portal_and_state_together(self):
        with SessionLocal() as db:
            cycle = self._cycle(1, self.now + timedelta(hours=6))
            db.add(cycle)
            db.flush()
            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.0)):
                create_cycle_portals(db, self.campaign_id, cycle, [self._region(db)])
                db.rollback()
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(RegionalPortalSpawnState.id).where(
                RegionalPortalSpawnState.campaign_id == self.campaign_id,
            )), None)
            self.assertEqual(db.scalar(select(RegionalEvent.id).where(
                RegionalEvent.campaign_id == self.campaign_id,
                RegionalEvent.event_type == "portal",
            )), None)

    def test_concurrent_same_cycle_creates_one_portal_and_one_state(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            configure_database(f"sqlite:///{(Path(temp_dir.name) / 'portal-race.db').resolve().as_posix()}")
            Base.metadata.create_all(bind=get_engine())
            with SessionLocal() as db:
                db.add(CampaignMetadata(
                    campaign_id=self.campaign_id,
                    campaign_name="Portal race",
                    created_at_utc=self.now,
                ))
                self._add_content(db)
                db.add(RegionalRegionState(
                    campaign_id=self.campaign_id,
                    region_code="vale-norte",
                    region_name="Vale do Norte",
                ))
                db.add(self._cycle(1, self.now + timedelta(hours=6)))
                db.commit()
            barrier = Barrier(2)

            def generate():
                with SessionLocal() as db:
                    cycle = db.scalar(select(RegionalCycle).where(
                        RegionalCycle.campaign_id == self.campaign_id,
                        RegionalCycle.cycle_number == 1,
                    ))
                    region = self._region(db)
                    barrier.wait(timeout=5)
                    create_cycle_portals(db, self.campaign_id, cycle, [region])
                    db.commit()

            with patch("app.services.regional_event_service._rng", side_effect=lambda *_: FixedRng(0.0)):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(generate) for _ in range(2)]
                    for future in futures:
                        future.result(timeout=10)
            with SessionLocal() as db:
                self.assertEqual(db.scalar(select(RegionalPortalSpawnState.id).where(
                    RegionalPortalSpawnState.campaign_id == self.campaign_id,
                )), 1)
                self.assertEqual(len(list(db.scalars(select(RegionalEvent).where(
                    RegionalEvent.campaign_id == self.campaign_id,
                    RegionalEvent.event_type == "portal",
                )))), 1)
        finally:
            configure_database("sqlite:///:memory:")
            temp_dir.cleanup()


class RegionalPortalSpawnMigrationTests(unittest.TestCase):
    def test_additive_migration_preserves_existing_cycles_as_unmarked(self):
        migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "f31a9c7d2b84_add_versioned_portal_spawn_state.py"
        spec = importlib.util.spec_from_file_location("portal_spawn_migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE campaign_metadata (campaign_id VARCHAR(36) PRIMARY KEY)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE regional_cycles (id INTEGER PRIMARY KEY, campaign_id VARCHAR(36) NOT NULL, cycle_number INTEGER NOT NULL)"
                )
                connection.exec_driver_sql("INSERT INTO campaign_metadata(campaign_id) VALUES ('save-old')")
                connection.exec_driver_sql(
                    "INSERT INTO regional_cycles(id, campaign_id, cycle_number) VALUES (1, 'save-old', 1)"
                )
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                inspector = inspect(connection)
                self.assertIn("portal_spawn_rules_version", {
                    column["name"] for column in inspector.get_columns("regional_cycles")
                })
                self.assertIn("regional_portal_spawn_state", inspector.get_table_names())
                self.assertIsNone(connection.exec_driver_sql(
                    "SELECT portal_spawn_rules_version FROM regional_cycles WHERE id=1"
                ).scalar_one())
                self.assertEqual(
                    str(connection.exec_driver_sql(
                        "PRAGMA table_info(regional_portal_spawn_state)"
                    ).fetchall()[3][4]).strip("'\""),
                    "0",
                )
                with Operations.context(MigrationContext.configure(connection)):
                    migration.downgrade()
                self.assertNotIn("regional_portal_spawn_state", inspect(connection).get_table_names())
                self.assertNotIn("portal_spawn_rules_version", {
                    column["name"] for column in inspect(connection).get_columns("regional_cycles")
                })
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
