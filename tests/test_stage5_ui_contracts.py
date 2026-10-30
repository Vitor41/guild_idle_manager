from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Stage5UiContractTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_startup_modals_are_queued_in_offline_tutorial_rebellion_order(self):
        main = self.read("app/static/js/main.js")
        evolution = self.read("app/static/js/evolution-dialogs.js")
        self.assertIn("window.GIMStartupModalQueue = startupModalQueue", main)
        self.assertIn("startupModalQueue.enqueue(offlineDialog, 0)", main)
        self.assertIn("startupModalQueue.enqueue(tutorialInvite, 1)", main)
        self.assertIn("window.GIMStartupModalQueue?.enqueue(dialog, 2)", evolution)
        self.assertIn('next.addEventListener("close"', main)
        self.assertIn("pending.sort((left, right) => left.priority - right.priority", main)
        self.assertNotIn("dialog.showModal()", evolution.split('document.querySelectorAll("dialog[data-regional-rebellion-auto-open]")', 1)[1].split("document.querySelectorAll(\".evolution-page img\")", 1)[0])

    def test_offline_dialog_scrolls_body_and_keeps_acknowledgement_reachable(self):
        css = self.read("app/static/css/main.css")
        dialog = css.split(".offline-dialog {", 1)[1].split("}", 1)[0]
        body = css.split(".offline-dialog > .offline-summary {", 1)[1].split("}", 1)[0]
        self.assertIn("max-height: calc(100dvh - 24px)", dialog)
        self.assertNotIn("display:", dialog)
        self.assertIn(".offline-dialog:not([open]) { display: none; }", css)
        self.assertIn(".offline-dialog[open] {\n  display: flex;", css)
        self.assertIn("overflow-y: auto", body)
        self.assertIn("min-height: 0", body)
        self.assertIn("flex: 0 0 auto", css.split(".offline-dialog > .confirmation-dialog__header,", 1)[1].split("}", 1)[0])
        self.assertIn(".offline-dialog > .confirmation-dialog__actions { padding-bottom:", css)

    def test_codex_detail_destination_and_filters_keep_both_selections(self):
        template = self.read("app/templates/codex/index.html")
        route = self.read("app/routes/codex_routes.py")
        self.assertIn("&amp;trail={{ selected_trail }}", template)
        self.assertIn("&amp;category={{ selected_category }}", template)
        self.assertIn("&amp;entry={{ entry.id }}#codex-entry-detail", template)
        self.assertIn('id="codex-entry-detail"', template)
        self.assertIn("request.query_params.get(\"category\", \"all\")", route)
        self.assertIn("request.query_params.get(\"trail\", \"all\")", route)
        self.assertIn("selected_codex_entry", route)

    def test_codex_detail_localizes_mythic_and_hides_internal_entry_key(self):
        template = self.read("app/templates/codex/index.html")
        detail = template.split('{% if selected_codex_entry %}', 1)[1].split('{% endif %}', 1)[0]
        self.assertIn("'mythic':'Mítico'", detail)
        self.assertIn("<dt>Categoria</dt>", detail)
        self.assertIn("<dt>Raridade</dt>", detail)
        self.assertNotIn("Identificação", detail)
        self.assertNotIn("selected_codex_entry.key", detail)

    def test_user_facing_labels_do_not_leak_internal_terms(self):
        campaigns = self.read("app/templates/desktop/campaigns.html")
        codex = self.read("app/templates/codex/index.html")
        regional = self.read("app/templates/regional/index.html")
        base = self.read("app/templates/base.html")
        self.assertIsNone(re.search(r"\bsave\b", campaigns, re.IGNORECASE))
        self.assertNotIn("criterion_type", codex)
        self.assertIn("card.criterion_label", codex)
        self.assertNotIn("{{ card.event.status }}", regional)
        self.assertNotIn("{{ card.summary.reason|replace", regional)
        self.assertIn("card.status_label", regional)
        self.assertIn("card.reason_label", regional)

    def test_codex_visual_hierarchy_exposes_campaign_progress_and_discovery_count(self):
        template = self.read("app/templates/codex/index.html")
        css = self.read("app/static/css/main.css")
        self.assertIn('class="dashboard codex-page"', template)
        self.assertIn('class="codex-page-heading"', template)
        self.assertIn("achievement-reliquary.webp", template)
        self.assertIn("achievement-medal.png", template)
        self.assertIn('class="codex-discovery-count"', template)
        self.assertIn('class="codex-achievement-state', template)
        self.assertIn(".codex-page-heading h1", css)
        self.assertIn(".codex-discovery-count", css)
        self.assertIn(".codex-achievement-state", css)

    def test_codex_art_legendary_rewards_and_responsive_http_structure(self):
        template = self.read("app/templates/codex/index.html")
        service = self.read("app/services/achievement_service.py")
        route = self.read("app/routes/codex_routes.py")
        css = self.read("app/static/css/main.css")
        self.assertIn('href="#codex-legendary"', template)
        self.assertIn('id="codex-legendary"', template)
        self.assertIn("legendary_achievement_cards", template)
        self.assertIn('entry.icon_path', template)
        self.assertIn('aria-valuenow="{{ achievement.progress }}"', template)
        self.assertIn('aria-label="Filtrar Códex"', template)
        self.assertIn("'legendary':'Lendário'", template)
        self.assertIn('"item_rarity_label": rarity_label(item_template.rarity)', service)
        self.assertIn("reward.get('item_rarity_label')", route)
        self.assertIn('"legendary_achievement_cards": legendary_achievement_cards', service)
        self.assertIn('assets/desktop/sprites/64/dungeon-gate.png', service)
        self.assertTrue((ROOT / "app/static/assets/desktop/sprites/64/dungeon-gate.png").is_file())
        self.assertIn(".codex-legendary-card.is-ready", css)
        self.assertIn(".codex-page-heading__art", css)
        self.assertIn("@media (max-width: 640px)", css)
        reduced_motion = css.split("@media (prefers-reduced-motion: reduce)", 1)[1].split("\n}", 1)[0]
        self.assertIn(".codex-anchor-tabs { scroll-behavior: auto;", reduced_motion)
        self.assertIn("html { scroll-behavior: auto !important; }", reduced_motion)

    def test_offline_report_names_processed_vigils(self):
        template = self.read("app/templates/base.html")
        clock_guard_test = self.read("tests/test_clock_guard.py")
        self.assertIn("{{ offline.regional_context.cycles_processed }} Vigília{% if offline.regional_context.cycles_processed != 1 %}s", template)
        self.assertIn('report["regional_context"]["cycles_processed"], 2', clock_guard_test)

    def test_group_supply_appears_in_contract_dungeon_and_portal_preparation_only(self):
        mission = self.read("app/templates/missions/index.html")
        dungeon = self.read("app/templates/dungeons/index.html")
        regional = self.read("app/templates/regional/index.html")
        base = self.read("app/templates/base.html")
        mission_service = self.read("app/services/mission_service.py")
        self.assertNotIn('class="supply-preparation"', mission)
        self.assertNotIn('name="supply"', mission)
        self.assertIn('class="supply-preparation"', dungeon)
        self.assertIn('class="supply-preparation"', regional)
        self.assertIn("card.supply_quote.cost_gold", regional)
        self.assertIn('data-supply-quote-url="/dungeons/supply-quote"', dungeon)
        self.assertNotIn("dungeon.supply_quotes.items()", dungeon)
        self.assertIn('path=\'/js/regional-supply.js\'', base)
        self.assertIn("selected_start_mercenary_ids", regional)
        self.assertIn("selected_start_supply", regional)
        self.assertIn("data-supply-quote-url", regional)
        self.assertIn("/offers/{offer_id}/supply-quote", self.read("app/routes/regional_routes.py"))
        dungeon_routes = self.read("app/routes/dungeon_routes.py")
        self.assertIn('@router.post("/supply-quote")', dungeon_routes)
        regional_supply_script = self.read("app/static/js/regional-supply.js")
        self.assertIn('method: "POST"', regional_supply_script)
        self.assertIn('select[name="run_multiplier"]', regional_supply_script)
        self.assertIn("allow_regional_supply: bool = False", mission_service)
        self.assertIn("not allow_regional_supply", mission_service)
        self.assertIn('{"gathering", "long_idle"}', mission_service)

    def test_selected_supply_is_preserved_during_quote_and_server_revalidates_submit(self):
        script = self.read("app/static/js/regional-supply.js")
        pending = script.split("const refreshQuote = async () => {", 1)[1].split("try {", 1)[0]
        pending_with_team = pending.split("return;", 1)[1]
        self.assertIn("supply.disabled = false", pending_with_team)
        self.assertNotIn("supply.disabled = true", pending_with_team)

        unavailable = script.split('if (!response.ok || !quote.available) {', 1)[1].split("return;", 1)[0]
        self.assertIn('quoteState = "unavailable"', unavailable)
        self.assertIn("supply.disabled = !supply.checked", unavailable)
        self.assertNotIn("supply.checked = false", unavailable)
        self.assertIn('quoteState = "available"', script)
        self.assertNotIn("supply.checked = wanted", script)

        submit_guard = script.split('form.addEventListener("submit",', 1)[1].split("});", 1)[0]
        self.assertIn('supply.checked && quoteState === "unavailable"', submit_guard)
        self.assertIn("event.preventDefault()", submit_guard)
        self.assertIn('supply.addEventListener("change"', script)
        self.assertIn("prepare_supply_snapshot(", self.read("app/services/dungeon_service.py"))
        self.assertIn('supply_selected=(form.get("supply") or [""])[0] == "1"', self.read("app/routes/dungeon_routes.py"))

    def test_blacksmith_shows_effective_craft_cost_and_explains_when_it_changes(self):
        blacksmith = self.read("app/templates/blacksmith/index.html")
        guide = self.read("app/templates/guide/index.html")
        service = self.read("app/services/crafting_service.py")
        self.assertIn("Total ao fabricar: {{ recipe.effective_gold_cost }} ouro", blacksmith)
        self.assertIn("o valor da receita é sempre o exato débito", blacksmith)
        self.assertIn("total de ouro de cada receita aparece na oficina", guide)
        self.assertIn("recipe.effective_gold_cost = _effective_recipe_gold_cost", service)
        self.assertIn("resources.gold -= gold_cost", service)

    def test_market_quota_is_explained_and_disabled_material_sales_name_the_blocker(self):
        template = self.read("app/templates/market/index.html")
        guide = self.read("app/templates/guide/index.html")
        css = self.read("app/static/css/main.css")
        self.assertIn("Materiais: {{ material_sale_quota.used }}/{{ material_sale_quota.limit }} unidades usadas", template)
        self.assertIn("janela móvel", template)
        self.assertIn("Próximas unidades liberadas a partir de", template)
        self.assertIn("todos os espaços de venda estão ocupados", template)
        self.assertIn("cota de materiais esgotada", template)
        self.assertIn("L5–9: 30; L10–14: 35; L100: 125", guide)
        self.assertIn("completar 24 horas", guide)
        self.assertIn("overflow-wrap: anywhere", css)


if __name__ == "__main__":
    unittest.main()
