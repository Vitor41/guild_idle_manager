import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.balance.audit_fresh_save_economy import affordability


class FreshSaveEconomyAuditTests(unittest.TestCase):
    def test_affordability_tracks_gold_and_material_shortfalls(self):
        result = affordability(
            {"gold": 30, "wood": 0, "ore": 0, "crystals": 0},
            {"gold": 180, "wood": 20, "ore": 20, "crystals": 0},
        )

        self.assertEqual(result, {
            "affordable": False,
            "shortfalls": {"gold": 150, "wood": 20, "ore": 20, "crystals": 0},
            "balance_after_if_paid": {"gold": -150, "wood": -20, "ore": -20, "crystals": 0},
        })

    def test_affordability_accepts_exact_balance(self):
        result = affordability(
            {"gold": 180, "wood": 20, "ore": 20, "crystals": 0},
            {"gold": 180, "wood": 20, "ore": 20, "crystals": 0},
        )

        self.assertTrue(result["affordable"])
        self.assertEqual(result["shortfalls"], {"gold": 0, "wood": 0, "ore": 0, "crystals": 0})
        self.assertEqual(result["balance_after_if_paid"], {"gold": 0, "wood": 0, "ore": 0, "crystals": 0})


if __name__ == "__main__":
    unittest.main()
