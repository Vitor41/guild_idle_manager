import gc
from contextlib import closing
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta, timezone, datetime
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from alembic import command
from fastapi import FastAPI, Request
import sqlite3
from sqlalchemy import func, select, text

from app.database.connection import SessionLocal, configure_database
from app.core.dependencies import CampaignPlayer
from app.models import (
    CraftingRecipe,
    CampaignMetadata,
    DockOffer,
    DungeonRun,
    DungeonTemplate,
    GuildItemInstance,
    GuildInventoryItem,
    ItemTemplate,
    Mercenary,
    MissionTemplate,
    MissionTemplateItemDrop,
    MissionRun,
    ProfessionTemplate,
    User,
)
from app.repositories.item_repository import RESOURCE_MATERIAL_FAMILIES, add_inventory_quantity
from app.repositories.building_repository import get_guild_building_by_effect
from app.services.building_service import ensure_guild_buildings, upgrade_guild_building
from app.services.campaign_service import CampaignService
from app.services.dungeon_service import claim_dungeon_loot, get_advanced_dungeon_chance, get_dungeons_page_context, start_dungeon
from app.services.achievement_service import evaluate_achievements, get_codex_context, sync_codex
from app.services.crafting_service import craft_recipe, get_blacksmith_context
from app.services.dock_service import buy_dock_offer, create_dock_rotation, get_docks_context
from app.services.equipment_service import create_equipment_instance_from_template, equip_item
from app.services.guild_service import get_current_guild_context
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.market_service import collect_market_sale, get_market_page_context, start_material_sale
from app.services.mission_service import claim_mission_loot, get_missions_page_context, start_mission
from app.services.profession_service import complete_profession_training, get_professions_context, start_profession_training
from app.services.tavern_service import generate_apprentice_preview, get_tavern_page_context, hire_apprentice, tavern_summary
from app.routes.tavern_routes import _get_apprentice_preview


