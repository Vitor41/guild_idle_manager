import os
import asyncio
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import CampaignPlayer, get_current_player, get_db
from app.database.connection import Base, create_database_engine
from app.desktop import gameplay_diagnostics
from app.desktop.gameplay_diagnostics import close_gameplay_logger
from app.main import protect_desktop_loopback
from app.models import CampaignMetadata, Guild, GuildInventoryItem, ItemTemplate
from app.models.workshop import SupplyWorkshopJob
from app.repositories.item_repository import add_inventory_quantity
from app.routes import workshop_routes
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.workshop_service import (
    HERBS_PER_KIT,
    MEAT_PER_KIT,
    craft_supply_kit,
    ensure_supply_kit,
)
from datetime import datetime, timezone


class WorkshopRouteDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.original_env = patch.dict(os.environ, {
            "APP_MODE": "desktop",
            "LOCALAPPDATA": str(self.root / "local-app-data"),
        })
        self.original_env.start()
        self.addCleanup(self.original_env.stop)

        self.database_path = self.root / "workshop-route.db"
        self.engine = create_database_engine(f"sqlite:///{self.database_path.as_posix()}")
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)

        with Session(self.engine, autoflush=False, expire_on_commit=False) as db:
            guild = Guild(name="Oficina de diagnóstico", level=1)
            guild.campaign_id = "temporary-campaign"
            campaign = CampaignMetadata(
                campaign_id="temporary-campaign", campaign_name="Oficina de diagnóstico",
            )
            meat = ItemTemplate(
                name="Carne", description="", item_type="material", rarity="common",
                material_family="meat", item_level=1, level_band="1-20", tier=1,
            )
            herb = ItemTemplate(
                name="Erva", description="", item_type="material", rarity="common",
                material_family="herb", item_level=1, level_band="1-20", tier=1,
            )
            filler = ItemTemplate(
                name="Madeira", description="", item_type="material", rarity="common",
                material_family="wood", item_level=1, level_band="1-20", tier=1,
            )
            db.add_all([campaign, guild, meat, herb, filler])
            db.flush()
            ensure_supply_kit(db)
            db.commit()
            self.guild_id = guild.id
            self.meat_id = meat.id
            self.herb_id = herb.id
            self.filler_id = filler.id

        self.app = FastAPI()
        self.app.state.app_mode = "desktop"
        self.app.state.desktop_allowed_host = "testserver"
        self.app.state.desktop_allowed_origin = "http://testserver"
        self.app.state.active_campaign = type("ActiveCampaign", (), {
            "campaign_id": "temporary-campaign",
            "stamina_seconds": 8 * 60 * 60,
            "stamina_recharge_remainder_seconds": 0,
        })()
        self.app.middleware("http")(protect_desktop_loopback)
        self.app.mount(
            "/static",
            StaticFiles(directory=Path(__file__).resolve().parents[1] / "app" / "static"),
            name="static",
        )
        self.app.include_router(workshop_routes.router)
        self.app.dependency_overrides[get_db] = self._request_db
        self.app.dependency_overrides[workshop_routes.get_current_player] = lambda: CampaignPlayer(
            id="temporary-campaign", username="Oficina de diagnóstico",
        )
        self.gameplay_log = self.root / "local-app-data" / "GuildIdleManager" / "logs" / "gameplay-actions.log"
        self.addCleanup(lambda: close_gameplay_logger(self.gameplay_log))
        # The CI sandbox may only allow writes inside the checkout. Give the
        # logger an explicit per-test path so this fixture does not accidentally
        # treat its temporary LOCALAPPDATA as the installed user's data folder.
        self.gameplay_log_path_patch = patch.object(
            gameplay_diagnostics, "gameplay_log_path", return_value=self.gameplay_log,
        )
        self.gameplay_log_path_patch.start()
        self.addCleanup(self.gameplay_log_path_patch.stop)

    def _request_db(self):
        with Session(self.engine, autoflush=False, expire_on_commit=False) as db:
            yield db

    def _guild_context(self, db, _current_user):
        return db.get(Guild, self.guild_id), None

    def _request(self, path: str):
        async def run():
            messages = []
            first_request = True

            async def receive():
                nonlocal first_request
                if first_request:
                    first_request = False
                    return {"type": "http.request", "body": b"", "more_body": False}
                return {"type": "http.disconnect"}

            async def send(message):
                messages.append(message)

            await self.app({
                "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1", "method": "GET", "scheme": "http",
                "path": path, "raw_path": path.encode("ascii"), "query_string": b"",
                "headers": [(b"host", b"testserver")], "server": ("127.0.0.1", 8000),
                "client": ("127.0.0.1", 12345),
            }, receive, send)
            status = messages[0]["status"]
            headers = dict(messages[0]["headers"])
            body = b"".join(message.get("body", b"") for message in messages
                             if message["type"] == "http.response.body")
            return status, headers, body

        return asyncio.run(run())

    def test_forced_get_workshops_exception_has_reference_and_persistent_traceback(self):
        with patch.object(
            workshop_routes,
            "get_current_guild_context",
            side_effect=RuntimeError("forced-workshops-route-diagnostic"),
        ):
            status, _headers, body = self._request("/workshops")

        self.assertEqual(status, 500)
        response_text = body.decode("utf-8")
        self.assertIn(r"%LOCALAPPDATA%\GuildIdleManager\logs\gameplay-actions.log", response_text)
        diagnostic_match = re.search(r"Referência: <code>([a-f0-9]{32})</code>", response_text)
        self.assertIsNotNone(diagnostic_match, response_text)
        diagnostic_id = diagnostic_match.group(1)
        trace = self.gameplay_log.read_text(encoding="utf-8")
        self.assertIn(
            f"event=exception action=workshops.page route=/workshops ref={diagnostic_id} "
            "status=500 outcome=unexpected_exception",
            trace,
        )
        self.assertIn("Traceback (most recent call last)", trace)
        self.assertIn("RuntimeError: forced-workshops-route-diagnostic", trace)

    def test_workshop_route_renders_normally_for_available_campaign(self):
        with patch.object(workshop_routes, "get_current_guild_context", side_effect=self._guild_context):
            status, _headers, body = self._request("/workshops")

        response_text = body.decode("utf-8")
        self.assertEqual(status, 200, response_text)
        self.assertIn("Oficina de Suprimentos", response_text)
        self.assertNotIn("Não foi possível abrir esta tela", response_text)

    def test_regional_advance_exception_before_workshop_route_is_persisted(self):
        from app.services import regional_cycle_service

        self.app.dependency_overrides[workshop_routes.get_current_player] = get_current_player
        with patch.object(
            regional_cycle_service,
            "advance_regional_world",
            side_effect=RuntimeError("forced-regional-advance-diagnostic"),
        ):
            status, _headers, body = self._request("/workshops")

        response_text = body.decode("utf-8")
        self.assertEqual(status, 500, response_text)
        diagnostic_match = re.search(r"Referência: <code>([a-f0-9]{32})</code>", response_text)
        self.assertIsNotNone(diagnostic_match, response_text)
        trace = self.gameplay_log.read_text(encoding="utf-8")
        self.assertIn(
            f"event=exception action=workshops.page route=/workshops ref={diagnostic_match.group(1)} "
            "status=500 outcome=unexpected_exception",
            trace,
        )
        self.assertIn("RuntimeError: forced-regional-advance-diagnostic", trace)

    def test_due_batch_with_overcommitted_reservation_renders_and_preserves_job(self):
        with Session(self.engine, autoflush=False, expire_on_commit=False) as db:
            guild = db.get(Guild, self.guild_id)
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            db.add_all([
                GuildInventoryItem(guild_id=self.guild_id, item_template_id=self.meat_id, quantity=MEAT_PER_KIT),
                GuildInventoryItem(guild_id=self.guild_id, item_template_id=self.herb_id, quantity=HERBS_PER_KIT),
            ])
            db.flush()
            job = craft_supply_kit(db, guild, 1, now=start)
            capacity = get_inventory_capacity(db, guild)
            add_inventory_quantity(db, self.guild_id, self.filler_id, capacity)
            job_id = job.id
            db.commit()

        with patch.object(workshop_routes, "get_current_guild_context", side_effect=self._guild_context):
            status, _headers, body = self._request("/workshops")

        response_text = body.decode("utf-8")
        self.assertEqual(status, 200, response_text)
        self.assertIn("Produção pronta, aguardando espaço no Armazém", response_text)
        self.assertIn("O débito dos materiais já realizado e a reserva dos Kits foram preservados", response_text)
        with Session(self.engine, autoflush=False, expire_on_commit=False) as db:
            job = db.get(SupplyWorkshopJob, job_id)
            guild = db.get(Guild, self.guild_id)
            kit = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "supply_kit"))
            kit_quantity = db.scalar(select(GuildInventoryItem.quantity).where(
                GuildInventoryItem.guild_id == self.guild_id,
                GuildInventoryItem.item_template_id == kit.id,
            )) or 0
            self.assertEqual(job.status, "in_progress")
            self.assertIsNone(job.completed_at)
            self.assertEqual(kit_quantity, 0)
            self.assertEqual(get_inventory_usage(db, self.guild_id), get_inventory_capacity(db, guild) + 1)

    def test_due_batch_from_disk_backed_save_completes_without_datetime_evaluator_error(self):
        with Session(self.engine, autoflush=False, expire_on_commit=False) as db:
            guild = db.get(Guild, self.guild_id)
            db.add_all([
                GuildInventoryItem(guild_id=self.guild_id, item_template_id=self.meat_id, quantity=MEAT_PER_KIT),
                GuildInventoryItem(guild_id=self.guild_id, item_template_id=self.herb_id, quantity=HERBS_PER_KIT),
            ])
            db.flush()
            job = craft_supply_kit(db, guild, 1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
            job_id = job.id
            db.commit()

        with patch.object(workshop_routes, "get_current_guild_context", side_effect=self._guild_context):
            status, _headers, body = self._request("/workshops")

        response_text = body.decode("utf-8")
        self.assertEqual(status, 200, response_text)
        self.assertIn("Produção concluída: 1 Kit(s) adicionados", response_text)
        with Session(self.engine, autoflush=False, expire_on_commit=False) as db:
            job = db.get(SupplyWorkshopJob, job_id)
            guild = db.get(Guild, self.guild_id)
            kit = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "supply_kit"))
            kit_quantity = db.scalar(select(GuildInventoryItem.quantity).where(
                GuildInventoryItem.guild_id == self.guild_id,
                GuildInventoryItem.item_template_id == kit.id,
            )) or 0
            self.assertEqual(job.status, "completed")
            self.assertIsNotNone(job.completed_at)
            self.assertEqual(kit_quantity, 1)
            self.assertLessEqual(get_inventory_usage(db, self.guild_id), get_inventory_capacity(db, guild))


if __name__ == "__main__":
    unittest.main()
