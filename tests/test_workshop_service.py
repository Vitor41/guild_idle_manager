import unittest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import Guild, GuildInventoryItem, ItemTemplate
from app.services.supply_preparation_service import regional_kit_quote
from app.services.workshop_service import craft_supply_kit, ensure_supply_kit, get_supply_workshop_context


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

        resulting_kit_stock = craft_supply_kit(self.db, self.guild)

        self.assertEqual(resulting_kit_stock, 1)
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
