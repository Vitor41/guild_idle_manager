from datetime import datetime, timedelta, timezone
from contextlib import closing
import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database, get_engine
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.desktop.lifecycle import (
    close_campaign,
    close_suspended_campaigns,
    open_campaign,
    suspend_campaign,
)
from app.models import CampaignMetadata, GuildResources
from app.services.campaign_service import CampaignService


class FakeClock:
    def __init__(self, now: datetime):
        self.now = now
        self.monotonic = 10.0

    def wall(self) -> datetime:
        return self.now

    def tick(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)
        self.monotonic += seconds


class ClockGuardTests(unittest.TestCase):
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
