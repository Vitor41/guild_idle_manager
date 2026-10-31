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
from app.models.regional import RegionalEvent, RegionalEventActivity, RegionalEventParticipant, RegionalGuildState, RegionalRegionState
from app.models.achievement import AchievementTemplate, GuildAchievement
from app.models.item import GuildItemInstance
from app.models.mission import MissionTemplate
from app.models.building import BuildingTemplate
from app.repositories.mercenary_repository import create_mercenary
from app.services.regional_cycle_service import ensure_campaign_world
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

    def request(path, method="GET", body=None):
        client = http.client.HTTPConnection("127.0.0.1", port, timeout=40)
        headers = {"Host": host}
        if method not in {"GET", "HEAD"}:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = "application/json" if body.startswith("{") else "application/x-www-form-urlencoded"
        client.request(method, path, body=body, headers=headers)
        response = client.getresponse()
        result = response.status, response.getheader("location"), response.read()
        client.close()
        return result

    create_status, _create_location, create_body = request(
        "/desktop/api/campaigns", method="POST", body=json.dumps({"guild_name": "Smoke desktop"}),
    )
    assert create_status == 200, create_body
    created_campaign = json.loads(create_body)
    campaign = saves.inspect_campaign(created_campaign["campaign_id"])
    assert created_campaign["redirect"] == "/dashboard"
    with SessionLocal() as db:
        guild = db.query(Guild).first()
        mercenary_class = db.query(MercenaryClass).order_by(MercenaryClass.id).first()
        item_template = db.query(ItemTemplate).filter(ItemTemplate.icon_group.is_not(None)).order_by(ItemTemplate.id).first()
        assert guild and mercenary_class and item_template, "campaign must seed display entities for the desktop art smoke"
        guild_id = guild.id
        mercenary_class_id = mercenary_class.id
        mercenary = create_mercenary(db, guild.id, mercenary_class, "Teste visual")
        gathering_worker = create_mercenary(db, guild.id, mercenary_class, "Trabalhador disponível")
        db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=item_template.id, quantity=1))
        db.flush()
        mercenary_id = mercenary.id
        gathering_worker_id = gathering_worker.id
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
        gathering_status, gathering_location, gathering_body = request(
            "/gathering/assign", method="POST",
            body=f"mercenary_id={gathering_worker_id}&resource_family=wood",
        )
        assert gathering_status == 303 and gathering_location.startswith("/gathering?message="), (gathering_status, gathering_location, gathering_body[:300])
        with SessionLocal() as db:
            assignment = db.query(GatheringAssignment).filter_by(mercenary_id=gathering_worker_id, resource_family="wood").one_or_none()
            assert assignment is not None, "gathering form POST must persist its worker assignment"
        assert b"/static/js/regional-supply.js?v=20261030-2" in rendered_pages["/dungeons"]
        assert b"Modo Offline" in rendered_pages["/dashboard"]
        assert b"Estamina 8h 0min / 8h" in rendered_pages["/dashboard"]
        assert b"2h de estamina por 1h online" in rendered_pages["/dashboard"]
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
