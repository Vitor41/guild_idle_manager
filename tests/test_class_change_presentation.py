import unittest

from app.services.class_change_presentation import build_transition_stage_cards


class ClassChangePresentationTests(unittest.TestCase):
    def setUp(self):
        self.transition = {
            "tier": 1,
            "from_class_id": 10,
            "required_mercenary_level": 20,
            "required_guild_level": 5,
            "required_training_ground_level": 10,
            "gold_cost": 1000,
        }

    def _cards(self, *, gold=1000, guild=5, training=10, workers=None, transitions=None):
        return build_transition_stage_cards(
            transitions or [self.transition],
            workers or [],
            gold=gold,
            guild_level=guild,
            training_ground_level=training,
        )

    def test_all_requirements_and_available_worker_unlock_stage(self):
        cards = self._cards(workers=[
            {"id": 1, "class_id": 10, "level": 20, "status": "available"},
        ])

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["label"], "1ª troca")
        self.assertEqual(cards[0]["state"], "Liberada")
        self.assertEqual(cards[0]["eligible_count"], 1)
        self.assertTrue(all(check["met"] for check in cards[0]["checks"]))

    def test_shortfalls_are_reported_without_changing_stage_requirements(self):
        cards = self._cards(
            gold=700, guild=4, training=8,
            workers=[{"id": 1, "class_id": 10, "level": 18, "status": "available"}],
        )

        self.assertEqual(cards[0]["state"], "Faltam requisitos")
        self.assertEqual([check["shortfall"] for check in cards[0]["checks"]], [300, 1, 2, 2])
        self.assertEqual(cards[0]["eligible_count"], 0)

    def test_global_requirements_without_available_eligible_worker_are_explicit(self):
        cards = self._cards(workers=[
            {"id": 1, "class_id": 10, "level": 30, "status": "busy"},
        ])

        self.assertEqual(cards[0]["state"], "Sem mercenário elegível")
        self.assertEqual(cards[0]["eligible_count"], 0)
        self.assertTrue(cards[0]["checks"][3]["met"])

    def test_equivalent_paths_are_grouped_and_requirement_variants_remain_separate(self):
        second_path = {**self.transition, "from_class_id": 11}
        variant = {**self.transition, "from_class_id": 12, "gold_cost": 1500}
        cards = self._cards(
            workers=[{"id": 1, "class_id": 11, "level": 24, "status": "available"}],
            transitions=[self.transition, second_path, variant],
        )

        self.assertEqual(len(cards), 2)
        grouped = next(card for card in cards if card["gold_cost"] == 1000)
        self.assertEqual(grouped["path_count"], 2)
        self.assertEqual(grouped["eligible_count"], 1)


if __name__ == "__main__":
    unittest.main()
