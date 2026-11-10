import unittest
from datetime import datetime, timedelta, timezone

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
    RegionalGuildState,
    RegionalOffer,
    SupplyWorkshopJob,
)
from app.services.navigation_work_status_service import get_navigation_work_status


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

        def count_selects(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", count_selects)
        try:
            result = get_navigation_work_status(self.db, self.guild.id, campaign_id="campaign-a", now=self.now)
        finally:
            event.remove(self.engine, "before_cursor_execute", count_selects)

        self.assertEqual(len(statements), 1)
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


if __name__ == "__main__":
    unittest.main()
