import json
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
ART_ROOT = STATIC / "assets" / "desktop"


class DesktopArtIntegrationTests(unittest.TestCase):
    def test_desktop_ui_asset_references_resolve_through_the_art_manifest(self):
        manifest = json.loads((ART_ROOT / "manifest.json").read_text(encoding="utf-8"))
        script = (STATIC / "js" / "desktop-art.js").read_text(encoding="utf-8")
        navigation_routes = re.findall(r'\["(/[^"\n]+)",\s*"([a-z0-9_-]+)"\]', script)

        self.assertGreaterEqual(len(navigation_routes), 15)
        for route, sprite_key in navigation_routes:
            with self.subTest(route=route, sprite=sprite_key):
                self.assertIn(sprite_key, manifest["sprites"])
                paths = manifest["sprites"][sprite_key]["paths"]
                sprite_path = paths.get("64") or paths.get("128")
                self.assertIsNotNone(sprite_path)
                self.assertTrue((ART_ROOT / sprite_path).is_file())

        for illustration_key in ("guild_hall", "tavern", "dungeon"):
            with self.subTest(illustration=illustration_key):
                self.assertTrue((ART_ROOT / manifest["assets"][illustration_key]["path"]).is_file())

    def test_desktop_art_only_loads_from_desktop_views(self):
        base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
        campaigns = (ROOT / "app" / "templates" / "desktop" / "campaigns.html").read_text(encoding="utf-8")

        self.assertIn("request.app.state.app_mode == 'desktop'", base)
        self.assertIn("/css/desktop-art.css", base)
        self.assertIn("/js/desktop-art.js", base)
        self.assertIn('data-app-mode="desktop"', campaigns)
        self.assertIn("/js/desktop-art.js", campaigns)

    def test_semantic_entity_maps_have_matching_art_and_keep_names_in_templates(self):
        manifest = json.loads((ART_ROOT / "manifest.json").read_text(encoding="utf-8"))
        script = (STATIC / "js" / "desktop-art.js").read_text(encoding="utf-8")
        required_keys = {
            "class-warrior", "class-archer", "class-rogue", "class-mage", "class-cleric",
            "building-housing", "building-tavern", "building-blacksmith", "building-market", "building-docks",
            "item-sword", "item-shield", "item-ring", "material-wood", "material-ore", "resource-gold",
            "resource-crystal", "status-ready", "status-progress", "status-locked", "status-failed",
        }
        self.assertTrue(required_keys.issubset(manifest["sprites"]))
        for marker in ("data-desktop-class", "data-desktop-building", "data-desktop-item-group", "data-desktop-item-slot", "data-desktop-resource", ".status-badge"):
            self.assertIn(marker, script)

        template_requirements = {
            "mercenaries/index.html": ("data-desktop-class=", "{{ mercenary.class_label }}"),
            "mercenaries/detail.html": ("data-desktop-class=", "{{ mercenary.name }}"),
            "classes/index.html": ("data-desktop-class=", "{{ card.class.view_label }}"),
            "buildings/index.html": ("data-desktop-building=", "{{ building.building_template.name }}"),
            "inventory/index.html": ("data-desktop-item-group=", "{{ inventory_item.display_name }}"),
            "market/index.html": ("data-desktop-item-group=", "{{ item.item_template.name }}"),
        }
        for relative_path, markers in template_requirements.items():
            with self.subTest(template=relative_path):
                source = (ROOT / "app" / "templates" / relative_path).read_text(encoding="utf-8")
                for marker in markers:
                    self.assertIn(marker, source)

    def test_item_semantics_follow_manifest_priority_and_resolve_groups_without_fallback_data(self):
        manifest = json.loads((ART_ROOT / "manifest.json").read_text(encoding="utf-8"))
        script = (STATIC / "js" / "desktop-art.js").read_text(encoding="utf-8")
        maps = manifest["icon_maps"]

        expected_groups = {
            "heavy_armor": "item-chest",
            "ancient_relic": "material-relic",
            "dungeon_key": "resource-dungeon-key",
        }
        for group, sprite in expected_groups.items():
            with self.subTest(group=group):
                self.assertEqual(maps["item_icon_groups"][group], sprite)
                self.assertIn(sprite, manifest["sprites"])

        self.assertEqual(maps["equipment_slots"]["off_hand"], "item-dagger")
        self.assertIn("iconMaps.item_icon_groups?.[group]", script)
        self.assertIn("iconMaps.material_families?.[family]", script)
        self.assertIn("iconMaps.equipment_slots?.[slot]", script)
        group_lookup = script.index("iconMaps.item_icon_groups?.[group]")
        family_lookup = script.index("iconMaps.material_families?.[family]")
        slot_lookup = script.index("iconMaps.equipment_slots?.[slot]")
        self.assertLess(group_lookup, family_lookup)
        self.assertLess(family_lookup, slot_lookup)
        self.assertNotIn("const itemAliases", script)
        self.assertNotIn("const slotAliases", script)

        # A group-only item resolves from the manifest's first candidate; empty family and slot
        # values leave the map lookup intact and require no JS-side group alias.
        group_only_candidates = [maps["item_icon_groups"].get("heavy_armor"), None, None]
        self.assertEqual(next((key for key in group_only_candidates if key), None), "item-chest")

    def test_server_side_desktop_icons_use_new_manifest_and_web_icons_remain_legacy(self):
        with patch.dict(os.environ, {"APP_MODE": "desktop", "DATABASE_URL": "sqlite:///:memory:"}):
            from app.services import icon_service

        cases = (
            ("heavy_armor", None, None, "item-chest"),
            ("ancient_relic", None, None, "material-relic"),
            ("dungeon_key", None, None, "resource-dungeon-key"),
            (None, "relic", None, "material-relic"),
            (None, None, "off_hand", "item-dagger"),
        )
        with patch("app.services.icon_service.settings", SimpleNamespace(app_mode="desktop")):
            for group, family, slot, sprite_key in cases:
                item = SimpleNamespace(
                    name="fixture",
                    item_type="misc",
                    icon_group=group,
                    material_family=family,
                    equipment_slot=slot,
                )
                with self.subTest(group=group, family=family, slot=slot):
                    icon_path = icon_service.get_item_icon_path(item)
                    self.assertIsNotNone(icon_path)
                    self.assertIn("/assets/desktop/", icon_path)
                    self.assertTrue((ART_ROOT / icon_path.split("/assets/desktop/", 1)[1]).is_file())
                    sprite_paths = json.loads((ART_ROOT / "manifest.json").read_text(encoding="utf-8"))
                    expected_relative = sprite_paths["sprites"][sprite_key]["paths"].get("64") or sprite_paths["sprites"][sprite_key]["paths"]["128"]
                    self.assertEqual(icon_path, f"/assets/desktop/{expected_relative}")

            self.assertEqual(
                icon_service.get_class_icon_path(SimpleNamespace(code="warrior", display_name="Guerreiro", name="Guerreiro")),
                f"/assets/desktop/{sprite_paths['sprites']['class-warrior']['paths']['64']}",
            )
            self.assertEqual(
                icon_service.get_building_icon_path(SimpleNamespace(effect_type="tavern", name="Taverna")),
                f"/assets/desktop/{sprite_paths['sprites']['building-tavern']['paths']['64']}",
            )
            self.assertIsNone(icon_service.get_building_icon_path(SimpleNamespace(effect_type="future_building", name="Nova Construção")))

            for class_code, sprite_key in sprite_paths["icon_maps"]["classes"].items():
                with self.subTest(class_code=class_code):
                    class_path = icon_service.get_class_icon_path(SimpleNamespace(code=class_code))
                    sprite_relative = sprite_paths["sprites"][sprite_key]["paths"].get("64") or sprite_paths["sprites"][sprite_key]["paths"]["128"]
                    self.assertEqual(class_path, f"/assets/desktop/{sprite_relative}")

        fixture = SimpleNamespace(
            name="espada_de_ferro",
            item_type="weapon",
            icon_group="sword",
            material_family=None,
            equipment_slot="main_hand",
        )
        with patch("app.services.icon_service.settings", SimpleNamespace(app_mode="web")):
            legacy_path = icon_service.get_item_icon_path(fixture)
        self.assertTrue(legacy_path and "/assets/desktop/" not in legacy_path)


if __name__ == "__main__":
    unittest.main()
