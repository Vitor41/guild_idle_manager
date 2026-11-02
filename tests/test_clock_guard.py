from datetime import datetime, timedelta, timezone
from contextlib import closing, contextmanager
import gc
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database, get_engine
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore, project_stamina_after_active_seconds
from app.desktop.lifecycle import (
    close_campaign,
    close_suspended_campaigns,
    open_campaign,
    suspend_campaign,
)
from app.models import (
    BuildingTemplate, CampaignMetadata, DungeonTemplate, Guild, GuildBuilding,
    GuildResources, Mercenary, MercenaryClass,
)
from app.models.dungeon import DungeonRun
from app.models.item import GuildItemInstance
from app.models.regional import (
    RegionalEvent, RegionalEventActivity, RegionalEventParticipant,
)
from app.repositories.mercenary_repository import create_mercenary
from app.services.campaign_service import CampaignService
from app.services.dungeon_service import claim_dungeon_loot, start_dungeon
from app.services.regional_cycle_service import (
    REGIONS, ensure_campaign_world, get_current_player_regional_guild,
)
from app.services.regional_event_service import (
    active_portals_for_region, attach_event_activity,
    build_portal_boss_snapshot, build_portal_loot_snapshot,
)
from app.services import dungeon_service


class FakeClock:
    def __init__(self, now: datetime):
        self.now = now
        self.monotonic = 10.0

    def wall(self) -> datetime:
        return self.now

    def tick(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)
        self.monotonic += seconds


@contextmanager
def temporary_campaign_saves():
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            yield temp_dir
        finally:
            configure_database("sqlite:///:memory:")


