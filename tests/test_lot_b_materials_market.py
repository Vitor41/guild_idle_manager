import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import (
    BuildingTemplate, Guild, GuildBuilding, GuildInventoryItem, GuildItemInstance,
    GuildResources, ItemTemplate, MarketSale, Mercenary, MercenaryClass,
)
from app.models.gathering import GatheringAssignment
from app.services.gathering_service import _material_template, advance_assignment, assign_worker, freeze_legacy_assignment_targets
from app.services.inventory_capacity_service import get_inventory_capacity
from app.services.market_service import (
    MarketError, _sale_duration_seconds, cancel_market_sale, collect_market_sale,
    get_market_bonuses, start_equipment_sale, start_material_sale,
)
from app.seeds.massive_content import (
    MATERIAL_PROGRESS_STAGES, PACK_KEY, _legacy_material_rows, _material_rows,
    _reconcile_material_progression,
)


class LotBMaterialProgressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_seed_matrix_covers_all_families_and_level_seven_selects_only_common_stage(self):
        rows = _material_rows()
        self.assertEqual(len(rows), 447)
        self.assertEqual(len({row["material_family"] for row in rows}), 13)
        self.db.add_all(ItemTemplate(**row) for row in rows)
        guild = Guild(name="Progressão lote B", level=7)
        self.db.add(guild)
        self.db.flush()

        selected_wood = _material_template(self.db, "wood", guild.level)
        selected_ore = _material_template(self.db, "ore", guild.level)
        self.assertIsNotNone(selected_wood)
        self.assertIsNotNone(selected_ore)
        self.assertIn("Bruta", selected_wood.name)
        self.assertEqual(selected_wood.rarity, "common")
        self.assertEqual(selected_wood.required_level, 1)
        self.assertLessEqual(selected_wood.item_level, 7)
        self.assertIn("de Cobre", selected_ore.name)
        self.assertEqual(selected_ore.rarity, "common")
        mithril_rows = [row for row in rows if row["material_family"] == "ore" and "Mithril" in str(row["name"])]
        self.assertTrue(mithril_rows)
        self.assertTrue(all(row["required_level"] >= 101 and row["rarity"] == "epic" for row in mithril_rows))

        for stage_index, (unlock, _end, rarity) in enumerate(MATERIAL_PROGRESS_STAGES):
            guild.level = unlock
            for family in {row["material_family"] for row in rows}:
                selected = _material_template(self.db, family, guild.level)
                self.assertIsNotNone(selected, (family, unlock))
                self.assertEqual(selected.required_level, unlock, (family, unlock, selected.name))
                self.assertEqual(selected.rarity, rarity, (family, unlock, selected.name))

    def test_legacy_content_reconciliation_is_idempotent_and_preserves_admin_edits_and_inventory(self):
        old_rows = {row["slug"]: row for row in _legacy_material_rows()}
        new_rows = {row["slug"]: row for row in _material_rows()}
        arcana = ItemTemplate(**old_rows["material_wood_1_025"])
        old_arcana_name = arcana.name
        customized = ItemTemplate(**old_rows["material_wood_2_026"])
        customized.description = "Descrição personalizada pelo Admin."
        name_conflict = ItemTemplate(
            name=new_rows["material_wood_1_025"]["name"], description="Nome criado pelo Admin.",
            item_type="material", rarity="common", material_family="wood",
        )
        guild = Guild(name="Save legado", level=7)
        self.db.add_all([arcana, customized, name_conflict, guild])
        self.db.flush()
        arcana_id, customized_id = arcana.id, customized.id
        self.db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=arcana.id, quantity=23))
        self.db.commit()

        changed = _reconcile_material_progression(self.db)
        self.db.commit()
        self.assertGreater(changed, 0)
        self.assertEqual(arcana.id, arcana_id)
        self.assertEqual(arcana.rarity, "epic")
        self.assertEqual(arcana.name, old_arcana_name)
        self.assertEqual(arcana.required_level, 101)
        self.assertEqual(arcana.item_level, 167)
        self.assertEqual(customized.description, "Descrição personalizada pelo Admin.")
        self.assertEqual(name_conflict.name, new_rows["material_wood_1_025"]["name"])
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == guild.id,
            GuildInventoryItem.item_template_id == arcana_id,
        )), 23)

        self.assertEqual(_reconcile_material_progression(self.db), 0)
        self.assertEqual(self.db.get(ItemTemplate, customized_id).description, "Descrição personalizada pelo Admin.")

    def test_assignment_freezes_legacy_fallback_before_level_up_and_keeps_target_on_live_advance(self):
        guild = Guild(name="Coleta congelada", level=1)
        profession = MercenaryClass(
            name="Trabalhador", code="worker", description="", base_power=5,
            base_vitality=5, base_agility=5, base_intelligence=5, base_luck=5,
        )
        self.db.add_all([guild, profession])
        self.db.flush()
        worker = Mercenary(
            guild_id=guild.id, class_id=profession.id, name="Lina", level=1,
            power=5, vitality=5, agility=5, intelligence=5, luck=5,
        )
        raw = ItemTemplate(
            name="Madeira Bruta", description="", item_type="material", rarity="common",
            material_family="wood", item_level=1, level_band="1-20", required_level=1, tier=1,
        )
        self.db.add_all([worker, raw])
        self.db.flush()
        assignment = GatheringAssignment(
            guild_id=guild.id, mercenary_id=worker.id, resource_family="wood", node_code="forest",
            rng_seed=123, started_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            checkpoint_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.db.add(assignment)
        self.db.flush()

        first = advance_assignment(
            self.db, guild, assignment,
            now=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(first["stored"], 1)
        self.assertEqual(assignment.target_item_template_id, raw.id)
        advanced = ItemTemplate(
            name="Madeira Arcana", description="", item_type="material", rarity="epic",
            material_family="wood", item_level=101, level_band="101-130", required_level=101, tier=4,
        )
        self.db.add(advanced)
        guild.level = 200
        second = advance_assignment(
            self.db, guild, assignment,
            now=datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        )
        rows = list(self.db.scalars(select(GuildInventoryItem).where(GuildInventoryItem.guild_id == guild.id)))
        self.assertEqual(second["stored"], 1)
        self.assertEqual({row.item_template_id for row in rows}, {raw.id})
        self.assertEqual(assignment.target_item_template_id, raw.id)

    def test_content_migration_freezes_each_legacy_assignment_once(self):
        guild = Guild(name="Campanha antiga", level=7)
        profession = MercenaryClass(
            name="Trabalhador", code="worker", description="", base_power=5,
            base_vitality=5, base_agility=5, base_intelligence=5, base_luck=5,
        )
        self.db.add_all([guild, profession])
        self.db.flush()
        worker = Mercenary(
            guild_id=guild.id, class_id=profession.id, name="Lina", level=1,
            power=5, vitality=5, agility=5, intelligence=5, luck=5,
        )
        raw = ItemTemplate(
            name="Madeira Bruta migrada", description="", item_type="material", rarity="common",
            material_family="wood", item_level=6, level_band="1-20", required_level=1, tier=1,
        )
        self.db.add_all([worker, raw])
        self.db.flush()
        assignment = GatheringAssignment(
            guild_id=guild.id, mercenary_id=worker.id, resource_family="wood", node_code="forest",
            rng_seed=3, started_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            checkpoint_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.db.add(assignment)
        self.db.flush()

        self.assertEqual(freeze_legacy_assignment_targets(self.db), 1)
        self.assertEqual(assignment.target_item_template_id, raw.id)
        guild.level = 300
        self.assertEqual(freeze_legacy_assignment_targets(self.db), 0)
        self.assertEqual(assignment.target_item_template_id, raw.id)


class LotBMarketTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.guild = Guild(name="Mercado lote B", level=1)
        self.resources = GuildResources(guild=self.guild, gold=100)
        self.market_template = BuildingTemplate(
            name="Mercado lote B", description="", effect_type="market", base_upgrade_gold_cost=0,
            max_level=100,
        )
        self.db.add_all([self.guild, self.resources, self.market_template])
        self.db.flush()
        self.building = GuildBuilding(
            guild_id=self.guild.id, building_template_id=self.market_template.id, level=1,
        )
        self.item = ItemTemplate(
            name="Madeira de teste", description="", item_type="material", rarity="rare",
            item_level=7, level_band="1-20", required_level=1, tier=8,
            material_family="wood", base_sell_value=4,
        )
        self.db.add_all([self.building, self.item])
        self.db.flush()
        self.db.add(GuildInventoryItem(guild_id=self.guild.id, item_template_id=self.item.id, quantity=50))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_duration_uses_rarity_times_quantity_then_market_reduction_and_floor(self):
        expected = {"common": 10, "uncommon": 25, "rare": 60, "epic": 180, "legendary": 600, "mythic": 1200}
        for rarity, seconds in expected.items():
            self.assertEqual(_sale_duration_seconds(rarity, 1, 0), seconds)
            self.assertEqual(_sale_duration_seconds(rarity, 3, 0), seconds * 3)
            self.assertEqual(_sale_duration_seconds(rarity, 3, 50), seconds * 3 // 2)
        self.assertEqual(_sale_duration_seconds("common", 1, 99), 5)

        sale = start_material_sale(self.db, self.guild, str(self.item.id), "2")
        snapshot = sale.ends_at
        bonuses = get_market_bonuses(self.db, self.guild.id)
        self.assertEqual(
            int((sale.ends_at - sale.started_at).total_seconds()),
            _sale_duration_seconds("rare", 2, bonuses["time_reduction_percent"]),
        )
        self.item.tier = 1
        self.item.item_level = 350
        self.building.level = 50
        self.db.commit()
        self.db.refresh(sale)
        self.assertEqual(sale.ends_at, snapshot)

    def test_material_cancel_returns_exact_quantity_once_without_gold_or_sale_credit(self):
        initial_gold = self.resources.gold
        sale = start_material_sale(self.db, self.guild, str(self.item.id), "17")
        cancelled = cancel_market_sale(self.db, self.guild, sale.id)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(cancelled.cancelled_at is not None, True)
        quantity = self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.item.id,
        ))
        self.assertEqual(quantity, 50)
        self.assertEqual(self.resources.gold, initial_gold)
        with self.assertRaisesRegex(MarketError, "finalizada"):
            cancel_market_sale(self.db, self.guild, sale.id)
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.item.id,
        )), 50)

    def test_cancel_at_exact_deadline_is_rejected_and_collection_can_win(self):
        sale = start_material_sale(self.db, self.guild, str(self.item.id), "3")
        deadline = sale.ends_at.replace(tzinfo=timezone.utc) if sale.ends_at.tzinfo is None else sale.ends_at
        with self.assertRaisesRegex(MarketError, "prazo terminou"):
            cancel_market_sale(self.db, self.guild, sale.id, now=deadline)
        self.db.rollback()
        collected = collect_market_sale(self.db, self.guild, self.resources, sale.id, now=deadline)
        self.assertEqual(collected.status, "completed")
        self.assertEqual(self.resources.gold, 100 + sale.total_value)
        with self.assertRaisesRegex(MarketError, "finalizada"):
            cancel_market_sale(self.db, self.guild, sale.id, now=deadline)

    def test_full_warehouse_rejects_cancel_without_mutating_escrowed_sale(self):
        sale = start_material_sale(self.db, self.guild, str(self.item.id), "5")
        capacity = get_inventory_capacity(self.db, self.guild)
        inventory = self.db.scalar(select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.item.id,
        ))
        inventory.quantity = capacity
        self.db.commit()

        with self.assertRaisesRegex(MarketError, "Nao ha espaco suficiente"):
            cancel_market_sale(self.db, self.guild, sale.id)
        self.db.rollback()
        self.db.refresh(sale)
        self.assertEqual(sale.status, "in_progress")
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.item.id,
        )), capacity)
        self.assertEqual(self.resources.gold, 100)

    def test_equipment_cancel_returns_same_instance_and_allows_a_new_announcement(self):
        equipment_template = ItemTemplate(
            name="Espada de teste", description="", item_type="equipment", rarity="epic",
            item_level=80, level_band="51-100", required_level=51, tier=4,
            equipment_slot="main_hand", base_sell_value=40,
        )
        self.db.add(equipment_template)
        self.db.flush()
        instance = GuildItemInstance(
            guild_id=self.guild.id, item_template_id=equipment_template.id, equipment_slot="main_hand",
        )
        self.db.add(instance)
        self.db.commit()
        instance_id = instance.id

        sale = start_equipment_sale(self.db, self.guild, str(instance.id))
        equipment_bonuses = get_market_bonuses(self.db, self.guild.id)
        self.assertEqual(
            int((sale.ends_at - sale.started_at).total_seconds()),
            _sale_duration_seconds("epic", 1, equipment_bonuses["time_reduction_percent"]),
        )
        cancelled = cancel_market_sale(self.db, self.guild, sale.id)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertIsNone(cancelled.item_instance_id)
        self.assertEqual(self.db.get(GuildItemInstance, instance_id).id, instance_id)
        self.assertEqual(self.db.get(GuildItemInstance, instance_id).guild_id, self.guild.id)
        self.assertIsNone(self.db.get(GuildItemInstance, instance_id).equipped_to_mercenary_id)
        second_sale = start_equipment_sale(self.db, self.guild, str(instance_id))
        self.assertNotEqual(second_sale.id, sale.id)

    def test_guild_ownership_and_stale_competing_calls_cannot_duplicate_refund_or_gold(self):
        other_guild = Guild(name="Outra campanha", level=1)
        other_resources = GuildResources(guild=other_guild, gold=50)
        self.db.add_all([other_guild, other_resources])
        self.db.flush()
        sale = start_material_sale(self.db, self.guild, str(self.item.id), "7")
        deadline = sale.ends_at.replace(tzinfo=timezone.utc) if sale.ends_at.tzinfo is None else sale.ends_at
        with self.assertRaisesRegex(MarketError, "Venda nao encontrada"):
            cancel_market_sale(self.db, other_guild, sale.id)
        self.db.rollback()
        before_gold = self.resources.gold

        competing_session = Session(self.engine, autoflush=False, expire_on_commit=False)
        try:
            stale_sale = competing_session.get(MarketSale, sale.id)
            self.assertEqual(stale_sale.status, "in_progress")
            cancel_market_sale(self.db, self.guild, sale.id, now=deadline - timedelta(microseconds=1))
            with self.assertRaisesRegex(MarketError, "cancelada"):
                collect_market_sale(
                    competing_session, competing_session.get(Guild, self.guild.id),
                    competing_session.get(GuildResources, self.resources.id), sale.id, now=deadline,
                )
            competing_session.rollback()
            with self.assertRaises(MarketError):
                cancel_market_sale(competing_session, competing_session.get(Guild, self.guild.id), sale.id)
            competing_session.rollback()
        finally:
            competing_session.close()

        self.assertEqual(self.resources.gold, before_gold)
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.item.id,
        )), 50)
        self.assertEqual(self.db.get(MarketSale, sale.id).status, "cancelled")


if __name__ == "__main__":
    unittest.main()
