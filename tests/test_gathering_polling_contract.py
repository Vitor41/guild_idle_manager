from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GatheringPollingContractTests(unittest.TestCase):
    def test_f12_free_target_catalog_and_team_states_have_direct_partial_and_polling_paths(self):
        template = (ROOT / "app/templates/gathering/index.html").read_text(encoding="utf-8-sig")
        base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8-sig")
        main = (ROOT / "app/static/js/main.js").read_text(encoding="utf-8-sig")
        script = (ROOT / "app/static/js/gathering-cycle.js").read_text(encoding="utf-8-sig")

        self.assertIn("{% if assignment %}", template)
        self.assertIn("Posto disponível", template)
        self.assertIn("Próximo alvo disponível:", template)
        self.assertIn("Nenhum material disponível para este posto", template)
        self.assertIn("O alvo desta designação não tem um material comum ativo", template)
        self.assertIn("Não há mercenários disponíveis", template)
        self.assertIn("data-gathering-status-url", template)
        self.assertIn("data-gathering-catalog-warning", template)
        self.assertIn("catalog_unavailable", template)
        self.assertIn("/js/gathering-cycle.js", base)
        self.assertIn('document.addEventListener("DOMContentLoaded", window.initializeGatheringCycles)', script)
        self.assertIn("window.initializeGatheringCycles?.()", main)
        self.assertIn("window.setInterval(refreshGatheringStatus, 15000)", script)

    def test_capacity_state_and_accessible_progress_are_present_for_polling_transitions(self):
        template = (ROOT / "app/templates/gathering/index.html").read_text(encoding="utf-8-sig")
        self.assertIn('data-gathering-capacity-state role="status"', template)
        self.assertIn('data-gathering-warehouse-progress aria-label="Armazém: {{ used }} de {{ capacity }}"', template)
        self.assertIn("evolution-status--paused", template)
        self.assertIn("evolution-status--active", template)


if __name__ == "__main__":
    unittest.main()