class ClockGuardTests(unittest.TestCase):
    def test_stamina_status_projects_active_recharge_without_mutating_balance(self):
        balance = 4 * 3600
        remainder = 1800
        clock = [1800.0]
        guard = ClockGuard(MemoryAnchorStore(), monotonic_clock=lambda: clock[0])
        guard._session_started["campaign-preview"] = 0.0

        status = guard.preview_active_stamina("campaign-preview", balance, remainder)

        self.assertEqual(project_stamina_after_active_seconds(balance, remainder, 1799), (balance, 3599))
        self.assertEqual(status["stamina_seconds"], 6 * 3600)
        self.assertEqual(status["recharge_remainder_seconds"], 0)
        self.assertEqual(status["seconds_until_recharge"], 3600)
        self.assertEqual(project_stamina_after_active_seconds(7 * 3600, 3599, 1), (8 * 3600, 0))
        self.assertEqual((balance, remainder), (4 * 3600, 1800))

    def tearDown(self):
        configure_database("sqlite:///:memory:")
        gc.collect()

    def test_matrix_minimum_cap_rollback_and_import_anchor(self):
        store = MemoryAnchorStore()
        close = datetime(2026, 1, 1, tzinfo=timezone.utc)
        now = [close]
        guard = ClockGuard(store, wall_clock=lambda: now[0])
        store.save("campaign-a", close)

        below_minimum = guard.evaluate_return("campaign-a", "offline", close, close + timedelta(minutes=4))
        self.assertEqual(below_minimum.credited_seconds, 0)
        normal = guard.evaluate_return("campaign-a", "offline", close, close + timedelta(minutes=30))
        self.assertEqual(normal.credited_seconds, 30 * 60)
        capped = guard.evaluate_return("campaign-a", "offline", close, close + timedelta(hours=10))
        self.assertEqual(capped.credited_seconds, 8 * 60 * 60)

        rolled_back = guard.evaluate_return("campaign-a", "offline", close, close - timedelta(seconds=1))
        self.assertEqual(rolled_back.credited_seconds, 0)
        self.assertIn("voltou", rolled_back.warning)
        imported = guard.evaluate_return("campaign-b", "created", close - timedelta(days=2), close)
        self.assertEqual(imported.credited_seconds, 0)

    def test_only_explicit_offline_mode_awards_and_report_waits_for_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Teste do relogio")
            fake = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
            guard = ClockGuard(MemoryAnchorStore(), fake.wall, lambda: fake.monotonic)

            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            guard.activate_campaign(campaign.campaign_id)
            guard.close_campaign(campaign.campaign_id, campaigns)
            fake.tick(30 * 60)

            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            summary = guard.activate_campaign(campaign.campaign_id)
            self.assertIsNone(summary)
            with SessionLocal() as db:
                resources = db.scalar(select(GuildResources))
                self.assertEqual(resources.gold, 100)

            guard.suspend_campaign(campaign.campaign_id)
            campaigns.suspend_active_campaign(campaign.campaign_id, offline_started_at=fake.now)
            fake.tick(30 * 60)
            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            report = guard.activate_campaign(campaign.campaign_id)
            self.assertEqual(report["credited_seconds"], 30 * 60)
            self.assertIn("guild_production", report["gold_sources"])
            self.assertIn("warehouse", report["gold_sources"])
            self.assertEqual(sum(report["gold_sources"].values()), report["gold"])
            self.assertEqual(report["regional_context"]["cycle_number"], 1)
            self.assertIn("active_portals", report["regional_context"])
            with SessionLocal() as db:
                resources = db.scalar(select(GuildResources))
                metadata = db.get(CampaignMetadata, campaign.campaign_id)
                self.assertEqual(resources.gold, 102)
                self.assertEqual(metadata.stamina_seconds, 7 * 60 * 60 + 30 * 60)
                self.assertEqual(metadata.last_session_state, "active")
                self.assertIsNotNone(metadata.pending_offline_report)
            self.assertTrue(guard.acknowledge_offline_report(campaign.campaign_id, report["report_id"]))
            self.assertTrue(guard.acknowledge_offline_report(campaign.campaign_id, report["report_id"]))
            campaigns.close_active_campaign(campaign.campaign_id)

    def test_regional_catchup_runs_when_offline_stamina_is_empty_without_rewards(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Vigilia sem estamina")
            fake = FakeClock(campaign.created_at_utc + timedelta(seconds=1))
            guard = ClockGuard(MemoryAnchorStore(), fake.wall, lambda: fake.monotonic)
            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            guard.activate_campaign(campaign.campaign_id)
            guard.suspend_campaign(campaign.campaign_id)
            campaigns.suspend_active_campaign(campaign.campaign_id, offline_started_at=fake.now)
            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            with SessionLocal() as db:
                metadata = db.get(CampaignMetadata, campaign.campaign_id)
                metadata.stamina_seconds = 0
                db.commit()
                before_gold = db.scalar(select(GuildResources)).gold
            fake.tick(12 * 60 * 60)
            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            report = guard.activate_campaign(campaign.campaign_id)
            self.assertEqual(report["credited_seconds"], 0)
            self.assertEqual(report["gold"], 0)
            self.assertEqual(report["regional_context"]["cycle_number"], 3)
            self.assertEqual(report["regional_context"]["cycles_processed"], 2)
            with SessionLocal() as db:
                self.assertEqual(db.scalar(select(GuildResources)).gold, before_gold)
                metadata = db.get(CampaignMetadata, campaign.campaign_id)
                self.assertIsNotNone(metadata.pending_offline_report)
            guard.close_campaign(campaign.campaign_id, campaigns)

    def test_offline_portal_deadline_waits_for_started_dungeon_and_reward_is_not_duplicated(self):
        with temporary_campaign_saves() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Portal durante ausencia")
            base = campaign.created_at_utc
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            fake = FakeClock(base + timedelta(minutes=1))
            store = MemoryAnchorStore()
            guard = ClockGuard(store, fake.wall, lambda: fake.monotonic)

            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            guard.activate_campaign(campaign.campaign_id)
            with SessionLocal() as db:
                metadata = db.get(CampaignMetadata, campaign.campaign_id)
                guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign.campaign_id))
                resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild.id))
                scout_template = db.scalar(select(BuildingTemplate).where(BuildingTemplate.effect_type == "scouts"))
                portal_template = db.scalar(select(DungeonTemplate).where(
                    DungeonTemplate.is_active.is_(True),
                    DungeonTemplate.content_type == "boss",
                    DungeonTemplate.biome == "portal",
                ).order_by(DungeonTemplate.id))
                mercenary_class = db.scalar(select(MercenaryClass).where(MercenaryClass.is_active.is_(True)))
                self.assertIsNotNone(scout_template)
                self.assertIsNotNone(portal_template)
                self.assertIsNotNone(mercenary_class)
                db.add(GuildBuilding(guild_id=guild.id, building_template_id=scout_template.id, level=1))
                mercenary = create_mercenary(db, guild.id, mercenary_class, "Equipe do portal")
                db.flush()
                ensure_campaign_world(db, metadata, guild)
                player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
                home_code = next(code for code, name in REGIONS if name == metadata.home_region)

                # Relax only the frozen fixture snapshot so one seeded guild can
                # reach the actual dungeon-service lifecycle; no catalog rule changes.
                boss_snapshot = build_portal_boss_snapshot(portal_template)
                boss_snapshot.update({
                    "min_party_size": 1, "max_party_size": 1,
                    "required_guild_level": 1, "required_min_mercenary_level": 1,
                    "required_building_type": None, "required_building_level": 0,
                    "required_total_power": 0, "required_class_code": None,
                    "required_tank_count": 0, "required_support_count": 0,
                    "required_damage_count": 0, "required_equipment_tier": 0,
                    "duration_seconds": 3600, "base_gold_reward": 100,
                    "base_xp_reward": 100, "base_success_chance": 95,
                })
                event_seed = "fixture-active-portal-no-natural-roll"
                portal_event = RegionalEvent(
                    campaign_id=campaign.campaign_id,
                    event_type="portal", region_code=home_code,
                    trigger_cycle_number=0, rules_version="regional-events-v1",
                    seed=event_seed, status="active",
                    dungeon_template_id=portal_template.id,
                    created_at_utc=fake.now,
                    expires_at_utc=fake.now + timedelta(hours=3),
                    summary_json=json.dumps({
                        "portal_boss": {"version": "portal-boss-v1", "template": boss_snapshot},
                        "portal_loot": build_portal_loot_snapshot(db, portal_template, event_seed),
                    }),
                )
                db.add(portal_event)
                db.flush()
                event_id = portal_event.id
                start_time = fake.now + timedelta(minutes=30)
                fake.now = start_time
                with patch.object(dungeon_service, "utc_now", return_value=start_time):
                    run = start_dungeon(
                        db, guild, str(portal_template.id), [str(mercenary.id)],
                        commit=False,
                        regional_duration_seconds=6 * 3600,
                        regional_min_duration_seconds=6 * 3600,
                        template_snapshot=boss_snapshot,
                    )
                    activity = attach_event_activity(db, portal_event, player_state, "dungeon", run.id)
                db.commit()
                run_id = run.id
                guild_id = guild.id
                mercenary_id = mercenary.id
                activity_id = activity.id
                run_end = run.ends_at
                if run_end.tzinfo is None:
                    run_end = run_end.replace(tzinfo=timezone.utc)
                initial_gold = int(resources.gold)
                self.assertEqual(activity.status, "in_progress")
                self.assertEqual(db.get(Mercenary, mercenary_id).status, "busy")
                self.assertGreaterEqual((run.ends_at - run.started_at).total_seconds(), 3600)

            # Begin offline before the portal deadline and return after it, while
            # the six-hour dungeon run remains unfinished.
            offline_start = guard.suspend_campaign(campaign.campaign_id)
            fake.tick(4 * 3600)
            offline_return = fake.now
            self.assertGreater(offline_return, base + timedelta(hours=3))
            self.assertLess(offline_return, run_end)
            offline_summary = guard.activate_campaign(campaign.campaign_id)
            self.assertIsNotNone(offline_summary)
            self.assertGreater(offline_summary["elapsed_seconds"], 3 * 3600)
            self.assertEqual(offline_summary["elapsed_seconds"], 4 * 3600)

            with SessionLocal() as db:
                event = db.get(RegionalEvent, event_id)
                run = db.get(DungeonRun, run_id)
                activity = db.get(RegionalEventActivity, activity_id)
                participant = db.scalar(select(RegionalEventParticipant).where(
                    RegionalEventParticipant.event_id == event_id,
                ))
                resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))
                stored_report = json.loads(db.get(CampaignMetadata, campaign.campaign_id).pending_offline_report)
                event_summary = json.loads(event.summary_json)
                self.assertLess(event.expires_at_utc.replace(tzinfo=timezone.utc), offline_return)
                self.assertEqual(event.status, "in_progress")
                self.assertEqual(event_summary["reason"], "deadline_elapsed_waiting_for_started_activities")
                self.assertFalse(event_summary["new_entries_after_expiry"])
                self.assertTrue(event_summary["started_activities_may_finish"])
                self.assertEqual(active_portals_for_region(db, campaign.campaign_id, event.region_code), [])
                self.assertEqual(run.status, "in_progress")
                self.assertEqual(activity.status, "in_progress")
                self.assertEqual(participant.status, "participating")
                self.assertEqual(db.get(Mercenary, mercenary_id).status, "busy")
                self.assertEqual(
                    stored_report["regional_context"]["recent_events"][0]["status"],
                    "in_progress",
                )
                self.assertEqual(stored_report["regional_context"]["active_portals"], 0)
                self.assertEqual(stored_report["elapsed_seconds"], 4 * 3600)
                gold_after_catchup = int(resources.gold)
                offline_gold = int(offline_summary["gold"])
                self.assertEqual(gold_after_catchup - initial_gold, offline_gold)

                # Complete the pre-deadline run through the real reward service.
                # The success roll is fixed only for this isolated fixture so the
                # test verifies the reward ledger and delayed event finalization.
                with patch.object(dungeon_service, "utc_now", return_value=run_end), patch.object(
                    dungeon_service, "randint", return_value=1,
                ):
                    resolved = claim_dungeon_loot(db, db.get(Guild, guild_id), resources, run_id)
                db.refresh(event)
                db.refresh(resources)
                self.assertEqual(resolved.status, "completed")
                self.assertTrue(resolved.success)
                self.assertGreater(resolved.gold_reward, 0)
                self.assertEqual(event.status, "resolved")
                self.assertEqual(db.get(RegionalEventActivity, activity_id).status, "resolved")
                self.assertEqual(db.get(RegionalEventParticipant, participant.id).status, "resolved")
                self.assertEqual(db.get(Mercenary, mercenary_id).status, "available")
                final_gold = int(resources.gold)
                self.assertEqual(final_gold - gold_after_catchup, int(resolved.gold_reward))
                item_instances_after_claim = int(db.query(GuildItemInstance).filter_by(guild_id=guild_id).count())
                self.assertEqual(final_gold, initial_gold + offline_gold + int(resolved.gold_reward))
                guild_after_claim = db.get(Guild, guild_id)
                mercenary_after_claim = db.get(Mercenary, mercenary_id)
                xp_after_claim = (int(guild_after_claim.xp), int(mercenary_after_claim.xp))

                with self.assertRaises(dungeon_service.DungeonError):
                    claim_dungeon_loot(db, guild_after_claim, resources, run_id)
                db.refresh(resources)
                db.refresh(guild_after_claim)
                db.refresh(mercenary_after_claim)
                self.assertEqual(int(resources.gold), final_gold)
                self.assertEqual(
                    (int(guild_after_claim.xp), int(mercenary_after_claim.xp)),
                    xp_after_claim,
                )
                self.assertEqual(
                    int(db.query(GuildItemInstance).filter_by(guild_id=guild_id).count()),
                    item_instances_after_claim,
                )

            # Reopening the same pending offline report is idempotent and must not
            # apply either the offline credit or the dungeon reward a second time.
            repeated_summary = guard.activate_campaign(campaign.campaign_id)
            self.assertEqual(repeated_summary, offline_summary)
            with SessionLocal() as db:
                resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))
                event = db.get(RegionalEvent, event_id)
                run = db.get(DungeonRun, run_id)
                self.assertEqual(int(resources.gold), final_gold)
                self.assertEqual(event.status, "resolved")
                self.assertEqual(run.status, "completed")
                self.assertEqual(
                    int(db.query(GuildItemInstance).filter_by(guild_id=guild_id).count()),
                    item_instances_after_claim,
                )
                persisted_report = json.loads(db.get(CampaignMetadata, campaign.campaign_id).pending_offline_report)
                self.assertEqual(persisted_report["regional_context"]["recent_events"][0]["status"], "in_progress")
            self.assertGreaterEqual(offline_start, base)
            guard.close_campaign(campaign.campaign_id, campaigns)

    def test_crystal_is_granted_once_at_cap_and_survives_reopen(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Cristal no cap")
            fake = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
            guard = ClockGuard(MemoryAnchorStore(), fake.wall, lambda: fake.monotonic)

            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            guard.activate_campaign(campaign.campaign_id)
            guard.suspend_campaign(campaign.campaign_id)
            campaigns.suspend_active_campaign(campaign.campaign_id, offline_started_at=fake.now)
            fake.tick(8 * 60 * 60)

            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            report = guard.activate_campaign(campaign.campaign_id)
            self.assertEqual(report["credited_seconds"], 8 * 60 * 60)
            self.assertEqual(sum(report["gold_sources"].values()), report["gold"])
            self.assertEqual(report["crystals"], 1)
            self.assertEqual(report["materials"]["crystals"], 1)
            with SessionLocal() as db:
                resources = db.scalar(select(GuildResources))
                self.assertEqual(resources.crystals, 1)
                self.assertEqual(resources.crystal_reserve, 1)
                from app.repositories.item_repository import sync_inventory_resource_totals
                sync_inventory_resource_totals(db, resources)
                self.assertEqual(resources.crystals, 1)
            reopened = guard.activate_campaign(campaign.campaign_id)
            self.assertEqual(reopened["report_id"], report["report_id"])
            with SessionLocal() as db:
                resources = db.scalar(select(GuildResources))
                self.assertEqual(resources.crystals, 1)
            configure_database("sqlite:///:memory:")
            gc.collect()

    def test_import_initializes_new_anchor_without_crediting_pre_import_time(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            campaigns = CampaignService(root / "saves")
            original = campaigns.create_campaign("Importada")
            closed_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
            with closing(sqlite3.connect(original.database_path)) as connection:
                connection.execute(
                    "UPDATE campaign_metadata SET last_session_state = 'offline', last_clean_shutdown_utc = ?",
                    (closed_at.isoformat(),),
                )
                connection.commit()
            export_path = root / "export.gimcampaign"
            campaigns.export_campaign(original.campaign_id, export_path)
            imported = campaigns.import_campaign(export_path)

            fake = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
            store = MemoryAnchorStore()
            guard = ClockGuard(store, fake.wall, lambda: fake.monotonic)
            guard.initialize_campaign(imported.campaign_id)
            self.assertEqual(store.load(imported.campaign_id)["high_water_utc"], fake.now.isoformat())
            decision = guard.evaluate_return(
                imported.campaign_id,
                imported.last_session_state,
                imported.last_clean_shutdown_utc,
                fake.now + timedelta(days=2),
            )
            self.assertEqual(decision.credited_seconds, 0)

    def test_clock_anchor_high_water_blocks_rewind_after_eight_hour_cap(self):
        store = MemoryAnchorStore()
        closed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        future = closed + timedelta(hours=10)
        store.save("campaign-cap", closed)
        guard = ClockGuard(store, wall_clock=lambda: future)
        capped = guard.evaluate_return("campaign-cap", "offline", closed, future)
        self.assertEqual(capped.credited_seconds, 8 * 60 * 60)
        store.save("campaign-cap", future)

        rewound = guard.evaluate_return("campaign-cap", "offline", closed, closed + timedelta(hours=2))

        self.assertEqual(rewound.credited_seconds, 0)
        self.assertIn("voltou", rewound.warning)
        self.assertEqual(store.load("campaign-cap")["high_water_utc"], future.isoformat())

    def test_missing_or_corrupt_anchor_and_unclean_exit_grant_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Preservada")
            before = campaign.database_path.read_bytes()
            now = datetime(2026, 1, 2, tzinfo=timezone.utc)
            store = MemoryAnchorStore()
            guard = ClockGuard(store, wall_clock=lambda: now)

            missing = guard.evaluate_return(campaign.campaign_id, "offline", now - timedelta(days=2), now)
            self.assertEqual(missing.credited_seconds, 0)
            self.assertIn("não foi encontrada", missing.warning.lower())
            store.values[campaign.campaign_id] = {"campaign_id": campaign.campaign_id, "high_water_utc": "invalid"}
            corrupt = guard.evaluate_return(campaign.campaign_id, "offline", now - timedelta(days=2), now)
            self.assertEqual(corrupt.credited_seconds, 0)
            self.assertIn("inválida", corrupt.warning.lower())
            interrupted = guard.evaluate_return(campaign.campaign_id, "active", now - timedelta(days=2), now)
            self.assertEqual(interrupted.credited_seconds, 0)
            self.assertIn("não foi encerrada corretamente", interrupted.warning.lower())
            self.assertEqual(campaign.database_path.read_bytes(), before)

    def test_active_duration_uses_monotonic_clock_when_wall_clock_moves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Tempo monotônico")
            fake = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
            guard = ClockGuard(MemoryAnchorStore(), fake.wall, lambda: fake.monotonic)
            campaigns.activate_campaign(campaign.campaign_id, mark_active=False)
            guard.activate_campaign(campaign.campaign_id)

            fake.monotonic += 125
            fake.now -= timedelta(days=4)
            active_seconds = guard.close_campaign(campaign.campaign_id, campaigns)

            self.assertEqual(active_seconds, 125)

    def test_native_bridge_javascript_names_match_exposed_python_methods(self):
        import re
        from app.desktop.bridge import DesktopBridge

        js_path = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "desktop-campaigns.js"
        called = set(re.findall(r'nativeCall\("([a-z_]+)"', js_path.read_text(encoding="utf-8")))
        exposed = {name for name in dir(DesktopBridge) if not name.startswith("_") and callable(getattr(DesktopBridge, name))}
        self.assertEqual(called, {"import_campaign", "export_campaign", "confirm_export", "restore_backup"})
        self.assertTrue(called <= exposed)

    def test_active_campaign_cannot_be_abandoned_when_opening_another(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                first = campaigns.create_campaign("Primeira")
                second = campaigns.create_campaign("Segunda")
                fake = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
                guard = ClockGuard(MemoryAnchorStore(), fake.wall, lambda: fake.monotonic)
                app = FastAPI()
                app.state.active_campaign = None
                app.state.suspended_campaigns = set()

                open_campaign(app, campaigns, guard, first.campaign_id)
                with self.assertRaisesRegex(ValueError, "feche a campanha atual"):
                    open_campaign(app, campaigns, guard, second.campaign_id)
                self.assertEqual(app.state.active_campaign.campaign_id, first.campaign_id)
                self.assertEqual(Path(get_engine().url.database).resolve(), first.database_path.resolve())

                suspend_campaign(app, campaigns, guard)
                self.assertIsNone(app.state.active_campaign)
                reopened_same_process, same_process_summary = open_campaign(app, campaigns, guard, first.campaign_id)
                self.assertEqual(reopened_same_process.campaign_id, first.campaign_id)
                self.assertIsNone(same_process_summary)
                with SessionLocal() as db:
                    self.assertEqual(db.scalar(select(GuildResources)).gold, 100)
                suspend_campaign(app, campaigns, guard)

                open_campaign(app, campaigns, guard, second.campaign_id)
                close_campaign(app, campaigns, guard)
                close_suspended_campaigns(app, campaigns, guard)
                fake.tick(30 * 60)

                restarted_app = FastAPI()
                restarted_app.state.active_campaign = None
                restarted_app.state.suspended_campaigns = set()
                reopened_first, summary = open_campaign(restarted_app, campaigns, guard, first.campaign_id)
                self.assertEqual(reopened_first.campaign_id, first.campaign_id)
                self.assertIsNone(summary)
                with SessionLocal() as db:
                    resources = db.scalar(select(GuildResources))
                    self.assertEqual(resources.gold, 100)
                _, immediate_summary = open_campaign(restarted_app, campaigns, guard, first.campaign_id)
                self.assertIsNone(immediate_summary)
                with SessionLocal() as db:
                    self.assertEqual(db.scalar(select(GuildResources)).gold, 100)
                close_campaign(restarted_app, campaigns, guard)
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def test_suspended_campaign_is_cleanly_closed_when_process_exits_from_menu(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Menu de campanhas")
            fake = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
            guard = ClockGuard(MemoryAnchorStore(), fake.wall, lambda: fake.monotonic)
            app = FastAPI()
            app.state.active_campaign = None
            app.state.suspended_campaigns = set()
            open_campaign(app, campaigns, guard, campaign.campaign_id)
            suspend_campaign(app, campaigns, guard)
            self.assertIsNone(app.state.active_campaign)

            close_suspended_campaigns(app, campaigns, guard)

            self.assertFalse(app.state.suspended_campaigns)
            self.assertEqual(campaigns.inspect_campaign(campaign.campaign_id).last_session_state, "offline")

    def test_explicit_offline_period_after_app_exit_is_credited_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Modo offline")
            fake = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
            guard = ClockGuard(MemoryAnchorStore(), fake.wall, lambda: fake.monotonic)
            app = FastAPI()
            app.state.active_campaign = None
            app.state.suspended_campaigns = set()
            open_campaign(app, campaigns, guard, campaign.campaign_id)
            suspend_campaign(app, campaigns, guard)
            close_suspended_campaigns(app, campaigns, guard)

            fake.tick(30 * 60)
            restarted_app = FastAPI()
            restarted_app.state.active_campaign = None
            restarted_app.state.suspended_campaigns = set()
            _info, report = open_campaign(restarted_app, campaigns, guard, campaign.campaign_id)
            self.assertEqual(report["credited_seconds"], 30 * 60)
            with SessionLocal() as db:
                self.assertEqual(db.scalar(select(GuildResources)).gold, 102)
            close_campaign(restarted_app, campaigns, guard)


if __name__ == "__main__":
    unittest.main()
