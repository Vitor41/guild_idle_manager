import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.routes.regional_routes import _portal_drop_preview
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
            '{{ drop_preview(drops, available, chance_basis, title) }}'
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
        self.assertEqual(preview["chance_basis"], "base")
        self.assertEqual(len(preview["drops"]), 4)
        self.assertEqual(preview["drops"][0]["chance_percent"], 12)
        self.assertEqual(preview["drops"][0]["quantity_unit"], "instância(s)")
        self.assertEqual(preview["drops"][0]["min_quantity"], 1)
        self.assertEqual(preview["drops"][0]["max_quantity"], 2)
        self.assertEqual(preview["drops"][0]["icon_path"], "/assets/item.png")
        self.assertEqual(preview["drops"][1]["quantity_unit"], "unidade(s)")

        html = self.render.render(drops=preview["drops"], available=True, chance_basis=preview["chance_basis"], title="")
        self.assertIn("Drops · chance base", html)
        self.assertIn("Ver todos (4)", html)
        self.assertIn("Recolher drops", html)
        self.assertIn("Iteme 0", html)
        self.assertIn("Iteme 3", html)
        self.assertIn("12%", html)
        self.assertIn("×1–2", html)
        self.assertIn('aria-label="Chance base: 12%"', html)
        self.assertIn('aria-label="Quantidade: 1 a 2 instância(s)"', html)
        self.assertIn("instância(s)", html)
        self.assertNotIn("12% base", html)
        self.assertNotIn("Qtd. base", html)
        self.assertEqual(html.count('class="loot-preview-item"'), 4)
        initial_list = html.split("</ul>", 1)[0]
        self.assertIn("Iteme 0", initial_list)
        self.assertNotIn("Iteme 3", initial_list)

    def test_effective_chance_uses_plain_drops_heading_without_frontend_recalculation(self):
        drop = {
            "display_name": "Iteme efetivo", "rarity_class": "rare", "rarity_label": "Raro",
            "icon_path": None, "chance_percent": 18, "chance_label": "efetiva",
            "min_quantity": 1, "max_quantity": 1, "quantity_unit": "unidade(s)",
        }
        html = self.render.render(drops=[drop], available=True, chance_basis="effective", title="")

        self.assertIn(">Drops</strong>", html)
        self.assertIn("data-chance-basis=\"effective\"", html)
        self.assertIn("18%", html)
        self.assertIn("efetiva", html)
        self.assertIn('aria-label="Chance: 18% efetiva"', html)
        self.assertNotIn("Drops · chance base", html)

    def test_portal_preview_keeps_conditional_chance_semantics_from_snapshot(self):
        summary = {
            "portal_loot": {
                "roll_model": "one_100_point_roll;exclusive_rarity_bands;no_guaranteed_equipment",
                "entries": [{
                    "item_template_id": 8,
                    "chance_percent": 14,
                    "quantity": 1,
                    "item_snapshot": {
                        "id": 8, "item_type": "equipment", "name": "Lança do Portal",
                        "rarity": "rare", "equipment_slot": "spear",
                    },
                }],
            },
        }
        with patch("app.routes.regional_routes.get_item_icon_path", return_value="/assets/spear.png"):
            preview = _portal_drop_preview(None, summary)

        self.assertTrue(preview["drop_preview_available"])
        self.assertEqual(preview["drop_chance_basis"], "conditional")
        self.assertEqual(preview["visible_drops"][0]["chance_label"], "após sucesso")
        html = self.render.render(
            drops=preview["visible_drops"], available=True,
            chance_basis=preview["drop_chance_basis"], title="Loot do portal",
        )
        self.assertIn("Loot do portal", html)
        self.assertIn("14%", html)
        self.assertIn("após sucesso", html)
        self.assertIn('aria-label="Chance condicional: 14% após sucesso"', html)
        self.assertNotIn("Drops · chance base", html)

        unknown_model = _portal_drop_preview(None, {"portal_loot": {
            "roll_model": "unknown", "entries": summary["portal_loot"]["entries"],
        }})
        self.assertFalse(unknown_model["drop_preview_available"])

    def test_empty_data_and_inconsistent_active_rows_have_distinct_states(self):
        empty_preview = build_drop_preview([])
        missing_preview = build_drop_preview(None)
        invalid_preview = build_drop_preview([
            SimpleNamespace(is_active=True, item_template=None, drop_chance=25, min_quantity=1, max_quantity=1)
        ])

        self.assertTrue(empty_preview["available"])
        self.assertEqual(empty_preview["drops"], [])
        self.assertFalse(missing_preview["available"])
        self.assertIsNone(missing_preview["chance_basis"])
        self.assertFalse(invalid_preview["available"])
        empty_html = self.render.render(drops=[], available=True, chance_basis=empty_preview["chance_basis"], title="")
        missing_html = self.render.render(drops=[], available=False, chance_basis=None, title="")
        self.assertIn("Somente recompensa fixa", empty_html)
        self.assertIn("Drops não registrados", missing_html)
        self.assertNotIn("Somente recompensa fixa", missing_html)


if __name__ == "__main__":
    unittest.main()
