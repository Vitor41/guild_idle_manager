import unittest
from types import SimpleNamespace

from app.services.building_balance_service import (
    BUILDING_MAX_LEVEL,
    blacksmith_drop_bonus,
    building_cost_factor,
    housing_capacity,
    market_values,
    tavern_values,
    training_xp_bonus,
    warehouse_material_bonus,
)
from app.services.profession_service import get_profession_drop_bonus_percentage_points
from app.services.mission_service import LONG_IDLE_CONFIGS, can_start_long_idle_mission


class PrdBuildingBalanceTests(unittest.TestCase):
    def test_tavern_milestones(self):
        expected = {
            1: (90, 10, 0), 5: (88, 12, 2), 10: (86, 14, 4),
            25: (80, 20, 10), 50: (70, 30, 20),
        }
        for level, values in expected.items():
            result = tavern_values(level)
            self.assertEqual(values, (
                result["common_final"], result["uncommon_final"], result["hire_discount_percent"],
            ))

    def test_housing_early_levels_and_cap(self):
        self.assertEqual([housing_capacity(level) for level in (1, 2, 3)], [1, 2, 3])
        self.assertEqual(housing_capacity(5), 5)
        self.assertEqual(housing_capacity(50), 20)
        self.assertEqual(housing_capacity(BUILDING_MAX_LEVEL), 30)

    def test_warehouse_fixed_bonus(self):
        self.assertEqual(warehouse_material_bonus(1), 1)
        self.assertEqual(warehouse_material_bonus(25), 10)
        self.assertEqual(warehouse_material_bonus(50), 20)
        self.assertEqual(warehouse_material_bonus(100), 30)

    def test_maximum_building_benefits(self):
        self.assertEqual(training_xp_bonus(50), 50)
        self.assertEqual(blacksmith_drop_bonus(50), 25)
        self.assertEqual(market_values(50)["slots"], 10)
        self.assertEqual(market_values(100)["slots"], 20)
        self.assertGreater(building_cost_factor(50), building_cost_factor(25))
        existing_total = sum(building_cost_factor(level) for level in range(1, 51))
        extension_total = sum(building_cost_factor(level) for level in range(51, 101))
        self.assertLess(extension_total / existing_total, 3)


class PrdProfessionTests(unittest.TestCase):
    def test_matching_profession_adds_percentage_points(self):
        profession = SimpleNamespace(code="woodcutter", bonus_percent=15)
        mercenary = SimpleNamespace(profession=profession)
        self.assertEqual(get_profession_drop_bonus_percentage_points([mercenary], "woodcutter"), 15)
        self.assertEqual(min(100, 85 + get_profession_drop_bonus_percentage_points([mercenary], "woodcutter")), 100)
        self.assertEqual(40 + get_profession_drop_bonus_percentage_points([mercenary], "woodcutter"), 55)

    def test_wrong_profession_does_not_apply(self):
        mercenary = SimpleNamespace(profession=SimpleNamespace(code="miner", bonus_percent=15))
        self.assertEqual(get_profession_drop_bonus_percentage_points([mercenary], "woodcutter"), 0)


class PrdLongIdleMissionTests(unittest.TestCase):
    def test_long_idle_duration_and_chance_rules(self):
        self.assertEqual([(hours, chance) for hours, chance, _ in LONG_IDLE_CONFIGS], [(1, 75), (3, 70), (8, 60)])

    def test_only_three_long_idle_missions_can_run(self):
        self.assertTrue(can_start_long_idle_mission(0))
        self.assertTrue(can_start_long_idle_mission(2))
        self.assertFalse(can_start_long_idle_mission(3))
        self.assertFalse(can_start_long_idle_mission(4))


if __name__ == "__main__":
    unittest.main()
