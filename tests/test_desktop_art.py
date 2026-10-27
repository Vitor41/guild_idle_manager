import json
import re
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
