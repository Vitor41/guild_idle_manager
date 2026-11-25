from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Ml057ResidualContractTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_prepared_start_preserves_authoritative_team_eligibility(self):
        component = self.read("app/templates/components/regional_offer_actions.html")
        script = self.read("app/static/js/regional-supply.js")
        self.assertIn('data-prepared-team-can-start="{{ \'true\' if offer.prepared_team_can_start else \'false\' }}"', component)
        self.assertIn("preparedMembersRetained", script)
        self.assertIn("preparedTeamCanStart", script)
        self.assertIn("teamAvailable && preparedTeamCanStart && preparedMembersRetained && validPartySize", script)

    def test_report_dialog_grid_only_applies_while_native_dialog_is_open(self):
        css = self.read("app/static/css/desktop-evolution.css")
        self.assertIn('.evolution-dialog[id^="report-"][open] { display: grid;', css)
        self.assertNotIn('.evolution-dialog[id^="report-"] { display: grid;', css)


if __name__ == "__main__":
    unittest.main()
