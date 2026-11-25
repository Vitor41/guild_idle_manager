import json
import unittest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from alembic import command
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from app.database.connection import Base, create_database_engine
from app.models import (
    CampaignMetadata,
    BuildingTemplate,
    ClassChangeRun,
    DungeonRun,
    DungeonTemplate,
    GatheringAssignment,
    Guild,
    GuildBuilding,
    GuildBuildingInvestment,
    GuildBuildingReset,
    GuildBuildingResetState,
    GuildInventoryItem,
    GuildResources,
    GuildSalvageJob,
    ItemTemplate,
    MarketSale,
    Mercenary,
    MercenaryClass,
    MissionRun,
    MissionTemplate,
    RegionalCycle,
    RegionalGuildState,
    RegionalOffer,
    SupplyWorkshopJob,
)
from app.repositories.item_repository import add_inventory_quantity
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_VERSION
from app.services import building_reset_service
from app.services.building_reset_service import (
    BlockedBuildingReset,
    StaleBuildingResetPreview,
    get_building_reset_preview,
    perform_building_reset,
)
from app.services.building_service import upgrade_guild_building
from app.services.building_balance_service import housing_capacity
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage


class BuildingResetServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        apply_initial_campaign_content(self.db)
        self.campaign = CampaignMetadata(
            campaign_id="00000000-0000-0000-0000-000000000046",
            campaign_name="Reset fixture",
            schema_version=8,
            content_version=PACK_VERSION,
            home_region="Vale da Fronteira",
        )
        self.guild = Guild(campaign_id=self.campaign.campaign_id, name="Guilda reset", level=10)
        self.resources = GuildResources(guild=self.guild, gold=1_000_000, crystal_reserve=0)
        self.db.add_all((self.campaign, self.guild, self.resources))
        self.db.flush()
        from app.services.building_service import ensure_guild_buildings

        ensure_guild_buildings(self.db, self.guild.id)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _building(self, effect_type: str) -> GuildBuilding:
        return self.db.scalar(
            select(GuildBuilding)
            .join(GuildBuilding.building_template)
            .where(
                GuildBuilding.guild_id == self.guild.id,
                GuildBuilding.building_template.has(effect_type=effect_type),
            )
        )

    def _reset(self, preview: dict) -> GuildBuildingReset:
        return perform_building_reset(
            self.db,
            self.guild.id,
            expected_fingerprint=preview["fingerprint"],
            idempotency_key=preview["idempotency_key"],
        )

    def _material_templates(self, resource: str, count: int) -> list[ItemTemplate]:
        families = {"wood": ("wood",), "crystals": ("gem", "essence", "crystal")}[resource]
        rows = list(self.db.scalars(select(ItemTemplate).where(
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family.in_(families),
        ).order_by(ItemTemplate.id)))
        self.assertGreaterEqual(len(rows), count)
        return rows[:count]

    def test_reset_refunds_exact_material_templates_reserve_and_initial_building_gold_once(self):
        warehouse = self._building("warehouse")
        warehouse.building_template.base_upgrade_gold_cost = 17
        warehouse.building_template.base_upgrade_wood_cost = 30
        warehouse.building_template.base_upgrade_ore_cost = 0
        warehouse.building_template.base_upgrade_crystals_cost = 20
        wood_one, wood_two = self._material_templates("wood", 2)
        crystal_one, crystal_two = self._material_templates("crystals", 2)
        self.resources.gold = 1_000
        self.resources.crystal_reserve = 10
        add_inventory_quantity(self.db, self.guild.id, wood_one.id, 20)
        add_inventory_quantity(self.db, self.guild.id, wood_two.id, 20)
        add_inventory_quantity(self.db, self.guild.id, crystal_one.id, 7)
        add_inventory_quantity(self.db, self.guild.id, crystal_two.id, 5)
        self.db.commit()

        warehouse = upgrade_guild_building(self.db, self.guild, self.resources, warehouse.id)
        tavern = upgrade_guild_building(self.db, self.guild, self.resources, self._building("tavern").id)
        housing = upgrade_guild_building(self.db, self.guild, self.resources, self._building("housing").id)
        self.assertEqual(tavern.level, 1)
        self.assertEqual(housing.level, 1)
        self.assertEqual(warehouse.level, 1)

        investments = list(self.db.scalars(select(GuildBuildingInvestment).where(
            GuildBuildingInvestment.guild_id == self.guild.id,
        )))
        warehouse_investment = next(row for row in investments if row.guild_building_id == warehouse.id)
        self.assertEqual(warehouse_investment.gold_debited, 17)
        self.assertEqual(warehouse_investment.crystal_reserve_debited, 8)
        self.assertEqual(
            {(row["item_template_id"], row["quantity"]) for row in warehouse_investment.materials_json},
            {(wood_one.id, 20), (wood_two.id, 10), (crystal_one.id, 7), (crystal_two.id, 5)},
        )
        self.assertEqual(self.resources.crystal_reserve, 2)

        preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertTrue(preview["was_free"])
        self.assertTrue(preview["can_confirm"])
        self.assertEqual(preview["refund"]["gold"]["exact"], 37)
        self.assertFalse(preview["has_estimated_refund"])
        reset = self._reset(preview)

        self.assertEqual(self.resources.gold, 1_000)
        self.assertEqual(self.resources.crystal_reserve, 10)
        self.assertEqual(warehouse.level, 0)
        self.assertEqual(tavern.level, 0)
        self.assertEqual(housing.level, 0)
        self.assertEqual(self.guild.xp, 30)
        self.assertEqual(self.db.scalar(select(func.sum(GuildInventoryItem.quantity)).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id.in_((wood_one.id, wood_two.id)),
        )), 40)
        self.assertEqual(self.db.scalar(select(func.sum(GuildInventoryItem.quantity)).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id.in_((crystal_one.id, crystal_two.id)),
        )), 12)
        self.assertTrue(all(row.refunded_by_reset_id == reset.id for row in investments))

        replay = perform_building_reset(
            self.db,
            self.guild.id,
            expected_fingerprint=preview["fingerprint"],
            idempotency_key=preview["idempotency_key"],
        )
        self.assertEqual(replay.id, reset.id)
        self.assertEqual(self.resources.gold, 1_000)
        state = self.db.get(GuildBuildingResetState, self.guild.id)
        self.assertTrue(state.free_reset_used)
        self.assertEqual(state.reset_count, 1)

    def test_first_free_requires_level_ten_then_paid_costs_persist_and_round_up(self):
        building = self._building("warehouse")
        guild_id = self.guild.id
        building.building_template.base_upgrade_gold_cost = 0
        building.building_template.base_upgrade_wood_cost = 0
        building.building_template.base_upgrade_ore_cost = 0
        building.building_template.base_upgrade_crystals_cost = 0
        self.guild.level = 9
        self.db.commit()
        upgrade_guild_building(self.db, self.guild, self.resources, building.id)
        preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertFalse(preview["can_confirm"])
        self.assertEqual([row["code"] for row in preview["blockers"]], ["guild_level"])
        with self.assertRaises(BlockedBuildingReset):
            self._reset(preview)
        self.db.rollback()
        self.assertIsNone(self.db.get(GuildBuildingResetState, self.guild.id))
        self.assertEqual(self._building("warehouse").level, 1)

        self.guild.level = 10
        self.resources.crystal_reserve = 1_000
        self.db.commit()
        free_preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertTrue(free_preview["was_free"])
        self._reset(free_preview)
        self.db.commit()
        state = self.db.get(GuildBuildingResetState, self.guild.id)
        self.assertTrue(state.free_reset_used)

        self.guild.level = 1
        self.db.commit()
        expected_costs = (50, 65, 85, 111, 145)
        for expected in expected_costs:
            building = self._building("warehouse")
            upgrade_guild_building(self.db, self.guild, self.resources, building.id)
            preview = get_building_reset_preview(self.db, self.guild.id)
            self.assertEqual(preview["crystal_cost"], expected)
            self.assertTrue(preview["can_confirm"])
            reset = self._reset(preview)
            self.assertEqual(reset.charge_json, {
                "crystal_cost": expected,
                "crystal_reserve": expected,
                "items": [],
            })
            replay = perform_building_reset(
                self.db, self.guild.id,
                expected_fingerprint=preview["fingerprint"],
                idempotency_key=preview["idempotency_key"],
            )
            self.assertEqual(replay.id, reset.id)
            self.assertEqual(replay.charge_json, reset.charge_json)
            self.db.commit()
            self.db.close()
            self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
            self.guild = self.db.get(Guild, guild_id)
            self.resources = self.db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))
        state = self.db.get(GuildBuildingResetState, guild_id)
        self.assertEqual(state.paid_reset_count, 5)
        self.assertEqual(state.previous_paid_cost, 145)
        self.assertEqual(state.reset_count, 6)
        self.assertEqual(self.resources.crystal_reserve, 1_000 - sum(expected_costs))

    def test_paid_reset_charge_records_exact_material_stacks_and_reserve_composition(self):
        crystal_one, crystal_two = self._material_templates("crystals", 2)
        warehouse = self._building("warehouse")
        warehouse.level = 1
        self.resources.crystal_reserve = 0
        self.db.add(GuildBuildingResetState(
            guild_id=self.guild.id, free_reset_used=True, paid_reset_count=0,
            previous_paid_cost=0, reset_count=0,
        ))
        add_inventory_quantity(self.db, self.guild.id, crystal_one.id, 30)
        add_inventory_quantity(self.db, self.guild.id, crystal_two.id, 20)
        self.db.commit()

        preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertEqual(preview["crystal_cost"], 50)
        reset = self._reset(preview)
        self.assertEqual(reset.charge_json["crystal_cost"], 50)
        self.assertEqual(reset.charge_json["crystal_reserve"], 0)
        self.assertEqual(
            {item["item_template_id"]: item["quantity"] for item in reset.charge_json["items"]},
            {crystal_one.id: 30, crystal_two.id: 20},
        )
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingReset.id))), 1)
        self.assertEqual(self.db.get(GuildBuildingResetState, self.guild.id).paid_reset_count, 1)

    def test_paid_reset_charge_records_mixed_material_and_reserve_exactly(self):
        crystal_one, crystal_two = self._material_templates("crystals", 2)
        warehouse = self._building("warehouse")
        warehouse.level = 1
        self.resources.crystal_reserve = 30
        self.db.add(GuildBuildingResetState(
            guild_id=self.guild.id, free_reset_used=True, paid_reset_count=0,
            previous_paid_cost=0, reset_count=0,
        ))
        add_inventory_quantity(self.db, self.guild.id, crystal_one.id, 8)
        add_inventory_quantity(self.db, self.guild.id, crystal_two.id, 12)
        self.db.commit()

        preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertEqual(preview["crystal_cost"], 50)
        reset = self._reset(preview)
        self.assertEqual(reset.charge_json["crystal_cost"], 50)
        self.assertEqual(reset.charge_json["crystal_reserve"], 30)
        self.assertEqual(
            {item["item_template_id"]: item["quantity"] for item in reset.charge_json["items"]},
            {crystal_one.id: 8, crystal_two.id: 12},
        )

    def test_stale_preview_rejects_without_changing_building_or_balance(self):
        building = self._building("warehouse")
        building.level = 1
        self.resources.crystal_reserve = 200
        self.db.commit()
        preview = get_building_reset_preview(self.db, self.guild.id)
        self.resources.gold -= 1
        self.db.commit()

        with self.assertRaises(StaleBuildingResetPreview):
            self._reset(preview)
        self.db.rollback()
        self.assertEqual(self._building("warehouse").level, 1)
        self.assertEqual(self.resources.gold, 1_000_000 - 1)
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingReset.id))), 0)

    def test_all_pending_work_types_block_even_when_ready_and_terminal_history_does_not(self):
        now = datetime.now(timezone.utc)
        warehouse = self._building("warehouse")
        warehouse.level = 1
        item = self._material_templates("wood", 1)[0]
        mission = self.db.scalar(select(MissionTemplate))
        dungeon = self.db.scalar(select(DungeonTemplate))
        mercenary_class = self.db.scalar(select(MercenaryClass).where(MercenaryClass.code == "apprentice"))
        member = Mercenary(
            guild_id=self.guild.id, class_id=mercenary_class.id, name="Bloqueador",
            level=1, xp=0, status="available", rarity="common", hire_cost=0,
            power=mercenary_class.base_power, vitality=mercenary_class.base_vitality,
            agility=mercenary_class.base_agility, intelligence=mercenary_class.base_intelligence,
            luck=mercenary_class.base_luck,
        )
        cycle = RegionalCycle(
            campaign_id=self.campaign.campaign_id, cycle_number=880,
            starts_at_utc=now - timedelta(hours=7), ends_at_utc=now - timedelta(hours=1),
            seed="reset-blocker", rules_version="test",
        )
        state = RegionalGuildState(
            campaign_id=self.campaign.campaign_id, region_code="vale", slot=99,
            guild_id=self.guild.id, name=self.guild.name, profile="balanced", archetype="balanced",
        )
        self.db.add_all((member, cycle, state))
        self.db.flush()
        sale = MarketSale(
            guild_id=self.guild.id, item_template_id=item.id, quantity=1, unit_value=1,
            total_value=1, status="in_progress", started_at=now - timedelta(hours=1),
            ends_at=now - timedelta(minutes=1),
        )
        mission_run = MissionRun(
            guild_id=self.guild.id, mission_template_id=mission.id, status="in_progress",
            started_at=now - timedelta(hours=1), ends_at=now - timedelta(minutes=1),
        )
        dungeon_run = DungeonRun(
            guild_id=self.guild.id, dungeon_template_id=dungeon.id, status="in_progress",
            started_at=now - timedelta(hours=1), ends_at=now - timedelta(minutes=1),
        )
        class_run = ClassChangeRun(
            guild_id=self.guild.id, mercenary_id=member.id,
            from_class_id=mercenary_class.id, to_class_id=mercenary_class.id,
            gold_cost=0, status="in_progress", started_at=now - timedelta(hours=1),
            ends_at=now - timedelta(minutes=1),
        )
        salvage = GuildSalvageJob(
            guild_id=self.guild.id, slot_number=1, item_template_id=item.id,
            material_template_id=item.id, quantity=1, gold_cost=0, status="in_progress",
            started_at=now - timedelta(hours=1), ends_at=now - timedelta(minutes=1),
        )
        workshop = SupplyWorkshopJob(
            guild_id=self.guild.id, output_item_template_id=item.id, kit_quantity=1,
            meat_per_kit=1, herb_per_kit=1, seconds_per_kit=1, status="in_progress",
            started_at=now - timedelta(hours=1), ends_at=now - timedelta(minutes=1),
        )
        assignment = GatheringAssignment(
            guild_id=self.guild.id, mercenary_id=member.id, resource_family="wood",
            node_code="woodland", progress_seconds=1, cycle_count=0, quantity_collected=0,
            capacity_paused=True, extra_chance=0, rng_seed=1,
            started_at_utc=now - timedelta(hours=1), checkpoint_at_utc=now - timedelta(minutes=1),
        )
        offer = RegionalOffer(
            campaign_id=self.campaign.campaign_id, cycle_id=cycle.id, cycle_number=cycle.cycle_number,
            region_code="vale", offer_type="mission", slot=99, rank="D", name_snapshot="Preparo pronto",
            description_snapshot="", level_band_snapshot="1-20", recommended_level_snapshot=1,
            recommended_power_snapshot=1, duration_seconds_snapshot=60, gold_reward_snapshot=0,
            xp_reward_snapshot=0, success_chance_snapshot=100, status="supply_preparing",
            reserved_by_guild_state_id=state.id,
        )
        self.db.add_all((sale, mission_run, dungeon_run, class_run, salvage, workshop, assignment, offer))
        self.db.commit()

        preview = get_building_reset_preview(self.db, self.guild.id)
        codes = {row["code"] for row in preview["blockers"]}
        self.assertEqual(codes, {
            "market_sales", "mission_runs", "dungeon_runs", "class_change_runs",
            "guild_salvage_jobs", "supply_workshop_jobs", "gathering_assignments",
            "regional_supply_preparing",
        })
        with self.assertRaises(BlockedBuildingReset):
            self._reset(preview)

        for row in (sale, mission_run, dungeon_run, class_run, salvage, workshop):
            row.status = "completed"
        self.db.delete(assignment)
        offer.status = "completed"
        self.db.commit()
        terminal_preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertEqual(terminal_preview["blockers"], [])
        self.assertTrue(terminal_preview["can_confirm"])

    def test_reset_preserves_over_capacity_stock_and_roster_without_dismissals(self):
        housing = self._building("housing")
        warehouse = self._building("warehouse")
        housing.level = 100
        warehouse.level = 100
        item = self._material_templates("wood", 1)[0]
        add_inventory_quantity(self.db, self.guild.id, item.id, 3_000)
        mercenary_class = self.db.scalar(select(MercenaryClass).where(MercenaryClass.code == "apprentice"))
        members = [Mercenary(
            guild_id=self.guild.id, class_id=mercenary_class.id, name=f"Persistente {number}",
            level=1, xp=0, status="available", rarity="common", hire_cost=0,
            power=mercenary_class.base_power, vitality=mercenary_class.base_vitality,
            agility=mercenary_class.base_agility, intelligence=mercenary_class.base_intelligence,
            luck=mercenary_class.base_luck,
        ) for number in range(2)]
        self.db.add_all(members)
        self.db.commit()
        before_usage = get_inventory_usage(self.db, self.guild.id)

        preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertEqual(preview["capacity_after"]["housing_slots"], 0)
        self.assertEqual(preview["capacity_after"]["active_mercenaries"], 2)
        projected_usage = before_usage - sum(
            row["quantity"] for row in preview["charge_quote"]["items"]
        ) + sum(row["quantity"] for row in preview["refund"]["items"])
        self.assertEqual(preview["capacity_after"]["inventory_usage"], projected_usage)
        self.assertEqual(preview["capacity_after"]["inventory_over_capacity"], max(
            0, projected_usage - preview["capacity_after"]["warehouse_capacity"]
        ))
        self._reset(preview)

        self.assertEqual(housing_capacity(0), 0)
        self.assertEqual(self.db.scalar(select(func.count(Mercenary.id)).where(
            Mercenary.guild_id == self.guild.id,
            Mercenary.status != "dismissed",
        )), 2)
        self.assertEqual(get_inventory_usage(self.db, self.guild.id), preview["capacity_after"]["inventory_usage"])
        self.assertEqual(get_inventory_capacity(self.db, self.guild), 1_590)
        self.assertGreaterEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == item.id,
        )), 3_000)

    def test_legacy_estimates_are_read_only_in_preview_then_frozen_on_reset(self):
        building = self._building("warehouse")
        building.level = 2
        self.db.commit()
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingInvestment.id))), 0)

        preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertTrue(preview["has_estimated_refund"])
        self.assertIn("Não é histórico comprovado", preview["estimate_basis"])
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingInvestment.id))), 0)
        self._reset(preview)
        self.db.commit()
        estimates = list(self.db.scalars(select(GuildBuildingInvestment).where(
            GuildBuildingInvestment.guild_building_id == building.id,
        )))
        self.assertEqual(len(estimates), 2)
        self.assertTrue(all(row.estimated for row in estimates))
        costs = [row.gold_debited for row in estimates]
        building.building_template.base_upgrade_gold_cost += 900
        self.db.commit()
        self.db.close()
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.guild = self.db.get(Guild, self.guild.id)
        frozen = list(self.db.scalars(select(GuildBuildingInvestment).where(
            GuildBuildingInvestment.guild_building_id == building.id,
        ).order_by(GuildBuildingInvestment.to_level)))
        self.assertEqual([row.gold_debited for row in frozen], costs)
        self.assertTrue(all(row.refunded_by_reset_id is not None for row in frozen))

    def test_failure_after_charge_and_refund_rolls_back_everything(self):
        building = self._building("warehouse")
        building.level = 1
        self.resources.crystal_reserve = 300
        self.db.add(GuildBuildingResetState(
            guild_id=self.guild.id, free_reset_used=True, paid_reset_count=0,
            previous_paid_cost=0, reset_count=1,
        ))
        self.db.commit()
        preview = get_building_reset_preview(self.db, self.guild.id)
        self.assertEqual(preview["crystal_cost"], 50)
        original_sync = building_reset_service.sync_inventory_resource_totals
        calls = 0

        def fail_after_refund(db, resources):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected reset rollback")
            return original_sync(db, resources)

        with patch.object(building_reset_service, "sync_inventory_resource_totals", side_effect=fail_after_refund):
            with self.assertRaisesRegex(RuntimeError, "injected reset rollback"):
                self._reset(preview)
        self.db.rollback()
        self.assertEqual(self._building("warehouse").level, 1)
        self.assertEqual(self.resources.crystal_reserve, 300)
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingReset.id))), 0)
        state = self.db.get(GuildBuildingResetState, self.guild.id)
        self.assertEqual(state.paid_reset_count, 0)
        self.assertEqual(state.reset_count, 1)

    def test_preview_route_shows_cost_refund_capacity_and_linked_blockers_and_stale_post_refreshes(self):
        from app.routes.building_routes import buildings_index, reset_buildings

        warehouse = self._building("warehouse")
        warehouse.level = 1
        item = self._material_templates("wood", 1)[0]
        common_materials = list(self.db.scalars(select(ItemTemplate).where(
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family.in_(("wood", "ore")),
            ItemTemplate.rarity.ilike("common"),
        )))
        self.assertTrue(common_materials)
        for material in common_materials:
            material.rarity = "uncommon"
        now = datetime.now(timezone.utc)
        self.db.add(MarketSale(
            guild_id=self.guild.id, item_template_id=item.id, quantity=1, unit_value=1,
            total_value=1, status="in_progress", started_at=now, ends_at=now + timedelta(minutes=1),
        ))
        self.db.commit()
        user = SimpleNamespace(
            id=1, username="route-test", is_admin=False, confirmation_preferences="{}",
            home_region=None,
        )
        app = FastAPI()
        app.state.app_mode = "web"
        app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parents[1] / "app/static"), name="static")
        scope = {
            "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": "/buildings", "raw_path": b"/buildings", "root_path": "",
            "query_string": b"reset_preview=1", "headers": [], "client": ("testclient", 123),
            "server": ("testserver", 80), "app": app,
        }
        with patch("app.routes.building_routes.get_current_guild_context", return_value=(self.guild, self.resources)):
            response = buildings_index(Request(scope), self.db, user)
        html = response.body.decode("utf-8")
        header_html = html.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
        self.assertIn('class="button-link secondary buildings-heading__action"', header_html)
        self.assertLess(header_html.index("buildings-heading__action"), header_html.index('class="user-menu"'))
        self.assertIn('data-building-reset-dialog open', html)
        self.assertIn("Custo do reset", html)
        self.assertIn("Você recebe", html)
        self.assertIn("Capacidade após o reset", html)
        self.assertIn("estoque e reservas após a cobrança e os reembolsos", html)
        self.assertIn('class="building-costs"', html)
        self.assertIn('aria-label="Custo para o próximo nível"', html)
        self.assertNotIn("0 ouro, 0 madeira, 0 minério, 0 cristais", html)
        reset_dialog = html.split('<dialog class="building-reset-dialog"', 1)[1].split("</dialog>", 1)[0]
        self.assertIn('class="building-reset-provenance"><summary>Ver composição do investimento registrado</summary>', reset_dialog)
        self.assertIn("<summary>Ver base da estimativa</summary>", reset_dialog)
        self.assertNotIn('class="building-reset-provenance" open', reset_dialog)
        self.assertIn("Estimativa de investimento antigo:", reset_dialog)
        self.assertIn('href="/market"', reset_dialog)
        self.assertIn("Vendas em andamento", reset_dialog)
        pending_materials = get_building_reset_preview(self.db, self.guild.id)["refund"]["pending_materials"]
        material_labels = {"wood": "Madeira", "ore": "Minério"}
        for pending in pending_materials:
            label = material_labels[pending["resource"]]
            expected = (
                f"Reset indisponível: {label} Comum ausente do catálogo. "
                f"Estimativa preservada: {pending['quantity']} unidades."
            )
            self.assertIn(f"<span>{expected}</span>", reset_dialog)
        self.assertNotIn('href="/updates"', reset_dialog)
        self.assertIn('data-reset-cancel autofocus', html)
        self.assertIn('aria-live="polite" data-reset-status', html)
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingReset.id))), 0)
        self.assertIsNone(self.db.get(GuildBuildingResetState, self.guild.id))

        with patch("app.routes.building_routes.get_current_guild_context", return_value=(self.guild, None)):
            unavailable_response = buildings_index(Request(scope), self.db, user)
        unavailable_html = unavailable_response.body.decode("utf-8")
        self.assertIn('data-resource-total="gold">Indisponível</dd>', unavailable_html)
        self.assertIn("Saldo indisponível", unavailable_html)
        self.assertNotIn('data-resource-total="gold">0</dd>', unavailable_html)

        with patch("app.routes.building_routes.get_current_guild_context", return_value=(self.guild, self.resources)):
            response = reset_buildings(
                self.db, expected_fingerprint="outdated", idempotency_key=str(uuid4()), current_user=user,
            )
        self.assertEqual(response.status_code, 303)
        self.assertIn("reset_preview=1", response.headers["location"])
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingReset.id))), 0)

        scope["query_string"] = (
            b"reset_preview=1&error=O%20estado%20da%20guilda%20mudou%20desde%20a%20pr%C3%A9via.%20"
            b"Confira%20os%20valores%20atualizados%20antes%20de%20confirmar."
        )
        with patch("app.routes.building_routes.get_current_guild_context", return_value=(self.guild, self.resources)):
            stale_preview_response = buildings_index(Request(scope), self.db, user)
        stale_html = stale_preview_response.body.decode("utf-8")
        stale_dialog = stale_html.split('<dialog class="building-reset-dialog"', 1)[1].split("</dialog>", 1)[0]
        stale_message = "O estado da guilda mudou desde a prévia. Confira os valores atualizados antes de confirmar."
        self.assertIn(stale_message, stale_dialog)
        self.assertIn('role="alert" aria-live="assertive" data-reset-preview-error', stale_dialog)
        self.assertEqual(stale_html.count(stale_message), 1)
        self.assertNotIn(stale_message, stale_html.split('<dialog class="building-reset-dialog"', 1)[0])

        for material in common_materials:
            material.rarity = "common"
        self.db.commit()
        sale = self.db.scalar(select(MarketSale).where(MarketSale.guild_id == self.guild.id))
        sale.status = "completed"
        self.db.commit()
        preview = get_building_reset_preview(self.db, self.guild.id)
        with patch("app.routes.building_routes.get_current_guild_context", return_value=(self.guild, self.resources)):
            response = reset_buildings(
                self.db, expected_fingerprint=preview["fingerprint"],
                idempotency_key=preview["idempotency_key"], current_user=user,
            )
        self.assertEqual(response.status_code, 303)
        self.assertIn("reset_id=", response.headers["location"])
        reset_id = int(response.headers["location"].rsplit("=", 1)[1])
        scope["query_string"] = f"reset_id={reset_id}".encode("ascii")
        with patch("app.routes.building_routes.get_current_guild_context", return_value=(self.guild, self.resources)):
            result_response = buildings_index(Request(scope), self.db, user)
        result_html = result_response.body.decode("utf-8")
        self.assertIn("Reset concluído", result_html)
        self.assertIn("Você recebe", result_html)
        self.assertEqual(self._building("warehouse").level, 0)

    def test_progress_and_buildings_routes_share_building_benefits_and_max_level_presentation(self):
        from app.routes.building_routes import buildings_index
        from app.routes.progress_routes import guild_progress
        from app.services.building_balance_service import get_building_benefit

        warehouse = self._building("warehouse")
        warehouse.level = 10
        maximum_building = self._building("blacksmith")
        maximum_building.level = maximum_building.building_template.max_level
        self.db.commit()

        user = SimpleNamespace(
            id=1, username="progress-view-test", is_admin=False,
            confirmation_preferences="{}", home_region=None,
        )
        app = FastAPI()
        app.state.app_mode = "web"
        app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parents[1] / "app/static"), name="static")

        def request(path: str) -> Request:
            return Request({
                "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
                "path": path, "raw_path": path.encode("ascii"), "root_path": "",
                "query_string": b"", "headers": [], "client": ("testclient", 123),
                "server": ("testserver", 80), "app": app,
            })

        with patch(
            "app.routes.building_routes.get_current_guild_context",
            return_value=(self.guild, self.resources),
        ):
            buildings_html = buildings_index(request("/buildings"), self.db, user).body.decode("utf-8")
        with patch(
            "app.routes.progress_routes.get_current_guild_context",
            return_value=(self.guild, self.resources),
        ):
            progress_html = guild_progress(request("/guild/progress"), self.db, user).body.decode("utf-8")

        warehouse_benefit = get_building_benefit("warehouse", warehouse.level)
        self.assertIsNotNone(warehouse_benefit["next_milestone_level"])
        self.assertIn(f"Próximo marco: nível {warehouse_benefit['next_milestone_level']}", progress_html)
        self.assertIn("<dt>Nível</dt><dd>10 /", progress_html)
        for line in (*warehouse_benefit["current"], *warehouse_benefit["next"]):
            self.assertIn(line, buildings_html)
            self.assertIn(line, progress_html)

        maximum_benefit = get_building_benefit(
            maximum_building.building_template.effect_type,
            maximum_building.level,
        )
        self.assertIsNone(maximum_benefit["next_milestone_level"])
        self.assertIn("Nível máximo atingido", progress_html)
        self.assertIn("Não há próxima evolução.", progress_html)
        self.assertNotIn("None", progress_html)

    def test_reset_status_is_read_only_and_scoped_to_current_guild(self):
        from app.routes.building_routes import building_reset_status

        idempotency_key = str(uuid4())
        other_campaign = CampaignMetadata(
            campaign_id="00000000-0000-0000-0000-000000000146",
            campaign_name="Outra campanha",
            schema_version=8,
            content_version=PACK_VERSION,
            home_region="Vale da Fronteira",
        )
        other_guild = Guild(campaign_id=other_campaign.campaign_id, name="Outra guilda", level=10)
        self.db.add(other_campaign)
        self.db.add(other_guild)
        self.db.flush()
        self.db.add(GuildBuildingReset(
            guild_id=other_guild.id,
            idempotency_key=idempotency_key,
            was_free=True,
            crystal_cost=0,
            charge_json={},
            refund_json={},
            levels_before_json={},
            has_estimated_refund=False,
        ))
        self.db.commit()
        user = SimpleNamespace(id=1, username="route-test", is_admin=False)

        with patch("app.routes.building_routes.get_current_guild_context", return_value=(self.guild, self.resources)):
            other_guild_status = building_reset_status(self.db, idempotency_key, user)
            missing_status = building_reset_status(self.db, str(uuid4()), user)

        self.assertEqual(json.loads(other_guild_status.body), {"completed": False, "reset_id": None})
        self.assertEqual(json.loads(missing_status.body), {"completed": False, "reset_id": None})
        self.assertEqual(other_guild_status.headers["cache-control"], "no-store")
        self.assertEqual(self.db.scalar(select(func.count(GuildBuildingReset.id))), 1)


