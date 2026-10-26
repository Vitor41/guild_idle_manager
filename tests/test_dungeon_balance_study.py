import unittest

from app.services.dungeon_balance_study_service import (
    _current_equipment_probabilities,
    _proposed_equipment_probabilities,
)


class DungeonBossBalanceStudyTests(unittest.TestCase):
    def test_recommended_endgame_boss_caps_completion_and_mythic(self):
        record = {
            "type": "boss", "band_index": 7, "base_chance": 33,
            "power": 5000, "roles": 5,
            "drops": [{"type": "equipment", "rarity": "mythic", "base_chance": 3}],
        }
        result = _proposed_equipment_probabilities(record, "Máximo")
        self.assertAlmostEqual(result["completion"], 0.35)
        self.assertLess(result["any_equipment"], 0.06)
        self.assertLess(result["mythic"], 0.002)

    def test_current_additive_bonus_makes_mythic_too_frequent(self):
        record = {
            "type": "boss", "band_index": 7, "base_chance": 33,
            "power": 5000, "roles": 5,
            "drops": [{"type": "equipment", "rarity": "mythic", "base_chance": 3}],
        }
        result = _current_equipment_probabilities(record, "Máximo")
        self.assertAlmostEqual(result["completion"], 0.95)
        self.assertGreater(result["mythic"], 0.5)


if __name__ == "__main__":
    unittest.main()
