import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import Guild, GuildInventoryItem, ItemTemplate
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.supply_preparation_service import regional_kit_quote
from app.services.workshop_service import (
    HERBS_PER_KIT, MEAT_PER_KIT, craft_supply_kit, ensure_supply_kit, get_supply_workshop_context,
)


class WorkshopServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.guild = Guild(name="Oficina QA", level=1)
        self.db.add(self.guild)
        self.db.flush()
        self.meat = ItemTemplate(name="Carne", description="", item_type="material", rarity="common",
                                 material_family="meat", item_level=1, level_band="1-20", tier=1)
        self.herb = ItemTemplate(name="Erva", description="", item_type="material", rarity="common",
                                 material_family="herb", item_level=1, level_band="1-20", tier=1)
        self.db.add_all([self.meat, self.herb])
        self.kit = ensure_supply_kit(self.db)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _stock(self, item, quantity):
        self.db.add(GuildInventoryItem(guild_id=self.guild.id, item_template_id=item.id, quantity=quantity))
        self.db.flush()

    def test_recipe_consumes_exact_inputs_and_produces_one_kit(self):
        self._stock(self.meat, 6)
        self._stock(self.herb, 4)
        self.assertTrue(get_supply_workshop_context(self.db, self.guild)["can_craft"])

        job = craft_supply_kit(self.db, self.guild, 1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertEqual(job.kit_quantity, 1)
        self.assertEqual(job.ends_at - job.started_at, timedelta(seconds=5))
        self.assertEqual(get_supply_workshop_context(self.db, self.guild, now=job.ends_at - timedelta(seconds=1))["stock"]["kit"], 0)
        completed = get_supply_workshop_context(self.db, self.guild, now=job.ends_at)
        self.assertEqual(completed["stock"]["kit"], 1)
        self.assertEqual(get_supply_workshop_context(self.db, self.guild, now=job.ends_at + timedelta(seconds=1))["stock"]["kit"], 1)
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.meat.id,
        )), 3)
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.herb.id,
        )), 2)

    def test_regional_kit_quote_uses_rank_cost_and_never_consumes_at_chance_cap(self):
        self._stock(self.kit, 3)
        quote = regional_kit_quote(self.db, self.guild.id, "C", 80)
        self.assertTrue(quote["available"])
        self.assertEqual(quote["cost_kits"], 3)
        self.assertEqual(quote["final_chance"], 85)
        capped = regional_kit_quote(self.db, self.guild.id, "E", 95)
        self.assertFalse(capped["available"])
        self.assertIn("nenhum kit será consumido", capped["reason"])
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.kit.id,
        )), 3)

    def test_incomplete_recipe_does_not_consume_materials(self):
        self._stock(self.meat, 3)
        with self.assertRaisesRegex(ValueError, "Faltam Ervas"):
            craft_supply_kit(self.db, self.guild)
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.meat.id,
        )), 3)

    def test_recipe_sums_and_consumes_materials_across_tiers(self):
        higher_tier_meat = ItemTemplate(
            name="Carne de tier superior", description="", item_type="material", rarity="common",
            material_family="meat", item_level=1, level_band="1-20", tier=2,
        )
        self.db.add(higher_tier_meat)
        self.db.flush()
        self._stock(self.meat, 2)
        self._stock(higher_tier_meat, 1)
        self._stock(self.herb, 2)
        self.assertTrue(get_supply_workshop_context(self.db, self.guild)["can_craft"])

        job = craft_supply_kit(self.db, self.guild, 1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(job.kit_quantity, 1)
        self.assertEqual(get_supply_workshop_context(self.db, self.guild, now=job.ends_at)["stock"]["kit"], 1)

        self.assertEqual(int(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.meat.id,
        )) or 0), 0)
        self.assertEqual(int(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == higher_tier_meat.id,
        )) or 0), 0)
        self.assertEqual(int(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.herb.id,
        )) or 0), 0)

    def test_insufficient_split_stack_recipe_consumes_nothing(self):
        higher_tier_meat = ItemTemplate(
            name="Carne de tier superior", description="", item_type="material", rarity="common",
            material_family="meat", item_level=1, level_band="1-20", tier=2,
        )
        self.db.add(higher_tier_meat)
        self.db.flush()
        self._stock(self.meat, 2)
        self._stock(higher_tier_meat, 1)
        self._stock(self.herb, 1)

        with self.assertRaisesRegex(ValueError, "Faltam Ervas"):
            craft_supply_kit(self.db, self.guild)

        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.meat.id,
        )), 2)
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == higher_tier_meat.id,
        )), 1)
        self.assertEqual(self.db.scalar(select(GuildInventoryItem.quantity).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.herb.id,
        )), 1)

    def test_batch_debits_once_reserves_output_and_blocks_second_job(self):
        self._stock(self.meat, 9)
        self._stock(self.herb, 6)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        job = craft_supply_kit(self.db, self.guild, 3, now=now)
        self.assertEqual((job.kit_quantity, job.ends_at - job.started_at), (3, timedelta(seconds=15)))
        with self.assertRaisesRegex(ValueError, "produção em andamento"):
            craft_supply_kit(self.db, self.guild, 1, now=now)
        self.assertEqual(get_supply_workshop_context(self.db, self.guild, now=now)["max_batch"], 0)
        self.assertEqual(get_inventory_usage(self.db, self.guild.id), 3)
        context = get_supply_workshop_context(self.db, self.guild, now=job.ends_at)
        self.assertEqual(context["stock"]["kit"], 3)
        self.assertEqual(get_inventory_usage(self.db, self.guild.id), 3)

    def test_full_warehouse_allows_recipe_that_reduces_usage_without_exceeding_capacity(self):
        filler = ItemTemplate(
            name="Material de preenchimento", description="", item_type="material", rarity="common",
            material_family="wood", item_level=1, level_band="1-20", tier=1,
        )
        self.db.add(filler)
        self.db.flush()
        self._stock(self.meat, 3)
        self._stock(self.herb, 2)
        capacity = get_inventory_capacity(self.db, self.guild)
        self._stock(filler, capacity - MEAT_PER_KIT - HERBS_PER_KIT)
        self.assertEqual(get_inventory_usage(self.db, self.guild.id), capacity)
        self.assertTrue(get_supply_workshop_context(self.db, self.guild)["can_craft"])

        job = craft_supply_kit(self.db, self.guild, 1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertEqual(get_inventory_usage(self.db, self.guild.id), capacity - 4)
        self.assertLessEqual(get_inventory_usage(self.db, self.guild.id), capacity)
        get_supply_workshop_context(self.db, self.guild, now=job.ends_at)
        self.assertEqual(get_inventory_usage(self.db, self.guild.id), capacity - 4)
