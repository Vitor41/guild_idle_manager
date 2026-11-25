import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]


class ML056RosterResultViewTests(unittest.TestCase):
    def test_tavern_cards_keep_content_height_when_the_special_offer_is_empty(self):
        template = (ROOT / "app/templates/tavern/index.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")

        self.assertIn('class="dashboard tavern-dashboard"', template)
        self.assertIn(".tavern-dashboard > .dashboard-grid { align-items: start; }", css)

    def test_roster_precedes_compact_hiring_summary_and_class_name_is_not_repeated_as_image_alt(self):
        template = (ROOT / "app/templates/mercenaries/index.html").read_text(encoding="utf-8")
        roster_position = template.index('class="mercenary-grid table-panel"')
        hiring_position = template.index('class="panel mercenary-hiring-summary"')

        self.assertLess(roster_position, hiring_position)
        self.assertIn("<dt>Ocupação</dt>", template)
        self.assertNotIn("<dt>Vagas</dt>", template)
        self.assertIn('alt="" loading="lazy">', template)
        self.assertIn("{{ mercenary.class_label }} · Nível {{ mercenary.level }}", template)

    def test_mercenary_attributes_keep_table_headers_and_add_labeled_narrow_values(self):
        template = (ROOT / "app/templates/mercenaries/detail.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/desktop-theme.css").read_text(encoding="utf-8")

        self.assertIn('class="table-wrap mercenary-attribute-table-wrap"', template)
        self.assertIn('class="mercenary-attribute-table"', template)
        self.assertIn('<th scope="row"', template)
        self.assertIn('class="mercenary-attribute-table__mobile-label"', template)
        self.assertIn('class="secondary-button danger-button equipment-slot__remove" type="submit">Remover</button>', template)
        self.assertIn("table.mercenary-attribute-table { width: 100%; min-width: 0; table-layout: fixed; }", css)
        self.assertIn("@media (max-width: 480px)", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn(".mercenary-dismiss-form .danger-button", css)

    def test_equipment_details_use_a_viewport_panel_on_narrow_screens_and_keep_accessible_controls(self):
        main_css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")
        desktop_css = (ROOT / "app/static/css/desktop-theme.css").read_text(encoding="utf-8")
        script = (ROOT / "app/static/js/equipment-details.js").read_text(encoding="utf-8")
        base_template = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")

        self.assertIn(".equipment-details__close { flex: 0 0 40px; width: 40px; min-width: 40px; min-height: 40px !important;", main_css)
        self.assertIn("@media (max-width: 760px) {\n  .equipment-details.is-open {\n    position: fixed;", main_css)
        narrow_panel_start = main_css.index("@media (max-width: 760px) {\n  .equipment-details.is-open")
        narrow_panel_end = main_css.index("  .equipment-details__meta", narrow_panel_start)
        self.assertNotIn("position: static;", main_css[narrow_panel_start:narrow_panel_end])
        self.assertIn("window.matchMedia(\"(max-width: 760px)\").matches", script)
        self.assertIn('panel.style.left = `${left}px`;', script)
        self.assertIn('panel.style.top = `${top}px`;', script)
        self.assertIn("border-color: #a66f62", desktop_css)
        self.assertIn("outline: 3px solid #f5d798; outline-offset: 3px;", desktop_css)
        self.assertIn("/js/equipment-details.js') }}?v=20261125-2", base_template)

    def test_result_history_details_are_collapsed_and_rewards_remain_visible(self):
        env = Environment(loader=FileSystemLoader(ROOT / "app/templates"), autoescape=True)
        template = env.from_string(
            '{% from "components/result_card.html" import result_card %}{{ result_card(run, "A trilha") }}'
        )
        run = SimpleNamespace(
            success=True,
            resolved_at=None,
            gold_reward=25,
            xp_reward=10,
            members=[object()],
            run_multiplier=1.5,
            result_view={
                "has_details": True,
                "xp_awards": ["Lina: +10 XP"],
                "level_ups": [],
                "guild_progress": [],
                "items": ["Espada curta"],
                "notes": [],
            },
        )

        html = template.render(run=run)
        details = html.index('<details class="result-history-details">')
        summary = html.index("Ver detalhes do resultado")
        item = html.index("Espada curta")

        self.assertIn("25</dd>", html)
        self.assertIn("A trilha", html)
        self.assertLess(details, summary)
        self.assertLess(summary, item)
        self.assertNotIn('class="result-history-details" open', html)

    def test_result_without_long_details_keeps_the_short_status(self):
        env = Environment(loader=FileSystemLoader(ROOT / "app/templates"), autoescape=True)
        template = env.from_string(
            '{% from "components/result_card.html" import result_card %}{{ result_card(run, "Masmorra") }}'
        )
        run = SimpleNamespace(
            success=False,
            resolved_at=None,
            gold_reward=0,
            xp_reward=0,
            members=[],
            run_multiplier=1,
            result_view={
                "has_details": False,
                "xp_awards": [],
                "level_ups": [],
                "guild_progress": [],
                "items": [],
                "notes": [],
            },
        )

        html = template.render(run=run)
        self.assertIn("Nenhuma ocorrência adicional neste resultado.", html)
        self.assertNotIn("<details", html)


if __name__ == "__main__":
    unittest.main()
