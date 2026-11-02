import unittest

from app.services.offline_progress_service import calculate_offline_material_rewards
from app.services.prd2_balance_service import (
    equipment_drop_chance,
    gathering_xp_for_level,
)


class OfflineMaterialRewardTests(unittest.TestCase):
    def test_passive_offline_reward_excludes_gathering_materials(self):
        one_hour = calculate_offline_material_rewards(20, 3600, 8 * 3600, 2)
        three_hours = calculate_offline_material_rewards(20, 3 * 3600, 8 * 3600, 2)
        eight_hours = calculate_offline_material_rewards(20, 8 * 3600, 8 * 3600, 2)
        self.assertEqual((one_hour["wood_base"], one_hour["ore_base"]), (0, 0))
        self.assertEqual((three_hours["wood_base"], three_hours["ore_base"]), (0, 0))
        self.assertEqual((eight_hours["wood_base"], eight_hours["ore_base"]), (0, 0))
        self.assertEqual(one_hour["warehouse_bonus"], 0)
        self.assertEqual(eight_hours["crystals"], 1)

    def test_crystal_only_at_effective_cap(self):
        self.assertEqual(calculate_offline_material_rewards(20, 7 * 3600, 8 * 3600)["crystals"], 0)
        self.assertEqual(calculate_offline_material_rewards(20, 8 * 3600, 8 * 3600)["crystals"], 1)


class Prd2MissionBalanceTests(unittest.TestCase):
    def test_gathering_xp_grows_between_levels_one_and_nine(self):
        values = [gathering_xp_for_level(level) for level in range(1, 10)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual((values[0], values[4], values[8]), (65, 75, 85))

    def test_equipment_drop_hierarchy(self):
        rarity_order = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
        for content_type in ("mission", "gathering", "dungeon", "boss"):
            chances = [equipment_drop_chance(content_type, rarity) for rarity in rarity_order]
            self.assertEqual(chances, sorted(chances, reverse=True))
        self.assertGreater(equipment_drop_chance("mission", "common"), equipment_drop_chance("gathering", "common"))
        self.assertGreater(equipment_drop_chance("boss", "epic"), equipment_drop_chance("dungeon", "epic"))


if __name__ == "__main__":
    unittest.main()
