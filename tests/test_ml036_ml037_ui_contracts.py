from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClassChangeAndEquipmentUiContractTests(unittest.TestCase):
    def test_class_change_template_distinguishes_level_and_availability_states(self):
        template = (ROOT / "app/templates/class_change/index.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")

        self.assertIn("Requisitos por etapa", template)
        self.assertIn("step.label", template)
        self.assertIn("step.worker_summary", template)
        self.assertIn("step.state_class", template)
        self.assertIn("check.required", template)
        self.assertIn("check.current", template)
        self.assertIn("check.shortfall", template)
        self.assertIn("check.missing", template)
        self.assertNotIn("Requisitos globais", template)
        self.assertIn(".class-requirement-cards { display: grid; grid-template-columns: repeat(2", css)
        self.assertIn(".class-requirement-cards { grid-template-columns: minmax(0, 1fr); }", css)
        self.assertIn(".class-requirement-state--occupied", css)

    def test_equipment_details_are_compact_and_keep_accessible_interaction(self):
        template = (ROOT / "app/templates/mercenaries/detail.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")
        desktop_css = (ROOT / "app/static/css/desktop-theme.css").read_text(encoding="utf-8")
        script = (ROOT / "app/static/js/equipment-details.js").read_text(encoding="utf-8")
        base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")

        self.assertIn("FORTE {{ bonus.label }} +{{ bonus.strong_value }}", template)
        self.assertIn("= +{{ bonus.total_value }} aplicado", template)
        self.assertIn("FORTE {{ bonus.label }} +{{ bonus.strong_value }}", template)
        self.assertIn("{{ bonus.label }} +{{ bonus.normal_value }}", template)
        self.assertNotIn("Total aplicado", template)
        self.assertIn("rarity-", template)
        slot_rule = css.split(".equipment-slot.filled {", 1)[1].split("}", 1)[0]
        self.assertIn("border-left: 3px solid var(--rarity-color", slot_rule)
        self.assertIn("background: #203035", slot_rule)
        self.assertNotIn("linear-gradient", slot_rule)
        self.assertEqual(css.count(".equipment-slot.filled {"), 1)
        theme_override = desktop_css.index(".equipment-slot.filled > button.equipment-slot__trigger")
        global_hover_rule = desktop_css.index("button:not(.secondary-button):not(.danger-button):not(.topbar-back-button):not(.text-button):hover")
        self.assertGreater(theme_override, global_hover_rule)
        self.assertIn(".equipment-slot.filled > button.equipment-slot__trigger:not(.secondary-button)", desktop_css)
        self.assertIn(".equipment-slot.filled > button.equipment-slot__trigger:not(.secondary-button):not(.danger-button):not(.topbar-back-button):not(.text-button):hover:not(:disabled)", desktop_css)
        self.assertIn("background: #203035", desktop_css[theme_override:])
        self.assertIn("filter: none", desktop_css[theme_override:])
        self.assertIn("outline: 3px solid var(--gold-2)", desktop_css[theme_override:])
        self.assertIn("?v=20261117-2", base)
        self.assertIn("desktop-theme.css') }}?v=20261117-1", base)
        self.assertIn("aria-expanded=\"false\"", template)
        self.assertIn("event.key === \"Escape\"", script)

    def test_guide_source_rows_are_by_category_and_do_not_show_gathering_bands(self):
        guide = (ROOT / "app/static/js/guide.js").read_text(encoding="utf-8")
        utils = (ROOT / "app/static/js/guide-utils.js").read_text(encoding="utf-8")

        self.assertIn("[source.type, source.label]", utils)
        self.assertIn("Fonte: ${variant.source.name}", guide)
        self.assertIn('`A partir da guilda Nv. ${minimumGuildLevel ?? "—"}`', guide)
        self.assertIn('variant.source.type !== "gathering"', guide)
        self.assertNotIn("Nível inicial listado:", guide)
        self.assertNotIn("disponibilidade varia por faixa", guide)


if __name__ == "__main__":
    unittest.main()