class CampaignServiceTests(unittest.TestCase):
    def test_desktop_home_without_campaign_uses_asgi_and_omits_session_expiry(self):
        script = r'''
import asyncio
from app.main import app
app.state.desktop_allowed_host = "localhost"
app.state.desktop_allowed_origin = "http://localhost"

async def main():
    sent = []
    first_receive = True
    async def receive():
        nonlocal first_receive
        if first_receive:
            first_receive = False
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}
    async def send(message):
        sent.append(message)
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": "/", "raw_path": b"/", "query_string": b"",
        "headers": [(b"host", b"localhost")], "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 12345),
    }
    await app(scope, receive, send)
    status = sent[0]["status"]
    headers = dict(sent[0]["headers"])
    body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    paths = set(app.openapi()["paths"])
    assert status == 303, status
    assert headers[b"location"] == b"/desktop/campaigns"
    assert b"/login" not in body and b"/register" not in body
    assert "/login" not in paths and "/register" not in paths
    assert not any(middleware.cls.__name__ == "SessionMiddleware" for middleware in app.user_middleware)
    assert b"data-session-started-at" not in body

asyncio.run(main())
'''
        environment = os.environ.copy()
        environment["APP_MODE"] = "desktop"
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_two_campaigns_create_open_and_persist_in_isolation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                self._assert_campaigns_are_isolated(Path(temp_dir))
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def _assert_campaigns_are_isolated(self, temp_path: Path) -> None:
        campaigns = CampaignService(temp_path / "saves")
        first = campaigns.create_campaign("Campanha Norte", "Guilda Norte")
        second = campaigns.create_campaign("Campanha Sul", "Guilda Sul")
        self.assertEqual(first.stamina_seconds, 8 * 60 * 60)
        self.assertEqual(first.stamina_recharge_remainder_seconds, 0)

        self.assertNotEqual(first.campaign_id, second.campaign_id)
        self.assertNotEqual(first.database_path, second.database_path)
        self.assertEqual(len(campaigns.list_campaigns()), 2)
        with closing(sqlite3.connect(first.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone()[0], "b1c2d3e4f5a6")

        campaigns.activate_campaign(first.campaign_id)
        with SessionLocal() as db:
            guild, resources = get_current_guild_context(db, first.campaign_id)
            self.assertIsNotNone(guild)
            self.assertEqual(guild.name, "Guilda Norte")
            self.assertIsNotNone(resources)
            resources.gold = 321
            db.commit()
            self.assertEqual(db.scalar(select(func.count(User.id))), 0)
            self.assertEqual(db.scalar(select(func.count(CampaignMetadata.campaign_id))), 1)
            self.assertEqual(db.scalar(text("PRAGMA foreign_keys")), 1)
            content_count = db.scalar(select(func.count(MissionTemplate.id)))
            self.assertGreater(content_count, 0)
            # The normal fresh-campaign path applies the full campaign catalog
            # before returning. Prove the first real Vigília can use it without
            # fixture-only seeding or a ClockGuard fallback.
            from app.services.regional_cycle_service import get_regional_board
            campaign_metadata = db.get(CampaignMetadata, first.campaign_id)
            regional_board = get_regional_board(db, campaign_metadata, guild)
            self.assertEqual(regional_board["cycle"].cycle_number, 0)
            self.assertEqual(len(regional_board["offers"]["contract"]), 10)
            self.assertEqual(len(regional_board["offers"]["dungeon"]), 3)
            self.assertEqual(len(regional_board["offers"]["boss"]), 1)

        campaigns.activate_campaign(second.campaign_id)
        with SessionLocal() as db:
            guild, resources = get_current_guild_context(db, second.campaign_id)
            self.assertIsNotNone(guild)
            self.assertEqual(guild.name, "Guilda Sul")
            self.assertIsNotNone(resources)
            self.assertEqual(resources.gold, 100)
            self.assertEqual(db.scalar(select(func.count(Mercenary.id))), 0)
            self.assertEqual(db.scalar(select(func.count(GuildInventoryItem.id))), 0)
            self.assertEqual(db.scalar(select(func.count(GuildItemInstance.id))), 0)
            self.assertEqual(db.scalar(select(func.count(MissionRun.id))), 0)
            self.assertEqual(db.scalar(select(func.count(DungeonRun.id))), 0)

        campaigns.activate_campaign(first.campaign_id)
        with SessionLocal() as db:
            guild, resources = get_current_guild_context(db, first.campaign_id)
            self.assertIsNotNone(guild)
            self.assertEqual(guild.name, "Guilda Norte")
            self.assertIsNotNone(resources)
            self.assertEqual(resources.gold, 321)
            self.assertEqual(db.scalar(select(func.count(MissionTemplate.id))), content_count)
            self._exercise_gameplay(db, guild, resources)
            preferences = db.get(CampaignMetadata, first.campaign_id)
            preferences.tutorial_status = "completed"
            preferences.confirmation_preferences = '{"dismiss_mercenary":false}'
            db.commit()

        campaigns.activate_campaign(second.campaign_id)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count(Mercenary.id))), 0)
            self.assertEqual(db.scalar(select(func.count(GuildInventoryItem.id))), 0)
            self.assertEqual(db.scalar(select(func.count(GuildItemInstance.id))), 0)
            self.assertEqual(db.scalar(select(func.count(MissionRun.id))), 0)
            self.assertEqual(db.scalar(select(func.count(DungeonRun.id))), 0)

        reopened = campaigns.activate_campaign(first.campaign_id)
        self.assertEqual(reopened.campaign_id, first.campaign_id)
        self.assertEqual(reopened.campaign_name, "Campanha Norte")
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count(Mercenary.id))), 2)
            self.assertGreater(db.scalar(select(func.count(GuildInventoryItem.id))), 0)
            self.assertGreater(db.scalar(select(func.count(MissionRun.id))), 0)
            self.assertGreater(db.scalar(select(func.count(DungeonRun.id))), 0)
        campaigns.close_active_campaign(first.campaign_id)
        closed = campaigns.inspect_campaign(first.campaign_id)
        self.assertEqual(closed.last_session_state, "closed")
        self.assertIsNotNone(closed.last_clean_shutdown_utc)
        campaigns.activate_campaign(first.campaign_id)
        with SessionLocal() as db:
            preferences = db.get(CampaignMetadata, first.campaign_id)
            self.assertEqual(preferences.tutorial_status, "completed")
            self.assertEqual(preferences.confirmation_preferences, '{"dismiss_mercenary":false}')
            self.assertEqual(db.scalar(select(func.count(Mercenary.id))), 2)
            self.assertGreater(db.scalar(select(func.count(GuildInventoryItem.id))), 0)
            self.assertGreater(db.scalar(select(func.count(MissionRun.id))), 0)
            self.assertGreater(db.scalar(select(func.count(DungeonRun.id))), 0)

    def test_listing_campaigns_does_not_migrate_or_back_up_saves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            campaign_id = str(uuid4())
            database_path = saves / f"{campaign_id}.db"
            campaigns = CampaignService(saves)
            command.upgrade(campaigns._alembic_config(database_path), "c9d0e1f2a3b4")
            before = database_path.read_bytes()

            listing = campaigns.list_campaigns()
            self.assertEqual(listing, [])
            self.assertEqual(len(listing.unavailable), 1)
            self.assertTrue(listing.unavailable[0]["reason"])
            self.assertEqual(database_path.read_bytes(), before)
            self.assertFalse((Path(temp_dir) / "backups").exists())

    def test_partial_unversioned_save_is_rejected_without_stamping_or_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            campaign_id = str(uuid4())
            database_path = saves / f"{campaign_id}.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE campaign_metadata "
                    "(campaign_id TEXT PRIMARY KEY, campaign_name TEXT, schema_version INTEGER, content_version INTEGER)"
                )
                connection.execute("INSERT INTO campaign_metadata VALUES (?, ?, ?, ?)", (campaign_id, "Parcial", 1, 0))
                connection.execute("CREATE TABLE guilds (id INTEGER PRIMARY KEY, campaign_id TEXT)")
                connection.commit()
            before = database_path.read_bytes()
            campaigns = CampaignService(saves)

            listing = campaigns.list_campaigns()
            self.assertEqual(listing, [])
            self.assertEqual(len(listing.unavailable), 1)
            self.assertEqual(listing.unavailable[0]["filename"], f"{campaign_id}.db")
            with self.assertRaisesRegex(ValueError, "dados da campanha estão incompletos"):
                campaigns.activate_campaign(campaign_id)
            self.assertEqual(database_path.read_bytes(), before)

    def test_campaign_listing_keeps_corrupt_file_visible_for_recovery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            corrupt = saves / f"{uuid4()}.db"
            corrupt.write_bytes(b"not a sqlite database")

            listing = CampaignService(saves).list_campaigns()

            self.assertEqual(listing, [])
            self.assertEqual(listing.unavailable[0]["filename"], corrupt.name)
            self.assertIn("corrompido", listing.unavailable[0]["reason"].lower())
            self.assertEqual(corrupt.read_bytes(), b"not a sqlite database")

    def test_campaign_listing_explains_unknown_migration_revision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Revisao desconhecida")
            with closing(sqlite3.connect(campaign.database_path)) as connection:
                connection.execute("UPDATE alembic_version SET version_num = 'revision_xxx'")
                connection.commit()

            listing = campaigns.list_campaigns()

            self.assertEqual(listing, [])
            self.assertIn("versão", listing.unavailable[0]["reason"].lower())

    def test_corrupt_campaign_can_be_restored_from_matching_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saves = CampaignService(root / "saves")
            campaign = saves.create_campaign("Recuperacao")
            backup = saves.create_manual_backup(campaign.campaign_id)
            campaign.database_path.write_bytes(b"damaged save contents")

            listing = saves.list_campaigns()
            self.assertEqual(listing, [])
            self.assertTrue(listing.unavailable)
            restored = saves.restore_backup(campaign.campaign_id, backup)

            self.assertEqual(restored.campaign_id, campaign.campaign_id)
            self.assertEqual(restored.campaign_name, "Recuperacao")
            diagnostic = list((root / "backups" / campaign.campaign_id).glob("pre-restore-*.db"))
            self.assertEqual(len(diagnostic), 1)
            self.assertEqual(diagnostic[0].read_bytes(), b"damaged save contents")

    def test_restore_parks_stale_sqlite_sidecars_and_keeps_diagnostic_copies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            campaigns = CampaignService(root / "saves")
            campaign = campaigns.create_campaign("Com sidecars")
            backup = campaigns.create_manual_backup(campaign.campaign_id)
            wal = Path(f"{campaign.database_path}-wal")
            shm = Path(f"{campaign.database_path}-shm")
            wal.write_bytes(b"stale wal data")
            shm.write_bytes(b"stale shm data")

            restored = campaigns.restore_backup(campaign.campaign_id, backup)

            self.assertEqual(restored.campaign_id, campaign.campaign_id)
            self.assertFalse(wal.exists())
            self.assertFalse(shm.exists())
            diagnostic = list((root / "backups" / campaign.campaign_id).glob("pre-restore-*.db"))
            self.assertEqual(len(diagnostic), 1)
            self.assertEqual(Path(f"{diagnostic[0]}-wal").read_bytes(), b"stale wal data")
            self.assertEqual(Path(f"{diagnostic[0]}-shm").read_bytes(), b"stale shm data")

    def test_empty_sqlite_file_is_rejected_before_migration_without_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            campaign_id = str(uuid4())
            database_path = saves / f"{campaign_id}.db"
            database_path.touch()
            before = database_path.read_bytes()
            campaigns = CampaignService(saves)

            with self.assertRaisesRegex(ValueError, "não é uma campanha reconhecida"):
                campaigns.activate_campaign(campaign_id)
            self.assertEqual(database_path.read_bytes(), before)
            self.assertFalse((Path(temp_dir) / "backups").exists())

    def test_mismatched_internal_campaign_id_is_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Campanha valida")
            different_id = str(uuid4())
            with closing(sqlite3.connect(campaign.database_path)) as connection:
                connection.execute(
                    "UPDATE campaign_metadata SET campaign_id = ? WHERE campaign_id = ?",
                    (different_id, campaign.campaign_id),
                )
                connection.commit()
            before = campaign.database_path.read_bytes()

            with self.assertRaisesRegex(ValueError, "identificador da campanha não corresponde"):
                campaigns.activate_campaign(campaign.campaign_id)
            self.assertEqual(campaign.database_path.read_bytes(), before)
            self.assertFalse((Path(temp_dir) / "backups").exists())

    def test_unknown_future_revision_is_rejected_before_backup_or_upgrade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            campaign_id = str(uuid4())
            database_path = saves / f"{campaign_id}.db"
            campaigns = CampaignService(saves)
            command.upgrade(campaigns._alembic_config(database_path), "c9d0e1f2a3b4")
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute("UPDATE alembic_version SET version_num = 'future_revision_000000000000'")
                connection.commit()
            before = database_path.read_bytes()

            with self.assertRaisesRegex(ValueError, "versão desconhecida"):
                campaigns._ensure_schema(database_path, campaign_id)
            self.assertEqual(database_path.read_bytes(), before)
            self.assertFalse((Path(temp_dir) / "backups").exists())

    def test_upgrade_from_previous_alembic_revision_keeps_data_and_makes_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            campaigns = CampaignService(saves)
            campaign_id = str(uuid4())
            database_path = saves / f"{campaign_id}.db"
            config = campaigns._alembic_config(database_path)
            command.upgrade(config, "c9d0e1f2a3b4")

            with closing(sqlite3.connect(database_path)) as connection:
                self._insert_legacy_row(connection, "users", {
                    "id": 7,
                    "username": "usuario-legado",
                    "email": None,
                    "password_hash": "isolated-test-hash",
                    "is_active": 1,
                    "is_admin": 0,
                    "tutorial_status": "pending",
                    "confirmation_preferences": "{}",
                })
                self._insert_legacy_row(connection, "guilds", {
                    "id": 11,
                    "user_id": 7,
                    "name": "Guilda preservada",
                    "level": 1,
                    "xp": 0,
                    "reputation": 0,
                })
                connection.commit()

            campaigns._ensure_schema(database_path, campaign_id)
            with closing(sqlite3.connect(database_path)) as connection:
                revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                guild = connection.execute(
                    "SELECT user_id, name, campaign_id FROM guilds WHERE id = 11"
                ).fetchone()
                columns = {row[1]: row for row in connection.execute("PRAGMA table_info(guilds)")}
                self.assertEqual(revision, "b1c2d3e4f5a6")
                self.assertEqual(guild, (7, "Guilda preservada", None))
                self.assertEqual(columns["user_id"][3], 0)
                self.assertTrue(list((Path(temp_dir) / "backups" / campaign_id).glob("pre-migration-c9d0e1f2a3b4-*.db")))
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_upgrade_from_pre_event_revision_preserves_campaign_regional_run_and_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            campaigns = CampaignService(saves)
            campaign_id = str(uuid4())
            database_path = saves / f"{campaign_id}.db"
            command.upgrade(campaigns._alembic_config(database_path), "d7e8f9a0b1c2")

            with closing(sqlite3.connect(database_path)) as connection:
                self._insert_legacy_row(connection, "campaign_metadata", {
                    "campaign_id": campaign_id,
                    "campaign_name": "Save regional anterior a eventos",
                    "schema_version": 5,
                })
                self._insert_legacy_row(connection, "guilds", {
                    "id": 31,
                    "campaign_id": campaign_id,
                    "name": "Guilda preservada",
                    "level": 12,
                    "xp": 345,
                    "reputation": 67,
                })
                self._insert_legacy_row(connection, "regional_guild_state", {
                    "id": 41,
                    "campaign_id": campaign_id,
                    "region_code": "vale-fronteira",
                    "slot": 0,
                    "guild_id": 31,
                    "name": "Guilda preservada",
                    "profile": "player",
                    "archetype": "player",
                    "level": 12,
                    "xp": 345,
                    "power": 88,
                    "reputation": 67,
                })
                self._insert_legacy_row(connection, "regional_cycles", {
                    "id": 51,
                    "campaign_id": campaign_id,
                    "cycle_number": 3,
                    "starts_at_utc": "2026-10-28 06:00:00",
                    "ends_at_utc": "2026-10-28 12:00:00",
                    "seed": "a" * 64,
                    "rules_version": "vigilia-v2",
                    "status": "completed",
                })
                self._insert_legacy_row(connection, "regional_offers", {
                    "id": 61,
                    "campaign_id": campaign_id,
                    "cycle_id": 51,
                    "cycle_number": 3,
                    "region_code": "vale-fronteira",
                    "offer_type": "contract",
                    "slot": 0,
                    "rank": "C",
                    "name_snapshot": "Contrato antigo",
                    "recommended_level_snapshot": 10,
                    "recommended_power_snapshot": 80,
                    "duration_seconds_snapshot": 3600,
                    "gold_reward_snapshot": 75,
                    "xp_reward_snapshot": 120,
                    "success_chance_snapshot": 80,
                    "status": "resolved",
                })
                self._insert_legacy_row(connection, "regional_run_outcomes", {
                    "id": 71,
                    "campaign_id": campaign_id,
                    "guild_state_id": 41,
                    "offer_id": 61,
                    "source_type": "mission",
                    "source_run_id": 99,
                    "offer_cycle_number": 3,
                    "applied_cycle_number": 3,
                    "rank": "C",
                    "success": 1,
                    "contribution": 2,
                    "gold_earned": 75,
                    "xp_earned": 120,
                })
                connection.commit()

            migration = campaigns._ensure_schema(database_path, campaign_id)
            self.assertIsNotNone(migration)
            self.assertEqual(migration.previous_revision, "d7e8f9a0b1c2")
            self.assertEqual(migration.current_revision, "b1c2d3e4f5a6")
            backups = list((Path(temp_dir) / "backups" / campaign_id).glob(
                "pre-migration-d7e8f9a0b1c2-*.db"
            ))
            self.assertEqual(len(backups), 1)

            expected_guild = ("Guilda preservada", 12, 345, 67)
            expected_regional_guild = ("Guilda preservada", 12, 345, 88, 67)
            expected_run = (campaign_id, "mission", 99, "C", 1, 2, 75, 120)
            for path, expected_revision in ((database_path, "b1c2d3e4f5a6"), (backups[0], "d7e8f9a0b1c2")):
                with closing(sqlite3.connect(path)) as connection:
                    self.assertEqual(
                        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0],
                        expected_revision,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT campaign_name FROM campaign_metadata WHERE campaign_id = ?",
                            (campaign_id,),
                        ).fetchone(),
                        ("Save regional anterior a eventos",),
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT name, level, xp, reputation FROM guilds WHERE id = 31"
                        ).fetchone(),
                        expected_guild,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT name, level, xp, power, reputation FROM regional_guild_state WHERE id = 41"
                        ).fetchone(),
                        expected_regional_guild,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT campaign_id, source_type, source_run_id, rank, success, "
                            "contribution, gold_earned, xp_earned FROM regional_run_outcomes WHERE id = 71"
                        ).fetchone(),
                        expected_run,
                    )
                    self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_upgrade_from_work_one_head_adds_pause_state_and_updates_schema_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            campaigns = CampaignService(saves)
            campaign = campaigns.create_campaign("Save Work 1")
            command.downgrade(
                campaigns._alembic_config(campaign.database_path),
                "a6b7c8d9e0f1",
            )
            with closing(sqlite3.connect(campaign.database_path)) as connection:
                connection.execute(
                    "UPDATE campaign_metadata SET schema_version = 3 WHERE campaign_id = ?",
                    (campaign.campaign_id,),
                )
                connection.commit()
                self.assertNotIn(
                    "capacity_paused",
                    {row[1] for row in connection.execute("PRAGMA table_info(gathering_assignments)")},
                )

            migration = campaigns._ensure_schema(campaign.database_path, campaign.campaign_id)
            self.assertIsNotNone(migration)
            self.assertEqual(migration.previous_revision, "a6b7c8d9e0f1")
            self.assertEqual(migration.current_revision, "b1c2d3e4f5a6")
            self.assertEqual(migration.previous_save_version, 3)
            self.assertEqual(migration.current_save_version, 6)
            with closing(sqlite3.connect(campaign.database_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT version_num FROM alembic_version").fetchone()[0],
                    "b1c2d3e4f5a6",
                )
                self.assertIn(
                    "capacity_paused",
                    {row[1] for row in connection.execute("PRAGMA table_info(gathering_assignments)")},
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT schema_version FROM campaign_metadata WHERE campaign_id = ?",
                        (campaign.campaign_id,),
                    ).fetchone()[0],
                    6,
                )

    def test_failed_migration_restores_original_schema_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            saves.mkdir()
            campaigns = CampaignService(saves)
            campaign_id = str(uuid4())
            database_path = saves / f"{campaign_id}.db"
            command.upgrade(campaigns._alembic_config(database_path), "c9d0e1f2a3b4")
            with closing(sqlite3.connect(database_path)) as connection:
                self._insert_legacy_row(connection, "guilds", {"id": 31, "name": "Guilda intacta"})
                connection.commit()

            def partial_failure(_config, _head):
                with closing(sqlite3.connect(database_path)) as connection:
                    connection.execute("ALTER TABLE guilds ADD COLUMN partial_migration_marker TEXT")
                    connection.commit()
                raise RuntimeError("falha simulada depois de uma alteracao parcial")

            with patch("app.services.campaign_service.command.upgrade", side_effect=partial_failure):
                with self.assertRaisesRegex(RuntimeError, "arquivo original foi restaurado"):
                    campaigns._ensure_schema(database_path, campaign_id)

            with closing(sqlite3.connect(database_path)) as connection:
                revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                guild = connection.execute("SELECT name FROM guilds WHERE id = 31").fetchone()[0]
                columns = {row[1] for row in connection.execute("PRAGMA table_info(guilds)")}
                self.assertEqual(revision, "c9d0e1f2a3b4")
                self.assertEqual(guild, "Guilda intacta")
                self.assertNotIn("partial_migration_marker", columns)
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            backups = list((Path(temp_dir) / "backups" / campaign_id).glob("pre-migration-c9d0e1f2a3b4-*.db"))
            self.assertEqual(len(backups), 1)
            with closing(sqlite3.connect(backups[0])) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("SELECT name FROM guilds WHERE id = 31").fetchone()[0], "Guilda intacta")

    def test_campaign_export_import_restore_backup_and_delete_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                self._assert_campaign_file_lifecycle(Path(temp_dir))
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def _assert_campaign_file_lifecycle(self, temp_path: Path) -> None:
        campaigns = CampaignService(temp_path / "saves")
        original = campaigns.create_campaign("Arquivo de origem", "Guilda original")
        with closing(sqlite3.connect(original.database_path)) as connection:
            connection.execute(
                "INSERT INTO offline_return_reports "
                "(report_id, campaign_id, report_json, created_at_utc) VALUES (?, ?, ?, ?)",
                (str(uuid4()), original.campaign_id, "{}", datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
        export_path = temp_path / "exports" / "origem.gimcampaign"
        campaigns.export_campaign(original.campaign_id, export_path)
        with self.assertRaises(FileExistsError):
            campaigns.export_campaign(original.campaign_id, export_path)
        campaigns.export_campaign(original.campaign_id, export_path, overwrite=True)

        imported = campaigns.import_campaign(export_path)
        self.assertNotEqual(imported.campaign_id, original.campaign_id)
        self.assertEqual(imported.last_session_state, "created")
        self.assertIsNone(imported.last_clean_shutdown_utc)
        with closing(sqlite3.connect(imported.database_path)) as connection:
            metadata_id = connection.execute("SELECT campaign_id FROM campaign_metadata").fetchone()[0]
            guild_id = connection.execute("SELECT campaign_id FROM guilds").fetchone()[0]
            self.assertEqual(metadata_id, imported.campaign_id)
            self.assertEqual(guild_id, imported.campaign_id)
            report_campaign_ids = connection.execute(
                "SELECT DISTINCT campaign_id FROM offline_return_reports"
            ).fetchall()
            self.assertEqual(report_campaign_ids, [(imported.campaign_id,)])

        backup_path = campaigns.create_manual_backup(imported.campaign_id)
        campaigns.rename_campaign(imported.campaign_id, "Nome temporario")
        restored = campaigns.restore_backup(imported.campaign_id, backup_path)
        self.assertEqual(restored.campaign_name, "Arquivo de origem")

        campaigns.activate_campaign(original.campaign_id)
        with self.assertRaisesRegex(ValueError, "Feche a campanha"):
            campaigns.delete_campaign(original.campaign_id)
        campaigns.close_active_campaign(original.campaign_id)
        delete_backup = campaigns.delete_campaign(original.campaign_id)
        self.assertTrue(delete_backup.is_file())
        self.assertFalse(original.database_path.exists())

    @staticmethod
    def _insert_legacy_row(connection, table: str, values: dict[str, object]) -> None:
        column_info = list(connection.execute(f"PRAGMA table_info({table})"))
        row_values = {}
        for column in column_info:
            name, type_name, not_null, default, primary_key = column[1], column[2].upper(), column[3], column[4], column[5]
            if name in values:
                row_values[name] = values[name]
            elif primary_key:
                continue
            elif not not_null or default is not None:
                continue
            elif "DATE" in type_name or "TIME" in type_name:
                row_values[name] = "2026-10-26 12:00:00"
            elif "INT" in type_name or "BOOL" in type_name:
                row_values[name] = 0
            else:
                row_values[name] = ""
        names = list(row_values)
        placeholders = ", ".join("?" for _ in names)
        connection.execute(
            f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})",
            [row_values[name] for name in names],
        )

    def _exercise_gameplay(self, db, guild, resources) -> None:
        resources.gold = 100_000
        db.add(resources)
        seeded_resource_families: set[str] = set()
        for material_template in db.scalars(select(ItemTemplate).where(ItemTemplate.item_type == "material")):
            quantity = 1
            for resource_name, families in RESOURCE_MATERIAL_FAMILIES.items():
                if material_template.material_family in families and resource_name not in seeded_resource_families:
                    quantity = 300
                    seeded_resource_families.add(resource_name)
                    break
            add_inventory_quantity(db, guild.id, material_template.id, quantity)
        db.commit()
        ensure_guild_buildings(db, guild.id)
        # Keep this persistence fixture's initial stock under a finite capacity
        # while retaining enough core resources for its later upgrade sequence.
        warehouse = get_guild_building_by_effect(db, guild.id, "warehouse")
        warehouse.level = 10
        db.add(warehouse)
        db.commit()
        housing = get_guild_building_by_effect(db, guild.id, "housing")
        tavern = get_guild_building_by_effect(db, guild.id, "tavern")
        self.assertIsNotNone(housing)
        self.assertIsNotNone(tavern)
        housing = upgrade_guild_building(db, guild, resources, housing.id)
        self.assertEqual(housing.level, 1)
        housing.level = 3  # the revised milestone curve grants the second slot here
        db.commit()
        tavern = upgrade_guild_building(db, guild, resources, tavern.id)
        self.assertEqual(tavern.level, 1)

        tavern_context = get_tavern_page_context(db, guild, resources)
        self.assertTrue(tavern_context["next_special_check_at_iso"].endswith("+00:00"))
        self.assertTrue(tavern_summary(db, guild)["next_special_check_at_iso"].endswith("+00:00"))
        campaign = db.scalar(select(CampaignMetadata).where(CampaignMetadata.campaign_id == guild.campaign_id))
        desktop_app = FastAPI()
        desktop_app.state.app_mode = "desktop"
        request = Request({"type": "http", "app": desktop_app})
        player = CampaignPlayer(campaign.campaign_id, campaign.campaign_name)
        saved_preview = _get_apprentice_preview(
            request, db, player, tavern_context["config"], tavern_context["tavern_level"]
        )
        self.assertEqual(json.loads(campaign.apprentice_preview), saved_preview)
        self.assertEqual(
            _get_apprentice_preview(request, db, player, tavern_context["config"], tavern_context["tavern_level"]),
            saved_preview,
        )
        for name, preview in (("Aprendiz de teste", saved_preview), ("Segundo aprendiz", None)):
            if preview is None:
                preview = generate_apprentice_preview(tavern_context["config"], tavern_context["tavern_level"])
            hire_apprentice(db, guild, resources, name, preview)
        mercenaries = list(guild.mercenaries)
        self.assertEqual(len(mercenaries), 2)

        mission_template = MissionTemplate(
            name="Missao de integracao SQLite",
            description="Cenario temporario isolado para validar transacao de missao.",
            display_order=999999,
            difficulty="normal",
            level_band="1-20",
            mission_type="standard",
            recommended_level=1,
            recommended_power=1,
            duration_seconds=1,
            base_gold_reward=10,
            base_xp_reward=5,
            base_success_chance=100,
            min_party_size=1,
            max_party_size=1,
            required_guild_level=1,
            required_min_mercenary_level=1,
            required_building_level=0,
            is_active=True,
        )
        db.add(mission_template)
        db.flush()
        material = db.scalar(select(ItemTemplate).where(ItemTemplate.item_type == "material"))
        self.assertIsNotNone(material)
        db.add(MissionTemplateItemDrop(
            mission_template_id=mission_template.id,
            item_template_id=material.id,
            drop_chance=100,
            min_quantity=1,
            max_quantity=1,
            is_active=True,
        ))
        db.commit()
        mission_run = start_mission(db, guild, str(mission_template.id), [str(mercenaries[0].id)])
        mission_context = get_missions_page_context(db, guild)
        rendered_mission_run = mission_context["in_progress_runs"][0]
        self.assertTrue(rendered_mission_run.ends_at_iso.endswith("+00:00"))
        self.assertFalse(rendered_mission_run.ready_for_loot)
        with self.assertRaisesRegex(ValueError, "ainda não foi concluída"):
            claim_mission_loot(db, guild, resources, mission_run.id)
        mission_run.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.flush()
        with patch("app.services.mission_service.randint", return_value=1):
            completed_mission = claim_mission_loot(db, guild, resources, mission_run.id)
        self.assertEqual(completed_mission.status, "completed")
        self.assertGreater(
            db.scalar(select(func.count(GuildInventoryItem.id)).where(GuildInventoryItem.guild_id == guild.id))
            + db.scalar(select(func.count(GuildItemInstance.id)).where(GuildItemInstance.guild_id == guild.id)),
            0,
        )
        failed_run = start_mission(db, guild, str(mission_template.id), [str(mercenaries[0].id)])
        failed_run.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with patch("app.services.mission_service.randint", return_value=100):
            failed_mission = claim_mission_loot(db, guild, resources, failed_run.id)
        self.assertEqual(failed_mission.status, "failed")

        scouts = get_guild_building_by_effect(db, guild.id, "scouts")
        scouts.level = 1
        db.add(scouts)
        mercenaries[0].power = mercenaries[1].power = 500
        mercenaries[0].vitality = mercenaries[1].vitality = 500
        db.add_all(mercenaries)
        db.commit()
        dungeon_template = db.scalar(
            select(DungeonTemplate)
            .where(
                DungeonTemplate.is_active.is_(True),
                DungeonTemplate.content_type == "dungeon",
                DungeonTemplate.required_min_mercenary_level <= 1,
                DungeonTemplate.min_party_size <= 2,
                DungeonTemplate.required_class_code.is_(None),
            )
            .order_by(DungeonTemplate.required_total_power, DungeonTemplate.id)
        )
        self.assertIsNotNone(dungeon_template)
        dungeon_template.base_success_chance = 100
        db.add(dungeon_template)
        db.flush()
        self.assertEqual(
            get_advanced_dungeon_chance(db, guild.id, dungeon_template, mercenaries[:2])["final_chance"],
            95,
        )
        dungeon_run = start_dungeon(
            db,
            guild,
            str(dungeon_template.id),
            [str(mercenaries[0].id), str(mercenaries[1].id)],
        )
        dungeon_context = get_dungeons_page_context(db, guild)
        rendered_dungeon_run = dungeon_context["in_progress_runs"][0]
        self.assertTrue(rendered_dungeon_run.ends_at_iso.endswith("+00:00"))
        self.assertFalse(rendered_dungeon_run.ready_for_loot)
        dungeon_run.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.flush()
        with patch("app.services.dungeon_service.randint", return_value=1):
            completed_dungeon = claim_dungeon_loot(db, guild, resources, dungeon_run.id)
        self.assertEqual(completed_dungeon.status, "completed")

        capped_dungeon_run = start_dungeon(
            db,
            guild,
            str(dungeon_template.id),
            [str(mercenaries[0].id), str(mercenaries[1].id)],
        )
        capped_dungeon_run.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with patch("app.services.dungeon_service.randint", return_value=100):
            capped_dungeon = claim_dungeon_loot(db, guild, resources, capped_dungeon_run.id)
        self.assertEqual(capped_dungeon.status, "failed")

        introductory_boss = db.scalar(select(DungeonTemplate).where(
            DungeonTemplate.is_active.is_(True),
            DungeonTemplate.content_type == "boss",
            DungeonTemplate.level_band == "1-20",
            DungeonTemplate.recommended_level <= 1,
        ).order_by(DungeonTemplate.id))
        self.assertIsNotNone(introductory_boss)
        boss_run = start_dungeon(
            db, guild, str(introductory_boss.id), [str(mercenaries[0].id)]
        )
        with self.assertRaisesRegex(ValueError, "ainda não foi concluída"):
            claim_dungeon_loot(db, guild, resources, boss_run.id)
        boss_run.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with patch("app.services.dungeon_service.randint", return_value=1):
            completed_boss = claim_dungeon_loot(db, guild, resources, boss_run.id)
        self.assertEqual(completed_boss.status, "completed")

        # Equipment creation and equip state are committed in the campaign database.
        armor = db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "equipment",
            ItemTemplate.equipment_slot == "chest",
            ItemTemplate.required_level <= mercenaries[0].level,
        ).order_by(ItemTemplate.id))
        self.assertIsNotNone(armor)
        equipment = create_equipment_instance_from_template(db, guild.id, armor)
        db.flush()
        equipped = equip_item(db, guild.id, mercenaries[0].id, equipment.id)
        self.assertEqual(equipped.equipped_to_mercenary_id, mercenaries[0].id)

        # Market uses a real inventory item and does not pay until the timer has ended.
        market = get_guild_building_by_effect(db, guild.id, "market")
        market = upgrade_guild_building(db, guild, resources, market.id)
        material_stock = db.scalar(select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == guild.id,
            GuildInventoryItem.item_template_id == material.id,
        ))
        self.assertIsNotNone(material_stock)
        sale = start_material_sale(db, guild, str(material.id), "1")
        sale_context = get_market_page_context(db, guild)
        rendered_sale = sale_context["active_sales"][0]
        self.assertTrue(rendered_sale.ends_at_iso.endswith("+00:00"))
        self.assertFalse(rendered_sale.ready_for_loot)
        with self.assertRaisesRegex(ValueError, "ainda nao foi concluida"):
            collect_market_sale(db, guild, resources, sale.id)
        sale.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        collected_sale = collect_market_sale(db, guild, resources, sale.id)
        self.assertEqual(collected_sale.status, "completed")

        # Profession training and dock offers are timed/stock-backed campaign transactions.
        profession = db.scalar(select(ProfessionTemplate).where(ProfessionTemplate.is_active.is_(True)).order_by(ProfessionTemplate.id))
        self.assertIsNotNone(profession)
        training = start_profession_training(db, guild, resources, mercenaries[0].id, profession.id)
        profession_context = get_professions_context(db, guild)
        rendered_training = profession_context["trainings"][0]
        self.assertTrue(rendered_training.ends_at_iso.endswith("+00:00"))
        self.assertFalse(rendered_training.ready_for_loot)
        with self.assertRaisesRegex(ValueError, "ainda não terminou"):
            complete_profession_training(db, guild, training.id)
        training.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        completed_training = complete_profession_training(db, guild, training.id)
        self.assertEqual(completed_training.status, "completed")

        docks = get_guild_building_by_effect(db, guild.id, "docks")
        docks = upgrade_guild_building(db, guild, resources, docks.id)
        rotation = create_dock_rotation(db, guild, docks.level)
        dock_context = get_docks_context(db, guild)
        self.assertTrue(dock_context["rotation"].ends_at_iso.endswith("+00:00"))
        dock_merchant_ids = [merchant.id for merchant in rotation.merchants]
        dock_offer = db.scalar(select(DockOffer).where(
            DockOffer.dock_rotation_merchant_id.in_(dock_merchant_ids)
        ).order_by(DockOffer.id))
        self.assertIsNotNone(dock_offer)
        # Initial fixture stock is normalized above; verify space remains for
        # this purchase after the mission, dungeon, market and training flows.
        self.assertLessEqual(get_inventory_usage(db, guild.id) + 1, get_inventory_capacity(db, guild))
        buy_dock_offer(db, guild, resources, dock_offer.id, 1)
        self.assertLess(dock_offer.remaining_stock, dock_offer.initial_stock)

        # Blacksmith crafting, guild progression, achievements, and Codex all persist locally.
        blacksmith = get_guild_building_by_effect(db, guild.id, "blacksmith")
        blacksmith = upgrade_guild_building(db, guild, resources, blacksmith.id)
        blacksmith_context = get_blacksmith_context(db, guild)
        self.assertTrue(blacksmith_context["rotation"]["ends_at_iso"].endswith("+00:00"))
        recipe = next((entry for entry in blacksmith_context["recipes"] if entry.materials), None)
        if recipe is None:
            recipe = db.scalar(select(CraftingRecipe).where(CraftingRecipe.is_active.is_(True)).order_by(CraftingRecipe.id))
        self.assertIsNotNone(recipe)
        if not hasattr(recipe, "effective_gold_cost"):
            from app.services.crafting_service import _effective_recipe_gold_cost
            docks_level = get_guild_building_by_effect(db, guild.id, "docks").level
            recipe.effective_gold_cost = _effective_recipe_gold_cost(db, recipe, docks_level)
        shown_craft_gold = int(recipe.effective_gold_cost)
        for ingredient in recipe.materials:
            owned = db.scalar(select(GuildInventoryItem).where(
                GuildInventoryItem.guild_id == guild.id,
                GuildInventoryItem.item_template_id == ingredient.item_template_id,
            ))
            shortfall = ingredient.quantity - (owned.quantity if owned else 0)
            if shortfall > 0:
                add_inventory_quantity(db, guild.id, ingredient.item_template_id, shortfall)
        db.commit()
        gold_before_craft = resources.gold
        self.assertIn("criado com sucesso", craft_recipe(db, guild, resources, str(recipe.id)))
        self.assertEqual(gold_before_craft - resources.gold, shown_craft_gold)
        self.assertLessEqual(get_inventory_usage(db, guild.id) + 1, get_inventory_capacity(db, guild))
        add_inventory_quantity(db, guild.id, material.id, 1)
        db.commit()

        from app.services.guild_progression_service import add_guild_xp
        prior_level = guild.level
        add_guild_xp(guild, 10_000)
        db.add(guild)
        db.commit()
        self.assertGreaterEqual(guild.level, prior_level)
        self.assertTrue(evaluate_achievements(db, guild))
        sync_codex(db, guild)
        self.assertGreater(get_codex_context(db, guild)["total_count"], 0)


if __name__ == "__main__":
    unittest.main()
