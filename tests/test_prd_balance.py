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
from app.services.building_service import get_upgrade_cost
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

    def test_housing_scales_to_twentieth_slot_at_level_100(self):
        self.assertEqual([housing_capacity(level) for level in (0, 1, 2, 3, 5, 10)], [0, 1, 1, 2, 3, 4])
        self.assertEqual(housing_capacity(50), 11)
        self.assertEqual(housing_capacity(55), 12)
        self.assertEqual(housing_capacity(95), 19)
        self.assertEqual(housing_capacity(99), 19)
        self.assertEqual(housing_capacity(100), 20)
        self.assertEqual(housing_capacity(BUILDING_MAX_LEVEL), 20)
        capacities = [housing_capacity(level) for level in range(BUILDING_MAX_LEVEL + 1)]
        self.assertEqual(capacities, sorted(capacities))
        self.assertEqual([level for level in range(1, 101) if housing_capacity(level) == 20], [100])

    def test_housing_upgrade_cost_preserves_first_level_exception_and_existing_curve(self):
        def quote_for_next_level(target_level):
            return get_upgrade_cost(SimpleNamespace(
                level=target_level - 1,
                building_template=SimpleNamespace(
                    effect_type="housing", base_upgrade_gold_cost=100,
                    base_upgrade_wood_cost=20, base_upgrade_ore_cost=0,
                    base_upgrade_crystals_cost=0,
                ),
            ))

        first = get_upgrade_cost(SimpleNamespace(
            level=0,
            building_template=SimpleNamespace(
                effect_type="housing", base_upgrade_gold_cost=100,
                base_upgrade_wood_cost=20, base_upgrade_ore_cost=0,
                base_upgrade_crystals_cost=0,
            ),
        ))
        level_two = quote_for_next_level(2)
        level_fifty = quote_for_next_level(50)
        level_fifty_one = quote_for_next_level(51)
        self.assertEqual(first, {"gold": 10, "wood": 0, "ore": 0, "crystals": 0})
        self.assertEqual((level_two["gold"], level_two["wood"]), (200, 40))
        self.assertEqual((level_fifty["gold"], level_fifty["wood"]), (9_250, 1_850))
        self.assertEqual((level_fifty_one["gold"], level_fifty_one["wood"]), (9_300, 1_860))

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
