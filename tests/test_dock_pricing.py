import unittest
from datetime import datetime, timedelta, timezone

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.models import (
    BuildingTemplate,
    DockOffer,
    DockRotation,
    DockRotationMerchant,
    Guild,
    GuildBuilding,
    GuildInventoryItem,
    GuildResources,
    ItemTemplate,
    MerchantOfferTemplate,
    MerchantTemplate,
)
from app.services.building_balance_service import market_values
from app.services.dock_service import buy_dock_offer, create_dock_rotation, get_docks_context
from app.services.economy_pricing_service import (
    dock_no_arbitrage_price_floor,
    effective_dock_unit_price,
    market_sale_unit_value,
)


class DockPricingTests(unittest.TestCase):
    def setUp(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(bind=get_engine())

    def tearDown(self):
        configure_database("sqlite:///:memory:")

    def _guild(self, db, gold=3000):
        guild = Guild(name="Guilda QA", level=1, xp=0, reputation=0)
        db.add(guild)
        db.flush()
        resources = GuildResources(guild_id=guild.id, gold=gold, wood=0, ore=0, crystals=0)
        db.add(resources)
        db.flush()
        return guild, resources

    def _material(self, db, *, sell_value=1238):
        item = ItemTemplate(
            name="Minério de teste", description="Item para teste de margem.", item_type="material",
            rarity="common", item_level=40, level_band="21-50", tier=8,
            base_sell_value=sell_value, material_family="ore", is_active=True,
        )
        db.add(item)
        db.flush()
        return item

    def test_price_floor_covers_market_levels_and_admin_configured_low_price(self):
        item_value = 1238
        configured_price = 787  # Reproduces the underpriced seeded offer.
        safe_price = effective_dock_unit_price(configured_price, item_value)

        self.assertEqual(market_values(1)["value_bonus_percent"], 0)
        self.assertEqual(market_values(100)["value_bonus_percent"], 30)
        self.assertEqual(safe_price, dock_no_arbitrage_price_floor(item_value))
        self.assertEqual(safe_price, 1610)
        self.assertLess(market_sale_unit_value(item_value, market_values(1)["value_bonus_percent"]), safe_price)
        self.assertLess(market_sale_unit_value(item_value, market_values(100)["value_bonus_percent"]), safe_price)
        self.assertEqual(effective_dock_unit_price(2000, item_value), 2000)

    def test_new_rotation_applies_floor_to_seeded_or_future_admin_offer(self):
        with SessionLocal() as db:
            guild, _resources = self._guild(db)
            item = self._material(db)
            merchant = MerchantTemplate(
                slug="merchant-floor-test", name="Mercante de teste", description="Teste.",
                merchant_type="ore", min_dock_level=1, rotation_weight=100, is_active=True,
            )
            db.add(merchant)
            db.flush()
            db.add(MerchantOfferTemplate(
                merchant_template_id=merchant.id, item_template_id=item.id, base_price=787,
                min_stock=3, max_stock=3, min_dock_level=8, weight=100, is_active=True,
            ))
            db.commit()

            rotation = create_dock_rotation(db, guild, dock_level=40)
            offers = [offer for merchant_row in rotation.merchants for offer in merchant_row.offers]

            self.assertEqual(len(offers), 1)
            self.assertEqual(offers[0].unit_price, 1610)
            self.assertEqual(offers[0].initial_stock, 3)

    def test_purchase_reprices_legacy_open_rotation_before_charging(self):
        with SessionLocal() as db:
            guild, resources = self._guild(db)
            item = self._material(db)
            docks_template = BuildingTemplate(
                name="Docas QA", description="Teste.", effect_type="docks",
                base_upgrade_gold_cost=100, base_upgrade_wood_cost=0, base_upgrade_ore_cost=0,
                base_upgrade_crystals_cost=0, max_level=100, required_guild_level=1, is_active=True,
            )
            merchant = MerchantTemplate(
                slug="merchant-legacy-test", name="Mercante legado", description="Teste.",
                merchant_type="ore", min_dock_level=1, rotation_weight=100, is_active=True,
            )
            db.add_all([docks_template, merchant])
            db.flush()
            db.add(GuildBuilding(guild_id=guild.id, building_template_id=docks_template.id, level=1))
            rotation = DockRotation(
                guild_id=guild.id, status="active", starts_at=datetime.now(timezone.utc),
                ends_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            db.add(rotation)
            db.flush()
            rotation_merchant = DockRotationMerchant(dock_rotation_id=rotation.id, merchant_template_id=merchant.id, slot=1)
            db.add(rotation_merchant)
            db.flush()
            offer = DockOffer(
                dock_rotation_merchant_id=rotation_merchant.id, item_template_id=item.id,
                unit_price=787, initial_stock=1, remaining_stock=1,
            )
            db.add(offer)
            db.commit()
            offer_id = offer.id
            guild_id = guild.id
            resources_id = resources.id

            dock_context = get_docks_context(db, guild)
            surfaced_offer = dock_context["rotation"].merchants[0].offers[0]
            self.assertEqual(surfaced_offer.unit_price, 1610)
            # Simulate an old or administrator-edited stale active row to verify
            # the transactional purchase path also rechecks the price.
            surfaced_offer.unit_price = 787
            db.commit()

            buy_dock_offer(db, guild, resources, offer_id, 1)

            self.assertEqual(resources.gold, 3000 - 1610)
            self.assertEqual(offer.unit_price, 1610)
            self.assertEqual(offer.remaining_stock, 0)
            self.assertEqual(db.query(GuildInventoryItem).filter_by(guild_id=guild_id, item_template_id=item.id).one().quantity, 1)
            self.assertEqual(db.get(GuildResources, resources_id).gold, 1390)


if __name__ == "__main__":
    unittest.main()
