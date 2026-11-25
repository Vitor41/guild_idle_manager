from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GatheringPollingContractTests(unittest.TestCase):
    def test_capacity_state_and_accessible_progress_are_present_for_polling_transitions(self):
        template = (ROOT / "app/templates/gathering/index.html").read_text(encoding="utf-8-sig")
        self.assertIn('data-gathering-capacity-state role="status"', template)
        self.assertIn('data-gathering-warehouse-progress aria-label="Armazém: {{ used }} de {{ capacity }}"', template)
        self.assertIn("evolution-status--paused", template)
        self.assertIn("evolution-status--active", template)


if __name__ == "__main__":
    unittest.main()
