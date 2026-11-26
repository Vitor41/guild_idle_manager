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

    def test_qualified_busy_worker_is_not_reported_as_missing_level(self):
        cards = self._cards(workers=[
            {"id": 1, "class_id": 10, "level": 30, "status": "busy"},
        ])

        self.assertEqual(cards[0]["state"], "Mercenário ocupado")
        self.assertEqual(cards[0]["eligible_count"], 0)
        self.assertTrue(cards[0]["checks"][3]["met"])
        self.assertEqual(cards[0]["checks"][3]["current"], 30)
        self.assertIn("está ocupado", cards[0]["worker_summary"])

    def test_no_matching_worker_uses_dash_instead_of_fake_zero_level(self):
        cards = self._cards()

        self.assertEqual(cards[0]["state"], "Sem mercenário na classe")
        self.assertEqual(cards[0]["checks"][3]["current"], "—")
        self.assertEqual(cards[0]["checks"][3]["shortfall"], None)
        self.assertEqual(cards[0]["checks"][3]["missing"], "Sem mercenário da classe de origem")
        self.assertIn("Nenhum mercenário", cards[0]["worker_summary"])

    def test_unknown_gold_is_not_rendered_as_zero_or_a_numeric_shortfall(self):
        cards = self._cards(gold=None, workers=[
            {"id": 1, "class_id": 10, "level": 20, "status": "available"},
        ])

        gold_check = cards[0]["checks"][0]
        self.assertEqual(gold_check["current"], "—")
        self.assertFalse(gold_check["met"])
        self.assertIsNone(gold_check["shortfall"])
        self.assertEqual(gold_check["missing"], "Saldo indisponível")
        self.assertEqual(cards[0]["state"], "Saldo indisponível")
        self.assertEqual(cards[0]["eligible_count"], 0)

        known_zero = self._cards(gold=0, workers=[
            {"id": 1, "class_id": 10, "level": 20, "status": "available"},
        ])[0]["checks"][0]
        self.assertEqual(known_zero["current"], 0)
        self.assertEqual(known_zero["shortfall"], 1000)
        self.assertEqual(known_zero["missing"], "")

    def test_template_shows_shortfalls_first_and_keeps_full_requirement_matrix_expandable(self):
        from pathlib import Path

        template = (Path(__file__).resolve().parents[1] / "app/templates/class_change/index.html").read_text(encoding="utf-8")
        self.assertIn("class-requirement-checks--missing", template)
        self.assertIn("{% for check in step.checks if not check.met %}", template)
        self.assertIn("Ver matriz completa · {{ step.checks|length }} requisitos", template)
        self.assertIn("{% for check in step.checks %}", template)

    def test_available_worker_below_required_level_reports_shortfall(self):
        cards = self._cards(workers=[
            {"id": 1, "class_id": 10, "level": 18, "status": "available"},
        ])

        self.assertEqual(cards[0]["state"], "Nível insuficiente")
        self.assertEqual(cards[0]["checks"][3]["current"], 18)
        self.assertEqual(cards[0]["checks"][3]["shortfall"], 2)
        self.assertIn("mercenário disponível", cards[0]["worker_summary"])

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
