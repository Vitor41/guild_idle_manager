import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import BuildingTemplate, Guild, GuildBuilding, GuildInventoryItem, GuildItemInstance, ItemTemplate, MarketSale
from app.services.market_service import MarketError, get_market_page_context, start_equipment_sale, start_material_sale


class MarketMaxQuantityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.guild = Guild(name="Mercado QA", level=1)
        self.db.add(self.guild)
        self.db.flush()
        self.market_template = BuildingTemplate(name="Mercado QA", description="", effect_type="market",
                                                base_upgrade_gold_cost=0, max_level=100)
        self.db.add(self.market_template)
        self.db.flush()
        self.db.add(GuildBuilding(guild_id=self.guild.id, building_template_id=self.market_template.id, level=1))
        self.item = ItemTemplate(name="Erva para venda", description="", item_type="material", rarity="common",
                                 item_level=1, level_band="1-20", tier=1, material_family="herb", base_sell_value=3)
        self.db.add(self.item)
        self.db.flush()
        self.db.add(GuildInventoryItem(guild_id=self.guild.id, item_template_id=self.item.id, quantity=80))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_max_is_stock_and_quota_bounded_and_zero_without_a_listing_slot(self):
        context = get_market_page_context(self.db, self.guild)
        self.assertEqual(context["inventory_items"][0].market_max_quantity, 25)
        self.assertEqual(context["material_sale_quota"]["remaining"], 25)

        now = datetime.now(timezone.utc)
        self.db.add(MarketSale(guild_id=self.guild.id, item_template_id=self.item.id, quantity=1,
                               unit_value=3, total_value=3, status="in_progress",
                               started_at=now, ends_at=now + timedelta(hours=1)))
        self.db.commit()
        context = get_market_page_context(self.db, self.guild)
        self.assertEqual(context["inventory_items"][0].market_max_quantity, 0)

    def test_server_revalidates_quantity_against_remaining_quota(self):
        with self.assertRaisesRegex(MarketError, "Limite de materiais"):
            start_material_sale(self.db, self.guild, str(self.item.id), "26", commit=False)
        inventory = self.db.scalar(select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == self.item.id,
        ))
        self.assertEqual(inventory.quantity, 80)

    def test_equipment_remains_one_unit_per_instance_and_cannot_be_listed_twice(self):
        self.db.query(GuildBuilding).filter_by(
            guild_id=self.guild.id, building_template_id=self.market_template.id,
        ).one().level = 6
        equipment = ItemTemplate(
            name="Espada única", description="", item_type="equipment", rarity="rare",
            item_level=1, level_band="1-20", tier=1, equipment_slot="main_hand", base_sell_value=10,
        )
        self.db.add(equipment)
        self.db.flush()
        instance = GuildItemInstance(
            guild_id=self.guild.id, item_template_id=equipment.id, equipment_slot="main_hand",
        )
        self.db.add(instance)
        self.db.commit()

        sale = start_equipment_sale(self.db, self.guild, str(instance.id))
        self.assertEqual(sale.quantity, 1)
        with self.assertRaisesRegex(MarketError, "indisponivel"):
            start_equipment_sale(self.db, self.guild, str(instance.id))
