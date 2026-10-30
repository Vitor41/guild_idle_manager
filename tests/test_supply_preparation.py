import json
import unittest

from app.services.supply_preparation_service import quote_supply, supply_bonus_from_snapshot


class SupplyPreparationQuoteTests(unittest.TestCase):
    def test_rank_cost_never_exceeds_incremental_or_victory_value(self):
        caps = {"E": 1, "D": 2, "C": 3, "B": 4, "A": 5, "S": 6}
        for rank, cap in caps.items():
            with self.subTest(rank=rank):
                quote = quote_supply(rank=rank, success_gold=1000, expected_drop_sale=200,
                                     available_gold=100, applied_bonus_pp=5)
                self.assertTrue(quote["available"])
                self.assertLessEqual(quote["cost_gold"], cap)
                self.assertLessEqual(quote["cost_gold"], quote["incremental_ev_gold"])
                self.assertLessEqual(quote["cost_gold"], quote["gold_only_incremental_ev_gold"])
                self.assertLessEqual(quote["cost_gold"], quote["victory_value_gold"])

    def test_multiplier_and_effective_drop_sale_value_increase_expected_value(self):
        one = quote_supply(rank="S", success_gold=100, expected_drop_sale=20,
                           multiplier=1, available_gold=100)
        three = quote_supply(rank="S", success_gold=300, expected_drop_sale=60,
                             multiplier=3, available_gold=100)
        two = quote_supply(rank="S", success_gold=200, expected_drop_sale=40,
                           multiplier=2, available_gold=100)
        self.assertEqual(one["cost_gold"], 5)
        self.assertEqual(two["cost_gold"], 10)
        self.assertEqual(three["cost_gold"], 15)
        self.assertLessEqual(two["cost_gold"], two["gold_only_incremental_ev_gold"])
        self.assertEqual(three["incremental_ev_gold"], 18)

    def test_bonus_is_snapshot_driven_and_backward_compatible(self):
        self.assertEqual(supply_bonus_from_snapshot(None), 0)
        self.assertEqual(supply_bonus_from_snapshot("{}"), 0)
        self.assertEqual(supply_bonus_from_snapshot("not-json"), 0)
        snapshot = json.dumps({"schema": 1, "supply": "regional_group_supply", "chance_bonus_pp": 2})
        self.assertEqual(supply_bonus_from_snapshot(snapshot), 2)

    def test_no_economic_ev_or_insufficient_balance_disables_supply(self):
        no_return = quote_supply(rank="E", success_gold=19, available_gold=100)
        poor_guild = quote_supply(rank="S", success_gold=1000, available_gold=0)
        self.assertFalse(no_return["available"])
        self.assertIn("retorno esperado", no_return["reason"])
        self.assertFalse(poor_guild["available"])
        self.assertIn("Saldo insuficiente", poor_guild["reason"])

    def test_bonus_respects_existing_95_percent_ceiling(self):
        near_cap = quote_supply(rank="S", success_gold=2_000, available_gold=100,
                                applied_bonus_pp=min(5, 95 - 93))
        at_cap = quote_supply(rank="S", success_gold=2_000, available_gold=100,
                              applied_bonus_pp=min(5, 95 - 95))
        self.assertEqual(near_cap["chance_bonus_pp"], 2)
        self.assertEqual(near_cap["cost_gold"], 6)
        self.assertEqual(at_cap["chance_bonus_pp"], 0)
        self.assertFalse(at_cap["available"])


if __name__ == "__main__":
    unittest.main()
