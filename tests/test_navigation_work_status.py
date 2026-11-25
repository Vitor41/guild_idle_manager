import unittest
import json
from datetime import datetime, timedelta, timezone
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import (
    ClassChangeRun,
    CampaignMetadata,
    DungeonRun,
    DungeonTemplate,
    GatheringAssignment,
    Guild,
    GuildItemInstance,
    GuildSalvageJob,
    ItemTemplate,
    MarketSale,
    Mercenary,
    MercenaryClass,
    MissionRun,
    MissionTemplate,
    ProfessionTemplate,
    ProfessionTraining,
    RegionalCycle,
    RegionalEvent,
    RegionalEventActivity,
    RegionalEventParticipant,
    RegionalGuildState,
    RegionalOffer,
    SupplyWorkshopJob,
)
from app.services.navigation_work_status_service import get_navigation_work_status
from app.services.equipment_service import get_party_power_score
from app.services.regional_event_service import build_portal_boss_snapshot


class NavigationWorkStatusTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        self.db.add_all([
            CampaignMetadata(campaign_id="campaign-a", campaign_name="Campanha A"),
            CampaignMetadata(campaign_id="campaign-b", campaign_name="Campanha B"),
        ])
        self.db.flush()
        self.guild = Guild(name="Guilda A", campaign_id="campaign-a")
        self.other_guild = Guild(name="Guilda B", campaign_id="campaign-b")
        self.db.add_all([self.guild, self.other_guild])
        self.db.flush()

        self.mission = MissionTemplate(
            name="Missão QA", description="", duration_seconds=60,
            base_gold_reward=1, base_xp_reward=1, base_success_chance=50,
        )
        self.dungeon = DungeonTemplate(
            name="Masmorra QA", description="", duration_seconds=60,
            base_gold_reward=1, base_xp_reward=1, base_success_chance=50,
        )
        self.item = ItemTemplate(name="Material QA", item_type="material", rarity="common")
        self.material = ItemTemplate(name="Resultado QA", item_type="material", rarity="common")
        self.mercenary_class = MercenaryClass(
            name="Classe QA", description="", base_power=1, base_vitality=1,
            base_agility=1, base_intelligence=1, base_luck=1,
        )
        self.profession = ProfessionTemplate(code="qa", name="Profissão QA", material_family="wood")
        self.db.add_all([
            self.mission, self.dungeon, self.item, self.material,
            self.mercenary_class, self.profession,
        ])
        self.db.flush()
        self.worker = Mercenary(
            guild_id=self.guild.id, class_id=self.mercenary_class.id, name="Trabalhador QA",
            power=1, vitality=1, agility=1, intelligence=1, luck=1,
        )
        self.other_worker = Mercenary(
            guild_id=self.other_guild.id, class_id=self.mercenary_class.id, name="Outro QA",
            power=1, vitality=1, agility=1, intelligence=1, luck=1,
        )
        self.db.add_all([self.worker, self.other_worker])
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _run(self, model, guild_id, *, ends_in_seconds, **values):
        row = model(
            guild_id=guild_id,
            status="in_progress",
            started_at=self.now - timedelta(minutes=1),
            ends_at=self.now + timedelta(seconds=ends_in_seconds),
            **values,
        )
        self.db.add(row)
        return row

    def test_aggregates_all_menu_states_in_one_read_only_query(self):
        self._run(MissionRun, self.guild.id, ends_in_seconds=-1, mission_template_id=self.mission.id)
        self._run(MissionRun, self.guild.id, ends_in_seconds=60, mission_template_id=self.mission.id)
        resolved_mission = self._run(MissionRun, self.guild.id, ends_in_seconds=-5, mission_template_id=self.mission.id)
        resolved_mission.status = "completed"
        self._run(MissionRun, self.other_guild.id, ends_in_seconds=-1, mission_template_id=self.mission.id)
        self._run(DungeonRun, self.guild.id, ends_in_seconds=60, dungeon_template_id=self.dungeon.id)
        self.db.add(GatheringAssignment(
            guild_id=self.guild.id, mercenary_id=self.worker.id, resource_family="wood",
            node_code="qa", started_at_utc=self.now, checkpoint_at_utc=self.now,
        ))
        workshop = self._run(
            SupplyWorkshopJob, self.guild.id, ends_in_seconds=-1,
            output_item_template_id=self.item.id, kit_quantity=1, meat_per_kit=1,
            herb_per_kit=1, seconds_per_kit=1,
        )
        self._run(
            GuildSalvageJob, self.guild.id, ends_in_seconds=-1, slot_number=1,
            item_template_id=self.item.id, material_template_id=self.material.id,
            quantity=1, gold_cost=0,
        )
        self._run(
            MarketSale, self.guild.id, ends_in_seconds=-1,
            item_template_id=self.item.id, quantity=1, unit_value=1, total_value=1,
        )
        self._run(
            ClassChangeRun, self.guild.id, ends_in_seconds=-1,
            mercenary_id=self.worker.id, from_class_id=self.mercenary_class.id,
            to_class_id=self.mercenary_class.id, gold_cost=0,
        )
        self._run(
            ProfessionTraining, self.guild.id, ends_in_seconds=60,
            mercenary_id=self.worker.id, profession_id=self.profession.id,
        )
        self.db.flush()

        statements = []
        workshop.status = "completed"

        def capture_statements(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lstrip().split(None, 1)[0].upper())

        event.listen(self.engine, "before_cursor_execute", capture_statements)
        try:
            result = get_navigation_work_status(self.db, self.guild.id, campaign_id="campaign-a", now=self.now)
        finally:
            event.remove(self.engine, "before_cursor_execute", capture_statements)

        self.assertIn("SELECT", statements)
        self.assertFalse(set(statements) & {"INSERT", "UPDATE", "DELETE"})
        self.assertEqual(workshop.status, "completed")
        self.assertTrue(self.db.is_modified(workshop))
        self.assertEqual(result["missions"]["ready"], 1)
        self.assertEqual(result["missions"]["active"], 1)
        self.assertEqual(result["missions"]["state"], "ready")
        self.assertEqual(result["dungeons"]["state"], "active")
        self.assertEqual(result["gathering"]["active"], 1)
        self.assertEqual(result["gathering"]["ready"], 0)
        self.assertEqual(result["workshops"]["state"], "ready")
        self.assertEqual(result["blacksmith"]["state"], "ready")
        self.assertEqual(result["market"]["state"], "ready")
        self.assertEqual(result["class_change"]["state"], "ready")
        self.assertEqual(result["professions"]["state"], "active")
        self.assertIn("1 pronta para coletar; 1 em andamento", result["missions"]["label"])

        self.db.refresh(workshop)
        self.assertEqual(workshop.status, "in_progress")
        self.assertIsNone(workshop.completed_at)

    def test_absent_work_has_no_indicator_and_counts_are_guild_scoped(self):
        result = get_navigation_work_status(self.db, self.guild.id, now=self.now)
        self.assertEqual(result["missions"]["state"], "none")
        self.assertEqual(result["missions"]["active"], 0)
        self.assertEqual(result["missions"]["ready"], 0)

        self._run(MissionRun, self.other_guild.id, ends_in_seconds=-1, mission_template_id=self.mission.id)
        self.db.flush()
        isolated = get_navigation_work_status(self.db, self.guild.id, now=self.now)
        self.assertEqual(isolated["missions"]["state"], "none")

    def test_gathering_counts_continuous_and_finite_work_but_excludes_capacity_paused(self):
        finite_worker = Mercenary(
            guild_id=self.guild.id, class_id=self.mercenary_class.id, name="Coletor finito QA",
            power=1, vitality=1, agility=1, intelligence=1, luck=1,
        )
        paused_worker = Mercenary(
            guild_id=self.guild.id, class_id=self.mercenary_class.id, name="Coletor pausado QA",
            power=1, vitality=1, agility=1, intelligence=1, luck=1,
        )
        self.db.add_all([finite_worker, paused_worker])
        self.db.flush()
        self.db.add_all([
            GatheringAssignment(
                guild_id=self.guild.id, mercenary_id=self.worker.id, resource_family="wood",
                node_code="qa", started_at_utc=self.now, checkpoint_at_utc=self.now,
                target_quantity=None, capacity_paused=False,
            ),
            GatheringAssignment(
                guild_id=self.guild.id, mercenary_id=finite_worker.id, resource_family="ore",
                node_code="qa", started_at_utc=self.now, checkpoint_at_utc=self.now,
                target_quantity=10, quantity_collected=4, capacity_paused=False,
            ),
            GatheringAssignment(
                guild_id=self.guild.id, mercenary_id=paused_worker.id, resource_family="herb",
                node_code="qa", started_at_utc=self.now, checkpoint_at_utc=self.now,
                target_quantity=None, capacity_paused=True,
            ),
        ])
        self.db.flush()

        result = get_navigation_work_status(self.db, self.guild.id, now=self.now)

        self.assertEqual(result["gathering"]["active"], 2)
        self.assertEqual(result["gathering"]["ready"], 0)
        self.assertEqual(result["gathering"]["state"], "active")
        self.assertEqual(result["gathering"]["label"], "Coleta: 2 em andamento")

    def test_regional_preparation_is_scoped_to_the_active_campaign_and_guild(self):
        cycles = [
            RegionalCycle(
                campaign_id=campaign_id, cycle_number=1,
                starts_at_utc=self.now - timedelta(hours=1), ends_at_utc=self.now + timedelta(hours=1),
                seed=f"seed-{campaign_id}", rules_version="test",
            )
            for campaign_id in ("campaign-a", "campaign-b")
        ]
        self.db.add_all(cycles)
        self.db.flush()
        state_a = RegionalGuildState(
            campaign_id="campaign-a", region_code="north", slot=1, guild_id=self.guild.id,
            name="Guilda A", profile="player", archetype="balanced",
        )
        state_b = RegionalGuildState(
            campaign_id="campaign-b", region_code="north", slot=1, guild_id=self.other_guild.id,
            name="Guilda B", profile="player", archetype="balanced",
        )
        self.db.add_all([state_a, state_b])
        self.db.flush()

        def offer(campaign_id, cycle, state, slot, ends_in_seconds):
            return RegionalOffer(
                campaign_id=campaign_id, cycle_id=cycle.id, cycle_number=1,
                region_code="north", offer_type="contract", slot=slot,
                rank="E", name_snapshot=f"Oferta {campaign_id}-{slot}",
                recommended_level_snapshot=1, recommended_power_snapshot=1,
                duration_seconds_snapshot=60, gold_reward_snapshot=1,
                xp_reward_snapshot=1, success_chance_snapshot=50,
                status="supply_preparing", reserved_by_guild_state_id=state.id,
                supply_preparation_started_at_utc=self.now - timedelta(minutes=1),
                supply_preparation_ends_at_utc=self.now + timedelta(seconds=ends_in_seconds),
                supply_prepared_at_utc=self.now if ends_in_seconds <= 0 else None,
            )

        self.db.add_all([
            offer("campaign-a", cycles[0], state_a, 1, 60),
            offer("campaign-a", cycles[0], state_a, 2, -1),
            offer("campaign-b", cycles[1], state_b, 1, -1),
        ])
        self.db.flush()

        result = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )
        self.assertEqual(result["regional"]["active"], 1)
        self.assertEqual(result["regional"]["ready"], 1)
        self.assertEqual(result["regional"]["state"], "ready")

    def test_regional_event_indicator_is_campaign_scoped_and_read_only(self):
        campaign = self.db.get(CampaignMetadata, "campaign-a")
        campaign.home_region = "Vale da Fronteira"
        state = RegionalGuildState(
            campaign_id="campaign-a", region_code="vale-fronteira", slot=0,
            guild_id=self.guild.id, name=self.guild.name, profile="player", archetype="player",
        )
        portal = RegionalEvent(
            campaign_id="campaign-a", event_type="portal", region_code="vale-fronteira",
            trigger_cycle_number=10, rules_version="regional-events-v6", seed="portal-ready",
            status="active", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
        )
        rebellion = RegionalEvent(
            campaign_id="campaign-a", event_type="rebellion", region_code="bosque-ambar",
            trigger_cycle_number=10, rules_version="regional-events-v6", seed="rebellion-ready",
            status="active", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
        )
        self.db.add_all([state, portal, rebellion])
        self.db.flush()
        participant = RegionalEventParticipant(
            event_id=rebellion.id, guild_state_id=state.id, status="invited",
        )
        active_event = RegionalEventActivity(
            event_id=rebellion.id, guild_state_id=state.id, source_type="dungeon",
            source_run_id=7001, status="in_progress",
        )
        self.db.add_all([participant, active_event])
        self.db.flush()

        before = (state.id, portal.status, rebellion.status, participant.status, active_event.status)
        result = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )

        self.assertEqual(result["regional_events"]["ready"], 1)
        self.assertEqual(result["regional_events"]["active"], 0)
        self.assertEqual(result["regional_events"]["state"], "ready")
        self.assertEqual(
            (state.id, portal.status, rebellion.status, participant.status, active_event.status),
            before,
        )

    def test_portal_indicator_requires_live_template_and_available_party(self):
        campaign = self.db.get(CampaignMetadata, "campaign-a")
        campaign.home_region = "Vale da Fronteira"
        self.db.add(RegionalGuildState(
            campaign_id="campaign-a", region_code="vale-fronteira", slot=0,
            guild_id=self.guild.id, name=self.guild.name, profile="player", archetype="player",
        ))
        portal = RegionalEvent(
            campaign_id="campaign-a", event_type="portal", region_code="vale-fronteira",
            trigger_cycle_number=20, rules_version="regional-events-v6", seed="portal-no-route",
            status="active", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
        )
        self.db.add(portal)
        self.db.flush()

        unavailable = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((unavailable["ready"], unavailable["state"]), (0, "none"))

        portal.dungeon_template_id = self.dungeon.id
        self.dungeon.content_type = "boss"
        self.dungeon.recommended_level = 2
        self.dungeon.min_party_size = 2
        self.dungeon.max_party_size = 2
        self.dungeon.required_total_power = 999999
        def set_snapshot_power(required_power):
            snapshot = build_portal_boss_snapshot(self.dungeon)
            snapshot["required_total_power"] = required_power
            portal.summary_json = json.dumps({"portal_boss": {"template": snapshot}})

        set_snapshot_power(999999)
        self.db.flush()
        no_team = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((no_team["ready"], no_team["state"]), (0, "none"))

        second_worker = Mercenary(
            guild_id=self.guild.id, class_id=self.mercenary_class.id, name="Equipe disponível QA",
            power=1, vitality=1, agility=1, intelligence=1, luck=1,
        )
        self.db.add(second_worker)
        self.db.flush()
        not_powerful_enough = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((not_powerful_enough["ready"], not_powerful_enough["state"]), (0, "none"))

        expected_power = get_party_power_score(
            self.db, self.guild.id, [self.worker, second_worker],
        )
        set_snapshot_power(expected_power)
        self.db.flush()
        ready = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((ready["ready"], ready["state"]), (1, "ready"))

        set_snapshot_power(expected_power + 1)
        self.db.flush()
        one_point_short = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((one_point_short["ready"], one_point_short["state"]), (0, "none"))

    def test_portal_indicator_requires_one_party_with_composition_and_equipment(self):
        campaign = self.db.get(CampaignMetadata, "campaign-a")
        campaign.home_region = "Vale da Fronteira"
        self.db.add(RegionalGuildState(
            campaign_id="campaign-a", region_code="vale-fronteira", slot=0,
            guild_id=self.guild.id, name=self.guild.name, profile="player", archetype="player",
        ))
        portal = RegionalEvent(
            campaign_id="campaign-a", event_type="portal", region_code="vale-fronteira",
            trigger_cycle_number=20, rules_version="regional-events-v6", seed="portal-party-requirements",
            status="active", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
            dungeon_template_id=self.dungeon.id,
        )
        self.mercenary_class.role_type = "tank"
        self.dungeon.content_type = "boss"
        self.dungeon.recommended_level = 2
        self.dungeon.min_party_size = 2
        self.dungeon.max_party_size = 2
        self.dungeon.required_tank_count = 1
        self.dungeon.required_support_count = 1
        self.dungeon.required_equipment_tier = 2
        self.dungeon.required_min_mercenary_level = 99
        support_class = MercenaryClass(
            name="Suporte QA", code="support-qa", role_type="support", description="",
            base_power=1, base_vitality=1, base_agility=1, base_intelligence=1, base_luck=1,
        )
        self.db.add(support_class)
        self.db.flush()
        additional_tank = Mercenary(
            guild_id=self.guild.id, class_id=self.mercenary_class.id, name="Tanque extra QA",
            power=1, vitality=1, agility=1, intelligence=1, luck=1,
        )
        support = Mercenary(
            guild_id=self.guild.id, class_id=support_class.id, name="Suporte disponível QA",
            power=1, vitality=1, agility=1, intelligence=1, luck=1,
        )
        self.db.add_all([portal, additional_tank, support])
        self.db.flush()

        # The entire available roster has enough members, but every two-member
        # party is missing a required role until the support is available.
        support.status = "in_mission"
        self.db.flush()
        no_composition = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((no_composition["ready"], no_composition["state"]), (0, "none"))

        support.status = "available"
        self.db.flush()
        missing_equipment = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((missing_equipment["ready"], missing_equipment["state"]), (0, "none"))

        tier_two = ItemTemplate(
            name="Equipamento Tier 2 QA", item_type="equipment", rarity="common", tier=2,
        )
        self.db.add(tier_two)
        self.db.flush()
        for mercenary in (self.worker, support):
            self.db.add(GuildItemInstance(
                guild_id=self.guild.id, item_template_id=tier_two.id,
                equipped_to_mercenary_id=mercenary.id, equipment_slot="main_hand",
                required_level=1,
            ))
        self.db.flush()

        self.dungeon.required_class_code = "missing-class-qa"
        self.db.flush()
        missing_required_class = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((missing_required_class["ready"], missing_required_class["state"]), (0, "none"))

        self.dungeon.required_class_code = "support-qa"
        self.db.flush()
        before = (portal.status, self.worker.status, additional_tank.status, support.status)
        eligible_pair = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]

        self.assertEqual((eligible_pair["ready"], eligible_pair["state"]), (1, "ready"))
        # Three available characters exceed max_party_size=2; readiness comes
        # from one valid pair rather than aggregating the whole roster.
        self.assertEqual(before, (portal.status, self.worker.status, additional_tank.status, support.status))

        self._run(
            DungeonRun, self.guild.id, ends_in_seconds=3600,
            dungeon_template_id=self.dungeon.id,
        )
        self.db.flush()
        boss_already_running = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]
        self.assertEqual((boss_already_running["ready"], boss_already_running["state"]), (0, "none"))

    def test_portal_party_search_with_full_roster_has_bounded_database_queries(self):
        campaign = self.db.get(CampaignMetadata, "campaign-a")
        campaign.home_region = "Vale da Fronteira"
        self.db.add(RegionalGuildState(
            campaign_id="campaign-a", region_code="vale-fronteira", slot=0,
            guild_id=self.guild.id, name=self.guild.name, profile="player", archetype="player",
        ))
        portal = RegionalEvent(
            campaign_id="campaign-a", event_type="portal", region_code="vale-fronteira",
            trigger_cycle_number=20, rules_version="regional-events-v6", seed="portal-full-roster",
            status="active", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
            dungeon_template_id=self.dungeon.id,
        )
        self.dungeon.content_type = "boss"
        self.dungeon.recommended_level = 2
        self.dungeon.min_party_size = 2
        self.dungeon.max_party_size = 5
        self.dungeon.required_total_power = 999999
        self.db.add(portal)
        self.db.add_all([
            Mercenary(
                guild_id=self.guild.id, class_id=self.mercenary_class.id, name=f"Reserva QA {index}",
                power=1, vitality=1, agility=1, intelligence=1, luck=1,
            )
            for index in range(19)
        ])
        self.db.flush()

        statements = []

        def capture_statements(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lstrip().split(None, 1)[0].upper())

        event.listen(self.engine, "before_cursor_execute", capture_statements)
        started = perf_counter()
        try:
            result = get_navigation_work_status(
                self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
            )["regional_events"]
        finally:
            event.remove(self.engine, "before_cursor_execute", capture_statements)
        elapsed = perf_counter() - started

        self.assertEqual((result["ready"], result["state"]), (0, "none"))
        self.assertLessEqual(statements.count("SELECT"), 12)
        self.assertFalse(set(statements) & {"INSERT", "UPDATE", "DELETE"})
        self.assertLess(elapsed, 2.0, f"Full-roster eligibility scan took {elapsed:.3f}s")
        self.full_roster_query_count = statements.count("SELECT")
        self.full_roster_elapsed_seconds = elapsed

    def test_event_run_ready_to_collect_is_green_and_own_running_work_is_yellow(self):
        state = RegionalGuildState(
            campaign_id="campaign-a", region_code="north", slot=0, guild_id=self.guild.id,
            name=self.guild.name, profile="player", archetype="player",
        )
        resolved_event = RegionalEvent(
            campaign_id="campaign-a", event_type="rebellion", region_code="north",
            trigger_cycle_number=21, rules_version="regional-events-v6", seed="ready-to-collect",
            status="in_progress", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
        )
        active_event = RegionalEvent(
            campaign_id="campaign-a", event_type="rebellion", region_code="south",
            trigger_cycle_number=22, rules_version="regional-events-v6", seed="still-running",
            status="in_progress", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
        )
        other_campaign_event = RegionalEvent(
            campaign_id="campaign-b", event_type="rebellion", region_code="north",
            trigger_cycle_number=21, rules_version="regional-events-v6", seed="other-campaign",
            status="in_progress", created_at_utc=self.now, expires_at_utc=self.now + timedelta(hours=1),
        )
        self.db.add_all([state, resolved_event, active_event, other_campaign_event])
        self.db.flush()
        due_run = self._run(
            DungeonRun, self.guild.id, ends_in_seconds=-1, dungeon_template_id=self.dungeon.id,
        )
        running_run = self._run(
            MissionRun, self.guild.id, ends_in_seconds=60, mission_template_id=self.mission.id,
        )
        other_guild_run = self._run(
            MissionRun, self.other_guild.id, ends_in_seconds=60, mission_template_id=self.mission.id,
        )
        self.db.flush()
        due_activity = RegionalEventActivity(
            event_id=resolved_event.id, guild_state_id=state.id, source_type="dungeon",
            source_run_id=due_run.id, status="in_progress", due_at_utc=due_run.ends_at,
        )
        active_activity = RegionalEventActivity(
            event_id=active_event.id, guild_state_id=state.id, source_type="mission",
            source_run_id=running_run.id, status="in_progress", due_at_utc=running_run.ends_at,
        )
        cpu_activity = RegionalEventActivity(
            event_id=other_campaign_event.id, guild_state_id=state.id, source_type="mission",
            source_run_id=other_guild_run.id, status="in_progress", due_at_utc=other_guild_run.ends_at,
        )
        self.db.add_all([due_activity, active_activity, cpu_activity])
        self.db.flush()

        result = get_navigation_work_status(
            self.db, self.guild.id, campaign_id="campaign-a", now=self.now,
        )["regional_events"]

        self.assertEqual(result["ready"], 1)
        self.assertEqual(result["active"], 1)
        self.assertEqual(result["state"], "ready")
        self.assertEqual((due_activity.status, active_activity.status, cpu_activity.status),
                         ("in_progress", "in_progress", "in_progress"))


if __name__ == "__main__":
    unittest.main()
