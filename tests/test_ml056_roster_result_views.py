import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]


class ML056RosterResultViewTests(unittest.TestCase):
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
