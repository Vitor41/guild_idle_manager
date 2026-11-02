import unittest

from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import ItemTemplate
from app.seeds.massive_content import PACK_KEY, run_massive_content_seed
from app.services.economy_pricing_service import (
    EQUIPMENT_RARITY_PREMIUM_PERCENT,
    equipment_base_sell_value,
    market_sale_unit_value,
)


class EquipmentPricingTests(unittest.TestCase):
    def test_common_base_varies_by_slot_and_rarity_premiums_are_strict(self):
        self.assertNotEqual(equipment_base_sell_value("main_hand", "common"),
                            equipment_base_sell_value("earring", "common"))
        rarities = list(EQUIPMENT_RARITY_PREMIUM_PERCENT)
        for slot in ("main_hand", "shield", "chest", "helmet", "gloves", "boots", "ring", "necklace", "earring", "belt"):
            values = [equipment_base_sell_value(slot, rarity) for rarity in rarities]
            self.assertTrue(all(left < right for left, right in zip(values, values[1:])), (slot, values))
            for market_bonus in (0, 30):
                effective = [market_sale_unit_value(value, market_bonus) for value in values]
                self.assertTrue(all(left < right for left, right in zip(effective, effective[1:])), (slot, market_bonus, effective))

    def test_catalog_upgrade_reprices_legacy_values_but_preserves_admin_price(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine, autoflush=False, expire_on_commit=False) as db:
                admin_price = ItemTemplate(
                    slug="equipamento_99999", name="Equipamento ajustado pelo admin", description="",
                    item_type="equipment", rarity="common", item_level=1, level_band="1-20", tier=1,
                    content_pack=PACK_KEY, equipment_slot="main_hand", base_sell_value=777,
                )
                generated_legacy_price = ItemTemplate(
                    slug="equipamento_99998", name="Equipamento gerado legado", description="",
                    item_type="equipment", rarity="common", item_level=1, level_band="1-20", tier=1,
                    content_pack=PACK_KEY, equipment_slot="earring", base_sell_value=9,
                )
                db.add_all([admin_price, generated_legacy_price])
                db.flush()

                run_massive_content_seed(db)

                self.assertEqual(admin_price.base_sell_value, 777)
                self.assertEqual(generated_legacy_price.base_sell_value, equipment_base_sell_value("earring", "common"))
        finally:
            engine.dispose()