class BuildingResetMigrationTests(unittest.TestCase):
    def test_previous_campaign_schema_gets_frozen_estimates_without_losing_buildings(self):
        from app.services.campaign_service import CURRENT_SCHEMA_VERSION, CampaignService

        with TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_id = "00000000-0000-0000-0000-000000000047"
            database_path = root / f"{campaign_id}.db"
            campaign_service = CampaignService(root / "saves")
            config = campaign_service._alembic_config(database_path)
            command.upgrade(config, "0a1b2c3d4e5f")
            engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                with Session(engine, autoflush=False, expire_on_commit=False) as db:
                    campaign = CampaignMetadata(
                        campaign_id=campaign_id, campaign_name="Save anterior",
                        schema_version=7, content_version=PACK_VERSION,
                        home_region="Vale da Fronteira",
                    )
                    guild = Guild(campaign_id=campaign_id, name="Guilda anterior", level=10)
                    resources = GuildResources(guild=guild, gold=1_000)
                    db.add_all((campaign, guild, resources))
                    db.flush()
                    tavern_template = BuildingTemplate(
                        name="Taverna", description="", effect_type="tavern",
                        base_upgrade_gold_cost=140, base_upgrade_wood_cost=25,
                        base_upgrade_ore_cost=5, base_upgrade_crystals_cost=0,
                        max_level=100, required_guild_level=1, is_active=True,
                    )
                    db.add(tavern_template)
                    db.flush()
                    tavern = GuildBuilding(
                        guild_id=guild.id, building_template_id=tavern_template.id, level=1,
                    )
                    db.add(tavern)
                    db.commit()
                    guild_id = guild.id
            finally:
                engine.dispose()

            migration = campaign_service._ensure_schema(database_path, campaign_id)
            self.assertIsNotNone(migration)
            self.assertEqual(migration.previous_revision, "0a1b2c3d4e5f")
            self.assertEqual(migration.current_save_version, CURRENT_SCHEMA_VERSION)

            migrated_engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                with Session(migrated_engine) as db:
                    tavern = db.scalar(select(GuildBuilding).join(
                        GuildBuilding.building_template,
                    ).where(
                        GuildBuilding.guild_id == guild_id,
                        GuildBuilding.building_template.has(effect_type="tavern"),
                    ))
                    estimate = db.scalar(select(GuildBuildingInvestment).where(
                        GuildBuildingInvestment.guild_building_id == tavern.id,
                        GuildBuildingInvestment.to_level == 1,
                    ))
                    state = db.get(GuildBuildingResetState, guild_id)
                    metadata = db.get(CampaignMetadata, campaign_id)
                    self.assertEqual(tavern.level, 1)
                    self.assertIsNotNone(estimate)
                    self.assertTrue(estimate.estimated)
                    self.assertEqual(estimate.gold_debited, 10)
                    self.assertIn("Não é histórico comprovado", estimate.estimate_basis)
                    self.assertFalse(state.free_reset_used)
                    self.assertEqual(state.reset_count, 0)
                    self.assertEqual(metadata.schema_version, CURRENT_SCHEMA_VERSION)
                    estimate_cost = estimate.gold_debited
                    tavern.building_template.base_upgrade_gold_cost += 700
                    db.commit()
                    db.expire_all()
                    estimate = db.get(GuildBuildingInvestment, estimate.id)
                    self.assertEqual(estimate.gold_debited, estimate_cost)
            finally:
                migrated_engine.dispose()


if __name__ == "__main__":
    unittest.main()
