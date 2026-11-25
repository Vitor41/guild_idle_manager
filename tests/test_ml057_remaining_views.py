from pathlib import Path
import re
import unittest
from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]


class Ml057RemainingViewTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_changed_templates_parse(self):
        environment = Environment()
        for path in (
            "app/templates/base.html",
            "app/templates/components/regional_offer_actions.html",
            "app/templates/regional/index.html",
            "app/templates/regional/detail.html",
            "app/templates/classes/index.html",
            "app/templates/tiers/index.html",
            "app/templates/codex/index.html",
            "app/templates/tutorial/index.html",
            "app/templates/updates.html",
        ):
            with self.subTest(template=path):
                environment.parse(self.read(path))

    def test_regional_offers_lead_and_keep_recommendations_separate_from_requirements(self):
        page = self.read("app/templates/regional/index.html")
        css = self.read("app/static/css/desktop-evolution.css")
        self.assertIn('<details class="regional-map-details">', page)
        self.assertIn('href="/guide#vigilia-regional"', page)
        self.assertIn("Recomendado: nível {{ offer.recommended_level_snapshot }}", page)
        self.assertIn("Exige · Grupo mínimo–máximo", page)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)
        self.assertIn(".evolution-offer-card h4 { overflow-wrap: anywhere; }", css)
        self.assertIn(".evolution-region-grid, .evolution-offer-grid { grid-template-columns: 1fr; }", css)

    def test_regional_comparison_keeps_guild_identity_during_local_horizontal_scroll(self):
        page = self.read("app/templates/regional/detail.html")
        css = self.read("app/static/css/desktop-evolution.css")
        self.assertIn("regional-comparison-table", page)
        self.assertIn("<th scope=\"row\">{{ row.state.name }}", page)
        self.assertIn("overflow-x: auto", css)
        self.assertIn(".regional-comparison-table .evolution-ranking-table th:first-child { position: sticky; left: 0", css)
        self.assertIn("class=\"numeric\" data-comparison-field=\"wealth\"", page)
        regional_home = self.read("app/templates/regional/index.html")
        self.assertIn("regional-main-ranking", regional_home)
        self.assertIn("position: sticky; left: 70px", css)

    def test_regional_report_groups_cpu_stages_on_demand_and_labels_missing_data(self):
        page = self.read("app/templates/regional/index.html")
        self.assertNotIn("<p></p>", page)
        self.assertIn('<details class="regional-report-activity">', page)
        for label in ("Planejadas", "Elegíveis", "Iniciadas", "Resolvidas"):
            self.assertIn(f"<th scope=\"col\">{label}</th>", page)
        self.assertIn("activity.planned if activity.planned is not none else 'não registrado'", page)
        self.assertIn("activity.resolved if activity.resolved is not none else 'não registrado'", page)
        self.assertIn("report.has_unmeasured_cpu_activity", page)

    def test_class_guide_flattens_tiers_and_keeps_return_links_in_a_sticky_index(self):
        page = self.read("app/templates/classes/index.html")
        css = self.read("app/static/css/main.css")
        self.assertIn('id="classes-guide-index"', page)
        self.assertIn('class="class-tier-group"', page)
        self.assertIn('href="#classes-guide-index">Voltar ao índice</a>', page)
        self.assertIn(".classes-guide-index { position: sticky;", css)
        self.assertNotIn('<section class="panel table-panel">\n        <h2>{{ tier_label }}</h2>', page)

    def test_rarity_guide_uses_one_label_per_card_and_does_not_repeat_equipment_copy(self):
        page = self.read("app/templates/tiers/index.html")
        css = self.read("app/static/css/main.css")
        self.assertEqual(page.count("{{ rarity.description }}"), 1)
        self.assertNotIn("<h3>{{ rarity.label }}</h3>", page)
        self.assertIn("tier-guide-grid--equipment", page)
        self.assertIn("grid-template-columns: repeat(auto-fit, minmax(250px, 1fr))", css)
        self.assertEqual(page.count("{{ rarity.label }}"), 2)

    def test_codex_detail_return_preserves_filters_and_returns_to_the_selected_entry(self):
        page = self.read("app/templates/codex/index.html")
        route = self.read("app/routes/codex_routes.py")
        self.assertIn("/codex?category={{ selected_category }}&amp;trail={{ selected_trail }}#codex-entry-{{ selected_codex_entry.id }}", page)
        self.assertIn('id="codex-entry-{{ entry.id }}" tabindex="-1"', page)
        self.assertIn('request.query_params.get("category", "all")', route)
        self.assertIn('request.query_params.get("trail", "all")', route)

    def test_tutorial_has_thirteen_topic_icons_and_reachable_controls(self):
        page = self.read("app/templates/tutorial/index.html")
        route = self.read("app/routes/tutorial_routes.py")
        css = self.read("app/static/css/main.css")
        self.assertEqual(len(re.findall(r'^    \("', route, re.MULTILINE)), 13)
        self.assertIn("tutorial_icons = {1:", page)
        self.assertIn("13:'guild-sigil'", page)
        for sprite in ("guild-sigil", "building-tavern", "expedition-map", "dungeon-gate", "building-docks"):
            self.assertTrue((ROOT / f"app/static/assets/desktop/sprites/64/{sprite}.png").is_file())
        self.assertIn(".tutorial-actions > a, .tutorial-actions > form button { min-width: 40px; min-height: 40px; }", css)

    def test_updates_prioritize_version_channel_and_manual_verification(self):
        page = self.read("app/templates/updates.html")
        route = self.read("app/routes/update_routes.py")
        self.assertIn("updates-version-summary", page)
        self.assertIn("Canal {{ installed_channel or 'não configurado' }}", page)
        self.assertIn('"installed_channel": installed_channel', route)
        self.assertIn("Origem: GitHub Releases", page)
        self.assertIn(">Verificar</button>", page)
        self.assertNotIn("updates/install-release", page)
        self.assertNotIn("updates/apply-local", page)

    def test_prepared_activity_separates_team_and_reinforcements_with_real_class_icons(self):
        component = self.read("app/templates/components/regional_offer_actions.html")
        service = self.read("app/services/regional_cycle_service.py")
        css = self.read("app/static/css/desktop-evolution.css")
        self.assertIn('aria-labelledby="prepared-team-title-{{ offer.id }}"', component)
        self.assertIn('aria-labelledby="reinforcement-team-title-{{ offer.id }}"', component)
        self.assertIn('value="{{ mercenary.id }}" checked', component)
        self.assertIn("offer.prepared_mercenary_ids", component)
        self.assertIn("mercenary.class_icon_path", component)
        self.assertIn("annotate_mercenary_display(mercenary)", service)
        self.assertIn("selectinload(Mercenary.mercenary_class)", service)
        self.assertIn("grid-template-columns: 18px 36px minmax(0,1fr) auto", css)
        self.assertIn("min-height: 48px", css)
        self.assertIn("width: min(760px, calc(100vw - 32px))", css)
        self.assertIn("max-height: calc(100dvh - 32px)", css)


if __name__ == "__main__":
    unittest.main()
