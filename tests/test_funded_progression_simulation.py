import unittest
from types import SimpleNamespace

from scripts.balance.funded_progression_simulation import (
    bootstrap_median_ci_95,
    advance_offline_stamina,
    daily_offline_seconds,
    gather_with_capacity,
    modeled_no_route_stall,
    offline_stamina_restored,
    run_funded_simulation,
    wilson_interval_95,
    _next_purchase, _roster_party_minimum_level,
)
from scripts.balance.simulate_integrated_stage5_paths import _trajectory_recovery
from scripts.balance.simulate_guild_progression_profiles import Profile, _cycle_outcome


class FundedProgressionSimulationTests(unittest.TestCase):
    def test_offline_credit_never_exceeds_live_eight_hour_cap(self):
        self.assertEqual(daily_offline_seconds(2), 8 * 3600)
        self.assertEqual(daily_offline_seconds(12), 8 * 3600)
        self.assertEqual(daily_offline_seconds(20), 4 * 3600)
        self.assertEqual(offline_stamina_restored(2), 4)
        self.assertEqual(offline_stamina_restored(4), 8)
        self.assertEqual(offline_stamina_restored(8), 8)

    def test_offline_stamina_persists_and_regenerates_before_absence(self):
        first = advance_offline_stamina(2, 8)
        second = advance_offline_stamina(2, first["stamina_end_hours"])
        third = advance_offline_stamina(2, second["stamina_end_hours"])
        self.assertEqual(first["offline_credited_hours"], 8)
        self.assertEqual(first["stamina_end_hours"], 0)
        self.assertEqual(second["stamina_regenerated_hours"], 4)
        self.assertEqual(second["offline_credited_hours"], 4)
        self.assertEqual(second["stamina_end_hours"], 0)
        self.assertEqual(third["offline_credited_hours"], 4)
        self.assertEqual(advance_offline_stamina(1, 2)["offline_credited_hours"], 4)
        self.assertEqual(advance_offline_stamina(0, 4)["offline_credited_hours"], 4)
        self.assertEqual(advance_offline_stamina(0, 20)["offline_credited_hours"], 8)

    def test_short_session_and_return_offline_credit_is_compared_by_profile(self):
        casual = advance_offline_stamina(2, 8)
        # Each return replenishes only four hours for the 2h/day short-session profile.
        casual_day_two = advance_offline_stamina(2, casual["stamina_end_hours"])
        casual_day_three = advance_offline_stamina(2, casual_day_two["stamina_end_hours"])
        self.assertEqual([casual["offline_credited_hours"], casual_day_two["offline_credited_hours"],
                          casual_day_three["offline_credited_hours"]], [8, 4, 4])
        self.assertEqual(advance_offline_stamina(12, 8)["offline_credited_hours"], 8)
        self.assertEqual(advance_offline_stamina(8, 8)["offline_credited_hours"], 8)

    def test_funded_path_variants_diverge_after_minimum_party(self):
        buildings = {
            "housing": SimpleNamespace(level=10),
            "contract_office": SimpleNamespace(level=1, building_template=SimpleNamespace(effect_type="contract_office")),
            "training_ground": SimpleNamespace(level=0, building_template=SimpleNamespace(effect_type="training_ground")),
        }
        strategy = {"party_size": 3, "roster_target": 9, "office_target": 10}
        self.assertEqual(_next_purchase({**strategy, "path_variant": "roster_first"}, 3, buildings)[0],
                         "apprentice_hire")
        self.assertEqual(_next_purchase({**strategy, "path_variant": "office_after_minimum_party"}, 3, buildings)[0],
                         "contract_office_upgrade")

    def test_gathering_uses_worker_rate_and_shared_capacity(self):
        materials = {"wood": 0, "ore": 0, "leather": 0, "crystals": 0}
        stored, elapsed = gather_with_capacity(
            materials, family="wood", requested=500, free_capacity=35,
            worker_count=1, offline_seconds=8 * 3600,
        )
        self.assertEqual((stored, elapsed), (35, 35 * 60))
        self.assertEqual(sum(materials.values()), 35)
        crystal_stored, _ = gather_with_capacity(
            materials, family="crystals", requested=10, free_capacity=100,
            worker_count=1, offline_seconds=8 * 3600,
        )
        self.assertEqual(crystal_stored, 0)

    def test_binary_rate_and_median_intervals_are_reproducible(self):
        rate = wilson_interval_95(100, 100)
        self.assertEqual((rate["events"], rate["n"], rate["rate_percent"]), (100, 100, 100.0))
        self.assertGreater(rate["lower_percent"], 95.0)
        values = [1, 2, 3, 4, 5]
        self.assertEqual(bootstrap_median_ci_95(values, seed=14),
                         bootstrap_median_ci_95(values, seed=14))

    def test_hard_softlock_is_not_reported_when_unmeasured_and_model_stall_is_operational(self):
        def row(*, offline_gold=0, workers=0, materials=None, action=0, gold_shortfall=100):
            return {
                "contract_gold": 0, "offline_gold": offline_gold, "action_count": action,
                "gather_workers_available": workers, "gather_seconds_available": 28800 if workers else 0,
                "inventory_used": 0 if workers else 100, "inventory_capacity": 100,
                "next_purchase_requirements": {
                    "item": "contract_office_1", "gold_shortfall": gold_shortfall,
                    "guild_level_shortfall": 0,
                    "material_shortfalls": materials or {"wood": 0, "ore": 0, "leather": 0, "crystals": 0},
                },
            }

        blocked = [row() for _ in range(14)]
        recoverable_gold = [row(offline_gold=1) for _ in range(14)]
        recoverable_material = [row(workers=1, gold_shortfall=0,
                                    materials={"wood": 5, "ore": 0, "leather": 0, "crystals": 0})
                                for _ in range(14)]
        warehouse_blocked = [row(gold_shortfall=0, materials={"wood": 5, "ore": 0, "leather": 0, "crystals": 0})
                             for _ in range(14)]
        self.assertTrue(modeled_no_route_stall(blocked))
        self.assertFalse(modeled_no_route_stall(recoverable_gold))
        self.assertFalse(modeled_no_route_stall(recoverable_material))
        self.assertTrue(modeled_no_route_stall(warehouse_blocked))
        self.assertIsNone(modeled_no_route_stall(blocked[:13]))

    def test_funded_sqlite_trajectories_record_only_affordable_purchases(self):
        report = run_funded_simulation(runs_per_strategy=1, seed_start=711, max_days=14)
        self.assertEqual(set(report["strategies"]), {"ativo", "casual", "offline", "produtor", "combate"})
        self.assertEqual(len(report["raw_trajectories"]), 5)
        self.assertIn("temporary on-disk SQLite", report["database"])
        self.assertTrue(any(
            day["inventory_peak_used"] > 0
            for trajectory in report["raw_trajectories"]
            for day in trajectory["daily_ledger"]
        ))
        for trajectory in report["raw_trajectories"]:
            self.assertEqual(trajectory["gold_after_minimum_setup"], 30)
            for row in trajectory["daily_ledger"]:
                self.assertLessEqual(row["inventory_used"], row["inventory_capacity"])
                self.assertLessEqual(row["inventory_used"], sum(row["materials_balance"].values()))
            self.assertTrue(all(row["affordable_at_purchase"] for row in trajectory["purchases"]))
            self.assertTrue(all(row["balance_after"]["gold"] >= 0 for row in trajectory["purchases"]))
            self.assertEqual(trajectory["hard_economic_softlock_status"], "not_measured")
            self.assertIn(trajectory["modeled_no_route_stall_14d_observed"], (False, None))
        casual = next(row for row in report["raw_trajectories"] if row["strategy"] == "casual")
        self.assertEqual([row["offline_credited_hours"] for row in casual["daily_ledger"][:4]], [8, 4, 4, 4])

    def test_integrated_path_uses_conditional_drop_rolls_and_live_inventory_capacity(self):
        report = run_funded_simulation(
            runs_per_strategy=1, seed_start=9821, max_days=8,
            strategy_names=["casual"], integrate_item_sources=True,
            include_scouts_objective=True,
        )
        row = report["raw_trajectories"][0]
        self.assertGreater(row["material_drop_roll_count"], 0)
        self.assertLessEqual(row["material_drop_award_count"], row["material_drop_roll_count"])
        self.assertGreaterEqual(row["material_drop_stored_total"], 0)
        self.assertGreaterEqual(row["material_drop_discarded_total"], 0)
        for day in row["daily_ledger"]:
            self.assertLessEqual(day["inventory_used"], day["inventory_capacity"])
        self.assertEqual(sum(day["materials_spent"]["crystals"] for day in row["daily_ledger"]), 0)
        self.assertTrue(all(day["special_crystals_earned"] in (0, 1) for day in row["daily_ledger"]))

    def test_recovery_requires_same_blocked_purchase_to_be_later_bought(self):
        row = {
            "purchases": [{"item": "housing_2", "day": 5}],
            "daily_ledger": [
                {"day": 2, "next_purchase_requirements": {
                    "item": "housing_2", "gold_shortfall": 20, "guild_level_shortfall": 0,
                    "material_shortfalls": {"wood": 0, "ore": 0, "leather": 0, "crystals": 0}},
                    "contract_gold": 5, "offline_gold": 0, "mission_material_drop_stored_today": 0,
                    "materials_gathered": {"wood": 0, "ore": 0, "leather": 0}},
                {"day": 5, "contract_gold": 20, "offline_gold": 0,
                 "mission_material_drop_stored_today": 1,
                 "materials_gathered": {"wood": 2, "ore": 0, "leather": 0}},
            ],
        }
        recovery = _trajectory_recovery(row)
        self.assertEqual(len(recovery["recovered_blocked_purchases"]), 1)
        entry = recovery["recovered_blocked_purchases"][0]
        self.assertEqual((entry["item"], entry["days_until_purchase"]), ("housing_2", 3))
        self.assertEqual(recovery["unrecovered_blocked_items"], [])

    def test_party_eligibility_uses_member_levels_and_cycle_outcome_override(self):
        roster = [SimpleNamespace(level=1), SimpleNamespace(level=4), SimpleNamespace(level=3)]
        self.assertEqual(_roster_party_minimum_level(roster, 2), 3)
        self.assertEqual(_roster_party_minimum_level(roster, 2, active_count=2), 1)
        offer = {
            "offer_type": "contract", "duration_seconds": 3600, "success_chance_percent": 100,
            "xp_reward": 10, "gold_reward": 1, "min_party_size": 1, "max_party_size": 1,
            "rank": "C", "name": "Mercenary gate", "required_guild_level": 1,
            "required_min_mercenary_level": 3,
        }
        profile = Profile("gate-test", "mission", 1, 1, 1)
        below = _cycle_outcome(profile, [offer], 31, action_hours=1,
                               eligibility_guild_level=50, eligibility_mercenary_level=2)
        eligible = _cycle_outcome(profile, [offer], 31, action_hours=1,
                                  eligibility_guild_level=50, eligibility_mercenary_level=3)
        self.assertEqual(below["blocked_window_reasons"]["mercenary_level"], 1)
        self.assertEqual(eligible["actions"], 1)


if __name__ == "__main__":
    unittest.main()
