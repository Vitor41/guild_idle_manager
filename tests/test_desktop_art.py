import json
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from jinja2 import Environment, FileSystemLoader


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

    def test_new_visual_system_and_operation_hierarchy_are_desktop_scoped(self):
        base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
        theme = (STATIC / "css" / "desktop-theme.css").read_text(encoding="utf-8")
        dashboard = (ROOT / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
        missions = (ROOT / "app" / "templates" / "missions" / "index.html").read_text(encoding="utf-8")
        dungeons = (ROOT / "app" / "templates" / "dungeons" / "index.html").read_text(encoding="utf-8")

        self.assertIn("request.app.state.app_mode == 'desktop'", base)
        self.assertIn("/css/desktop-theme.css", base)
        self.assertIn('body[data-app-mode="desktop"]', theme)
        self.assertIn('font-family: "Segoe UI", Tahoma, sans-serif', theme)
        self.assertIn("--teal: #68c3b5", theme)
        self.assertIn("--gold: #e6b965", theme)
        self.assertIn("Gravada a cada ação concluída", base)
        self.assertNotIn('class="desktop-save-state" role="status"', base)
        self.assertIn("desktop-resource-row", dashboard)
        self.assertLess(dashboard.index("desktop-operations-band"), dashboard.index("Fundação da guilda"))
        self.assertIn("desktop-operations-intro", missions)
        self.assertIn("desktop-operations-intro", dungeons)

    def test_desktop_button_hover_and_focus_keep_secondary_and_danger_roles(self):
        theme = (STATIC / "css" / "desktop-theme.css").read_text(encoding="utf-8")

        primary_states = re.search(
            r'body\[data-app-mode="desktop"\] button:not\(\.secondary-button\):not\(\.danger-button\):hover:not\(:disabled\),'
            r'\s*body\[data-app-mode="desktop"\] button:not\(\.secondary-button\):not\(\.danger-button\):focus-visible,',
            theme,
        )
        self.assertIsNotNone(primary_states)
        for selector in (
            '.button-link.secondary:hover',
            '.button-link.secondary:focus-visible',
            '.secondary-button:hover:not(:disabled)',
            '.secondary-button:focus-visible',
            '.danger-button:hover:not(:disabled)',
            '.danger-button:focus-visible',
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, theme)
        self.assertIn('background: #21383b; color: var(--text); filter: none;', theme)
        self.assertIn('background: #653a35; color: #fff0e9; filter: none;', theme)
        self.assertIn('outline-color: var(--teal, #68c3b5)', theme)
        self.assertIn('outline-color: #d17669', theme)

    def test_visual_markup_preserves_web_dashboard_order_and_hides_desktop_panels(self):
        dashboard = (ROOT / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
        missions = (ROOT / "app" / "templates" / "missions" / "index.html").read_text(encoding="utf-8")
        dungeons = (ROOT / "app" / "templates" / "dungeons" / "index.html").read_text(encoding="utf-8")

        self.assertIn("{% if desktop_mode %}\n    <section class=\"desktop-resource-row\"", dashboard)
        self.assertIn("{% if not desktop_mode %}{{ operation_band() }}{% endif %}", dashboard)
        self.assertLess(dashboard.index("<section class=\"dashboard-band\"><h2>Fundação"), dashboard.index("{% if not desktop_mode %}{{ operation_band() }}"))
        self.assertLess(missions.index("{% if request.app.state.app_mode == 'desktop' %}"), missions.index('class="desktop-operations-intro desktop-page-hero"'))
        self.assertIn("{% if request.app.state.app_mode == 'desktop' %}", dungeons)
        self.assertLess(dungeons.index("{% if request.app.state.app_mode == 'desktop' %}"), dungeons.index('class="desktop-operations-intro desktop-page-hero"'))

    def test_web_dashboard_render_keeps_original_hierarchy_without_desktop_shell_theme(self):
        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "templates"), autoescape=True)
        environment.globals["url_for"] = lambda endpoint, **kwargs: "/static/" + str(kwargs.get("path", ""))
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(app_mode="web")),
            url=SimpleNamespace(path="/dashboard"),
            scope={},
            state=SimpleNamespace(_state={}),
        )
        current_user = SimpleNamespace(
            username="Web QA", is_admin=False, confirmation_preferences="{}", tutorial_status="complete"
        )
        context = {
            "request": request,
            "current_user": current_user,
            "guild": SimpleNamespace(name="Guild Web", level=1, xp=0, reputation=0),
            "resources": SimpleNamespace(gold=100, wood=3, ore=2, crystals=1),
            "mission_summary": SimpleNamespace(in_progress=0, awaiting_loot=0, completed=0),
            "dungeon_summary": SimpleNamespace(in_progress=0, awaiting_loot=0, completed=0),
            "building_summary": SimpleNamespace(owned=0, total=9, max_mission_party_size=1, max_run_multiplier=1, mercenary_limit=0),
            "inventory_summary": SimpleNamespace(equipment_count=0, distinct_items=0, total_quantity=0),
            "tavern_summary": SimpleNamespace(is_built=False, special_offer_active=False, apprentice_cost=10),
            "mercenary_summary": SimpleNamespace(total=0, available=0, busy=0),
        }
        markup = environment.get_template("dashboard.html").render(context)

        self.assertNotIn("/css/desktop-theme.css", markup)
        self.assertNotIn('class="desktop-resource-row"', markup)
        self.assertNotIn('class="desktop-operations-band"', markup)
        self.assertLess(markup.index("Fundação da guilda"), markup.index("Expedições"))
        self.assertIn("Madeira 3 · Minério 2 · Cristais 1", markup)

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
