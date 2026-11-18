import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.drop_preview_service import build_drop_preview


class DropPreviewServiceTests(unittest.TestCase):
    def setUp(self):
        template_root = Path(__file__).resolve().parents[1] / "app" / "templates"
        self.environment = Environment(
            loader=FileSystemLoader(template_root),
            autoescape=select_autoescape(("html",)),
        )
        self.environment.globals["url_for"] = lambda _endpoint, path: f"/static{path}"
        self.render = self.environment.from_string(
            '{% from "components/drop_preview.html" import drop_preview %}'
            '{{ drop_preview(drops, available, note) }}'
        )

    def test_active_entries_keep_resolver_chance_quantity_and_icon(self):
        rows = []
        for index in range(4):
            item = SimpleNamespace(
                is_active=True,
                item_type="equipment" if index == 0 else "material",
                rarity="rare" if index == 0 else "common",
                name=f"Iteme {index}",
            )
            rows.append(SimpleNamespace(
                is_active=True, item_template=item, drop_chance=12 + index,
                min_quantity=1, max_quantity=index + 2,
            ))
        rows.append(SimpleNamespace(is_active=False, item_template=None))

        with patch("app.services.drop_preview_service.get_item_icon_path", return_value="/assets/item.png"):
            preview = build_drop_preview(rows)

        self.assertTrue(preview["available"])
        self.assertEqual(len(preview["drops"]), 4)
        self.assertEqual(preview["drops"][0]["chance_percent"], 12)
        self.assertEqual(preview["drops"][0]["quantity_unit"], "instância(s)")
        self.assertEqual(preview["drops"][0]["min_quantity"], 1)
        self.assertEqual(preview["drops"][0]["max_quantity"], 2)
        self.assertEqual(preview["drops"][0]["icon_path"], "/assets/item.png")
        self.assertEqual(preview["drops"][1]["quantity_unit"], "unidade(s)")

        html = self.render.render(drops=preview["drops"], available=True, note="Chance-base após sucesso.")
        self.assertIn("Ver todos os 4 drops", html)
        self.assertIn("Iteme 0", html)
        self.assertIn("Iteme 3", html)
        self.assertIn("12% base", html)
        self.assertIn("instância(s)", html)

    def test_empty_data_and_inconsistent_active_rows_have_distinct_states(self):
        empty_preview = build_drop_preview([])
        missing_preview = build_drop_preview(None)
        invalid_preview = build_drop_preview([
            SimpleNamespace(is_active=True, item_template=None, drop_chance=25, min_quantity=1, max_quantity=1)
        ])

        self.assertTrue(empty_preview["available"])
        self.assertEqual(empty_preview["drops"], [])
        self.assertFalse(missing_preview["available"])
        self.assertFalse(invalid_preview["available"])
        empty_html = self.render.render(drops=[], available=True, note="")
        missing_html = self.render.render(drops=[], available=False, note="")
        self.assertIn("Apenas recompensas-base", empty_html)
        self.assertIn("Informações de drops indisponíveis", missing_html)


if __name__ == "__main__":
    unittest.main()
