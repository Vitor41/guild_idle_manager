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
import gc, http.client, json, logging, os, re, socket, sqlite3, tempfile, threading, time
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs, unquote_plus, urlsplit
from unittest.mock import patch
os.environ["APP_MODE"] = "desktop"
from app.main import app
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.desktop.lifecycle import close_campaign, open_campaign
from app.services.campaign_service import CampaignService
from app.database.connection import SessionLocal, configure_database
from app.models import (CampaignMetadata, ClassChangeRun, DungeonRun, DungeonRunMember, GatheringAssignment, Guild, GuildBuilding, GuildResources,
    GuildInventoryItem, GuildSalvageJob, ItemTemplate, MarketSale, MercenaryClass, MissionRun,
    MissionRunMember, ProfessionTemplate, ProfessionTraining)
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop
from app.models.regional import RegionalCpuCyclePlan, RegionalCycle, RegionalEvent, RegionalEventActivity, RegionalEventParticipant, RegionalGuildState, RegionalOffer, RegionalRegionState, RegionalRunOutcome
from app.models.mercenary import Mercenary
from app.models.achievement import AchievementTemplate, GuildAchievement
from app.models.item import GuildItemInstance
from app.models.mission import MissionTemplate
from app.models.building import BuildingTemplate
from app.models.tavern import TavernSpecialOffer
from app.repositories.mercenary_repository import create_mercenary
from app.services.regional_cycle_service import REGIONS, ensure_campaign_world, get_regional_board
from app.services.regional_event_service import expire_due_events
from app.services.equipment_service import RARITY_BONUS_RULES, get_item_bonus_rolls
from app.services.display_service import clean_generated_name
from app.services.icon_service import get_class_icon_path
from sqlalchemy import select
import uvicorn

