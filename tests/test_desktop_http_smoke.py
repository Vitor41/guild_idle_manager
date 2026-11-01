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
from unittest.mock import patch
os.environ["APP_MODE"] = "desktop"
from app.main import app
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.desktop.lifecycle import open_campaign
from app.services.campaign_service import CampaignService
from app.database.connection import SessionLocal, configure_database
from app.models import (CampaignMetadata, ClassChangeRun, DungeonRun, DungeonRunMember, GatheringAssignment, Guild, GuildBuilding, GuildResources,
    GuildInventoryItem, GuildSalvageJob, ItemTemplate, MarketSale, MercenaryClass, MissionRun,
    MissionRunMember, ProfessionTemplate, ProfessionTraining)
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop
from app.models.regional import RegionalCycle, RegionalEvent, RegionalEventActivity, RegionalEventParticipant, RegionalGuildState, RegionalOffer, RegionalRegionState
from app.models.mercenary import Mercenary
from app.models.achievement import AchievementTemplate, GuildAchievement
from app.models.item import GuildItemInstance
from app.models.mission import MissionTemplate
from app.models.building import BuildingTemplate
from app.repositories.mercenary_repository import create_mercenary
from app.services.regional_cycle_service import REGIONS, ensure_campaign_world
from app.services.regional_event_service import expire_due_events
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
    guard = ClockGuard(MemoryAnchorStore(), lambda: datetime.now(timezone.utc), time.monotonic)
    app.state.campaign_service = saves
    app.state.clock_guard = guard
    app.state.suspended_campaigns = set()

    def request(path, method="GET", body=None, extra_headers=None):
        client = http.client.HTTPConnection("127.0.0.1", port, timeout=40)
        headers = {"Host": host}
        headers.update(extra_headers or {})
        if method not in {"GET", "HEAD"}:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = "application/json" if body.startswith("{") else "application/x-www-form-urlencoded"
        client.request(method, path, body=body, headers=headers)
        response = client.getresponse()
        result = response.status, response.getheader("location"), response.read()
        client.close()
        return result

    async def fail_gameplay_action():
        raise RuntimeError("password=do-not-log Authorization=Bearer do-not-log-this")

    app.add_api_route("/regional/test-diagnostic", fail_gameplay_action, methods=["POST"])

    create_status, _create_location, create_body = request(
        "/desktop/api/campaigns", method="POST", body=json.dumps({"guild_name": "Smoke desktop"}),
    )
    assert create_status == 200, create_body
    created_campaign = json.loads(create_body)
    campaign = saves.inspect_campaign(created_campaign["campaign_id"])
    assert created_campaign["redirect"] == "/dashboard"
    stamina_status, _stamina_location, stamina_body = request("/desktop/api/stamina-status")
    stamina_payload = json.loads(stamina_body)
    assert stamina_status == 200 and stamina_payload["available"] is True, stamina_payload
    assert stamina_payload["stamina_seconds"] == 8 * 3600
    with closing(sqlite3.connect(campaign.database_path)) as connection:
        persisted_stamina = connection.execute(
            "SELECT stamina_seconds FROM campaign_metadata WHERE campaign_id = ?",
            (campaign.campaign_id,),
        ).fetchone()[0]
    assert persisted_stamina == 8 * 3600, "the status endpoint must not mutate the saved balance"
    with SessionLocal() as db:
        guild = db.query(Guild).first()
        mercenary_class = db.query(MercenaryClass).order_by(MercenaryClass.id).first()
        item_template = db.query(ItemTemplate).filter(ItemTemplate.icon_group.is_not(None)).order_by(ItemTemplate.id).first()
        assert guild and mercenary_class and item_template, "campaign must seed display entities for the desktop art smoke"
        guild_id = guild.id
        mercenary_class_id = mercenary_class.id
        mercenary = create_mercenary(db, guild.id, mercenary_class, "Teste visual")
        gathering_worker = create_mercenary(db, guild.id, mercenary_class, "Trabalhador disponível")
        regional_no_supply_worker = create_mercenary(db, guild.id, mercenary_class, "Contrato sem suprimento")
        regional_supply_worker = create_mercenary(db, guild.id, mercenary_class, "Contrato preparado")
        no_building_mission_worker = create_mercenary(db, guild.id, mercenary_class, "Missão sem prédios")
        no_building_dungeon_worker = create_mercenary(db, guild.id, mercenary_class, "Masmorra sem prédios")
        no_building_boss_worker = create_mercenary(db, guild.id, mercenary_class, "Chefe sem prédios")
        db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=item_template.id, quantity=1))
        db.flush()
        mercenary_id = mercenary.id
        gathering_worker_id = gathering_worker.id
        regional_no_supply_worker_id = regional_no_supply_worker.id
        regional_supply_worker_id = regional_supply_worker.id
        no_building_mission_worker_id = no_building_mission_worker.id
        no_building_dungeon_worker_id = no_building_dungeon_worker.id
        no_building_boss_worker_id = no_building_boss_worker.id
        for worker in (regional_no_supply_worker, regional_supply_worker):
            worker.level = 1
            worker.power, worker.vitality, worker.agility, worker.intelligence, worker.luck = 6, 4, 4, 2, 3
        now = datetime.now(timezone.utc)
        later = now + timedelta(hours=1)
        mission_template = db.query(MissionTemplate).filter(
            MissionTemplate.is_active.is_(True), MissionTemplate.mission_type.notin_(("gathering", "long_idle")),
        ).order_by(MissionTemplate.id).first()
        dungeon_template = db.query(DungeonTemplate).filter(DungeonTemplate.is_active.is_(True)).first()
        profession = db.query(ProfessionTemplate).filter(ProfessionTemplate.is_active.is_(True)).first()
        target_class = db.query(MercenaryClass).filter(MercenaryClass.id != mercenary.class_id).first()
        assert mission_template and dungeon_template and profession and target_class
        regional_mission_template_id = mission_template.id
        mission_template.min_party_size = 1
        mission_template.max_party_size = 1
        mission_template.required_guild_level = 1
        mission_template.required_min_mercenary_level = 1
        # Deliberately require a level-one Contract Office in the template:
        # regional contract start must still work with no buildings at all.
        mission_template.required_building_type = "contract_office"
        mission_template.required_building_level = 1
        no_building_mission_template = db.query(MissionTemplate).filter(
            MissionTemplate.is_active.is_(True), MissionTemplate.id != mission_template.id,
            MissionTemplate.mission_type.notin_(("gathering", "long_idle")),
        ).order_by(MissionTemplate.id).first()
        no_building_dungeon_template = db.query(DungeonTemplate).filter(
            DungeonTemplate.is_active.is_(True), DungeonTemplate.id != dungeon_template.id,
            DungeonTemplate.content_type == "dungeon",
        ).order_by(DungeonTemplate.id).first()
        no_building_boss_template = db.query(DungeonTemplate).filter(
            DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "boss",
        ).order_by(DungeonTemplate.id).first()
        assert no_building_mission_template and no_building_dungeon_template and no_building_boss_template
        no_building_mission_template.required_guild_level = 1
        no_building_mission_template.required_min_mercenary_level = 1
        no_building_mission_template.min_party_size = 1
        no_building_mission_template.max_party_size = 1
        no_building_mission_template.required_building_type = "contract_office"
        no_building_mission_template.required_building_level = 1
        for content_template in (no_building_dungeon_template, no_building_boss_template):
            content_template.required_guild_level = 1
            content_template.required_min_mercenary_level = 1
            content_template.min_party_size = 1
            content_template.max_party_size = 1
            content_template.required_total_power = 0
            content_template.required_class_code = None
            content_template.required_tank_count = 0
            content_template.required_support_count = 0
            content_template.required_damage_count = 0
            content_template.required_equipment_tier = 0
            content_template.required_building_type = "scouts"
            content_template.required_building_level = 1
        no_building_mission_template_id = no_building_mission_template.id
        no_building_dungeon_template_id = no_building_dungeon_template.id
        no_building_boss_template_id = no_building_boss_template.id
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
        eligible_region = db.query(RegionalRegionState).filter_by(campaign_id=campaign.campaign_id).order_by(RegionalRegionState.region_code).first()
        if eligible_region is None:
            ensure_campaign_world(db, db.get(CampaignMetadata, campaign.campaign_id), guild)
            eligible_region = db.query(RegionalRegionState).filter_by(campaign_id=campaign.campaign_id).order_by(RegionalRegionState.region_code).first()
        assert eligible_region
        eligible_region.threat = 90
        eligible_region.security = 20
        db.commit()

    try:
        rendered_pages = {}
        page_paths = ("/desktop/campaigns", "/dashboard", "/tavern", "/mercenaries", f"/mercenaries/{mercenary_id}", "/missions", "/gathering", "/dungeons", "/regional", "/codex", "/inventory", "/buildings", "/market", "/blacksmith", "/professions", "/class-change", "/docks", "/tutorial")
        for path in page_paths:
            if path == "/dashboard":
                with patch("app.services.regional_event_service.REBELLION_CHANCE", 1.0):
                    status, _location, body = request(path)
            else:
                status, _location, body = request(path)
            assert status == 200, (path, status, body[:400])
            assert b"Internal Server Error" not in body, path
            rendered_pages[path] = body

        with SessionLocal() as db:
            db.query(GuildBuilding).filter_by(guild_id=guild_id).delete(synchronize_session=False)
            active_cycle = db.query(RegionalCycle).filter_by(
                campaign_id=campaign.campaign_id, status="open",
            ).order_by(RegionalCycle.cycle_number.desc()).first()
            resources = db.query(GuildResources).filter_by(guild_id=guild_id).one()
            assert active_cycle is not None
            resources.gold = 1000
            home_region_code = next(code for code, name in REGIONS if name == campaign.home_region)
            no_supply_offer = RegionalOffer(
                campaign_id=campaign.campaign_id, cycle_id=active_cycle.id,
                cycle_number=active_cycle.cycle_number, region_code=home_region_code,
                offer_type="contract", slot=9001, mission_template_id=regional_mission_template_id,
                rank="E", name_snapshot="Contrato de teste sem suprimento",
                recommended_level_snapshot=1, recommended_power_snapshot=10,
                min_party_size_snapshot=1, max_party_size_snapshot=1,
                duration_seconds_snapshot=60, gold_reward_snapshot=100,
                xp_reward_snapshot=10, success_chance_snapshot=80,
            )
            prepared_offer = RegionalOffer(
                campaign_id=campaign.campaign_id, cycle_id=active_cycle.id,
                cycle_number=active_cycle.cycle_number, region_code=home_region_code,
                offer_type="contract", slot=9002, mission_template_id=regional_mission_template_id,
                rank="E", name_snapshot="Contrato de teste preparado",
                recommended_level_snapshot=1, recommended_power_snapshot=10,
                min_party_size_snapshot=1, max_party_size_snapshot=1,
                duration_seconds_snapshot=60, gold_reward_snapshot=100,
                xp_reward_snapshot=10, success_chance_snapshot=80,
            )
            db.add_all([no_supply_offer, prepared_offer])
            db.flush()
            no_supply_offer_id, prepared_offer_id = no_supply_offer.id, prepared_offer.id
            db.commit()

        no_supply_gold_before = 1000
        rejected_supply_status, rejected_supply_location, _rejected_supply_body = request(
            f"/regional/offers/{no_supply_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_no_supply_worker_id}&supply=1",
        )
        assert rejected_supply_status == 303 and rejected_supply_location.startswith("/regional?error="), (
            rejected_supply_status, rejected_supply_location,
        )
        rejected_supply_page_status, _rejected_supply_page_location, rejected_supply_page = request(rejected_supply_location)
        assert rejected_supply_page_status == 200 and b"Prepare o suprimento antes de iniciar" in rejected_supply_page

        no_supply_status, no_supply_location, no_supply_body = request(
            f"/regional/offers/{no_supply_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_no_supply_worker_id}",
        )
        assert no_supply_status == 303 and no_supply_location.startswith("/missions?message="), (
            no_supply_status, no_supply_location, no_supply_body[:300],
        )
        with SessionLocal() as db:
            no_supply_offer = db.get(RegionalOffer, no_supply_offer_id)
            no_supply_run = db.query(MissionRun).filter_by(regional_offer_id=no_supply_offer_id).one()
            no_supply_worker = db.get(Mercenary, regional_no_supply_worker_id)
            assert no_supply_offer.status == "in_progress"
            assert no_supply_run.preparation_snapshot_json is None
            assert no_supply_run.rank_snapshot == "E"
            assert no_supply_worker.status == "busy"
            assert db.query(GuildBuilding).filter_by(guild_id=guild_id).count() == 0
            assert db.get(Guild, guild_id).level == 1
            assert db.query(GuildResources).filter_by(guild_id=guild_id).one().gold == no_supply_gold_before

        quote_status, _quote_location, quote_body = request(
            f"/regional/offers/{prepared_offer_id}/supply-quote", method="POST",
            body=f"mercenary_ids={regional_supply_worker_id}",
        )
        supply_quote = json.loads(quote_body)
        assert quote_status == 200 and supply_quote["available"] is True, (quote_status, supply_quote)
        assert supply_quote["chance_bonus_pp"] == 5 and supply_quote["cost_gold"] > 0, supply_quote
        assert supply_quote["base_final_chance"] >= 86, supply_quote
        assert supply_quote["final_chance"] == min(95, supply_quote["base_final_chance"] + 5), supply_quote
        assert supply_quote["cost_gold"] == 1, supply_quote
        prepare_status, prepare_location, prepare_body = request(
            f"/regional/offers/{prepared_offer_id}/prepare", method="POST",
            body=f"mercenary_ids={regional_supply_worker_id}&supply=1",
        )
        assert prepare_status == 303 and prepare_location.startswith("/regional?message="), (
            prepare_status, prepare_location, prepare_body[:300],
        )
        with SessionLocal() as db:
            prepared_offer = db.get(RegionalOffer, prepared_offer_id)
            resources_after_prepare = db.query(GuildResources).filter_by(guild_id=guild_id).one().gold
            preparation = json.loads(prepared_offer.supply_preparation_snapshot_json)
            assert prepared_offer.status == "supply_preparing"
            assert preparation["prepared_for_offer_id"] == prepared_offer_id
            assert preparation["mercenary_ids"] == [str(regional_supply_worker_id)]
            assert preparation["chance_bonus_pp"] == 5
            assert preparation["cost_gold"] == supply_quote["cost_gold"]
            assert resources_after_prepare == 1000 - supply_quote["cost_gold"]

        preparation_deadline = time.monotonic() + 4
        while time.monotonic() < preparation_deadline:
            progress_status, _progress_location, progress_body = request("/regional")
            assert progress_status == 200
            if "Preparação concluída · pronta para iniciar".encode("utf-8") in progress_body:
                break
            time.sleep(0.1)
        assert "Preparação concluída · pronta para iniciar".encode("utf-8") in progress_body, "the server countdown must reach prepared state"
        assert re.search(rb'<progress max="100" value="100"', progress_body), progress_body[:2000]

        prepared_start_status, prepared_start_location, prepared_start_body = request(
            f"/regional/offers/{prepared_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_supply_worker_id}",
        )
        assert prepared_start_status == 303 and prepared_start_location.startswith("/missions?message="), (
            prepared_start_status, prepared_start_location, prepared_start_body[:300],
        )
        with SessionLocal() as db:
            prepared_offer = db.get(RegionalOffer, prepared_offer_id)
            prepared_run = db.query(MissionRun).filter_by(regional_offer_id=prepared_offer_id).one()
            prepared_worker = db.get(Mercenary, regional_supply_worker_id)
            run_snapshot = json.loads(prepared_run.preparation_snapshot_json)
            assert prepared_offer.status == "in_progress" and prepared_offer.supply_prepared_at_utc is not None
            assert run_snapshot["chance_bonus_pp"] == 5
            assert run_snapshot["cost_gold"] == supply_quote["cost_gold"]
            assert prepared_worker.status == "busy"
            assert db.query(GuildResources).filter_by(guild_id=guild_id).one().gold == resources_after_prepare

        gathering_status, gathering_location, gathering_body = request(
            "/gathering/assign", method="POST",
            body=f"mercenary_id={gathering_worker_id}&resource_family=wood",
        )
        assert gathering_status == 303 and gathering_location.startswith("/gathering?message="), (gathering_status, gathering_location, gathering_body[:300])
        with SessionLocal() as db:
            assignment = db.query(GatheringAssignment).filter_by(mercenary_id=gathering_worker_id, resource_family="wood").one_or_none()
            assert assignment is not None, "gathering form POST must persist its worker assignment"
            gathering_worker = db.get(Mercenary, gathering_worker_id)
            assert gathering_worker.status == "gathering"
            from app.services.gathering_service import advance_all_assignments
            guild_row = db.get(Guild, guild_id)
            cycle_result = advance_all_assignments(
                db, guild_row, now=assignment.started_at_utc.replace(tzinfo=timezone.utc) + timedelta(seconds=60),
            )
            assert cycle_result["wood"]["cycles"] == 1, cycle_result
            db.commit()
            db.refresh(assignment)
            assert assignment.cycle_count == 1 and assignment.progress_seconds == 0

        with SessionLocal() as db:
            from app.services.dungeon_service import start_dungeon
            from app.services.mission_service import start_mission
            guild_row = db.get(Guild, guild_id)
            assert db.query(GuildBuilding).filter_by(guild_id=guild_id).count() == 0
            normal_run = start_mission(
                db, guild_row, str(no_building_mission_template_id), [str(no_building_mission_worker_id)],
                commit=False,
            )
            dungeon_run_without_building = start_dungeon(
                db, guild_row, str(no_building_dungeon_template_id), [str(no_building_dungeon_worker_id)],
                commit=False,
            )
            boss_run_without_building = start_dungeon(
                db, guild_row, str(no_building_boss_template_id), [str(no_building_boss_worker_id)],
                commit=False,
            )
            db.commit()
            assert normal_run.id and dungeon_run_without_building.id and boss_run_without_building.id
            assert db.get(Mercenary, no_building_mission_worker_id).status == "busy"
            assert db.get(Mercenary, no_building_dungeon_worker_id).status == "busy"
            assert db.get(Mercenary, no_building_boss_worker_id).status == "busy"

        with SessionLocal() as db:
            guild_row = db.get(Guild, guild_id)
            resources = db.query(GuildResources).filter_by(guild_id=guild_id).one()
            resources.gold = 1000
            for family in ("wood", "ore"):
                material = db.query(ItemTemplate).filter_by(item_type="material", material_family=family).first()
                assert material is not None, f"test content must seed {family}"
                inventory_material = db.query(GuildInventoryItem).filter_by(
                    guild_id=guild_id, item_template_id=material.id,
                ).one_or_none()
                if inventory_material is None:
                    inventory_material = GuildInventoryItem(
                        guild_id=guild_id, item_template_id=material.id, quantity=100,
                    )
                    db.add(inventory_material)
                else:
                    inventory_material.quantity += 100
            db.flush()
            from app.repositories.item_repository import sync_inventory_resource_totals
            sync_inventory_resource_totals(db, resources)
            from app.services.building_service import ensure_guild_buildings
            tavern_building = next(
                building for building in ensure_guild_buildings(db, guild_id)
                if building.building_template.effect_type == "tavern"
            )
            tavern_building_id = tavern_building.id
            db.commit()
        first_upgrade_status, first_upgrade_location, _first_upgrade_body = request(
            f"/buildings/{tavern_building_id}/upgrade", method="POST", body="",
            extra_headers={"X-GIM-Diagnostic-ID": "1111111111111111"},
        )
        assert first_upgrade_status == 303 and first_upgrade_location.startswith("/buildings?message="), (
            first_upgrade_status, first_upgrade_location,
        )
        with SessionLocal() as db:
            tavern_building = db.get(GuildBuilding, tavern_building_id)
            assert tavern_building.level == 1, "building purchase must persist through the desktop route"
        second_upgrade_status, second_upgrade_location, _second_upgrade_body = request(
            f"/buildings/{tavern_building_id}/upgrade", method="POST", body="",
            extra_headers={"X-GIM-Diagnostic-ID": "2222222222222222"},
        )
        assert second_upgrade_status == 303 and second_upgrade_location.startswith("/buildings?message="), (
            second_upgrade_status, second_upgrade_location,
        )
        with SessionLocal() as db:
            tavern_building = db.get(GuildBuilding, tavern_building_id)
            assert tavern_building.level == 2, "building upgrade must persist through the desktop route"

        error_status, error_location, _error_body = request(
            "/regional/test-diagnostic", method="POST", body="",
            extra_headers={"X-GIM-Diagnostic-ID": "0123456789abcdef"},
        )
        assert error_status == 303 and error_location.startswith("/regional?"), (error_status, error_location)
        diagnostic_status, _diagnostic_location, diagnostic_page = request(error_location)
        assert diagnostic_status == 200
        assert b"A a\xc3\xa7\xc3\xa3o n\xc3\xa3o foi conclu\xc3\xadda" in diagnostic_page
        assert b"0123456789abcdef" in diagnostic_page
        client_failure_status, _client_failure_location, client_failure_body = request(
            "/desktop/api/diagnostics/client-error", method="POST",
            body=json.dumps({"route": f"/regional/offers/{prepared_offer_id}/prepare", "phase": "client_request_failed"}),
            extra_headers={"X-GIM-Diagnostic-ID": "fedcba9876543210"},
        )
        assert client_failure_status == 200 and json.loads(client_failure_body)["recorded"] is True
        client_start_status, _client_start_location, client_start_body = request(
            "/desktop/api/diagnostics/client-event", method="POST",
            body=json.dumps({"route": "/buildings/8/upgrade", "phase": "submit_started"}),
            extra_headers={"X-GIM-Diagnostic-ID": "abcdef0123456789"},
        )
        assert client_start_status == 200 and json.loads(client_start_body)["recorded"] is True
        gameplay_log = Path(os.environ["LOCALAPPDATA"]) / "GuildIdleManager" / "logs" / "gameplay-actions.log"
        gameplay_log_text = gameplay_log.read_text(encoding="utf-8")
        for action_name in ("gathering.assign", "regional.offer.start", "regional.offer.prepare", f"buildings.{tavern_building_id}.upgrade"):
            assert f"action={action_name}" in gameplay_log_text
        assert f"event=start action=buildings.{tavern_building_id}.upgrade route=/buildings/{tavern_building_id}/upgrade ref=1111111111111111" in gameplay_log_text
        assert "status=500 outcome=unexpected_exception" in gameplay_log_text
        assert "status=0 outcome=client_request_failed" in gameplay_log_text
        assert "event=start action=buildings.8.upgrade route=/buildings/8/upgrade ref=abcdef0123456789 status=0 outcome=client_submit_started" in gameplay_log_text
        assert "event=start action=gathering.assign" in gameplay_log_text
        assert "event=result action=gathering.assign" in gameplay_log_text
        assert "Traceback (most recent call last)" in gameplay_log_text
        assert "do-not-log" not in gameplay_log_text and "do-not-log-this" not in gameplay_log_text
        assert b"/static/js/regional-supply.js?v=20261031-1" in rendered_pages["/dungeons"]
        assert b"Modo Offline" in rendered_pages["/dashboard"]
        assert b"Estamina 8h 0min / 8h" in rendered_pages["/dashboard"]
        assert b"2h de estamina por 1h online" in rendered_pages["/dashboard"]
        assert b"/static/js/offline-stamina.js?v=20261030-1" in rendered_pages["/dashboard"]
        assert re.search(rb'data-evolution-countdown="[^"]+\+00:00"', rendered_pages["/regional"])
        supply_script_status, _location, supply_script = request("/static/js/regional-supply.js")
        assert supply_script_status == 200 and b'select[name="run_multiplier"]' in supply_script
        dashboard_with_invite = rendered_pages["/dashboard"]
        assert b'data-regional-rebellion-auto-open' in dashboard_with_invite
        assert b'value="accept"' in dashboard_with_invite and b'value="decline"' in dashboard_with_invite
        assert b'href="/regional#events-title"' in dashboard_with_invite
        assert b'href="/gathering"' in dashboard_with_invite
        assert b'href="/codex"' in dashboard_with_invite
        assert b"Conquistas e C\xc3\xb3dex" in rendered_pages["/codex"]
        campaign_page = rendered_pages["/desktop/campaigns"]
        assert b"Nome da guilda" in campaign_page and b"Nome da campanha" not in campaign_page
        assert re.search(rb'<h3>Smoke desktop</h3>\s*<p class="campaign-region">Regi\xc3\xa3o natal: [^<]+', campaign_page)
        assert all(selector in campaign_page for selector in (
            b"open-campaign", b"rename-campaign", b"backup-campaign", b"export-campaign",
            b"restore-campaign", b"delete-campaign", b"import-campaign",
        ))
        assert b"/static/css/desktop-campaigns.css?v=20261029-2" in campaign_page
        assert b"Trilhas de conquistas" in rendered_pages["/codex"]
        codex_page = rendered_pages["/codex"]
        assert b"evolution/illustrations/achievement-reliquary.webp" in codex_page
        assert b"evolution/sprites/ui_64/achievement-medal.png" in codex_page
        assert b'href="#codex-achievements"' in codex_page
        assert b'href="#codex-legendary"' in codex_page
        assert b'href="#codex-collection"' in codex_page
        assert b'id="codex-legendary"' in codex_page and bytes((79, 32, 195, 154)) + b"ltimo Desafio" in codex_page
        assert b'class="codex-legendary-card' in codex_page
        assert b'role="progressbar"' in codex_page
        assert b"sprites/64/" in codex_page
        assert b'aria-valuenow=' in codex_page and b'aria-label="Filtrar trilhas"' in codex_page
        assert b'aria-label="Filtrar C\xc3\xb3dex"' in codex_page
        assert b'class="codex-card__heading"' in codex_page
        assert b"Ver requisito e estado" in rendered_pages["/codex"]
        css_status, _location, codex_css = request("/static/css/main.css")
        assert css_status == 200
        assert b".codex-legendary-card.is-ready" in codex_css
        assert b".codex-page-heading__art" in codex_css
        assert b"@media (max-width: 640px)" in codex_css
        codex_status, _location, codex_filtered = request("/codex?category=class&trail=events")
        assert codex_status == 200 and b'href="/codex?category=class&amp;trail=events"' in codex_filtered
        assert b"criterion_type" not in codex_filtered and b"mercenaries_hired" not in codex_filtered
        detail_link = re.search(
            rb'href="/codex\?category=class&amp;trail=events&amp;entry=(\d+)#codex-entry-detail"',
            codex_filtered,
        )
        assert detail_link is not None, codex_filtered[:800]
        detail_status, _location, codex_detail = request(
            f"/codex?category=class&trail=events&entry={detail_link.group(1).decode('ascii')}"
        )
        assert detail_status == 200 and b"DETALHES DO REGISTRO" in codex_detail, (detail_status, codex_detail[:1000])
        assert b"Ver contribui\xc3\xa7\xc3\xa3o e resultado" in rendered_pages["/regional"]
        assert b"evolution/illustrations/gathering-worksite.webp" in rendered_pages["/gathering"]
        assert b"events-title" in rendered_pages["/regional"]
        assert b'/static/js/evolution-dialogs.js?v=20261030-2' in dashboard_with_invite
        with SessionLocal() as db:
            invite_event = db.query(RegionalEvent).filter_by(
                campaign_id=campaign.campaign_id, event_type="rebellion", status="active",
            ).one()
            invite_event_id = invite_event.id
            invite_cycle = invite_event.trigger_cycle_number
            invite_rows_before = db.query(RegionalEvent).filter_by(
                campaign_id=campaign.campaign_id, event_type="rebellion",
                trigger_cycle_number=invite_cycle,
            ).count()
            assert invite_rows_before == 5
            invited_participant = db.query(RegionalEventParticipant).filter_by(
                event_id=invite_event.id, guild_state_id=db.query(RegionalGuildState).filter_by(
                    campaign_id=campaign.campaign_id, guild_id=guild_id,
                ).one().id,
            ).one()
            assert invited_participant.status == "invited"
        repeat_status, _location, repeat_dashboard = request("/dashboard")
        assert repeat_status == 200 and b'data-regional-rebellion-auto-open' in repeat_dashboard
        with SessionLocal() as db:
            assert db.query(RegionalEvent).filter_by(
                campaign_id=campaign.campaign_id, event_type="rebellion",
                trigger_cycle_number=invite_cycle,
            ).count() == invite_rows_before, "an open route must not reroll an already-resolved cycle decision"
        decision_status, decision_location, _decision_body = request(
            f"/regional/events/{invite_event_id}/decision", method="POST", body="decision=accept",
        )
        assert decision_status == 303 and decision_location.endswith("#events-title")
        with SessionLocal() as db:
            invite_event = db.get(RegionalEvent, invite_event_id)
            invited_participant = db.query(RegionalEventParticipant).filter_by(event_id=invite_event_id).one()
            assert invite_event.player_decision == "accept" and invited_participant.status == "accepted"
        post_decision_status, _location, post_decision_dashboard = request("/dashboard")
        assert post_decision_status == 200 and b'data-regional-rebellion-auto-open' not in post_decision_dashboard
        assert b"/static/js/desktop-art.js" in rendered_pages["/dashboard"]
        assert b"/css/desktop-theme.css?v=20261027-1" in rendered_pages["/dashboard"]
        assert b'desktop-resource-row' in rendered_pages["/dashboard"]
        assert b'desktop-operations-band' in rendered_pages["/dashboard"]
        assert b'desktop-operations-intro desktop-page-hero' in rendered_pages["/missions"]
        assert b'desktop-operations-intro desktop-page-hero' in rendered_pages["/dungeons"]
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
            from app.services.achievement_service import LEGENDARY_MILESTONES, AchievementError, claim_achievement, ensure_campaign_achievement_catalog
            ensure_campaign_achievement_catalog(db)
            milestones = [db.query(AchievementTemplate).filter_by(key=key).one() for key, *_ in LEGENDARY_MILESTONES]
            milestone_slots = [item.equipment_slot for row in milestones for item in [row.reward_item_template]]
            milestone_item_ids = [row.reward_item_template_id for row in milestones]
            assert len(milestones) == 4 and len(set(milestone_item_ids)) == 4, (milestone_item_ids, milestone_slots)
            assert milestone_slots == [row[-1] for row in LEGENDARY_MILESTONES], milestone_slots
            resources = db.query(GuildResources).filter_by(guild_id=guild_id).one()
            initial_gold = resources.gold
            for template in milestones:
                achievement = db.query(GuildAchievement).filter_by(
                    guild_id=guild_id, achievement_template_id=template.id,
                ).one_or_none()
                if achievement is None:
                    achievement = GuildAchievement(guild_id=guild_id, achievement_template_id=template.id)
                    db.add(achievement)
                achievement.progress = template.threshold
                achievement.unlocked_at = datetime.now(timezone.utc)
                achievement.claimed_at = None
                db.flush()
                claim_achievement(db, db.get(Guild, guild_id), resources, achievement.id)
                instances_before_retry = db.query(GuildItemInstance).filter_by(
                    guild_id=guild_id, item_template_id=template.reward_item_template_id,
                ).all()
                assert len(instances_before_retry) == 1
                instance = instances_before_retry[0]
                assert instance.equipment_slot == template.reward_item_template.equipment_slot
                if template.reward_item_template.rng_bonus_max > 0:
                    assert instance.rng_bonus_attribute and template.reward_item_template.rng_bonus_min <= instance.rng_bonus_value <= template.reward_item_template.rng_bonus_max
                try:
                    claim_achievement(db, db.get(Guild, guild_id), resources, achievement.id)
                except AchievementError:
                    pass
                else:
                    raise AssertionError(f"duplicate claim was accepted for {template.key}")
                assert db.query(GuildItemInstance).filter_by(
                    guild_id=guild_id, item_template_id=template.reward_item_template_id,
                ).count() == 1
            assert resources.gold == initial_gold
            from app.services.regional_cycle_service import REGIONS
            from app.services.regional_event_service import build_portal_boss_snapshot, build_portal_loot_snapshot
            portal_template = db.query(DungeonTemplate).filter(
                DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "boss",
                DungeonTemplate.biome == "portal",
            ).order_by(DungeonTemplate.id).first()
            player_state = db.query(RegionalGuildState).filter_by(
                campaign_id=campaign.campaign_id, guild_id=guild_id,
            ).one()
            assert portal_template and player_state, "campaign should have a portal boss and home regional guild"
            portal_template.min_party_size = 1
            portal_template.max_party_size = 5
            portal_template.required_guild_level = 1
            portal_template.required_min_mercenary_level = 1
            portal_template.required_total_power = 0
            portal_template.required_class_code = None
            portal_template.required_tank_count = 0
            portal_template.required_support_count = 0
            portal_template.required_damage_count = 0
            portal_template.required_equipment_tier = 0
            portal_template.required_building_type = None
            portal_template.required_building_level = 0
            portal_template.duration_seconds = 3600
            portal_template.base_gold_reward = 100
            portal_template.base_xp_reward = 100
            portal_template.base_success_chance = 50
            generic_portal_drops = db.query(DungeonTemplateItemDrop).filter_by(
                dungeon_template_id=portal_template.id, is_active=True,
            ).all()
            assert generic_portal_drops, "portal template fixture should have generic drops to prove they are replaced"
            for generic_drop in generic_portal_drops:
                generic_drop.drop_chance = 100
            portal_loot_snapshot = build_portal_loot_snapshot(db, portal_template, "e" * 64)
            assert portal_loot_snapshot["entries"] and portal_loot_snapshot["version"] == "portal-loot-v1"
            portal_boss_snapshot = build_portal_boss_snapshot(portal_template)
            portal_item_snapshot = portal_loot_snapshot["entries"][0]["item_snapshot"]
            original_boss_name = portal_boss_snapshot["name"]
            original_item_name = portal_item_snapshot["name"]
            home_code = next(code for code, name in REGIONS if name == metadata.home_region)
            portal_event = RegionalEvent(
                campaign_id=campaign.campaign_id, event_type="portal", region_code=home_code,
                trigger_cycle_number=555, rules_version="regional-events-v1", seed="e" * 64,
                status="active", dungeon_template_id=portal_template.id,
                created_at_utc=datetime.now(timezone.utc),
                expires_at_utc=datetime.now(timezone.utc) + timedelta(hours=3),
                summary_json=json.dumps({
                    "portal_boss": {"version": "portal-boss-v1", "template": portal_boss_snapshot},
                    "portal_loot": portal_loot_snapshot,
                }),
            )
            db.add(portal_event)
            db.flush()
            portal_event_id = portal_event.id
            portal_template_id = portal_template.id
            portal_class = db.get(MercenaryClass, mercenary_class_id)
            portal_mercenary = create_mercenary(db, guild_id, portal_class, "Equipe do Portal")
            db.flush()
            portal_mercenary_id = portal_mercenary.id
            # Admin edits after the event spawn must not change its boss or loot.
            portal_template.name = "Chefe editado após o surgimento"
            portal_template.duration_seconds = 7200
            portal_template.base_gold_reward = 99999
            portal_template.base_xp_reward = 99999
            portal_template.base_success_chance = 5
            portal_template.min_party_size = 5
            portal_template.required_min_mercenary_level = 99
            portal_template.required_guild_level = 99
            portal_template.required_total_power = 999999
            portal_template.is_active = False
            portal_item_template = db.get(ItemTemplate, portal_item_snapshot["id"])
            portal_item_template.name = "Item editado após o surgimento"
            portal_item_template.equipment_slot = "ring"
            portal_item_template.required_level = 999
            portal_item_template.tier = 99
            portal_item_template.bonus_power = 0
            portal_item_template.bonus_vitality = 0
            portal_item_template.rng_bonus_min = 0
            portal_item_template.rng_bonus_max = 0
            portal_item_template.is_active = False
            db.commit()
        status, location, portal_start_body = request(
            f"/regional/events/{portal_event_id}/portals/start", method="POST",
            body=f"mercenary_ids={portal_mercenary_id}",
        )
        assert status == 303 and location == "/dungeons?message=Expedi%C3%A7%C3%A3o%20de%20portal%20iniciada", (status, location, portal_start_body)
        with SessionLocal() as db:
            portal_run = db.query(DungeonRun).filter_by(
                guild_id=guild_id, dungeon_template_id=portal_template_id, status="in_progress",
            ).one()
            run_id = portal_run.id
            assert (portal_run.ends_at - portal_run.started_at).total_seconds() >= 3600
            portal_activity = db.query(RegionalEventActivity).filter_by(
                event_id=portal_event_id, source_type="dungeon", source_run_id=run_id,
            ).one()
            assert portal_activity.status == "in_progress"
            portal_run.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        class FixedPortalRoll:
            def __init__(self, *_args): pass
            def randint(self, low, _high): return low
        with patch("app.services.dungeon_service.Random", FixedPortalRoll), patch(
            "app.services.dungeon_service.randint", return_value=1,
        ):
            status, _location, portal_claim_body = request(f"/dungeons/{run_id}/claim", method="POST", body="")
        assert status == 303, (status, portal_claim_body)
        with SessionLocal() as db:
            portal_event = db.get(RegionalEvent, portal_event_id)
            portal_activity = db.query(RegionalEventActivity).filter_by(event_id=portal_event_id).one()
            participant = db.query(RegionalEventParticipant).filter_by(event_id=portal_event_id).one()
            assert portal_event.status == "active" and portal_activity.status == "resolved"
            assert participant.success is not None and portal_activity.successes + portal_activity.failures == 1
            portal_summary = json.loads(portal_event.summary_json)
            assert portal_summary["portal_loot"]["version"] == "portal-loot-v1"
            assert portal_summary["portal_boss"]["template"]["name"] == original_boss_name
            assert portal_summary["portal_boss"]["template"]["duration_seconds"] == 3600
            assert portal_summary["portal_loot_result"]["table_version"] == "portal-loot-v1"
            assert participant.success is True, "the portal run should resolve using the frozen boss snapshot"
            resolved_run = db.get(DungeonRun, run_id)
            assert resolved_run.gold_reward < 99999 and resolved_run.xp_reward < 99999
            assert (resolved_run.ends_at - resolved_run.started_at).total_seconds() < 7200
            assert 1 <= portal_summary["portal_loot_result"]["roll_ticket"] <= 100
            result_details = json.loads(resolved_run.result_details)
            portal_item_id = portal_summary["portal_loot_result"]["item_template_id"]
            assert portal_item_id == portal_item_snapshot["id"]
            frozen_item_label = " ".join(original_item_name.split()[:3])
            assert any(frozen_item_label in item for item in result_details["items"])
            portal_instance = db.query(GuildItemInstance).filter_by(
                guild_id=guild_id, item_template_id=portal_item_id,
            ).order_by(GuildItemInstance.id.desc()).first()
            assert portal_instance is not None
            assert portal_instance.equipment_slot == portal_item_snapshot["equipment_slot"]
            assert portal_instance.required_level == portal_item_snapshot["required_level"]
            assert portal_instance.bonus_power == portal_item_snapshot["bonus_power"]
            assert portal_instance.bonus_vitality == portal_item_snapshot["bonus_vitality"]
            if portal_item_snapshot["rng_bonus_max"] > 0:
                assert portal_item_snapshot["rng_bonus_min"] <= portal_instance.rng_bonus_value <= portal_item_snapshot["rng_bonus_max"]
            expire_due_events(db, campaign.campaign_id, portal_event.expires_at_utc)
            db.refresh(portal_event)
            portal_summary = json.loads(portal_event.summary_json)
            assert portal_event.status == "resolved"
            assert portal_summary["aggregate"] == {"entries": 1, "successes": 1, "failures": 0}
            assert len(portal_summary["participant_results"]) == 1
        status, _location, _duplicate_claim_body = request(f"/dungeons/{run_id}/claim", method="POST", body="")
        assert status == 303
        with SessionLocal() as db:
            assert db.query(RegionalEventActivity).filter_by(event_id=portal_event_id).count() == 1
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

        return_at = datetime.fromisoformat(closed_at)
        simulated_now = [return_at + timedelta(minutes=30)]
        guard.wall_clock = lambda: simulated_now[0]
        status, _location, open_body = request(
            f"/desktop/api/campaigns/{campaign.campaign_id}/open", method="POST", body="{}"
        )
        assert status == 200, open_body
        offline_summary = json.loads(open_body)["offline_summary"]
        assert offline_summary and offline_summary["elapsed_seconds"] == 30 * 60, offline_summary
        status, _location, pending_dashboard = request("/dashboard")
        assert status == 200 and b'id="offline-dialog"' in pending_dashboard, status
        assert b'data-requires-ack="True"' in pending_dashboard
        with closing(sqlite3.connect(campaign.database_path)) as connection:
            pending_report = connection.execute(
                "SELECT pending_offline_report FROM campaign_metadata WHERE campaign_id = ?",
                (campaign.campaign_id,),
            ).fetchone()[0]
        pending_id = json.loads(pending_report)["report_id"]
        status, _location, still_pending_dashboard = request("/dashboard")
        assert status == 200 and b'id="offline-dialog"' in still_pending_dashboard
        status, _location, acknowledgement = request(
            "/desktop/api/offline-report/acknowledge", method="POST",
            body=json.dumps({"report_id": pending_id}),
        )
        assert status == 200 and json.loads(acknowledgement)["acknowledged"] is True, acknowledgement
        with closing(sqlite3.connect(campaign.database_path)) as connection:
            pending_after_ack, acknowledged_at = connection.execute(
                "SELECT campaign_metadata.pending_offline_report, offline_return_reports.acknowledged_at_utc "
                "FROM campaign_metadata JOIN offline_return_reports ON offline_return_reports.report_id = ? "
                "WHERE campaign_metadata.campaign_id = ?",
                (pending_id, campaign.campaign_id),
            ).fetchone()
        assert pending_after_ack is None and acknowledged_at is not None
        status, _location, acknowledged_dashboard = request("/dashboard")
        assert status == 200 and b'id="offline-dialog"' not in acknowledged_dashboard
        status, location, _body = request("/desktop/return-to-campaigns", method="POST")
        assert status == 303 and location == "/desktop/campaigns"

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
            "current_save_version": 6,
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
        assert "Versão 1 → 6".encode("utf-8") in dashboard_body
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
            environment["PYTHONPATH"] = os.pathsep.join(filter(None, (
                str(Path(__file__).resolve().parents[1]), environment.get("PYTHONPATH", ""),
            )))
            script_path = Path(temp_dir) / "desktop_http_smoke_child.py"
            script_path.write_text(script, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
