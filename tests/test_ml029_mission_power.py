from types import SimpleNamespace
import unittest

from app.models.mission import MissionTemplate
from app.services.mission_power_service import (
    REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS,
    common_apprentice_max_initial_attributes,
    common_apprentice_reference_curve,
    common_apprentice_reference_power,
    recommended_regional_contract_power,
)
from app.services.regional_cycle_service import _add_offer
from scripts.balance.study_ml029_contract_power import _maximum_class_bonus


class _CaptureSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


class MissionPowerTests(unittest.TestCase):
    def test_balance_study_class_bonus_cap_matches_actual_party_size(self):
        self.assertEqual(_maximum_class_bonus(1), 3)
        self.assertEqual(_maximum_class_bonus(2), 6)
        self.assertEqual(_maximum_class_bonus(3), 8)

    def test_reference_curve_uses_maximum_valid_common_apprentice_roll(self):
        self.assertEqual(
            common_apprentice_max_initial_attributes(),
            (("power", 7), ("vitality", 7), ("agility", 7), ("intelligence", 7), ("luck", 7)),
        )
        curve = common_apprentice_reference_curve()
        self.assertEqual(len(curve), 350)
        self.assertEqual(curve[0], {
            "level": 1, "power": 7, "vitality": 7, "agility": 7,
            "intelligence": 7, "luck": 7, "power_score": 18,
        })
        self.assertEqual(
            (curve[17]["power"], curve[17]["vitality"], curve[17]["agility"],
             curve[17]["intelligence"], curve[17]["luck"], curve[17]["power_score"]),
            (41, 41, 24, 24, 24, 93),
        )
        self.assertEqual(
            (curve[-1]["power"], curve[-1]["vitality"], curve[-1]["agility"],
             curve[-1]["intelligence"], curve[-1]["luck"], curve[-1]["power_score"]),
            (705, 705, 356, 356, 356, 1531),
        )
        self.assertTrue(all(
            curve[index]["power_score"] < curve[index + 1]["power_score"]
            for index in range(len(curve) - 1)
        ))

    def test_recommended_power_is_monotonic_and_rounds_up(self):
        self.assertEqual(common_apprentice_reference_power(18), 93)
        self.assertEqual(recommended_regional_contract_power(1, "E", 2, fallback_power=10), 26)
        self.assertEqual(recommended_regional_contract_power(18, "C", 2, fallback_power=49), 144)
        levels = [recommended_regional_contract_power(level, "C", 2, fallback_power=1)
                  for level in (1, 5, 18, 50, 75, 200, 350)]
        self.assertEqual(levels, sorted(levels))
        by_rank = [recommended_regional_contract_power(18, rank, 2, fallback_power=1)
                   for rank in REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS]
        self.assertEqual(by_rank, sorted(by_rank))
        by_group = [recommended_regional_contract_power(18, "C", size, fallback_power=1)
                    for size in range(1, 6)]
        self.assertEqual(by_group, sorted(by_group))
        self.assertEqual(recommended_regional_contract_power(1, "E", 3, fallback_power=0), 38)
        self.assertEqual(recommended_regional_contract_power(351, "S", 5, fallback_power=77), 77)
        self.assertEqual(recommended_regional_contract_power(18, "X", 5, fallback_power=77), 77)

    def test_new_combat_offer_snapshots_formula_without_mutating_admin_template(self):
        template = MissionTemplate(
            id=11,
            name="Contrato Rank C nível 18",
            description="",
            difficulty="normal",
            level_band="1-20",
            mission_type="combat",
            recommended_level=18,
            recommended_power=49,
            duration_seconds=900,
            base_gold_reward=100,
            base_xp_reward=100,
            base_success_chance=80,
            min_party_size=1,
            max_party_size=2,
            required_guild_level=1,
            required_min_mercenary_level=1,
            required_building_level=0,
        )
        db = _CaptureSession()
        offer = _add_offer(
            db,
            "campaign",
            SimpleNamespace(id=5, cycle_number=2),
            "vale-fronteira",
            "contract",
            1,
            template,
            "C",
        )
        self.assertEqual(offer.recommended_power_snapshot, 144)
        self.assertEqual((offer.min_party_size_snapshot, offer.max_party_size_snapshot), (1, 2))
        self.assertEqual(template.recommended_power, 49)
        self.assertEqual(db.added, [offer])

        template.recommended_power = 700
        template.max_party_size = 5
        self.assertEqual(offer.recommended_power_snapshot, 144)
        self.assertEqual(offer.max_party_size_snapshot, 2)

    def test_gathering_and_long_idle_contracts_keep_configured_power(self):
        db = _CaptureSession()
        for mission_type in ("gathering", "long_idle"):
            template = MissionTemplate(
                id=20,
                name=f"Missão {mission_type}",
                description="",
                difficulty="normal",
                level_band="1-20",
                mission_type=mission_type,
                recommended_level=18,
                recommended_power=49,
                duration_seconds=900,
                base_gold_reward=100,
                base_xp_reward=100,
                base_success_chance=80,
                min_party_size=1,
                max_party_size=2,
                required_guild_level=1,
                required_min_mercenary_level=1,
                required_building_level=0,
            )
            offer = _add_offer(
                db, "campaign", SimpleNamespace(id=6, cycle_number=3), "bosque-ambar",
                "contract", 1, template, "C",
            )
            self.assertEqual(offer.recommended_power_snapshot, 49)


if __name__ == "__main__":
    unittest.main()
