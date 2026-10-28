import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DesktopHttpSmokeTests(unittest.TestCase):
    def test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            script = r'''
import gc, http.client, json, os, re, socket, sqlite3, tempfile, threading, time
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone, timedelta
os.environ["APP_MODE"] = "desktop"
from app.main import app
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.desktop.lifecycle import open_campaign
from app.services.campaign_service import CampaignService
from app.database.connection import SessionLocal, configure_database
from app.models import (CampaignMetadata, ClassChangeRun, DungeonRun, DungeonRunMember, Guild, GuildBuilding,
    GuildInventoryItem, GuildSalvageJob, ItemTemplate, MarketSale, MercenaryClass, MissionRun,
    MissionRunMember, ProfessionTemplate, ProfessionTraining)
from app.models.dungeon import DungeonTemplate
from app.models.mission import MissionTemplate
from app.models.building import BuildingTemplate
from app.repositories.mercenary_repository import create_mercenary
from sqlalchemy import select
import uvicorn

with tempfile.TemporaryDirectory() as data_dir:
    saves = CampaignService(Path(data_dir) / "saves")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    port = sock.getsockname()[1]
    host = f"127.0.0.1:{port}"
    origin = f"http://{host}"
    app.state.desktop_allowed_host = host
    app.state.desktop_allowed_origin = origin
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline: time.sleep(.05)
    assert server.started, "server did not start"
    campaign = saves.create_campaign("Smoke desktop")
    guard = ClockGuard(MemoryAnchorStore(), lambda: datetime.now(timezone.utc), time.monotonic)
    guard.initialize_campaign(campaign.campaign_id)
    app.state.campaign_service = saves
    app.state.clock_guard = guard
    app.state.suspended_campaigns = set()
    open_campaign(app, saves, guard, campaign.campaign_id)
    with SessionLocal() as db:
        guild = db.query(Guild).first()
        mercenary_class = db.query(MercenaryClass).order_by(MercenaryClass.id).first()
        item_template = db.query(ItemTemplate).filter(ItemTemplate.icon_group.is_not(None)).order_by(ItemTemplate.id).first()
        assert guild and mercenary_class and item_template, "campaign must seed display entities for the desktop art smoke"
        mercenary = create_mercenary(db, guild.id, mercenary_class, "Teste visual")
        db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=item_template.id, quantity=1))
        db.flush()
        mercenary_id = mercenary.id
        now = datetime.now(timezone.utc)
        later = now + timedelta(hours=1)
        mission_template = db.query(MissionTemplate).filter(MissionTemplate.is_active.is_(True)).first()
        dungeon_template = db.query(DungeonTemplate).filter(DungeonTemplate.is_active.is_(True)).first()
        profession = db.query(ProfessionTemplate).filter(ProfessionTemplate.is_active.is_(True)).first()
        target_class = db.query(MercenaryClass).filter(MercenaryClass.id != mercenary.class_id).first()
        assert mission_template and dungeon_template and profession and target_class
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="scouts").one().id, level=1))
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="market").one().id, level=1))
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="blacksmith").one().id, level=1))
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="tavern").one().id, level=1))
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="docks").one().id, level=1))
        mission_run = MissionRun(guild_id=guild.id, mission_template_id=mission_template.id, started_at=now, ends_at=later)
        dungeon_run = DungeonRun(guild_id=guild.id, dungeon_template_id=dungeon_template.id, started_at=now, ends_at=later)
        db.add_all([mission_run, dungeon_run])
        db.flush()
        db.add_all([MissionRunMember(mission_run_id=mission_run.id, mercenary_id=mercenary.id),
            DungeonRunMember(dungeon_run_id=dungeon_run.id, mercenary_id=mercenary.id)])
        db.add(MarketSale(guild_id=guild.id, item_template_id=item_template.id, quantity=1, unit_value=1,
            total_value=1, started_at=now, ends_at=later))
        db.add(ProfessionTraining(guild_id=guild.id, mercenary_id=mercenary.id, profession_id=profession.id,
            started_at=now, ends_at=later))
        db.add(ClassChangeRun(guild_id=guild.id, mercenary_id=mercenary.id, from_class_id=mercenary.class_id,
            to_class_id=target_class.id, gold_cost=1, started_at=now, ends_at=later))
        material = db.query(ItemTemplate).filter(ItemTemplate.item_type == "material").first()
        assert material
        db.add(GuildSalvageJob(guild_id=guild.id, slot_number=1, item_template_id=item_template.id,
            material_template_id=material.id, quantity=1, gold_cost=1, started_at=now, ends_at=later))
        db.commit()

    def request(path, method="GET", body=None):
        client = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
        headers = {"Host": host}
        if method not in {"GET", "HEAD"}:
            headers["Origin"] = origin
        if body is not None: headers["Content-Type"] = "application/x-www-form-urlencoded"
        client.request(method, path, body=body, headers=headers)
        response = client.getresponse()
        result = response.status, response.getheader("location"), response.read()
        client.close()
        return result

    try:
        rendered_pages = {}
        for path in ("/dashboard", "/tavern", "/mercenaries", f"/mercenaries/{mercenary_id}", "/missions", "/dungeons", "/inventory", "/buildings", "/market", "/blacksmith", "/professions", "/class-change", "/docks", "/tutorial"):
            status, _location, body = request(path)
            assert status == 200, (path, status, body[:400])
            assert b"Internal Server Error" not in body, path
            rendered_pages[path] = body
        assert b"/static/js/desktop-art.js" in rendered_pages["/dashboard"]
        assert b"/css/desktop-theme.css?v=20261027-1" in rendered_pages["/dashboard"]
        assert b'desktop-resource-row' in rendered_pages["/dashboard"]
        assert b'desktop-operations-band' in rendered_pages["/dashboard"]
        assert b'desktop-operations-intro desktop-page-hero' in rendered_pages["/missions"]
        assert b'desktop-operations-intro desktop-page-hero' in rendered_pages["/dungeons"]
        assert b"Chance base" in rendered_pages["/missions"]
        assert b"chance final m\xc3\xa1xima de 95%" in rendered_pages["/missions"]
        assert b"Chance base" in rendered_pages["/dungeons"]
        assert b"limitada a 95%" in rendered_pages["/dungeons"]
        for timer_page in ("/missions", "/dungeons", "/market", "/professions", "/class-change", "/blacksmith"):
            assert re.search(rb'data-ends-at="[^\"]+\+00:00"', rendered_pages[timer_page]), timer_page
        for timer_page in ("/dashboard", "/tavern", "/docks"):
            assert re.search(rb'data-ends-at="[^\"]+\+00:00"', rendered_pages[timer_page]), timer_page
        assert b'data-desktop-resource="gold"' in rendered_pages["/dashboard"]
        assert b'data-desktop-building="' in rendered_pages["/buildings"]
        assert b'data-desktop-class="' in rendered_pages["/mercenaries"]
        assert b'data-desktop-class="' in rendered_pages[f"/mercenaries/{mercenary_id}"]
        assert b'data-desktop-item-slot="helmet"' in rendered_pages[f"/mercenaries/{mercenary_id}"]
        assert b'data-desktop-item-group="' in rendered_pages["/inventory"]
        assert b"/static/static/" not in b"".join(rendered_pages.values())
        sprite_refs = re.findall(rb"(/static/assets/desktop/sprites/[^\s\"'>]+)", b" ".join(rendered_pages.values()))
        assert sprite_refs, "desktop HTML should point directly to a bundled semantic sprite"
        sprite_status, _location, sprite_body = request(sprite_refs[0].decode("ascii"))
        assert sprite_status == 200 and sprite_body.startswith(b"\x89PNG"), (sprite_status, sprite_refs[0])
        status, _location, manifest_body = request("/static/assets/desktop/manifest.json")
        assert status == 200
        manifest = json.loads(manifest_body)
        assert "class-warrior" in manifest["sprites"] and "building-tavern" in manifest["sprites"]
        assert not any(item.cls.__name__ == "SessionMiddleware" for item in app.user_middleware)
        backup_status, _location, backup_body = request(
            f"/desktop/api/campaigns/{campaign.campaign_id}/backup", method="POST"
        )
        assert backup_status == 200, backup_body
        assert json.loads(backup_body)["message"] == "Cópia de segurança criada com sucesso."
        status, location, _body = request("/tutorial/start", method="POST")
        assert status == 303 and location == "/tutorial?step=1", (status, location)
        status, _location, _body = request(
            "/session/confirmation-preferences", method="POST", body="key=desktop_smoke"
        )
        assert status == 204, status
        with SessionLocal() as db:
            metadata = db.get(CampaignMetadata, campaign.campaign_id)
            assert '"desktop_smoke":false' in metadata.confirmation_preferences
        status, location, _body = request("/desktop/return-to-campaigns", method="POST")
        assert status == 303 and location == "/desktop/campaigns", (status, location)
        assert app.state.active_campaign is None
        assert campaign.campaign_id in app.state.suspended_campaigns
        with closing(sqlite3.connect(campaign.database_path)) as connection:
            session_state, closed_at = connection.execute(
                "SELECT last_session_state, last_clean_shutdown_utc FROM campaign_metadata WHERE campaign_id = ?",
                (campaign.campaign_id,),
            ).fetchone()
        assert session_state == "offline" and closed_at is not None, (session_state, closed_at)

        previous_campaign = saves.create_campaign("Save de versao anterior")
        with closing(sqlite3.connect(previous_campaign.database_path)) as connection:
            connection.execute(
                "UPDATE campaign_metadata SET schema_version = 1 WHERE campaign_id = ?",
                (previous_campaign.campaign_id,),
            )
            connection.commit()
        status, _location, migration_body = request(
            f"/desktop/api/campaigns/{previous_campaign.campaign_id}/open",
            method="POST",
            body="{}",
        )
        assert status == 200, migration_body
        migration_response = json.loads(migration_body)
        notice = migration_response["migration_notice"]
        assert notice == {
            "previous_revision": notice["previous_revision"],
            "current_revision": notice["current_revision"],
            "previous_save_version": 1,
            "current_save_version": 3,
            "backup_created": True,
        }, notice
        backup_files = list(
            (Path(data_dir) / "backups" / previous_campaign.campaign_id).glob("pre-migration-*.db")
        )
        assert len(backup_files) == 1, backup_files
        with closing(sqlite3.connect(backup_files[0])) as connection:
            backup_version, backup_revision = connection.execute(
                "SELECT campaign_metadata.schema_version, alembic_version.version_num "
                "FROM campaign_metadata CROSS JOIN alembic_version WHERE campaign_id = ?",
                (previous_campaign.campaign_id,),
            ).fetchone()
        assert backup_version == 1, backup_version
        with closing(sqlite3.connect(previous_campaign.database_path)) as connection:
            current_revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert notice["previous_revision"] == backup_revision, notice
        assert notice["current_revision"] == current_revision, notice
        status, _location, dashboard_body = request("/dashboard")
        assert status == 200
        assert b'role="status" aria-live="polite"' in dashboard_body
        assert "Dados da campanha atualizados.".encode("utf-8") in dashboard_body
        assert "Versão 1 → 3".encode("utf-8") in dashboard_body
        assert "cópia de segurança foi criada antes da atualização".encode("utf-8") in dashboard_body
        assert str(backup_files[0]).encode("utf-8") not in dashboard_body
        assert str(backup_files[0]).encode("utf-8") not in migration_body
        assert b"offline-dialog" not in dashboard_body
        status, _location, next_dashboard_body = request("/dashboard")
        assert status == 200
        assert b"save-migration-notice" not in next_dashboard_body
    finally:
        from app.desktop.lifecycle import close_campaign
        close_campaign(app, saves, guard)
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        configure_database("sqlite:///:memory:")
        gc.collect()
'''
            environment = os.environ.copy()
            environment["APP_MODE"] = "desktop"
            environment["LOCALAPPDATA"] = temp_dir
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
