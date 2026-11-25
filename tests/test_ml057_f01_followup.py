from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Ml057F01FollowupTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_mobile_header_keeps_stamina_balance_visible_after_compact_hide_rule(self):
        base = self.read("app/templates/base.html")
        theme = self.read("app/static/css/desktop-theme.css")
        hide_rule = 'body[data-app-mode="desktop"] .game-topbar > .topbar-back-button > span:last-child { display: none; }'
        show_rule = 'body[data-app-mode="desktop"] .offline-action .topbar-back-button > .offline-stamina-value { display: block; flex: 1 0 100%;'
        self.assertIn('class="offline-stamina-value" data-offline-stamina-value', base)
        self.assertIn("Estamina {{ stamina_label }} / 8h", base)
        self.assertIn(hide_rule, theme)
        self.assertIn(show_rule, theme)
        self.assertLess(theme.index(hide_rule), theme.index(show_rule))
        self.assertIn(".offline-action .topbar-back-button { display: flex; flex-wrap: wrap;", theme)

    def test_absence_report_links_have_forty_pixel_targets_and_visible_focus(self):
        base = self.read("app/templates/base.html")
        theme = self.read("app/static/css/desktop-theme.css")
        self.assertIn('href="/regional#events-title">Abrir Vigília e histórico</a>', base)
        self.assertIn('href="/guide#idle">Guia do Jogo</a>', base)
        self.assertIn(".offline-regional-context a,", theme)
        self.assertIn(".offline-summary__notice a { display: inline-flex; align-items: center; min-width: 40px; min-height: 40px;", theme)
        self.assertIn(".offline-summary__notice a:focus-visible { outline: 3px solid var(--gold-2); outline-offset: 2px; }", theme)


if __name__ == "__main__":
    unittest.main()
