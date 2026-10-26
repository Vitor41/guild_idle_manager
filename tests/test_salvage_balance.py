import unittest
from types import SimpleNamespace

from app.core.game_balance import MARKET_RARITY_SECONDS
from app.services.salvage_service import (
    SALVAGE_SLOT_RULES,
    salvage_duration_seconds,
    salvage_material_family,
    salvage_slot_count,
)


class SalvageBalanceTests(unittest.TestCase):
    def test_slots_unlock_at_expected_blacksmith_levels(self):
        self.assertEqual(salvage_slot_count(0), 0)
        self.assertEqual(salvage_slot_count(1), 1)
        self.assertEqual(salvage_slot_count(24), 1)
        self.assertEqual(salvage_slot_count(25), 2)
        self.assertEqual(salvage_slot_count(49), 2)
        self.assertEqual(salvage_slot_count(50), 3)
        self.assertEqual([rule["unit_cost"] for rule in SALVAGE_SLOT_RULES.values()], [50, 150, 300])

    def test_duration_reuses_market_rarity_time_and_scales_linearly(self):
        for rarity, base_seconds in MARKET_RARITY_SECONDS.items():
            self.assertEqual(salvage_duration_seconds(rarity, 3, 4), base_seconds * 3 * 4)

    def test_composition_comes_from_equipment_group(self):
        cases = {
            "bow": "wood", "staff": "wood", "heavy_armor": "ore",
            "light_armor": "leather", "robe": "cloth", "ring": "gem",
        }
        for icon_group, expected_family in cases.items():
            item = SimpleNamespace(icon_group=icon_group, equipment_slot="main_hand")
            self.assertEqual(salvage_material_family(item), expected_family)

    def test_unknown_group_has_safe_slot_fallback(self):
        item = SimpleNamespace(icon_group="future_weapon", equipment_slot="main_hand")
        self.assertEqual(salvage_material_family(item), "ore")


if __name__ == "__main__":
    unittest.main()