with tempfile.TemporaryDirectory() as data_dir:
    desktop_log = Path(data_dir) / "logs" / "desktop.log"
    desktop_log.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(desktop_log, encoding="utf-8")],
        force=True,
    )
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
            headers.setdefault("Origin", origin)
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
        mercenary_class = next((candidate for candidate in db.query(MercenaryClass).order_by(MercenaryClass.id).all()
                                if get_class_icon_path(candidate)), None)
        regional_class_icon_path = get_class_icon_path(mercenary_class) if mercenary_class else None
        item_template = db.query(ItemTemplate).filter(
            ItemTemplate.icon_group.is_not(None), ItemTemplate.item_type == "material",
        ).order_by(ItemTemplate.id).first()
        equipment_template = db.query(ItemTemplate).filter(
            ItemTemplate.item_type == "equipment",
            ItemTemplate.equipment_slot.in_("helmet chest gloves boots main_hand off_hand necklace earring belt ring".split()),
        ).order_by(ItemTemplate.id).first()
        equipment_route_template = db.query(ItemTemplate).filter(
            ItemTemplate.item_type == "equipment",
            ItemTemplate.equipment_slot == "ring",
        ).order_by(ItemTemplate.id).first()
        assert guild and mercenary_class and regional_class_icon_path and item_template and equipment_template and equipment_route_template, "campaign must seed display entities for the desktop art smoke"
        guild_id = guild.id
        smoke_market_item_template_id = item_template.id
        mercenary_class_id = mercenary_class.id
        mercenary = create_mercenary(db, guild.id, mercenary_class, "Teste visual")
        db.flush()
        equipped_detail_item = GuildItemInstance(
            guild_id=guild.id,
            item_template_id=equipment_template.id,
            equipped_to_mercenary_id=mercenary.id,
            equipment_slot=equipment_template.equipment_slot,
            required_level=1,
            bonus_power=3,
            bonus_rolls=[
                {"kind": "normal", "attribute": "power", "value": 2},
                {"kind": "strong", "attribute": "power", "value": 12},
            ],
            upgrade_level=2,
        )
        db.add(equipped_detail_item)
        db.add(GuildItemInstance(
            guild_id=guild.id,
            item_template_id=equipment_template.id,
            equipped_to_mercenary_id=None,
            equipment_slot=equipment_template.equipment_slot,
            required_level=1,
            bonus_power=2,
            bonus_rolls=[],
            upgrade_level=0,
        ))
        gathering_worker = create_mercenary(db, guild.id, mercenary_class, "Trabalhador disponível")
        meat_gathering_worker = create_mercenary(db, guild.id, mercenary_class, "Trabalhador de Carne")
        live_gathering_worker = create_mercenary(db, guild.id, mercenary_class, "Trabalhador ao vivo")
        regional_no_supply_worker = create_mercenary(db, guild.id, mercenary_class, "Contrato sem suprimento")
        regional_supply_worker = create_mercenary(db, guild.id, mercenary_class, "Contrato preparado")
        regional_snapshot_worker_a = create_mercenary(db, guild.id, mercenary_class, "Snapshot equipe A")
        regional_snapshot_worker_b = create_mercenary(db, guild.id, mercenary_class, "Snapshot equipe B")
        regional_reinforce_prepared_worker = create_mercenary(db, guild.id, mercenary_class, "Equipe preparada para reforço")
        regional_reinforce_extra_worker = create_mercenary(db, guild.id, mercenary_class, "Reforço disponível")
        regional_ineligible_worker = create_mercenary(db, guild.id, mercenary_class, "Snapshot inelegível")
        no_building_mission_worker = create_mercenary(db, guild.id, mercenary_class, "Missão sem prédios")
        no_building_dungeon_worker = create_mercenary(db, guild.id, mercenary_class, "Masmorra sem prédios")
        no_building_boss_worker = create_mercenary(db, guild.id, mercenary_class, "Chefe sem prédios")
        db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=item_template.id, quantity=1))
        db.flush()
        mercenary_id = mercenary.id
        equipment_route_mercenary = create_mercenary(db, guild.id, mercenary_class, "Equipamento HTTP")
        db.flush()
        equipment_route_equipped_item = GuildItemInstance(
            guild_id=guild.id,
            item_template_id=equipment_route_template.id,
            equipped_to_mercenary_id=equipment_route_mercenary.id,
            equipment_slot="ring",
            required_level=1,
        )
        equipment_route_second_equipped_item = GuildItemInstance(
            guild_id=guild.id,
            item_template_id=equipment_route_template.id,
            equipped_to_mercenary_id=equipment_route_mercenary.id,
            equipment_slot="ring",
            required_level=1,
        )
        equipment_route_free_item = GuildItemInstance(
            guild_id=guild.id,
            item_template_id=equipment_route_template.id,
            equipped_to_mercenary_id=None,
            equipment_slot="ring",
            required_level=1,
        )
        foreign_guild = Guild(campaign_id=None, name="Guilda externa do smoke", level=1)
        db.add(foreign_guild)
        db.flush()
        foreign_mercenary = create_mercenary(db, foreign_guild.id, mercenary_class, "Mercenário externo")
        foreign_item = GuildItemInstance(
            guild_id=foreign_guild.id,
            item_template_id=equipment_route_template.id,
            equipped_to_mercenary_id=None,
            equipment_slot="ring",
            required_level=1,
        )
        db.add_all((
            equipment_route_equipped_item,
            equipment_route_second_equipped_item,
            equipment_route_free_item,
            foreign_item,
        ))
        db.flush()
        equipment_route_mercenary_id = equipment_route_mercenary.id
        equipment_route_equipped_item_id = equipment_route_equipped_item.id
        equipment_route_second_equipped_item_id = equipment_route_second_equipped_item.id
        equipment_route_free_item_id = equipment_route_free_item.id
        foreign_mercenary_id = foreign_mercenary.id
        foreign_item_id = foreign_item.id
        gathering_worker_id = gathering_worker.id
        meat_gathering_worker_id = meat_gathering_worker.id
        live_gathering_worker_id = live_gathering_worker.id
        regional_no_supply_worker_id = regional_no_supply_worker.id
        regional_supply_worker_id = regional_supply_worker.id
        regional_snapshot_worker_a_id = regional_snapshot_worker_a.id
        regional_snapshot_worker_b_id = regional_snapshot_worker_b.id
        regional_reinforce_prepared_worker_id = regional_reinforce_prepared_worker.id
        regional_reinforce_extra_worker_id = regional_reinforce_extra_worker.id
        regional_ineligible_worker_id = regional_ineligible_worker.id
        no_building_mission_worker_id = no_building_mission_worker.id
        no_building_dungeon_worker_id = no_building_dungeon_worker.id
        no_building_boss_worker_id = no_building_boss_worker.id
        for worker in (
            regional_no_supply_worker, regional_supply_worker,
            regional_reinforce_prepared_worker, regional_reinforce_extra_worker,
        ):
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
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="blacksmith").one().id, level=25))
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="tavern").one().id, level=1))
        db.add(GuildBuilding(guild_id=guild.id, building_template_id=db.query(BuildingTemplate).filter_by(effect_type="docks").one().id, level=1))
        db.add(TavernSpecialOffer(
            guild_id=guild.id,
            name="Oferta Rara de teste",
            class_id=mercenary_class.id,
            rarity="rare",
            level=1,
            power=31,
            vitality=19,
            agility=17,
            intelligence=13,
            luck=11,
            gold_cost=4321,
            available_from=now,
            available_until=later,
            status="active",
        ))
        mission_run = MissionRun(guild_id=guild.id, mission_template_id=mission_template.id, started_at=now, ends_at=later)
        dungeon_run = DungeonRun(guild_id=guild.id, dungeon_template_id=dungeon_template.id, started_at=now, ends_at=later)
        db.add_all([mission_run, dungeon_run])
        db.flush()
        db.add_all([MissionRunMember(mission_run_id=mission_run.id, mercenary_id=mercenary.id),
            DungeonRunMember(dungeon_run_id=dungeon_run.id, mercenary_id=mercenary.id)])
        smoke_market_sale = MarketSale(guild_id=guild.id, item_template_id=item_template.id, quantity=1, unit_value=1,
            total_value=1, started_at=now, ends_at=later)
        db.add(smoke_market_sale)
        db.flush()
        smoke_market_sale_id = smoke_market_sale.id
        initial_market_gold = db.query(GuildResources).filter_by(guild_id=guild.id).one().gold
        db.add(ProfessionTraining(guild_id=guild.id, mercenary_id=mercenary.id, profession_id=profession.id,
            started_at=now, ends_at=later))
        db.add(ClassChangeRun(guild_id=guild.id, mercenary_id=mercenary.id, from_class_id=mercenary.class_id,
            to_class_id=target_class.id, gold_cost=1, started_at=now, ends_at=later))
        material = db.query(ItemTemplate).filter(ItemTemplate.item_type == "material").first()
        assert material
        inventory_material = db.query(GuildInventoryItem).filter_by(
            guild_id=guild.id, item_template_id=material.id,
        ).one_or_none()
        if inventory_material is None:
            db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=material.id, quantity=2))
        else:
            inventory_material.quantity += 2
        db.add(GuildSalvageJob(guild_id=guild.id, slot_number=2, item_template_id=item_template.id,
            material_template_id=material.id, quantity=1, gold_cost=1, started_at=now, ends_at=later))
        db.commit()
        ensure_campaign_world(db, db.get(CampaignMetadata, campaign.campaign_id), guild)
        eligible_region = db.query(RegionalRegionState).filter_by(campaign_id=campaign.campaign_id).order_by(RegionalRegionState.region_code).first()
        assert eligible_region
        eligible_region.threat = 90
        eligible_region.security = 20
        with patch("app.services.regional_event_service.REBELLION_CHANCE", 1.0):
            get_regional_board(db, db.get(CampaignMetadata, campaign.campaign_id), guild)
        outcome_state = db.query(RegionalGuildState).filter(
            RegionalGuildState.campaign_id == campaign.campaign_id,
            RegionalGuildState.guild_id.is_(None),
            RegionalGuildState.active.is_(True),
        ).order_by(RegionalGuildState.region_code, RegionalGuildState.slot).first()
        assert outcome_state is not None, "campaign should seed an active CPU guild for regional detail"
        outcome_offer = db.query(RegionalOffer).filter_by(
            campaign_id=campaign.campaign_id,
            region_code=outcome_state.region_code,
            offer_type="contract",
        ).order_by(RegionalOffer.cycle_number.desc(), RegionalOffer.slot).first()
        assert outcome_offer is not None, "campaign should seed a regional contract offer for outcome detail"
        db.add(RegionalRunOutcome(
            campaign_id=campaign.campaign_id,
            guild_state_id=outcome_state.id,
            offer_id=outcome_offer.id,
            source_type="mission",
            source_run_id=987654321,
            offer_cycle_number=outcome_offer.cycle_number,
            applied_cycle_number=outcome_offer.cycle_number,
            rank=outcome_offer.rank,
            success=True,
            contribution=1,
        ))
        home_region_code = next(code for code, name in REGIONS if name == campaign.home_region)
        player_regional_state = db.query(RegionalGuildState).filter_by(
            campaign_id=campaign.campaign_id, guild_id=guild.id,
        ).one()
        pending_portal = db.query(RegionalEvent).filter_by(
            campaign_id=campaign.campaign_id, event_type="portal", region_code=home_region_code, status="active",
        ).filter(RegionalEvent.expires_at_utc > now).order_by(RegionalEvent.expires_at_utc).first()
        if pending_portal is None:
            pending_portal = RegionalEvent(
                campaign_id=campaign.campaign_id, event_type="portal", region_code=home_region_code,
                trigger_cycle_number=10000, rules_version="smoke",
                seed="portal-notice-smoke", status="active", dungeon_template_id=dungeon_template.id,
                created_at_utc=now, expires_at_utc=now + timedelta(hours=3), summary_json="{}",
            )
            db.add(pending_portal)
            db.flush()
        portal_notice_event_id = pending_portal.id
        portal_notice_state_id = player_regional_state.id
        regional_outcome_region_code = outcome_state.region_code
        regional_outcome_guild_name = outcome_state.name
        regional_outcome_state_id = outcome_state.id
        outcome_offer_id = outcome_offer.id
        outcome_offer_type = outcome_offer.offer_type
        cpu_comparison_state = db.query(RegionalGuildState).filter(
            RegionalGuildState.campaign_id == campaign.campaign_id,
            RegionalGuildState.region_code == outcome_state.region_code,
            RegionalGuildState.guild_id.is_(None),
            RegionalGuildState.id != outcome_state.id,
            RegionalGuildState.active.is_(True),
        ).order_by(RegionalGuildState.slot).first()
        assert cpu_comparison_state is not None
        cpu_plan = db.query(RegionalCpuCyclePlan).filter_by(
            campaign_id=campaign.campaign_id, cycle_id=outcome_offer.cycle_id,
            guild_state_id=cpu_comparison_state.id,
        ).one_or_none()
        if cpu_plan is None:
            cpu_plan = RegionalCpuCyclePlan(
                campaign_id=campaign.campaign_id, cycle_id=outcome_offer.cycle_id,
                guild_state_id=cpu_comparison_state.id, seed="comparison-smoke",
            )
            db.add(cpu_plan)
        cpu_plan.outcomes_json = json.dumps([{"offer_id": outcome_offer.id, "success": False}])
        cpu_plan.successes = 0
        cpu_plan.failures = 1
        db.flush()
        cpu_plan_id = cpu_plan.id
        cpu_comparison_state_id = cpu_comparison_state.id
        db.commit()

    try:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            handlers=[logging.FileHandler(desktop_log, encoding="utf-8")],
            force=True,
        )
        with patch("app.services.regional_event_service.REBELLION_CHANCE", 1.0), patch(
            "app.routes.regional_routes.get_regional_board",
            side_effect=RuntimeError("Falha de consulta da tela de atividades"),
        ):
            failed_status, _failed_location, failed_body = request("/regional")
            assert failed_status == 500
            assert "Não foi possível abrir esta tela".encode("utf-8") in failed_body
            assert "Tentar novamente".encode("utf-8") in failed_body
            diagnostic_match = re.search(rb"Refer\xc3\xaancia: <code>([a-f0-9]{32})</code>", failed_body)
            assert diagnostic_match, failed_body
            regional_diagnostic_id = diagnostic_match.group(1).decode("ascii")
        desktop_trace = desktop_log.read_text(encoding="utf-8")
        assert f"Unhandled desktop request method=GET route=/regional ref={regional_diagnostic_id}" in desktop_trace, desktop_trace
        assert "RuntimeError: Falha de consulta da tela de atividades" in desktop_trace
        rendered_pages = {}
        regional_outcome_path = f"/regional/regions/{regional_outcome_region_code}"
        page_paths = ("/desktop/campaigns", "/dashboard", "/tavern", "/mercenaries", f"/mercenaries/{mercenary_id}", "/missions", "/gathering", "/workshops", "/dungeons", "/regional", "/regional/events", regional_outcome_path, "/codex", "/guide", "/inventory", "/buildings", "/market", "/blacksmith", "/professions", "/class-change", "/docks", "/guild/progress", "/tutorial", "/updates")
        for path in page_paths:
            if path in {"/dashboard", "/regional", "/regional/events"}:
                with patch("app.services.regional_event_service.REBELLION_CHANCE", 1.0):
                    status, _location, body = request(path)
            else:
                status, _location, body = request(path)
            assert status == 200, (path, status, body[:400])
            assert b"Internal Server Error" not in body, path
            rendered_pages[path] = body
        central_events_page = rendered_pages["/regional/events"]
        regional_class_icon_url = f"/static/{regional_class_icon_path.lstrip('/')}".encode("utf-8")
        assert b'aria-labelledby="map-title"' in rendered_pages["/regional"]
        assert '<summary id="map-title">Estado das cinco regiões</summary>'.encode("utf-8") in rendered_pages["/regional"]
        assert b"data-check-local-update" in rendered_pages["/updates"]
        update_check_status, _update_check_location, update_check_body = request("/updates/check")
        assert update_check_status == 200 and b'"channel":"dev-local"' in update_check_body, update_check_body[:400]
        assert b'id="regional-portals"' in central_events_page
        assert b'id="regional-rebellions"' in central_events_page
        regional_events_nav = re.search(
            rb'<nav class="classes-guide-index regional-events-index"[^>]*>.*?</nav>',
            central_events_page, re.S,
        )
        assert regional_events_nav, "the event hub should link its two primary sections"
        assert len(re.findall(rb'<a href="#regional-(?:portals|rebellions)"', regional_events_nav.group(0))) == 2
        assert b"Hist\xc3\xb3rico" not in regional_events_nav.group(0)
        regional_sidebar_events = re.search(rb'<a href="/regional/events"[^>]*>', central_events_page)
        regional_sidebar_vigil = re.search(rb'<a href="/regional"[^>]*>', central_events_page)
        vigil_page = rendered_pages["/regional"]
        vigil_sidebar_events = re.search(rb'<a href="/regional/events"[^>]*>', vigil_page)
        vigil_sidebar_vigil = re.search(rb'<a href="/regional"[^>]*>', vigil_page)
        assert regional_sidebar_events and b'aria-current="page"' in regional_sidebar_events.group(0)
        assert regional_sidebar_vigil and b'aria-current="page"' not in regional_sidebar_vigil.group(0)
        assert vigil_sidebar_vigil and b'aria-current="page"' in vigil_sidebar_vigil.group(0)
        assert vigil_sidebar_events and b'aria-current="page"' not in vigil_sidebar_events.group(0)
        assert b'data-nav-work-menu="regional_events"' in central_events_page
        equipment_detail_page = rendered_pages[f"/mercenaries/{mercenary_id}"]
        assert b"data-equipment-details-trigger" in equipment_detail_page
        assert b"role=\"region\" aria-label=\"Detalhes de" in equipment_detail_page
        assert b"FORTE FOR +12" in equipment_detail_page
        assert b"FOR +5 normal" in equipment_detail_page
        assert b"FORTE FOR +12" in equipment_detail_page
        assert b"= +17 aplicado" in equipment_detail_page
        assert b"/static/js/equipment-details.js" in equipment_detail_page

        def assert_equipment_error(location, expected_path, expected_reason):
            assert location, "equipment rejection should preserve a safe return location"
            parsed = urlsplit(location)
            assert parsed.path == expected_path, location
            query = parse_qs(parsed.query)
            actual_reason = query.get("error", [""])[0]
            assert expected_reason in actual_reason, f"expected={expected_reason!r}, actual={actual_reason!r}, location={location}"
            diagnostic_id = query.get("diagnostic", [""])[0]
            assert re.fullmatch(r"[a-fA-F0-9-]{16,40}", diagnostic_id), location
            status, _detail_location, detail_body = request(location)
            assert status == 200, (location, status, detail_body[:600])
            assert expected_reason.encode("utf-8") in detail_body
            assert b"Refer\xc3\xaancia de diagn\xc3\xb3stico" in detail_body
            assert diagnostic_id.encode("ascii") in detail_body
            return diagnostic_id

        equipment_route = f"/mercenaries/{equipment_route_mercenary_id}/equip"
        slot_failure_status, slot_failure_location, _slot_failure_body = request(
            equipment_route,
            method="POST",
            body=f"item_instance_id={equipment_route_free_item_id}",
            extra_headers={"X-GIM-Diagnostic-ID": "invalid/reference"},
        )
        assert slot_failure_status == 303, (slot_failure_status, slot_failure_location)
        slot_failure_diagnostic = assert_equipment_error(
            slot_failure_location,
            f"/mercenaries/{equipment_route_mercenary_id}",
            "Escolha qual equipamento deste slot deseja substituir.",
        )
        with SessionLocal() as db:
            assert db.get(GuildItemInstance, equipment_route_equipped_item_id).equipped_to_mercenary_id == equipment_route_mercenary_id
            assert db.get(GuildItemInstance, equipment_route_second_equipped_item_id).equipped_to_mercenary_id == equipment_route_mercenary_id
            assert db.get(GuildItemInstance, equipment_route_free_item_id).equipped_to_mercenary_id is None

        validation_diagnostics = []
        for item_id, expected_reason in (
            ("invalid", "Equipamento invalido."),
            ("999999999", "Equipamento nao encontrado."),
            (str(foreign_item_id), "Equipamento nao encontrado."),
        ):
            failure_status, failure_location, _failure_body = request(
                equipment_route,
                method="POST",
                body=f"item_instance_id={item_id}",
            )
            assert failure_status == 303, (failure_status, failure_location, item_id)
            validation_diagnostics.append(assert_equipment_error(
                failure_location,
                f"/mercenaries/{equipment_route_mercenary_id}",
                expected_reason,
            ))

        with SessionLocal() as db:
            http_mercenary = db.get(Mercenary, equipment_route_mercenary_id)
            http_mercenary.status = "busy"
            db.commit()
        busy_status, busy_location, _busy_body = request(
            equipment_route,
            method="POST",
            body=f"item_instance_id={equipment_route_free_item_id}",
        )
        assert busy_status == 303, (busy_status, busy_location)
        busy_diagnostic = assert_equipment_error(
            busy_location,
            f"/mercenaries/{equipment_route_mercenary_id}",
            "Mercenario ocupado nao pode trocar equipamentos.",
        )
        with SessionLocal() as db:
            db.get(Mercenary, equipment_route_mercenary_id).status = "available"
            db.commit()

        foreign_mercenary_status, foreign_mercenary_location, _foreign_mercenary_body = request(
            f"/mercenaries/{foreign_mercenary_id}/equip",
            method="POST",
            body=f"item_instance_id={equipment_route_free_item_id}",
        )
        assert foreign_mercenary_status == 303
        foreign_mercenary_diagnostic = assert_equipment_error(
            foreign_mercenary_location,
            "/mercenaries",
            "Este mercenário não está disponível nesta guilda.",
        )
        assert b"Mercen\xc3\xa1rio externo" not in request(foreign_mercenary_location)[2]

        with patch(
            "app.routes.mercenary_routes.equip_mercenary_item",
            side_effect=RuntimeError("unexpected equipment transaction failure"),
        ):
            exception_status, exception_location, _exception_body = request(
                equipment_route,
                method="POST",
                body=f"item_instance_id={equipment_route_free_item_id}",
            )
        assert exception_status == 303, (exception_status, exception_location)
        exception_diagnostic = assert_equipment_error(
            exception_location,
            f"/mercenaries/{equipment_route_mercenary_id}",
            "Não foi possível concluir o equipamento.",
        )
        assert b"unexpected equipment transaction failure" not in request(exception_location)[2]

        denied_status, denied_location, _denied_body = request(
            equipment_route,
            method="POST",
            body=f"item_instance_id={equipment_route_free_item_id}",
            extra_headers={
                "Origin": "http://invalid.example",
                "X-GIM-Diagnostic-ID": "aaaaaaaaaaaaaaaa",
            },
        )
        assert denied_status == 403 and denied_location is None
        with SessionLocal() as db:
            assert db.get(GuildItemInstance, equipment_route_equipped_item_id).equipped_to_mercenary_id == equipment_route_mercenary_id
            assert db.get(GuildItemInstance, equipment_route_second_equipped_item_id).equipped_to_mercenary_id == equipment_route_mercenary_id
            assert db.get(GuildItemInstance, equipment_route_free_item_id).equipped_to_mercenary_id is None

        success_status, success_location, _success_body = request(
            equipment_route,
            method="POST",
            body=(
                f"item_instance_id={equipment_route_free_item_id}"
                f"&replacement_item_instance_id={equipment_route_equipped_item_id}"
            ),
        )
        assert success_status == 303
        assert urlsplit(success_location).path == f"/mercenaries/{equipment_route_mercenary_id}"
        assert "error=" not in success_location
        with SessionLocal() as db:
            assert db.get(GuildItemInstance, equipment_route_equipped_item_id).equipped_to_mercenary_id is None
            assert db.get(GuildItemInstance, equipment_route_second_equipped_item_id).equipped_to_mercenary_id == equipment_route_mercenary_id
            assert db.get(GuildItemInstance, equipment_route_free_item_id).equipped_to_mercenary_id == equipment_route_mercenary_id

        assert b"data-salvage-form" in rendered_pages["/blacksmith"]
        assert b'name="item_template_id"' in rendered_pages["/blacksmith"]
        assert b'name="quantity"' in rendered_pages["/blacksmith"]
        assert b'data-salvage-cost' in rendered_pages["/blacksmith"]
        assert b'data-salvage-return' in rendered_pages["/blacksmith"]
        assert b'data-salvage-duration' in rendered_pages["/blacksmith"]
        assert b"Itens candidatos na ordem" not in rendered_pages["/blacksmith"]
        assert not re.search(rb"#[0-9]+\s", rendered_pages["/blacksmith"])
        guide_export_status, _guide_export_location, guide_export_body = request("/guide/export.md")
        assert guide_export_status == 200
        for body in (rendered_pages["/guide"], guide_export_body):
            assert "na ordem de registro do inventário".encode("utf-8") in body
            assert "retorno é sorteado por unidade entre 1 e 3 materiais".encode("utf-8") in body
        assert b'data-drop-preview' in rendered_pages["/regional"]
        assert "Drops · chance base".encode("utf-8") in rendered_pages["/regional"]
        assert b"class-requirement-card" in rendered_pages["/class-change"]
        assert b"Requisitos por etapa" in rendered_pages["/class-change"]
        assert "Navegar entre regiões".encode("utf-8") in rendered_pages[regional_outcome_path]
        assert b'class="rarity-badge rarity-rare">Raro</span>' in rendered_pages["/tavern"]
        outcome_row = next((row for row in re.findall(rb"<tr[^>]*>.*?</tr>", rendered_pages[regional_outcome_path], re.S)
                            if regional_outcome_guild_name.encode("utf-8") in row), None)
        assert outcome_row, regional_outcome_guild_name
        outcome_cells = re.findall(rb"<td[^>]*>(.*?)</td>", outcome_row, re.S)
        result_column = {"contract": 3, "dungeon": 4, "boss": 5}[outcome_offer_type]
        assert outcome_cells[result_column] == b"1", outcome_cells
        assert outcome_cells[6] == b"1 " + bytes([194, 183]) + b" 0", outcome_cells
        comparison_status, _comparison_location, comparison_body = request(
            f"/regional/regions/{regional_outcome_region_code}/comparison"
        )
        comparison_payload = json.loads(comparison_body)
        assert comparison_status == 200 and comparison_payload["guilds"][str(regional_outcome_state_id)]["results"]["successes"] == 1
        cpu_results = comparison_payload["guilds"][str(cpu_comparison_state_id)]["results"]
        assert cpu_results["contracts"] == 1 and cpu_results["failures"] == 1, cpu_results
        with SessionLocal() as db:
            refreshed_plan = db.get(RegionalCpuCyclePlan, cpu_plan_id)
            refreshed_plan.outcomes_json = json.dumps([{"offer_id": outcome_offer_id, "success": True}])
            refreshed_plan.successes = 1
            refreshed_plan.failures = 0
            db.commit()
        live_status, _live_location, live_body = request(
            f"/regional/regions/{regional_outcome_region_code}/comparison"
        )
        live_results = json.loads(live_body)["guilds"][str(cpu_comparison_state_id)]["results"]
        assert live_status == 200 and live_results["successes"] == 1 and live_results["failures"] == 0, live_results
        close_campaign(app, saves, guard)
        isolation_campaign = saves.create_campaign("Smoke isolamento", "Guilda isolamento")
        open_campaign(app, saves, guard, isolation_campaign.campaign_id)
        isolated_status, _isolated_location, isolated_body = request(
            f"/regional/regions/{regional_outcome_region_code}/comparison"
        )
        isolated_payload = json.loads(isolated_body)
        assert isolated_status == 200, (isolated_status, isolated_payload)
        assert isolated_payload["guilds"][str(cpu_comparison_state_id)]["results"]["contracts"] == 0, isolated_payload
        close_campaign(app, saves, guard)
        open_campaign(app, saves, guard, campaign.campaign_id)
        assert b"data-market-fill-max" in rendered_pages["/market"]
        assert b"Cada posto produz o mesmo material comum can\xc3\xb4nico da fam\xc3\xadlia em todos os n\xc3\xadveis da guilda" in rendered_pages["/guide"]
        assert b"cancelar antes do prazo" in rendered_pages["/guide"]
        assert b"todos os espa\xc3\xa7os de venda est\xc3\xa3o ocupados" in rendered_pages["/market"]
        assert b"Tempo base por raridade" not in rendered_pages["/market"]
        assert b"data-market-estimate" in rendered_pages["/market"]
        assert b"/market/" + str(smoke_market_sale_id).encode("ascii") + b"/cancel" in rendered_pages["/market"]
        assert b"T1\xe2\x80\x93T8" not in rendered_pages["/market"] and b"T1-T8" not in rendered_pages["/market"]
        for duration in (b"10 s", b"25 s", b"60 s", b"180 s", b"600 s", b"1.200 s"):
            assert duration in rendered_pages["/guide"], duration
        guide_export_status, _guide_export_location, guide_export_body = request("/guide/export.md")
        assert guide_export_status == 200 and b"| Raridade | Tempo-base por unidade |" in guide_export_body
        for duration in (b"10 s", b"25 s", b"60 s", b"180 s", b"600 s", b"1.200 s"):
            assert duration in guide_export_body, duration
        assert b"Pr\xc3\xb3ximo alvo dispon\xc3\xadvel" in rendered_pages["/gathering"]

        cancel_status, cancel_location, cancel_body = request(
            f"/market/{smoke_market_sale_id}/cancel", method="POST",
        )
        assert cancel_status == 303 and "Venda%20cancelada" in cancel_location, (cancel_status, cancel_location, cancel_body[:400])
        with SessionLocal() as db:
            cancelled_sale = db.get(MarketSale, smoke_market_sale_id)
            assert cancelled_sale.status == "cancelled" and cancelled_sale.cancelled_at is not None
            assert db.query(GuildResources).filter_by(guild_id=guild_id).one().gold == initial_market_gold
            assert db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=smoke_market_item_template_id,
            ).one().quantity >= 2
            assert db.query(MarketSale).filter_by(guild_id=guild_id, status="in_progress").count() == 0
        cancelled_market_status, _cancelled_market_location, cancelled_market_body = request("/market")
        assert cancelled_market_status == 200 and b"Cancelada \xc2\xb7 itens devolvidos" in cancelled_market_body

        with SessionLocal() as db:
            db.query(GuildBuilding).filter_by(guild_id=guild_id).delete(synchronize_session=False)
            active_cycle = db.query(RegionalCycle).filter_by(
                campaign_id=campaign.campaign_id, status="open",
            ).order_by(RegionalCycle.cycle_number.desc()).first()
            resources = db.query(GuildResources).filter_by(guild_id=guild_id).one()
            assert active_cycle is not None
            active_cycle_id = active_cycle.id
            resources.gold = 1000
            supply_kit = db.query(ItemTemplate).filter_by(slug="supply_kit").one()
            inventory_kit = db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit.id,
            ).one_or_none()
            if inventory_kit is None:
                db.add(GuildInventoryItem(guild_id=guild_id, item_template_id=supply_kit.id, quantity=2))
            else:
                inventory_kit.quantity = 2
            supply_kit_id = supply_kit.id
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
            ineligible_snapshot_offer = RegionalOffer(
                campaign_id=campaign.campaign_id, cycle_id=active_cycle.id,
                cycle_number=active_cycle.cycle_number, region_code=home_region_code,
                offer_type="contract", slot=9003, mission_template_id=regional_mission_template_id,
                rank="E", name_snapshot="Contrato com nível congelado",
                recommended_level_snapshot=1, recommended_power_snapshot=10,
                min_party_size_snapshot=1, max_party_size_snapshot=1,
                required_guild_level_snapshot=5, duration_seconds_snapshot=60,
                required_min_mercenary_level_snapshot=99,
                gold_reward_snapshot=100, xp_reward_snapshot=10, success_chance_snapshot=80,
            )
            party_snapshot_offer = RegionalOffer(
                campaign_id=campaign.campaign_id, cycle_id=active_cycle.id,
                cycle_number=active_cycle.cycle_number, region_code=home_region_code,
                offer_type="contract", slot=9004, mission_template_id=regional_mission_template_id,
                rank="E", name_snapshot="Contrato com grupo congelado",
                recommended_level_snapshot=1, recommended_power_snapshot=10,
                min_party_size_snapshot=2, max_party_size_snapshot=2,
                required_guild_level_snapshot=1, duration_seconds_snapshot=60,
                required_min_mercenary_level_snapshot=99,
                gold_reward_snapshot=100, xp_reward_snapshot=10, success_chance_snapshot=80,
            )
            reinforce_prepared_offer = RegionalOffer(
                campaign_id=campaign.campaign_id, cycle_id=active_cycle.id,
                cycle_number=active_cycle.cycle_number, region_code=home_region_code,
                offer_type="contract", slot=9005, mission_template_id=regional_mission_template_id,
                rank="E", name_snapshot="Contrato preparado com reforço",
                recommended_level_snapshot=1, recommended_power_snapshot=10,
                min_party_size_snapshot=1, max_party_size_snapshot=2,
                duration_seconds_snapshot=60000, gold_reward_snapshot=100,
                xp_reward_snapshot=10, success_chance_snapshot=80,
            )
            db.add_all([no_supply_offer, prepared_offer, ineligible_snapshot_offer, party_snapshot_offer, reinforce_prepared_offer])
            db.flush()
            no_supply_offer_id, prepared_offer_id = no_supply_offer.id, prepared_offer.id
            ineligible_snapshot_offer_id = ineligible_snapshot_offer.id
            party_snapshot_offer_id = party_snapshot_offer.id
            reinforce_prepared_offer_id = reinforce_prepared_offer.id
            # Simulate admin edits after offer creation: the offer's frozen level and party bounds win.
            db.get(MissionTemplate, regional_mission_template_id).required_guild_level = 99
            db.get(MissionTemplate, regional_mission_template_id).min_party_size = 1
            db.get(MissionTemplate, regional_mission_template_id).max_party_size = 1
            db.get(MissionTemplate, regional_mission_template_id).required_min_mercenary_level = 99
            db.commit()

        ineligible_start_status, ineligible_start_location, _ineligible_start_body = request(
            f"/regional/offers/{ineligible_snapshot_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_ineligible_worker_id}",
        )
        assert ineligible_start_status == 303 and ineligible_start_location.startswith("/regional?error="), (
            ineligible_start_status, ineligible_start_location,
        )
        with SessionLocal() as db:
            ineligible_offer = db.get(RegionalOffer, ineligible_snapshot_offer_id)
            ineligible_worker = db.get(Mercenary, regional_ineligible_worker_id)
            assert ineligible_offer.status == "available" and ineligible_offer.reserved_by_guild_state_id is None
            assert ineligible_worker.status == "available"
            assert db.query(MissionRun).filter_by(regional_offer_id=ineligible_snapshot_offer_id).count() == 0

        party_rejected_status, party_rejected_location, _party_rejected_body = request(
            f"/regional/offers/{party_snapshot_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_snapshot_worker_a_id}",
        )
        assert party_rejected_status == 303 and party_rejected_location.startswith("/regional?error="), (
            party_rejected_status, party_rejected_location,
        )
        with SessionLocal() as db:
            party_offer = db.get(RegionalOffer, party_snapshot_offer_id)
            party_worker_a = db.get(Mercenary, regional_snapshot_worker_a_id)
            assert party_offer.status == "available" and party_offer.reserved_by_guild_state_id is None
            assert party_worker_a.status == "available"
            assert db.query(MissionRun).filter_by(regional_offer_id=party_snapshot_offer_id).count() == 0

        party_started_status, party_started_location, party_started_body = request(
            f"/regional/offers/{party_snapshot_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_snapshot_worker_a_id}&mercenary_ids={regional_snapshot_worker_b_id}",
        )
        assert party_started_status == 303 and party_started_location.startswith("/regional?message="), (
            party_started_status, party_started_location, party_started_body[:300],
        )
        with SessionLocal() as db:
            party_offer = db.get(RegionalOffer, party_snapshot_offer_id)
            party_run = db.query(MissionRun).filter_by(regional_offer_id=party_snapshot_offer_id).one()
            team_ids = {member.mercenary_id for member in db.query(MissionRunMember).filter_by(mission_run_id=party_run.id)}
            assert party_offer.status == "in_progress"
            assert team_ids == {regional_snapshot_worker_a_id, regional_snapshot_worker_b_id}
            assert db.get(Mercenary, regional_snapshot_worker_a_id).status == "busy"
            assert db.get(Mercenary, regional_snapshot_worker_b_id).status == "busy"

        no_supply_gold_before = 1000
        rejected_supply_status, rejected_supply_location, _rejected_supply_body = request(
            f"/regional/offers/{no_supply_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_no_supply_worker_id}&supply=1",
            extra_headers={"X-GIM-Diagnostic-ID": "3333333333333333"},
        )
        assert rejected_supply_status == 303 and rejected_supply_location.startswith("/regional?error="), (
            rejected_supply_status, rejected_supply_location,
        )
        rejected_supply_page_status, _rejected_supply_page_location, rejected_supply_page = request(rejected_supply_location)
        assert rejected_supply_page_status == 200 and b"Prepare o suprimento antes de iniciar" in rejected_supply_page

        no_supply_status, no_supply_location, no_supply_body = request(
            f"/regional/offers/{no_supply_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_no_supply_worker_id}&supply_mode=none",
            extra_headers={"X-GIM-Diagnostic-ID": "4444444444444444"},
        )
        assert no_supply_status == 303 and no_supply_location.startswith("/regional?message="), (
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
            extra_headers={"X-GIM-Diagnostic-ID": "5555555555555555"},
        )
        supply_quote = json.loads(quote_body)
        assert quote_status == 200 and supply_quote["available"] is True, (quote_status, supply_quote)
        assert supply_quote["chance_bonus_pp"] == 5 and supply_quote["cost_kits"] == 1, supply_quote
        assert supply_quote["base_final_chance"] >= 86, supply_quote
        assert supply_quote["final_chance"] == min(95, supply_quote["base_final_chance"] + 5), supply_quote
        assert supply_quote["cost_gold"] == 0, supply_quote
        prepare_status, prepare_location, prepare_body = request(
            f"/regional/offers/{prepared_offer_id}/prepare", method="POST",
            body=f"mercenary_ids={regional_supply_worker_id}&supply=1",
            extra_headers={"X-GIM-Diagnostic-ID": "6666666666666666"},
        )
        assert prepare_status == 303 and prepare_location.startswith("/regional?message="), (
            prepare_status, prepare_location, prepare_body[:300],
        )
        with SessionLocal() as db:
            prepared_offer = db.get(RegionalOffer, prepared_offer_id)
            resources_after_prepare = db.query(GuildResources).filter_by(guild_id=guild_id).one().gold
            kits_after_prepare = db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit_id,
            ).one().quantity
            preparation = json.loads(prepared_offer.supply_preparation_snapshot_json)
            preparation_snapshot_text = prepared_offer.supply_preparation_snapshot_json
            assert prepared_offer.status == "supply_preparing"
            assert preparation["prepared_for_offer_id"] == prepared_offer_id
            assert preparation["mercenary_ids"] == [str(regional_supply_worker_id)]
            assert preparation["chance_bonus_pp"] == 5
            assert preparation["cost_kits"] == supply_quote["cost_kits"]
            assert kits_after_prepare == 1
            assert resources_after_prepare == 1000

        implicit_prepared_status, implicit_prepared_location, _implicit_prepared_body = request(
            f"/regional/offers/{prepared_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_supply_worker_id}",
        )
        assert implicit_prepared_status == 303 and "selected_mercenary_id=" in implicit_prepared_location
        assert "explicitamente" in implicit_prepared_location.lower(), implicit_prepared_location
        with SessionLocal() as db:
            implicit_offer = db.get(RegionalOffer, prepared_offer_id)
            assert implicit_offer.status == "supply_preparing"
            assert implicit_offer.supply_preparation_snapshot_json == preparation_snapshot_text
            assert db.query(MissionRun).filter_by(regional_offer_id=prepared_offer_id).count() == 0

        preparation_deadline = time.monotonic() + 4
        while time.monotonic() < preparation_deadline:
            progress_status, _progress_location, progress_body = request("/regional")
            assert progress_status == 200
            if "Preparação concluída · pronta para iniciar".encode("utf-8") in progress_body:
                break
            time.sleep(0.1)
        assert "Preparação concluída · pronta para iniciar".encode("utf-8") in progress_body, "the server countdown must reach prepared state"
        assert re.search(rb'<progress max="100" value="100"', progress_body), progress_body[:2000]
        prepared_dialog = re.search(
            rb'<dialog[^>]*id="offer-' + str(prepared_offer_id).encode("ascii") + rb'".*?</dialog>',
            progress_body, re.S,
        )
        assert prepared_dialog and re.search(
            rb'name="mercenary_ids" value="' + str(regional_supply_worker_id).encode("ascii") + rb'" checked>.*?Equipe preparada',
            prepared_dialog.group(0), re.S,
        ), prepared_dialog.group(0) if prepared_dialog else progress_body[:4000]
        assert b'data-prepared-team-available="true"' in prepared_dialog.group(0)
        prepared_team_status = re.findall(
            rb'<p[^>]*class="[^\"]*prepared-team-status[^\"]*"[^>]*>.*?</p>',
            prepared_dialog.group(0), re.S,
        )
        assert b'Equipe preparada selecionada' in prepared_dialog.group(0), prepared_team_status
        assert b'1 Kit(s) j\xc3\xa1 utilizado(s)' in prepared_dialog.group(0)

        with SessionLocal() as db:
            inventory_kit = db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit_id,
            ).one()
            inventory_kit.quantity = 0
            db.commit()
        empty_stock_quote_status, _empty_stock_quote_location, empty_stock_quote_body = request(
            f"/regional/offers/{prepared_offer_id}/supply-quote", method="POST",
            body=f"mercenary_ids={regional_supply_worker_id}",
        )
        empty_stock_quote = json.loads(empty_stock_quote_body)
        assert empty_stock_quote_status == 200 and empty_stock_quote["available"] is False, empty_stock_quote

        prepared_start_status, prepared_start_location, prepared_start_body = request(
            f"/regional/offers/{prepared_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_supply_worker_id}&supply_mode=prepared",
            extra_headers={"X-GIM-Diagnostic-ID": "7777777777777777"},
        )
        assert prepared_start_status == 303 and prepared_start_location.startswith("/regional?message="), (
            prepared_start_status, prepared_start_location, prepared_start_body[:300],
        )
        regional_after_start_status, _regional_after_start_location, regional_after_start_body = request("/regional")
        assert regional_after_start_status == 200 and b"Ofertas" in regional_after_start_body, (
            regional_after_start_status, regional_after_start_body[:500],
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
            assert db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit_id,
            ).one().quantity == 0

            inventory_kit = db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit_id,
            ).one()
            inventory_kit.quantity = 1
            db.commit()

        reinforce_prepare_status, reinforce_prepare_location, reinforce_prepare_body = request(
            f"/regional/offers/{reinforce_prepared_offer_id}/prepare", method="POST",
            body=f"mercenary_ids={regional_reinforce_prepared_worker_id}&supply=1",
        )
        assert reinforce_prepare_status == 303 and reinforce_prepare_location.startswith("/regional?message="), (
            reinforce_prepare_status, reinforce_prepare_location, reinforce_prepare_body[:300],
        )
        with SessionLocal() as db:
            reinforce_offer = db.get(RegionalOffer, reinforce_prepared_offer_id)
            reinforce_snapshot_text = reinforce_offer.supply_preparation_snapshot_json
            reinforce_snapshot = json.loads(reinforce_snapshot_text)
            assert reinforce_offer.status == "supply_preparing"
            assert reinforce_snapshot["mercenary_ids"] == [str(regional_reinforce_prepared_worker_id)]
            kits_during_reinforce_prepare = db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit_id,
            ).one().quantity
            assert kits_during_reinforce_prepare == 0
            reinforce_offer.supply_preparation_ends_at_utc = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        regional_during_prep_status, _regional_during_prep_location, regional_during_prep_body = request("/regional")
        assert regional_during_prep_status == 200
        offer_dialog = re.search(
            rb'<dialog[^>]*id="offer-' + str(reinforce_prepared_offer_id).encode("ascii") + rb'".*?</dialog>',
            regional_during_prep_body, re.S,
        )
        assert offer_dialog and b'name="supply_mode" value="none"' in offer_dialog.group(0)
        assert b'name="supply_mode" value="prepared"' in offer_dialog.group(0)
        assert b'Iniciar sem suprimento' in offer_dialog.group(0)
        assert b"multiplicador" not in offer_dialog.group(0).lower()
        assert re.search(
            rb'name="mercenary_ids" value="' + str(regional_reinforce_prepared_worker_id).encode("ascii")
            + rb'" checked>.*?Equipe preparada', offer_dialog.group(0), re.S,
        ), offer_dialog.group(0)
        assert re.search(
            rb'name="mercenary_ids" value="' + str(regional_reinforce_extra_worker_id).encode("ascii")
            + rb'">.*?' + "Reforço disponível".encode("utf-8"), offer_dialog.group(0), re.S,
        ), offer_dialog.group(0)
        assert b'data-prepared-team-status' in offer_dialog.group(0)

        with SessionLocal() as db:
            unavailable_worker = db.get(Mercenary, regional_reinforce_prepared_worker_id)
            unavailable_worker.status = "busy"
            db.commit()
        unavailable_page_status, _unavailable_location, unavailable_page = request("/regional")
        unavailable_dialog = re.search(
            rb'<dialog[^>]*id="offer-' + str(reinforce_prepared_offer_id).encode("ascii") + rb'".*?</dialog>',
            unavailable_page, re.S,
        )
        assert unavailable_page_status == 200 and unavailable_dialog
        assert re.search(
            rb'<input type="hidden" name="mercenary_ids" value="'
            + str(regional_reinforce_prepared_worker_id).encode("ascii")
            + rb'" data-prepared-member-hidden="true">', unavailable_dialog.group(0),
        ), unavailable_dialog.group(0)
        assert b"Equipe preparada indispon\xc3\xadvel" in unavailable_dialog.group(0)
        assert re.search(rb'name="supply_mode" value="none"[^>]* disabled', unavailable_dialog.group(0))
        with SessionLocal() as db:
            db.get(Mercenary, regional_reinforce_prepared_worker_id).status = "available"
            db.commit()

        missed_prepared_status, missed_prepared_location, _missed_prepared_body = request(
            f"/regional/offers/{reinforce_prepared_offer_id}/start", method="POST",
            body=f"mercenary_ids={regional_reinforce_extra_worker_id}&supply_mode=none",
        )
        assert missed_prepared_status == 303 and missed_prepared_location.startswith("/regional?error=")
        missed_prepared_page_status, _missed_prepared_page_location, missed_prepared_page = request(missed_prepared_location)
        assert missed_prepared_page_status == 200
        assert b"selectedIds.has(input.value) || preparedIds.has(input.value)" in missed_prepared_page
        with SessionLocal() as db:
            assert db.get(RegionalOffer, reinforce_prepared_offer_id).supply_preparation_snapshot_json == reinforce_snapshot_text
            assert db.query(MissionRun).filter_by(regional_offer_id=reinforce_prepared_offer_id).count() == 0

        wrong_prepared_status, wrong_prepared_location, _wrong_prepared_body = request(
            f"/regional/offers/{reinforce_prepared_offer_id}/start", method="POST",
            body=(f"mercenary_ids={regional_reinforce_prepared_worker_id}"
                  f"&mercenary_ids={regional_reinforce_extra_worker_id}&supply_mode=prepared"),
        )
        assert wrong_prepared_status == 303 and wrong_prepared_location.startswith("/regional?error=")
        assert "exatamente+a+equipe" in wrong_prepared_location.lower(), wrong_prepared_location

        occupied_reinforce_status, occupied_reinforce_location, _occupied_reinforce_body = request(
            f"/regional/offers/{reinforce_prepared_offer_id}/start", method="POST",
            body=(f"mercenary_ids={regional_reinforce_prepared_worker_id}"
                  f"&mercenary_ids={regional_no_supply_worker_id}&supply_mode=none"),
        )
        assert occupied_reinforce_status == 303 and occupied_reinforce_location.startswith("/regional?error="), (
            occupied_reinforce_status, occupied_reinforce_location,
        )
        with SessionLocal() as db:
            reinforce_offer = db.get(RegionalOffer, reinforce_prepared_offer_id)
            assert reinforce_offer.status == "supply_preparing"
            assert reinforce_offer.supply_preparation_snapshot_json == reinforce_snapshot_text
            assert db.query(MissionRun).filter_by(regional_offer_id=reinforce_prepared_offer_id).count() == 0

        reinforced_start_status, reinforced_start_location, reinforced_start_body = request(
            f"/regional/offers/{reinforce_prepared_offer_id}/start", method="POST",
            body=(f"mercenary_ids={regional_reinforce_prepared_worker_id}"
                  f"&mercenary_ids={regional_reinforce_extra_worker_id}&supply_mode=none"),
        )
        assert reinforced_start_status == 303 and reinforced_start_location.startswith("/regional?message="), (
            reinforced_start_status, reinforced_start_location, reinforced_start_body[:300],
        )
        with SessionLocal() as db:
            reinforce_offer = db.get(RegionalOffer, reinforce_prepared_offer_id)
            reinforce_run = db.query(MissionRun).filter_by(regional_offer_id=reinforce_prepared_offer_id).one()
            reinforce_team_ids = {
                member.mercenary_id for member in db.query(MissionRunMember).filter_by(mission_run_id=reinforce_run.id)
            }
            assert reinforce_offer.status == "in_progress"
            assert reinforce_offer.supply_preparation_snapshot_json == reinforce_snapshot_text
            assert json.loads(reinforce_offer.supply_preparation_snapshot_json)["mercenary_ids"] == [
                str(regional_reinforce_prepared_worker_id)
            ]
            assert reinforce_run.preparation_snapshot_json is None
            assert reinforce_team_ids == {
                regional_reinforce_prepared_worker_id, regional_reinforce_extra_worker_id,
            }
            assert db.get(Mercenary, regional_reinforce_prepared_worker_id).status == "busy"
            assert db.get(Mercenary, regional_reinforce_extra_worker_id).status == "busy"
            assert db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit_id,
            ).one().quantity == 0

        repeated_reinforced_status, _repeated_reinforced_location, _repeated_reinforced_body = request(
            f"/regional/offers/{reinforce_prepared_offer_id}/start", method="POST",
            body=(f"mercenary_ids={regional_reinforce_prepared_worker_id}"
                  f"&mercenary_ids={regional_reinforce_extra_worker_id}&supply_mode=none"),
        )
        assert repeated_reinforced_status == 303
        with SessionLocal() as db:
            assert db.query(MissionRun).filter_by(regional_offer_id=reinforce_prepared_offer_id).count() == 1

        gathering_status, gathering_location, gathering_body = request(
            "/gathering/assign", method="POST",
            body=f"mercenary_id={gathering_worker_id}&resource_family=wood",
            extra_headers={"X-GIM-Diagnostic-ID": "8888888888888888"},
        )
        assert gathering_status == 303 and gathering_location.startswith("/gathering?message="), (gathering_status, gathering_location, gathering_body[:300])
        with SessionLocal() as db:
            assignment = db.query(GatheringAssignment).filter_by(mercenary_id=gathering_worker_id, resource_family="wood").one_or_none()
            assert assignment is not None, "gathering form POST must persist its worker assignment"
            assert assignment.target_item_template_id is not None, "new assignment must persist its exact material target"
            wood_target_id = assignment.target_item_template_id
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
            assert assignment.target_item_template_id == wood_target_id

        with SessionLocal() as db:
            db.get(Guild, guild_id).level = 7
            db.commit()
        stable_gathering_status, _stable_gathering_location, stable_gathering_body = request("/gathering")
        assert stable_gathering_status == 200 and b"Alvo desta designa\xc3\xa7\xc3\xa3o" in stable_gathering_body
        with SessionLocal() as db:
            assignment = db.query(GatheringAssignment).filter_by(mercenary_id=gathering_worker_id).one()
            assert assignment.target_item_template_id == wood_target_id
            db.get(Guild, guild_id).level = 1
            db.commit()

        with SessionLocal() as db:
            assignment = db.query(GatheringAssignment).filter_by(
                mercenary_id=gathering_worker_id, resource_family="wood",
            ).one()
            assignment.checkpoint_at_utc = datetime.now(timezone.utc) - timedelta(seconds=60)
            assignment.capacity_paused = False
            db.commit()

        meat_status, meat_location, meat_body = request(
            "/gathering/assign", method="POST",
            body=f"mercenary_id={meat_gathering_worker_id}&resource_family=meat",
        )
        assert meat_status == 303 and meat_location.startswith("/gathering?message="), (meat_status, meat_location, meat_body[:300])
        with SessionLocal() as db:
            meat_assignment = db.query(GatheringAssignment).filter_by(
                mercenary_id=meat_gathering_worker_id, resource_family="meat",
            ).one()
            meat_assignment.checkpoint_at_utc = datetime.now(timezone.utc) - timedelta(seconds=61)
            meat_assignment.capacity_paused = False
            db.commit()
        inventory_status, _inventory_location, inventory_body = request("/inventory")
        assert inventory_status == 200, inventory_body[:300]
        assert b'data-desktop-item-family="meat"' in inventory_body, inventory_body[:1000]
        assert b"<dt>Quantidade</dt><dd>1</dd>" in inventory_body, inventory_body[:1000]
        with SessionLocal() as db:
            meat_stack = db.query(GuildInventoryItem).join(ItemTemplate).filter(
                GuildInventoryItem.guild_id == guild_id,
                ItemTemplate.item_type == "material",
                ItemTemplate.material_family == "meat",
            ).one()
            assert meat_stack.quantity == 1

        live_status, live_location, live_body = request(
            "/gathering/assign", method="POST",
            body=f"mercenary_id={live_gathering_worker_id}&resource_family=leather",
        )
        assert live_status == 303 and live_location.startswith("/gathering?message="), (live_status, live_location, live_body[:300])
        with SessionLocal() as db:
            live_assignment = db.query(GatheringAssignment).filter_by(
                mercenary_id=live_gathering_worker_id, resource_family="leather",
            ).one()
            live_assignment.checkpoint_at_utc = datetime.now(timezone.utc) - timedelta(seconds=61)
            live_assignment.capacity_paused = False
            db.commit()
        live_status, _live_location, live_body = request("/gathering/status")
        live_payload = json.loads(live_body)
        assert live_status == 200, live_body[:300]
        assert live_payload["advanced"]["leather"]["cycles"] == 1, live_payload
        assert live_payload["inventory_by_family"]["leather"] == 1, live_payload
        assert live_payload["assignments"]["leather"]["target_item_template_id"] is not None
        assert live_payload["assignments"]["leather"]["target_item_name"]
        with SessionLocal() as db:
            wood_assignment = db.query(GatheringAssignment).filter_by(
                mercenary_id=gathering_worker_id, resource_family="wood",
            ).one()
            wood_assignment.checkpoint_at_utc = datetime.now(timezone.utc) - timedelta(seconds=61)
            wood_assignment.capacity_paused = False
            db.commit()

        regional_advance_status, _regional_advance_location, regional_advance_body = request(
            "/regional", extra_headers={"X-GIM-Diagnostic-ID": "9999999999999999"},
        )
        assert regional_advance_status == 200, regional_advance_body[:300]

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
        client_click_status, _client_click_location, client_click_body = request(
            "/desktop/api/diagnostics/client-event", method="POST",
            body=json.dumps({"route": "/buildings/8/upgrade", "phase": "click_received"}),
            extra_headers={"X-GIM-Diagnostic-ID": "0123456789abcdef0"},
        )
        assert client_click_status == 200 and json.loads(client_click_body)["recorded"] is True
        gameplay_log = Path(os.environ["LOCALAPPDATA"]) / "GuildIdleManager" / "logs" / "gameplay-actions.log"
        gameplay_log_text = gameplay_log.read_text(encoding="utf-8")
        regional_production_lines = [
            line for line in gameplay_log_text.splitlines()
            if "action=gathering.production" in line and "route=/regional" in line
        ]
        assert len(regional_production_lines) == 1, regional_production_lines
        assert "family=wood cycles=1 produced=1 stored=1 discarded=0" in regional_production_lines[0]
        assert "state=active" in regional_production_lines[0]
        for action_name in ("gathering.assign", "regional.offer.start", "regional.offer.prepare", f"buildings.{tavern_building_id}.upgrade"):
            assert f"action={action_name}" in gameplay_log_text
        assert f"event=start action=buildings.{tavern_building_id}.upgrade route=/buildings/{tavern_building_id}/upgrade ref=1111111111111111" in gameplay_log_text
        assert "status=500 outcome=unexpected_exception" in gameplay_log_text
        assert "status=0 outcome=client_request_failed" in gameplay_log_text
        assert "event=start action=buildings.8.upgrade route=/buildings/8/upgrade ref=abcdef0123456789 status=0 outcome=client_submit_started" in gameplay_log_text
        assert "event=click action=buildings.8.upgrade route=/buildings/8/upgrade ref=0123456789abcdef0 status=0 outcome=client_click_received" in gameplay_log_text
        assert "event=start action=gathering.assign" in gameplay_log_text
        assert "event=result action=gathering.assign" in gameplay_log_text
        assert "Traceback (most recent call last)" in gameplay_log_text
        assert "do-not-log" not in gameplay_log_text and "do-not-log-this" not in gameplay_log_text
        base_template_for_supply_version = (Path.cwd() / "app" / "templates" / "base.html").read_bytes()
        regional_supply_version = re.search(
            rb"regional-supply\.js.*?\?v=([^\"&\s]+)", base_template_for_supply_version,
        )
        assert regional_supply_version, "base.html should declare the active regional supply script version"
        regional_supply_url = b"/static/js/regional-supply.js?v=" + regional_supply_version.group(1)
        assert regional_supply_url in rendered_pages["/dungeons"]
        assert b"Modo Offline" in rendered_pages["/dashboard"]
        assert b"Estamina 8h 0min / 8h" in rendered_pages["/dashboard"]
        assert b"2h de estamina por 1h online" in rendered_pages["/dashboard"]
        assert b"/static/js/offline-stamina.js?v=20261030-1" in rendered_pages["/dashboard"]
        assert re.search(rb'data-evolution-countdown="[^"]+\+00:00"', rendered_pages["/regional"])
        supply_script_status, _location, supply_script = request("/static/js/regional-supply.js")
        assert supply_script_status == 200 and b'select[name="run_multiplier"]' in supply_script
        dashboard_with_invite = rendered_pages["/dashboard"]
        assert b'data-regional-event-notice' not in dashboard_with_invite
        assert b'value="accept"' not in dashboard_with_invite and b'value="decline"' not in dashboard_with_invite
        assert b'href="/regional"' in dashboard_with_invite
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
        assert b"/static/css/desktop-campaigns.css?v=20261125-1" in campaign_page
        assert b"Trilhas de conquistas" in rendered_pages["/codex"]
        with SessionLocal() as db:
            first_hire_template = db.query(AchievementTemplate).filter_by(key="first_hire").one()
            first_hire = db.query(GuildAchievement).filter_by(
                guild_id=guild_id,
                achievement_template_id=first_hire_template.id,
            ).one_or_none()
            if first_hire is None:
                first_hire = GuildAchievement(
                    guild_id=guild_id,
                    achievement_template_id=first_hire_template.id,
                )
                db.add(first_hire)
            first_hire.progress = first_hire_template.threshold
            first_hire.unlocked_at = datetime.now(timezone.utc)
            first_hire.claimed_at = None
            db.flush()
            first_hire_id = first_hire.id
            first_hire_reward = first_hire_template.reward_gold
            assert first_hire_reward > 0 and first_hire_template.reward_xp == 0
            gold_before_codex_get = db.query(GuildResources).filter_by(guild_id=guild_id).one().gold
            db.commit()
        codex_ready_status, _codex_ready_location, codex_ready_body = request("/codex")
        ready_achievement_card = re.search(
            rb'<article[^>]*id="achievement-' + str(first_hire_id).encode("ascii") + rb'".*?</article>',
            codex_ready_body,
            re.S,
        )
        assert codex_ready_status == 200 and ready_achievement_card
        assert ready_achievement_card.group(0).count(b'class="codex-achievement-state"') == 1
        assert b"Pronta para resgate" in ready_achievement_card.group(0)
        assert b"Ver requisito e recompensa" in ready_achievement_card.group(0)
        assert (
            b'<form method="post" action="/codex/achievements/'
            + str(first_hire_id).encode("ascii")
            + b'/claim">'
        ) in ready_achievement_card.group(0)
        with SessionLocal() as db:
            persisted_ready = db.query(GuildAchievement).filter_by(id=first_hire_id).one()
            assert persisted_ready.claimed_at is None, "a Codex GET must not claim a ready reward"
            assert db.query(GuildResources).filter_by(guild_id=guild_id).one().gold == gold_before_codex_get
        codex_claim_status, codex_claim_location, _codex_claim_body = request(
            f"/codex/achievements/{first_hire_id}/claim", method="POST", body="",
        )
        assert codex_claim_status == 303 and codex_claim_location.startswith("/codex?message=")
        codex_claimed_status, _codex_claimed_location, codex_claimed_body = request("/codex")
        claimed_achievement_card = re.search(
            rb'<article[^>]*id="achievement-' + str(first_hire_id).encode("ascii") + rb'".*?</article>',
            codex_claimed_body,
            re.S,
        )
        assert codex_claimed_status == 200 and claimed_achievement_card
        assert b"Resgatada" in claimed_achievement_card.group(0)
        assert b"Pronta para resgate" not in claimed_achievement_card.group(0)
        assert b"/codex/achievements/" not in claimed_achievement_card.group(0)
        with SessionLocal() as db:
            persisted_claim = db.query(GuildAchievement).filter_by(id=first_hire_id).one()
            assert persisted_claim.claimed_at is not None
            assert db.query(GuildResources).filter_by(guild_id=guild_id).one().gold == gold_before_codex_get + first_hire_reward
        codex_page = codex_claimed_body
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
        assert b"Ver requisito e recompensa" in codex_page
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
        assert b"evolution/illustrations/gathering-worksite.webp" in rendered_pages["/gathering"]
        assert b"events-title" in rendered_pages["/regional"]
        base_template_for_ui_versions = (Path.cwd() / "app" / "templates" / "base.html").read_bytes()
        main_script_version = re.search(
            rb"main\.js.*?\?v=([^\"&\s]+)", base_template_for_ui_versions,
        )
        assert main_script_version, "base.html should declare the active main script version"
        main_script_url = b"/static/js/main.js?v=" + main_script_version.group(1)
        assert main_script_url in dashboard_with_invite
        main_script_status, _location, main_script = request(main_script_url.decode("ascii"))
        assert main_script_status == 200 and b"refreshRegionalEventAnchorOffset" in main_script
        evolution_dialogs_version = re.search(
            rb"evolution-dialogs\.js.*?\?v=([^\"&\s]+)", base_template_for_ui_versions,
        )
        assert evolution_dialogs_version, "base.html should declare the active evolution dialog script version"
        evolution_dialogs_url = b"/static/js/evolution-dialogs.js?v=" + evolution_dialogs_version.group(1)
        assert evolution_dialogs_url in dashboard_with_invite
        dialogs_script_status, _location, dialogs_script = request(evolution_dialogs_url.decode("ascii"))
        assert dialogs_script_status == 200 and b"GIMEnqueueRegionalNotices" in dialogs_script
        assert b'data-regional-event-notice' not in dashboard_with_invite, "event notices open when entering Vigília"
        regional_notice_status, _notice_location, regional_notice_body = request("/regional")
        assert regional_notice_status == 200
        evolution_css_version = re.search(
            rb"desktop-evolution\.css.*?\?v=([^\"&\s]+)", base_template_for_ui_versions,
        )
        assert evolution_css_version, "base.html should declare the active desktop evolution stylesheet version"
        evolution_css_url = b"/static/css/desktop-evolution.css?v=" + evolution_css_version.group(1)
        assert evolution_css_url in regional_notice_body
        evolution_css_status, _location, evolution_css = request(evolution_css_url.decode("ascii"))
        assert evolution_css_status == 200 and b"--game-sticky-topbar-height" in evolution_css
        local_portal_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(portal_notice_event_id).encode("ascii") + rb'".*?</article>',
            regional_notice_body, re.S,
        )
        assert local_portal_card
        assert b"Regi\xc3\xa3o:" in local_portal_card.group(0)
        assert b"Entrada dispon\xc3\xadvel" in local_portal_card.group(0)
        assert b"Portal aberto" not in local_portal_card.group(0)
        assert b'tabindex="-1"' in local_portal_card.group(0)
        assert b'id="regional-rebellion-notice"' in regional_notice_body
        assert b"Aceitar convite" in regional_notice_body and b"Delegar \xc3\xa0 CPU" in regional_notice_body
        assert b"regional-rebellion.webp" in regional_notice_body and b"rebellion-shield.png" in regional_notice_body
        assert b'id="regional-portal-notice"' in regional_notice_body
        assert f'id="regional-event-{portal_notice_event_id}"'.encode("ascii") in regional_notice_body
        assert b"dimensional-portal.webp" in regional_notice_body and b"portal-gate.png" in regional_notice_body
        portal_dialog = re.search(rb'<dialog[^>]*id="regional-portal-notice".*?</dialog>', regional_notice_body, re.S)
        assert portal_dialog and b"Enviar equipe" not in portal_dialog.group(0)
        assert b"Ver equipe e portal" in portal_dialog.group(0)
        with SessionLocal() as db:
            db.add(RegionalEventParticipant(
                event_id=portal_notice_event_id, guild_state_id=portal_notice_state_id, status="participating",
            ))
            db.commit()
        used_portal_status, _used_portal_location, used_portal_body = request("/regional")
        assert used_portal_status == 200 and b'id="regional-portal-notice"' not in used_portal_body
        used_portal_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(portal_notice_event_id).encode("ascii") + rb'".*?</article>',
            used_portal_body, re.S,
        )
        assert used_portal_card and b"Entrada j\xc3\xa1 utilizada" in used_portal_card.group(0)
        assert b"Portal aberto" not in used_portal_card.group(0)
        used_quote_status, _used_quote_location, used_quote_body = request(
            f"/regional/events/{portal_notice_event_id}/portals/supply-quote", method="POST", body="",
        )
        assert used_quote_status == 409, (
            used_quote_status, _used_quote_location, used_quote_body[:800],
        )
        used_quote_reason = json.loads(used_quote_body).get("reason", "")
        assert "já usou" in used_quote_reason, used_quote_reason
        with SessionLocal() as db:
            expired_portal = db.get(RegionalEvent, portal_notice_event_id)
            expired_portal.expires_at_utc = datetime.now(timezone.utc) - timedelta(seconds=5)
            db.commit()
        expired_portal_status, _expired_portal_location, expired_portal_body = request("/regional")
        assert expired_portal_status == 200 and b'id="regional-portal-notice"' not in expired_portal_body
        expired_quote_status, _expired_quote_location, expired_quote_body = request(
            f"/regional/events/{portal_notice_event_id}/portals/supply-quote", method="POST", body="",
        )
        assert expired_quote_status == 409 and "prazo" in json.loads(expired_quote_body)["reason"]
        with SessionLocal() as db:
            home_region_code = next(code for code, name in REGIONS if name == campaign.home_region)
            outside_region_code = next(code for code, _name in REGIONS if code != home_region_code)
            home_portal = db.get(RegionalEvent, portal_notice_event_id)
            outside_portal = RegionalEvent(
                campaign_id=campaign.campaign_id, event_type="portal", region_code=outside_region_code,
                trigger_cycle_number=home_portal.trigger_cycle_number, rules_version=home_portal.rules_version,
                seed="outside-home-portal-smoke", status="active",
                dungeon_template_id=home_portal.dungeon_template_id,
                created_at_utc=datetime.now(timezone.utc),
                expires_at_utc=datetime.now(timezone.utc) + timedelta(hours=3),
                summary_json=home_portal.summary_json,
            )
            db.add(outside_portal)
            db.flush()
            outside_portal_id = outside_portal.id
            db.commit()
        outside_portal_status, _outside_portal_location, outside_portal_body = request("/regional")
        outside_portal_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(outside_portal_id).encode("ascii") + rb'".*?</article>',
            outside_portal_body, re.S,
        )
        assert outside_portal_status == 200 and outside_portal_card
        assert b"Ver contribui\xc3\xa7\xc3\xa3o e resultado" in outside_portal_body
        assert b"Prazo aberto \xc2\xb7 fora do alcance da guilda" in outside_portal_card.group(0)
        assert b"Portais s\xc3\xb3 aceitam entrada na regi\xc3\xa3o natal" in outside_portal_card.group(0)
        assert b"/portals/start" not in outside_portal_card.group(0)
        central_outside_status, _central_outside_location, central_outside_body = request("/regional/events?section=portals")
        central_outside_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(outside_portal_id).encode("ascii") + rb'".*?</article>',
            central_outside_body, re.S,
        )
        assert central_outside_status == 200 and central_outside_card
        assert b"Prazo de entrada aberto \xc2\xb7 fora do alcance da guilda" in central_outside_card.group(0)
        assert b"/portals/start" not in central_outside_card.group(0)
        outside_portal_quote_status, _outside_portal_quote_location, outside_portal_quote_body = request(
            f"/regional/events/{outside_portal_id}/portals/supply-quote", method="POST", body="",
        )
        assert outside_portal_quote_status == 409
        assert "região natal" in json.loads(outside_portal_quote_body)["reason"]
        outside_portal_start_status, outside_portal_start_location, _outside_portal_start_body = request(
            f"/regional/events/{outside_portal_id}/portals/start", method="POST",
        )
        assert outside_portal_start_status == 303
        assert "região natal" in unquote_plus(outside_portal_start_location)
        with SessionLocal() as db:
            home_portal = db.get(RegionalEvent, portal_notice_event_id)
            expired_external_portal = RegionalEvent(
                campaign_id=campaign.campaign_id, event_type="portal", region_code=outside_region_code,
                trigger_cycle_number=home_portal.trigger_cycle_number + 1, rules_version=home_portal.rules_version,
                seed="expired-external-portal-smoke", status="in_progress",
                dungeon_template_id=home_portal.dungeon_template_id,
                created_at_utc=datetime.now(timezone.utc) - timedelta(minutes=20),
                expires_at_utc=datetime.now(timezone.utc) - timedelta(minutes=5),
                summary_json=home_portal.summary_json,
            )
            db.add(expired_external_portal)
            db.flush()
            expired_external_portal_id = expired_external_portal.id
            db.add(RegionalEventActivity(
                event_id=expired_external_portal.id, guild_state_id=portal_notice_state_id,
                source_type="dungeon", source_run_id=987654321,
                status="in_progress",
            ))
            db.commit()
        expired_external_status, _expired_external_location, expired_external_body = request("/regional")
        expired_external_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(expired_external_portal_id).encode("ascii") + rb'".*?</article>',
            expired_external_body, re.S,
        )
        assert expired_external_status == 200 and expired_external_card
        assert b"Prazo encerrado \xc2\xb7 fora do alcance da guilda" in expired_external_card.group(0)
        assert b"Prazo aberto" not in expired_external_card.group(0)
        with SessionLocal() as db:
            assert db.get(RegionalEvent, expired_external_portal_id).status == "in_progress"
        central_expired_external_status, _central_expired_external_location, central_expired_external_body = request(
            "/regional/events?section=portals",
        )
        central_expired_external_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(expired_external_portal_id).encode("ascii") + rb'".*?</article>',
            central_expired_external_body, re.S,
        )
        assert central_expired_external_status == 200 and central_expired_external_card
        assert b"Atividade em andamento \xc2\xb7 fora do alcance da guilda" in central_expired_external_card.group(0)
        assert b"Atividades iniciadas continuam" in central_expired_external_card.group(0)
        assert b"/portals/start" not in central_expired_external_card.group(0)
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
        assert repeat_status == 200 and b'data-regional-event-notice' not in repeat_dashboard
        repeat_regional_status, _location, repeat_regional = request("/regional")
        assert repeat_regional_status == 200 and b'id="regional-rebellion-notice"' in repeat_regional
        with SessionLocal() as db:
            assert db.query(RegionalEvent).filter_by(
                campaign_id=campaign.campaign_id, event_type="rebellion",
                trigger_cycle_number=invite_cycle,
            ).count() == invite_rows_before, "an open route must not reroll an already-resolved cycle decision"
        decision_status, decision_location, _decision_body = request(
            f"/regional/events/{invite_event_id}/decision", method="POST", body="decision=accept",
        )
        assert decision_status == 303 and decision_location.endswith(f"#regional-event-{invite_event_id}")
        with SessionLocal() as db:
            invite_event = db.get(RegionalEvent, invite_event_id)
            invited_participant = db.query(RegionalEventParticipant).filter_by(event_id=invite_event_id).one()
            assert invite_event.player_decision == "accept" and invited_participant.status == "accepted"
            regional_cycle = db.query(RegionalCycle).filter_by(
                campaign_id=campaign.campaign_id, status="open",
            ).order_by(RegionalCycle.cycle_number.desc()).first()
            assert regional_cycle is not None
            event_state = db.query(RegionalGuildState).filter_by(
                campaign_id=campaign.campaign_id, guild_id=guild_id,
            ).one()
            prepare_worker = create_mercenary(
                db, guild_id, db.get(MercenaryClass, mercenary_class_id), "Equipe preparada na central",
            )
            reinforce_worker = create_mercenary(
                db, guild_id, db.get(MercenaryClass, mercenary_class_id), "Reforço iniciado na central",
            )
            for worker in (prepare_worker, reinforce_worker):
                worker.level = 1
                worker.power, worker.vitality, worker.agility, worker.intelligence, worker.luck = 6, 4, 4, 2, 3
            db.add(RegionalOffer(
                campaign_id=campaign.campaign_id, cycle_id=regional_cycle.id,
                cycle_number=regional_cycle.cycle_number, region_code=invite_event.region_code,
                offer_type="contract", slot=9901, mission_template_id=regional_mission_template_id,
                rank="E", name_snapshot="Atividade iniciada pela central",
                recommended_level_snapshot=1, recommended_power_snapshot=9999,
                min_party_size_snapshot=1, max_party_size_snapshot=2,
                required_guild_level_snapshot=1, duration_seconds_snapshot=60,
                required_min_mercenary_level_snapshot=1, gold_reward_snapshot=1,
                xp_reward_snapshot=1, success_chance_snapshot=20,
            ))
            inventory_kit = db.query(GuildInventoryItem).filter_by(
                guild_id=guild_id, item_template_id=supply_kit_id,
            ).one()
            inventory_kit.quantity = max(inventory_kit.quantity, 10)
            db.query(GuildResources).filter_by(guild_id=guild_id).one().gold = 100000
            db.flush()
            central_offer_id = db.query(RegionalOffer).filter_by(
                cycle_id=regional_cycle.id, region_code=invite_event.region_code, slot=9901,
            ).one().id
            central_event_state_id = event_state.id
            prepare_worker_id, reinforce_worker_id = prepare_worker.id, reinforce_worker.id
            db.commit()
        central_events_status, _central_events_location, central_events_body = request(
            "/regional/events?section=rebellions",
        )
        assert central_events_status == 200
        assert regional_class_icon_url in central_events_body, central_events_body[:1200]
        central_offer_card = re.search(
            rb'<article[^>]*class="evolution-offer-card".*?Atividade iniciada pela central.*?</article>',
            central_events_body, re.S,
        )
        assert central_offer_card and b"Participar sem suprimento" in central_offer_card.group(0)
        assert b"/regional/events?section=rebellions#regional-event-" + str(invite_event_id).encode("ascii") in central_offer_card.group(0)
        central_return = (
            "%2Fregional%2Fevents%3Fsection%3Drebellions%23regional-event-"
            + str(invite_event_id)
        )
        central_prepare_status, central_prepare_location, central_prepare_body = request(
            f"/regional/offers/{central_offer_id}/prepare", method="POST",
            body=(f"return_to={central_return}&mercenary_ids={prepare_worker_id}&supply=1"),
        )
        assert central_prepare_status == 303 and central_prepare_location.startswith(
            f"/regional/events?section=rebellions&message="
        ), (central_prepare_status, central_prepare_location, central_prepare_body[:400])
        assert central_prepare_location.endswith(f"#regional-event-{invite_event_id}")
        with SessionLocal() as db:
            central_offer = db.get(RegionalOffer, central_offer_id)
            assert central_offer.status == "supply_preparing"
            assert central_offer.reserved_by_guild_state_id == central_event_state_id
            assert json.loads(central_offer.supply_preparation_snapshot_json)["mercenary_ids"] == [str(prepare_worker_id)]
            central_offer.supply_preparation_ends_at_utc = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        central_prepared_status, _central_prepared_location, central_prepared_body = request(
            "/regional/events?section=rebellions",
        )
        central_prepared_offer = re.search(
            rb'<article[^>]*class="evolution-offer-card".*?Atividade iniciada pela central.*?</article>',
            central_prepared_body, re.S,
        )
        assert central_prepared_status == 200 and central_prepared_offer
        assert b"Dispon\xc3\xadveis para refor\xc3\xa7o" in central_prepared_offer.group(0)
        assert b'<strong data-reinforcement-badge="' in central_prepared_offer.group(0)
        assert b'hidden>Refor\xc3\xa7o selecionado</strong>' in central_prepared_offer.group(0)
        selected_central_status, _selected_central_location, selected_central_body = request(
            f"/regional/events?section=rebellions&selected_mercenary_id={reinforce_worker_id}",
        )
        selected_reinforcement = re.search(
            rb'<label class="regional-team-member"><input[^>]*value="' + str(reinforce_worker_id).encode("ascii")
            + rb'"[^>]*checked>.*?<strong data-reinforcement-badge="' + str(reinforce_worker_id).encode("ascii")
            + rb'">' + "Refor\u00e7o selecionado</strong></label>".encode("utf-8"),
            selected_central_body, re.S,
        )
        assert selected_central_status == 200 and selected_reinforcement, selected_central_body[:1200]
        central_start_status, central_start_location, central_start_body = request(
            f"/regional/offers/{central_offer_id}/start", method="POST",
            body=(f"return_to={central_return}&mercenary_ids={prepare_worker_id}"
                  f"&mercenary_ids={reinforce_worker_id}&supply_mode=none"),
        )
        assert central_start_status == 303 and central_start_location.startswith(
            f"/regional/events?section=rebellions&message="
        ), (central_start_status, central_start_location, central_start_body[:400])
        assert central_start_location.endswith(f"#regional-event-{invite_event_id}")
        with SessionLocal() as db:
            central_offer = db.get(RegionalOffer, central_offer_id)
            central_run = db.query(MissionRun).filter_by(regional_offer_id=central_offer_id).one()
            central_activity = db.query(RegionalEventActivity).filter_by(
                event_id=invite_event_id, guild_state_id=central_event_state_id,
                source_type="mission", source_run_id=central_run.id,
            ).one()
            assert central_offer.status == "in_progress" and central_activity.status == "in_progress"
            assert central_run.status == "in_progress"
            assert {member.mercenary_id for member in central_run.members} == {
                prepare_worker_id, reinforce_worker_id,
            }
        with SessionLocal() as db:
            home_region = next(code for code, _name in REGIONS if code == home_region_code)
            empty_history_region = next(code for code, _name in REGIONS if code != home_region)
            history_now = datetime.now(timezone.utc)
            unregistered_history = RegionalEvent(
                campaign_id=campaign.campaign_id, event_type="portal", region_code=home_region,
                trigger_cycle_number=990001, rules_version="history-smoke-v1",
                seed="unregistered-history-smoke", status="expired",
                created_at_utc=history_now, expires_at_utc=history_now - timedelta(seconds=1),
                summary_json="{}",
            )
            empty_history = RegionalEvent(
                campaign_id=campaign.campaign_id, event_type="rebellion", region_code=empty_history_region,
                trigger_cycle_number=990002, rules_version="history-smoke-v1",
                seed="empty-history-smoke", status="resolved",
                created_at_utc=history_now, expires_at_utc=history_now - timedelta(seconds=1),
                summary_json=json.dumps({"activities": []}),
            )
            db.add_all([unregistered_history, empty_history])
            db.flush()
            unregistered_history_id, empty_history_id = unregistered_history.id, empty_history.id
            db.commit()
        history_status, _history_location, history_body = request("/regional/events")
        assert history_status == 200
        assert b"Encerrados" in history_body
        assert "Dados de participação não registrados neste evento.".encode("utf-8") in history_body
        assert b"Nenhuma atividade individual foi registrada neste evento." in history_body
        assert b"id=\"regional-event-" + str(unregistered_history_id).encode("ascii") in history_body
        assert b"id=\"regional-event-" + str(empty_history_id).encode("ascii") in history_body
        accepted_external_portal_status, _accepted_external_portal_location, accepted_external_portal_body = request(
            f"/regional/events/{outside_portal_id}/portals/supply-quote", method="POST", body="",
        )
        assert accepted_external_portal_status == 409
        assert "região natal" in json.loads(accepted_external_portal_body)["reason"]
        with SessionLocal() as db:
            active_regions = set(db.scalars(select(RegionalEvent.region_code).where(
                RegionalEvent.campaign_id == campaign.campaign_id,
                RegionalEvent.event_type == "rebellion",
                RegionalEvent.status.in_(("active", "in_progress")),
            )))
            blocked_external_offer = db.scalar(select(RegionalOffer).where(
                RegionalOffer.campaign_id == campaign.campaign_id,
                RegionalOffer.cycle_id == active_cycle_id,
                RegionalOffer.region_code != home_region_code,
                RegionalOffer.region_code.not_in(active_regions),
                RegionalOffer.status == "available",
            ).order_by(RegionalOffer.region_code, RegionalOffer.offer_type, RegionalOffer.slot).limit(1))
            assert blocked_external_offer is not None
            blocked_external_offer_id = blocked_external_offer.id
        blocked_quote_status, _blocked_quote_location, blocked_quote_body = request(
            f"/regional/offers/{blocked_external_offer_id}/supply-quote", method="POST",
        )
        assert blocked_quote_status == 409
        assert "sem uma rebelião ativa" in json.loads(blocked_quote_body)["reason"]
        blocked_prepare_status, blocked_prepare_location, _blocked_prepare_body = request(
            f"/regional/offers/{blocked_external_offer_id}/prepare", method="POST", body="supply=1",
        )
        assert blocked_prepare_status == 303
        assert "sem uma rebelião ativa" in unquote_plus(blocked_prepare_location)
        blocked_start_status, blocked_start_location, _blocked_start_body = request(
            f"/regional/offers/{blocked_external_offer_id}/start", method="POST", body="supply_mode=none",
        )
        assert blocked_start_status == 303
        assert "sem uma rebelião ativa" in unquote_plus(blocked_start_location)
        post_decision_status, _location, post_decision_dashboard = request("/dashboard")
        assert post_decision_status == 200 and b'data-regional-event-notice' not in post_decision_dashboard
        post_decision_regional_status, _location, post_decision_regional = request("/regional")
        assert post_decision_regional_status == 200 and b'id="regional-rebellion-notice"' not in post_decision_regional
        assert f'id="regional-event-{invite_event_id}"'.encode("ascii") in post_decision_regional
        assert b"Convite aceito." in post_decision_regional
        assert b"Sua prioridade segue at\xc3\xa9" in post_decision_regional
        assert b"Prioridade encerrada." not in post_decision_regional
        assert b"a CPU tamb\xc3\xa9m participa" not in post_decision_regional
        with SessionLocal() as db:
            expired_invite_now = datetime.now(timezone.utc)
            expired_invite_started_at = expired_invite_now - timedelta(hours=14)
            expired_invite = RegionalEvent(
                campaign_id=campaign.campaign_id, event_type="rebellion",
                region_code=next(code for code, _name in REGIONS if code != home_region_code),
                trigger_cycle_number=990003, rules_version="regional-events-v1",
                seed="expired-unaccepted-invite-smoke", status="active",
                created_at_utc=expired_invite_started_at,
                priority_ends_at_utc=expired_invite_started_at + timedelta(hours=1),
                expires_at_utc=expired_invite_started_at + timedelta(hours=13),
                summary_json="{}",
            )
            db.add(expired_invite)
            db.flush()
            expired_invite_id = expired_invite.id
            db.add(RegionalEventParticipant(
                event_id=expired_invite_id, guild_state_id=central_event_state_id,
                status="invited",
            ))
            expire_due_events(db, campaign.campaign_id, expired_invite_now)
            db.flush()
            assert expired_invite.status == "resolved"
            assert expired_invite.player_decision == "delegated_cpu"
            assert json.loads(expired_invite.summary_json)["priority_elapsed_offline"] is True
            db.commit()
        expired_invite_status, _expired_invite_location, expired_invite_body = request(
            "/regional/events",
        )
        expired_invite_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(expired_invite_id).encode("ascii") + rb'".*?</article>',
            expired_invite_body, re.S,
        )
        assert expired_invite_status == 200 and expired_invite_card
        assert "Convite expirado sem aceite; a CPU assumiu a defesa.".encode("utf-8") in expired_invite_card.group(0)
        assert b"/decision" not in expired_invite_card.group(0)
        assert b"/static/js/desktop-art.js" in rendered_pages["/dashboard"]
        base_template = (Path.cwd() / "app" / "templates" / "base.html").read_bytes()
        desktop_theme_version = re.search(rb"desktop-theme\.css.*?\?v=([^\"&\s]+)", base_template)
        assert desktop_theme_version, "base.html should declare the active desktop theme version"
        desktop_theme_url = b"/static/css/desktop-theme.css?v=" + desktop_theme_version.group(1)
        assert desktop_theme_url in rendered_pages["/dashboard"]
        theme_status, _theme_location, theme_body = request(desktop_theme_url.decode("ascii"))
        assert theme_status == 200 and theme_body, (theme_status, desktop_theme_url)
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
        portal_detail_status, _portal_detail_location, portal_detail_body = request("/regional")
        assert portal_detail_status == 200
        displayed_portal_item_name = clean_generated_name(original_item_name).encode("utf-8")
        portal_preview_card = re.search(
            rb'<article class="evolution-future-card"[^>]*id="regional-event-'
            + str(portal_event_id).encode("ascii")
            + rb'"(?:(?!<article class="evolution-future-card"[^>]*>).)*'
            + re.escape(displayed_portal_item_name)
            + rb'.*?</article>',
            portal_detail_body,
            re.S,
        )
        assert portal_preview_card and b"Loot do portal" in portal_preview_card.group(0), portal_detail_body[:4000]
        assert b"\xc3\xb3s sucesso" in portal_preview_card.group(0)
        assert b"\xc3\x971" in portal_preview_card.group(0)
        assert b"Qtd. base:" not in portal_preview_card.group(0)
        assert b"Como funcionam os drops" in portal_preview_card.group(0)
        assert b"multiplicador" not in portal_preview_card.group(0).lower()
        status, location, portal_start_body = request(
            f"/regional/events/{portal_event_id}/portals/start", method="POST",
            body=(f"mercenary_ids={portal_mercenary_id}"
                  f"&return_to=%2Fregional%2Fevents%3Fsection%3Dportals%23regional-event-{portal_event_id}"),
            extra_headers={"X-GIM-Diagnostic-ID": "9999999999999999"},
        )
        portal_return = urlsplit(location)
        assert status == 303 and portal_return.path == "/regional/events", (status, location, portal_start_body)
        assert parse_qs(portal_return.query).get("section") == ["portals"]
        assert portal_return.fragment == f"regional-event-{portal_event_id}"
        with SessionLocal() as db:
            portal_run = db.query(DungeonRun).filter_by(
                guild_id=guild_id, dungeon_template_id=portal_template_id, status="in_progress",
            ).one()
            run_id = portal_run.id
            portal_event = db.get(RegionalEvent, portal_event_id)
            portal_event.expires_at_utc = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        central_portal_status, _central_portal_location, central_portal_body = request(
            "/regional/events?section=portals",
        )
        assert central_portal_status == 200
        assert b"Prazo de entrada:" in central_portal_body
        assert b"Equipe em andamento" in central_portal_body
        assert b"Prazo da equipe" in central_portal_body
        started_portal_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(portal_event_id).encode("ascii") + rb'".*?</article>',
            central_portal_body, re.S,
        )
        assert started_portal_card and b"Entrada j\xc3\xa1 utilizada" in started_portal_card.group(0)
        assert b"/portals/start" not in started_portal_card.group(0)
        with SessionLocal() as db:
            assert db.get(RegionalEvent, portal_event_id).status == "in_progress"
        with SessionLocal() as db:
            portal_run = db.query(DungeonRun).filter_by(
                guild_id=guild_id, dungeon_template_id=portal_template_id, status="in_progress",
            ).one()
            assert portal_run.id == run_id
            assert (portal_run.ends_at - portal_run.started_at).total_seconds() >= 3600
            portal_activity = db.query(RegionalEventActivity).filter_by(
                event_id=portal_event_id, source_type="dungeon", source_run_id=run_id,
            ).one()
            assert portal_activity.status == "in_progress"
            portal_run.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        ready_portal_status, _ready_portal_location, ready_portal_body = request(
            "/regional/events?section=portals",
        )
        ready_portal_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(portal_event_id).encode("ascii") + rb'".*?</article>',
            ready_portal_body, re.S,
        )
        assert ready_portal_status == 200 and ready_portal_card
        assert "Resultado disponível para coleta".encode("utf-8") in ready_portal_card.group(0)
        assert b"Prazo da equipe" not in ready_portal_card.group(0)
        assert b'href="/dungeons"' in ready_portal_card.group(0)
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
            assert portal_event.status == "resolved" and portal_activity.status == "resolved"
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
            min_types, max_types, min_points, max_points = RARITY_BONUS_RULES[portal_item_snapshot["rarity"]]
            portal_bonus_rolls = get_item_bonus_rolls(portal_instance)
            assert min_types <= len(portal_bonus_rolls) <= max_types
            bonus_keys = {(roll["kind"], roll["attribute"]) for roll in portal_bonus_rolls}
            assert len(bonus_keys) == len(portal_bonus_rolls)
            for bonus_roll in portal_bonus_rolls:
                if bonus_roll["kind"] == "normal":
                    assert min_points <= bonus_roll["value"] <= max_points
                else:
                    assert bonus_roll["kind"] == "strong"
                    assert 10 <= bonus_roll["value"] <= 20
            strong_rolls = [roll for roll in portal_bonus_rolls if roll["kind"] == "strong"]
            if portal_item_snapshot["rarity"] == "legendary":
                assert len(strong_rolls) == 1
            elif portal_item_snapshot["rarity"] == "mythic":
                assert 2 <= len(strong_rolls) <= 4
            else:
                assert strong_rolls == []
            expire_due_events(db, campaign.campaign_id, portal_event.expires_at_utc)
            db.refresh(portal_event)
            portal_summary = json.loads(portal_event.summary_json)
            assert portal_event.status == "resolved"
            assert portal_summary["aggregate"] == {"entries": 1, "successes": 1, "failures": 0}
            assert len(portal_summary["participant_results"]) == 1
        collected_portal_status, _collected_portal_location, collected_portal_body = request(
            "/regional/events?section=portals",
        )
        collected_portal_card = re.search(
            rb'<article[^>]*id="regional-event-' + str(portal_event_id).encode("ascii") + rb'".*?</article>',
            collected_portal_body, re.S,
        )
        assert collected_portal_status == 200 and collected_portal_card
        assert "Resultado coletado".encode("utf-8") in collected_portal_card.group(0), collected_portal_card.group(0).decode("utf-8", "replace")
        assert b'href="/dungeons"' not in collected_portal_card.group(0)
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
            "current_save_version": 8,
            "backup_created": True,
        }, notice
        backup_files = list(
            (Path(data_dir) / "backups" / previous_campaign.campaign_id).glob("pre-migration-*.db")
        )
        migration_backups = [
            path for path in backup_files
            if path.name.startswith(f"pre-migration-{notice['previous_revision']}-")
        ]
        assert len(migration_backups) == 1, backup_files
        migration_backup = migration_backups[0]
        with closing(sqlite3.connect(migration_backup)) as connection:
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
        assert "Versão 1 → 8".encode("utf-8") in dashboard_body
        assert "cópia de segurança foi criada antes da atualização".encode("utf-8") in dashboard_body
        assert str(migration_backup).encode("utf-8") not in dashboard_body
        assert str(migration_backup).encode("utf-8") not in migration_body
        assert b"offline-dialog" not in dashboard_body
        status, _location, migrated_regional_body = request("/regional")
        assert status == 200, ("/regional after migration", status, migrated_regional_body[:400])
        assert b"Internal Server Error" not in migrated_regional_body
        assert b'id="evolution-title"' in migrated_regional_body
        status, _location, next_dashboard_body = request("/dashboard")
        assert status == 200
        assert b"save-migration-notice" not in next_dashboard_body
        gameplay_log_after_portal = Path(os.environ["LOCALAPPDATA"]) / "GuildIdleManager" / "logs" / "gameplay-actions.log"
        gameplay_trace = gameplay_log_after_portal.read_text(encoding="utf-8")
        for diagnostic_id in (
            "3333333333333333", "4444444444444444", "5555555555555555",
            "6666666666666666", "7777777777777777", "8888888888888888",
            "9999999999999999", slot_failure_diagnostic, foreign_mercenary_diagnostic,
            *validation_diagnostics, busy_diagnostic, exception_diagnostic, "aaaaaaaaaaaaaaaa",
        ):
            assert f"ref={diagnostic_id}" in gameplay_trace, f"missing correlated trace for {diagnostic_id}"
        for route, diagnostic_id, expected_status in (
            (f"/regional/offers/{no_supply_offer_id}/start", "3333333333333333", "status=303 outcome=error"),
            (f"/regional/offers/{no_supply_offer_id}/start", "4444444444444444", "status=303 outcome=redirect"),
            (f"/regional/offers/{prepared_offer_id}/supply-quote", "5555555555555555", "status=200 outcome=success"),
            (f"/regional/offers/{prepared_offer_id}/prepare", "6666666666666666", "status=303 outcome=redirect"),
            (f"/regional/offers/{prepared_offer_id}/start", "7777777777777777", "status=303 outcome=redirect"),
            ("/gathering/assign", "8888888888888888", "status=303 outcome=redirect"),
            (f"/regional/events/{portal_event_id}/portals/start", "9999999999999999", "status=303 outcome=redirect"),
        ):
            assert f"event=start " in gameplay_trace and f"route={route} ref={diagnostic_id}" in gameplay_trace
            assert any(
                line.startswith("20") and f"event=result " in line and f"route={route} ref={diagnostic_id} " in line
                and expected_status in line
                for line in gameplay_trace.splitlines()
            ), f"missing result trace for {route} ({diagnostic_id}): {expected_status}"
        expected_equipment_error_routes = [
            (equipment_route, slot_failure_diagnostic),
            *((equipment_route, diagnostic_id) for diagnostic_id in validation_diagnostics),
            (equipment_route, busy_diagnostic),
            (f"/mercenaries/{foreign_mercenary_id}/equip", foreign_mercenary_diagnostic),
        ]
        for route, diagnostic_id in expected_equipment_error_routes:
            route_mercenary_id = route.strip("/").split("/")[1]
            assert any(
                line.startswith("20")
                and f"event=result action=mercenaries.{route_mercenary_id}.equip " in line
                and f"route={route} ref={diagnostic_id} " in line
                and "status=303 outcome=error" in line
                for line in gameplay_trace.splitlines()
            ), f"expected equipment rejection trace for {diagnostic_id}"
        assert any(
            line.startswith("20")
            and f"event=exception action=mercenaries.{equipment_route_mercenary_id}.equip " in line
            and f"route={equipment_route} ref={exception_diagnostic} " in line
            and "status=500 outcome=unexpected_exception" in line
            for line in gameplay_trace.splitlines()
        ), f"expected unexpected equipment exception trace for {exception_diagnostic}"
        assert any(
            line.startswith("20")
            and f"event=rejected action=mercenaries.{equipment_route_mercenary_id}.equip " in line
            and f"route={equipment_route} ref=aaaaaaaaaaaaaaaa " in line
            and "status=403 outcome=origin_rejected" in line
            for line in gameplay_trace.splitlines()
        ), "the loopback origin guard should remain in effect for equipment actions"

        with SessionLocal() as db:
            macro_now = datetime.now(timezone.utc)
            active_campaign_id = app.state.active_campaign.campaign_id
            macro_campaign = db.get(CampaignMetadata, active_campaign_id)
            macro_guild = db.scalar(select(Guild).where(Guild.campaign_id == active_campaign_id))
            assert macro_campaign is not None and macro_guild is not None
            macro_board = get_regional_board(db, macro_campaign, macro_guild, now=macro_now)
            macro_cycle = macro_board["cycle"]
            macro_offer = next(
                offer for offer in macro_board["offers"]["contract"]
                if offer.status == "available"
                and macro_guild.level >= offer.required_guild_level_snapshot
            )
            macro_class = next((
                candidate for candidate in db.scalars(
                    select(MercenaryClass).order_by(MercenaryClass.id)
                ) if get_class_icon_path(candidate)
            ), None)
            assert macro_class is not None
            macro_class_icon_url = f"/static/{get_class_icon_path(macro_class).lstrip('/')}"
            macro_worker = create_mercenary(
                db, macro_guild.id, macro_class, "Ícone da Vigília",
            )
            macro_worker.status = "available"
            db.commit()
        regional_macro_status, _regional_macro_location, regional_macro_body = request("/regional")
        assert regional_macro_status == 200 and macro_class_icon_url.encode("utf-8") in regional_macro_body, (
            regional_macro_status, macro_class_icon_url,
        )
    finally:
        from app.desktop.lifecycle import close_campaign
        close_campaign(app, saves, guard)
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        configure_database("sqlite:///:memory:")
        gc.collect()
        logging.shutdown()
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
        lines = (result.stdout + result.stderr).splitlines()
        diagnostic = "\n".join(line[:600] for line in lines[-60:])
        self.assertEqual(result.returncode, 0, diagnostic)


if __name__ == "__main__":
    unittest.main()
