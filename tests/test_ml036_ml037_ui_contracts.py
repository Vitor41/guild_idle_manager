from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClassChangeAndEquipmentUiContractTests(unittest.TestCase):
    def test_class_change_template_shows_per_stage_requirements_and_eligibility(self):
        template = (ROOT / "app/templates/class_change/index.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")

        self.assertIn("Requisitos por etapa", template)
        self.assertIn("step.label", template)
        self.assertIn("step.eligible_count", template)
        self.assertIn("check.required", template)
        self.assertIn("check.current", template)
        self.assertIn("check.shortfall", template)
        self.assertNotIn("Requisitos globais", template)
        self.assertIn(".class-requirement-cards { display: grid; grid-template-columns: repeat(2", css)
        self.assertIn(".class-requirement-cards { grid-template-columns: minmax(0, 1fr); }", css)

    def test_equipment_details_are_compact_and_keep_accessible_interaction(self):
        template = (ROOT / "app/templates/mercenaries/detail.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")
        script = (ROOT / "app/static/js/equipment-details.js").read_text(encoding="utf-8")

        self.assertIn("FORTE {{ bonus.label }} +{{ bonus.strong_value }}", template)
        self.assertIn("= +{{ bonus.total_value }} aplicado", template)
        self.assertIn("FORTE {{ bonus.label }} +{{ bonus.strong_value }}", template)
        self.assertIn("{{ bonus.label }} +{{ bonus.normal_value }}", template)
        self.assertNotIn("Total aplicado", template)
        self.assertIn("rarity-", template)
        self.assertIn(".equipment-slot.filled { border: 1px solid #375057", css)
        self.assertIn("background: #203035", css)
        self.assertIn("aria-expanded=\"false\"", template)
        self.assertIn("event.key === \"Escape\"", script)


if __name__ == "__main__":
    unittest.main()
