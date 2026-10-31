import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.balance.simulate_guild_progression_profiles import (
    Profile,
    _build_profile_catalog,
    _cycle_outcome,
    _offline_cycle_window,
    _profile_investment_policy,
    _simulate_regional_progression,
    apply_candidate_upkeep,
    build_controlled_activity_audit,
)
from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.seeds.campaign_content import apply_initial_campaign_content


class RegionalEconomySimulationTests(unittest.TestCase):
    def test_profile_investment_cost_does_not_gate_party_on_contract_office(self):
        db = Mock()
        db.scalars.return_value = []
        db.scalar.return_value = None
        profile = Profile("office_optional", "mission", 2, 2, 3)
        legacy_template = SimpleNamespace(
            required_building_type="contract_office",
            required_building_level=100,
        )

        setup = _profile_investment_policy(db, profile, {1: [legacy_template]})

        building_cost_types = {row["effect_type"] for row in setup["building_costs"]}
        self.assertIn("housing", building_cost_types)
        self.assertNotIn("contract_office", building_cost_types)
        self.assertNotIn("scouts", building_cost_types)
        self.assertIn("do not gate", setup["policy"])

    def test_candidate_upkeep_charges_per_vigilia_and_never_exceeds_treasury(self):
        balance, first_charge = apply_candidate_upkeep(100, 0.02)
        self.assertEqual((balance, first_charge), (98, 2))
        balance, second_charge = apply_candidate_upkeep(balance, 0.02)
        self.assertEqual((balance, second_charge), (96, 2))
        self.assertEqual(apply_candidate_upkeep(1, 0.10), (0, 1))
        self.assertEqual(apply_candidate_upkeep(0, 0.10), (0, 0))

    def test_profile_cannot_claim_more_offers_than_exist_on_finite_board(self):
        profile = Profile("ativo", "mission", 12, 3, 3)
        board = [{
            "offer_type": "contract", "rank": "C", "name": f"Contrato {i}",
            "duration_seconds": 1800, "gold_reward": 25, "xp_reward": 60,
            "success_chance_percent": 90, "min_party_size": 2,
            "max_party_size": 3, "recommended_power": 100,
        } for i in range(2)]
        result = _cycle_outcome(profile, board, 123)
        self.assertLessEqual(result["actions"], len(board))
        self.assertEqual(result["actions"], 2)

    def test_blocked_window_is_attributed_to_offer_duration(self):
        profile = Profile("ativo", "mission", 12, 1, 3)
        board = [{
            "offer_type": "contract", "rank": "C", "name": "Contrato longo",
            "duration_seconds": 4 * 3600, "gold_reward": 25, "xp_reward": 60,
            "success_chance_percent": 90, "min_party_size": 3,
            "max_party_size": 3,
        }]
        result = _cycle_outcome(profile, board, 123, action_hours=3)
        self.assertEqual(result["actions"], 0)
        self.assertEqual(result["blocked_team_windows"], 1)
        self.assertEqual(result["blocked_window_reasons"]["duration"], 1)

    def test_blocked_window_identifies_offer_claimed_by_prior_team(self):
        profile = Profile("ativo", "mission", 12, 2, 3)
        board = [{
            "offer_type": "contract", "rank": "C", "name": "Contrato compartilhado",
            "duration_seconds": 1800, "gold_reward": 25, "xp_reward": 60,
            "success_chance_percent": 100, "min_party_size": 3,
            "max_party_size": 3,
        }]
        result = _cycle_outcome(profile, board, 456, action_hours=0.5)
        self.assertEqual(result["actions"], 1)
        self.assertEqual(result["blocked_team_windows"], 1)
        self.assertEqual(result["blocked_window_reasons"]["claimed_by_other_team"], 1)

    def test_parallel_team_dispatch_round_robins_shared_board_offers(self):
        profile = Profile("ativo", "mission", 12, 3, 3)
        board = [{
            "offer_type": "contract", "rank": "C", "name": f"Contrato {index}",
            "duration_seconds": 1800, "gold_reward": 25, "xp_reward": 60,
            "success_chance_percent": 100, "min_party_size": 3,
            "max_party_size": 3,
        } for index in range(10)]
        result = _cycle_outcome(profile, board, 654, action_hours=3)
        self.assertEqual(result["actions"], 10)
        self.assertEqual(result["blocked_team_windows"], 0)

    def test_mercenary_level_gate_is_distinguished_from_guild_level_gate(self):
        profile = Profile("ativo", "mission", 12, 1, 3)
        board = [{
            "offer_type": "contract", "rank": "C", "name": "Contrato de nível alto",
            "duration_seconds": 1800, "gold_reward": 25, "xp_reward": 60,
            "success_chance_percent": 90, "min_party_size": 3,
            "max_party_size": 3, "required_guild_level": 1,
            "required_min_mercenary_level": 7,
        }]
        result = _cycle_outcome(
            profile, board, 789, action_hours=1,
            eligibility_guild_level=10, eligibility_mercenary_level=5,
        )
        self.assertEqual(result["blocked_window_reasons"]["guild_level"], 0)
        self.assertEqual(result["blocked_window_reasons"]["mercenary_level"], 1)

    def test_selectable_team_uses_offer_valid_subset_for_guild_xp(self):
        profile = Profile("selectable", "mission", 4, 1, 3, party_selection_policy="selectable")
        board = [{
            "offer_type": "contract", "rank": "C", "name": "Contrato para dois",
            "duration_seconds": 1800, "gold_reward": 25, "xp_reward": 60,
            "success_chance_percent": 100, "min_party_size": 2,
            "max_party_size": 2,
        }]
        result = _cycle_outcome(profile, board, 901, action_hours=1)
        self.assertEqual(result["actions"], 1)
        self.assertEqual(result["guild_xp"], 12)

    def test_combat_profile_allows_normal_dungeons_without_boss_only_gates(self):
        profile = Profile("dungeon_audit", "dungeon", 8, 1, 3)
        board = [{
            "offer_type": "dungeon", "rank": "C", "name": "Masmorra normal",
            "duration_seconds": 3600, "gold_reward": 100, "xp_reward": 100,
            "success_chance_percent": 100, "min_party_size": 3,
            "max_party_size": 3, "recommended_power": 100,
            # Production only validates advanced party requirements for bosses.
            "required_total_power": 999, "required_class_code": "knight",
            "required_tank_count": 1, "required_support_count": 1,
            "required_damage_count": 1, "required_equipment_tier": 3,
        }]
        result = _cycle_outcome(
            profile, board, 1, action_hours=1, guild=type("GuildStub", (), {"level": 1, "xp": 0})(),
            player_power_snapshot=90, roster_size=9,
        )
        self.assertEqual(result["actions"], 1)
        self.assertEqual(result["gold"], 100)

    def test_official_combat_profile_prioritizes_contracts_when_available(self):
        profile = Profile("combate", "contract_priority", 8, 1, 3)
        board = [{
            "offer_type": "boss", "rank": "C", "name": "Chefe avançado",
            "duration_seconds": 3600, "gold_reward": 1000, "xp_reward": 100,
            "success_chance_percent": 100, "min_party_size": 3,
            "max_party_size": 5, "recommended_power": 100,
            "required_total_power": 10, "required_class_code": None,
            "required_tank_count": 1, "required_support_count": 1,
            "required_damage_count": 1, "required_equipment_tier": 1,
        }, {
            "offer_type": "contract", "rank": "C", "name": "Contrato disponível",
            "duration_seconds": 3600, "gold_reward": 50, "xp_reward": 80,
            "success_chance_percent": 100, "min_party_size": 3,
            "max_party_size": 3, "recommended_power": 10,
        }, {
            "offer_type": "contract", "rank": "S", "name": "Contrato de alto desafio",
            "duration_seconds": 3600, "gold_reward": 75, "xp_reward": 40,
            "success_chance_percent": 100, "min_party_size": 3,
            "max_party_size": 3, "recommended_power": 10,
        }]
        result = _cycle_outcome(
            profile, board, 2, action_hours=1, guild=type("GuildStub", (), {"level": 1, "xp": 0})(),
            player_power_snapshot=90, roster_size=9,
        )
        self.assertEqual(result["actions"], 1)
        self.assertEqual(result["gold"], 75)

    def test_offline_schedule_includes_return_activity_and_refills_stamina(self):
        windows = [_offline_cycle_window(index) for index in range(4)]
        self.assertEqual(windows[0], (8.0, 1, "pre_absence_dispatch"))
        self.assertEqual(windows[1:], [
            (4.0, None, "post_return_online"),
            (4.0, None, "post_return_online"),
            (0.0, 0, "unattended"),
        ])
        self.assertEqual(sum(window[0] for window in windows if window[2] == "post_return_online"), 8.0)
        profile = Profile("offline", "mission", 8, 1, 3)
        board = [{
            "offer_type": "contract", "rank": "C", "name": "Oferta após retorno",
            "duration_seconds": 3600, "gold_reward": 25, "xp_reward": 60,
            "success_chance_percent": 100, "min_party_size": 3,
            "max_party_size": 3,
        }]
        self.assertEqual(
            _cycle_outcome(profile, board, 3, action_hours=windows[1][0])["actions"], 1,
        )

    def test_regional_progression_materializes_finite_cycle_offers(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(get_engine())
        with SessionLocal() as db:
            apply_initial_campaign_content(db)
            db.commit()
            profile = Profile("casual", "mission", 2, 2, 2)
            catalog = _build_profile_catalog(db, profile)
            result = _simulate_regional_progression(
                db, profile, catalog, 20261028, sample_runs=1, max_days=1,
            )
            offline = Profile("offline", "mission", 8, 3, 3)
            offline_catalog = _build_profile_catalog(db, offline)
            offline_result = _simulate_regional_progression(
                db, offline, offline_catalog, 20261029, sample_runs=1, max_days=1,
            )
            combat = Profile("combate", "contract_priority", 8, 3, 3)
            combat_catalog = _build_profile_catalog(db, combat)
            combat_result = _simulate_regional_progression(
                db, combat, combat_catalog, 20261030, sample_runs=1, max_days=1,
            )
            controlled = build_controlled_activity_audit(db, sample_cycles=1)
        self.assertEqual(result["finite_offers_per_home_region_cycle"], {
            "contract": 10, "dungeon": 3, "boss": 1,
        })
        self.assertEqual(result["trajectories"], 1)
        self.assertEqual(result["trajectory_samples"][0]["cycles_simulated"], 4)
        self.assertLessEqual(result["trajectory_samples"][0]["actions"], 40)
        self.assertGreater(result["trajectory_samples"][0]["average_board_player_power"], 0)
        self.assertGreater(result["trajectory_samples"][0]["average_rank_progression_stage"], 0)
        offline_sample = offline_result["trajectory_samples"][0]
        self.assertLessEqual(offline_sample["offline_pre_absence_actions"], offline.slots)
        self.assertGreaterEqual(offline_sample["post_return_online_actions"], 0)
        self.assertGreater(combat_result["trajectory_samples"][0]["actions"], 0)
        for simulated in (result, offline_result, combat_result):
            sample = simulated["trajectory_samples"][0]
            self.assertEqual(
                sum(sample["blocked_window_reasons"].values()),
                sample["blocked_team_windows"],
            )
            self.assertEqual(
                sample["productive_team_windows"] + sample["blocked_team_windows"],
                sample["eligible_team_windows"],
            )
        self.assertEqual(controlled["sample_cycles_per_level"], 1)
        self.assertEqual(set(controlled["levels"]), {"1", "10", "20", "30", "40", "50"})
        for level in controlled["levels"].values():
            self.assertEqual(level["fixed_party_size"], 3)
            self.assertEqual(level["fixed_parallel_slots"], 3)
            self.assertEqual(set(level["hours_sensitivity_same_boards"]), {"0.5", "2.0", "3.0", "6.0"})
            self.assertEqual(set(level["party_size_sensitivity_same_boards"]), {"2", "3"})
            self.assertEqual(set(level["rank_accessibility_per_board"]), {"E", "D", "C", "B", "A", "S"})
            self.assertIn("mission_candidate_pool_before_fallback", level)
            self.assertIn("fixed_exact_actions_per_board", level["hours_sensitivity_same_boards"]["0.5"])
            self.assertIn("selectable_subset_actions_per_board", level["hours_sensitivity_same_boards"]["0.5"])


if __name__ == "__main__":
    unittest.main()
