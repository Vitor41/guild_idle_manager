from pathlib import Path
import unittest

from app.desktop.update_launcher import classify_launcher_result


ROOT = Path(__file__).resolve().parents[1]


class LauncherAndEquipmentUiContractTests(unittest.TestCase):
    def test_equipment_swap_ui_requires_a_specific_double_slot_item(self):
        template = (ROOT / "app/templates/mercenaries/detail.html").read_text(encoding="utf-8")
        script = (ROOT / "app/static/js/equipment-details.js").read_text(encoding="utf-8")
        route = (ROOT / "app/routes/mercenary_routes.py").read_text(encoding="utf-8")

        self.assertIn("data-replacement-required", template)
        self.assertIn("data-replacement-candidate-ids", template)
        self.assertIn("name=\"replacement_item_instance_id\"", template)
        self.assertIn("candidateIds.includes(Number(option.value))", script)
        self.assertIn('form.get("replacement_item_instance_id") or None', route)

    def test_campaign_update_page_only_checks_and_guides_to_launcher(self):
        template = (ROOT / "app/templates/updates.html").read_text(encoding="utf-8")
        route = (ROOT / "app/routes/update_routes.py").read_text(encoding="utf-8")
        self.assertIn("Verificar atualizações", template)
        self.assertIn("Feche a campanha e abra o launcher pelo atalho para atualizar.", template)
        self.assertNotIn("/updates/install-release", template)
        self.assertNotIn("/updates/apply-local", template)
        self.assertNotIn("def install_verified_release_update", route)
        self.assertNotIn("def apply_local_checkout_update", route)
        self.assertIn("download=False", route)

    def test_launcher_routes_expected_states_and_supports_failure_recovery(self):
        self.assertEqual(classify_launcher_result({"available": False, "query_enabled": True}, None), "current")
        self.assertEqual(classify_launcher_result({"available": True}, object()), "update-ready")
        self.assertEqual(classify_launcher_result({"failed": True}, None), "recoverable-error")
        self.assertEqual(classify_launcher_result({"query_enabled": False}, None), "unconfigured")
        source = (ROOT / "app/desktop/update_launcher.py").read_text(encoding="utf-8")
        self.assertIn("check_for_update(", source)
        self.assertIn("progress_callback=report_progress", source)
        self.assertIn("cancel_event=self.cancel_event", source)
        self.assertIn("prepared_file_is_valid(prepared, channel)", source)
        self.assertIn("Jogar versão instalada", source)
        self.assertIn("required_update", source)
        self.assertIn("None if self.required_update", source)
        self.assertIn("update-launcher.log", source)

    def test_equipment_details_are_accessible_and_reflow_without_hover(self):
        template = (ROOT / "app/templates/mercenaries/detail.html").read_text(encoding="utf-8")
        base_template = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
        script = (ROOT / "app/static/js/equipment-details.js").read_text(encoding="utf-8")
        main_script = (ROOT / "app/static/js/main.js").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")
        self.assertIn("aria-expanded=\"false\"", template)
        self.assertIn("aria-controls=\"{{ details_id }}\"", template)
        self.assertIn("data-equipment-details-close", template)
        self.assertIn("/js/equipment-details.js", base_template)
        self.assertNotIn("/js/equipment-details.js", template)
        self.assertIn("window.initializeEquipmentDetails?.(currentMain)", main_script)
        self.assertIn("window.initializeEquipmentDetails = initializeEquipmentDetails", script)
        self.assertIn("pointerenter", script)
        self.assertIn("event.key === \"Escape\"", script)
        self.assertIn("event.pointerType === \"mouse\"", script)
        self.assertIn("matchMedia(\"(max-width: 760px)\")", script)
        self.assertIn(".equipment-details.is-open", css)
        self.assertIn("@media (max-width: 760px)", css)

    def test_guide_export_component_exposes_progress_success_and_retry_states(self):
        template = (ROOT / "app/templates/guide/index.html").read_text(encoding="utf-8")
        script = (ROOT / "app/static/js/guide.js").read_text(encoding="utf-8")
        self.assertIn("role=\"progressbar\"", template)
        self.assertIn("role=\"status\"", template)
        self.assertIn("exportButton.disabled = true", script)
        self.assertIn("aria-busy", script)
        self.assertIn("Guia salvo em:", script)
        self.assertIn("Guia salvo como", script)
        self.assertIn("Tente novamente", script)

    def test_market_keeps_sale_controls_and_estimates_without_the_rarity_table(self):
        template = (ROOT / "app/templates/market/index.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")
        service = (ROOT / "app/services/market_service.py").read_text(encoding="utf-8")
        self.assertNotIn("Tempo base por raridade", template)
        self.assertIn("data-market-estimator", template)
        self.assertIn("data-market-quantity", template)
        self.assertIn("data-market-fill-max", template)
        self.assertIn("market-sale-estimate", template)
        self.assertIn("market-material-form .market-sell-button { grid-column: 3; grid-row: 2", css)
        self.assertIn(".market-item-info > strong { display: block", css)
        self.assertNotIn("-webkit-line-clamp: 2", css)
        self.assertIn("@media (max-width: 600px)", css)
        self.assertIn("_sale_duration_seconds", service)



if __name__ == "__main__":
    unittest.main()
