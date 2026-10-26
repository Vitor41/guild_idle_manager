import unittest

from app.services.prd3_dungeon_balance_service import (
    BOSS_TARGETS,
    DUNGEON_TARGETS,
    LEVEL_BANDS,
    _base_chance,
    _desired_rarity,
    _drop_chance,
    _even_selection,
)


class Prd3DungeonBalanceTests(unittest.TestCase):
    def test_catalog_targets_follow_healthy_ranges(self):
        self.assertEqual(len(LEVEL_BANDS), 8)
        self.assertEqual(sum(DUNGEON_TARGETS), 162)
        self.assertEqual(sum(BOSS_TARGETS), 43)
        self.assertTrue(all(8 <= amount <= 35 for amount in DUNGEON_TARGETS))
        self.assertTrue(all(1 <= amount <= 10 for amount in BOSS_TARGETS))

    def test_even_selection_preserves_catalog_extremes(self):
        values = list(range(100))
        selected = _even_selection(values, 10)
        self.assertEqual(len(selected), 10)
        self.assertEqual((selected[0], selected[-1]), (0, 99))
        self.assertEqual(selected, sorted(selected))

    def test_bosses_are_riskier_than_equivalent_dungeons(self):
        for band_index in range(len(LEVEL_BANDS)):
            self.assertLess(
                _base_chance("boss", "heroic", band_index),
                _base_chance("dungeon", "heroic", band_index),
            )

    def test_bosses_have_better_high_rarity_drop_chance(self):
        for band_index in range(len(LEVEL_BANDS)):
            for rarity in ("rare", "epic", "legendary", "mythic"):
                self.assertGreater(
                    _drop_chance("boss", rarity, band_index),
                    _drop_chance("dungeon", rarity, band_index),
                )

    def test_rarity_progresses_toward_endgame(self):
        early = {_desired_rarity("boss", 0, index) for index in range(6)}
        endgame = {_desired_rarity("boss", 7, index) for index in range(6)}
        self.assertNotIn("mythic", early)
        self.assertIn("mythic", endgame)


if __name__ == "__main__":
    unittest.main()
