import re
import unittest
from pathlib import Path

from app.services.admin_service import parse_dungeon_form, parse_mission_form


ROOT = Path(__file__).resolve().parents[1]


def mission_form(**overrides):
    form = {
        "name": "Missão de teste", "description": "Teste", "difficulty": "heroic",
        "level_band": "201-250", "mission_type": "combat",
        "duration_hours": "1", "duration_minutes": "2", "duration_seconds": "3",
        "base_gold_reward": "100", "base_xp_reward": "200", "base_success_chance": "70",
        "min_party_size": "1", "max_party_size": "3", "required_guild_level": "1",
        "required_min_mercenary_level": "201", "required_building_type": "",
        "required_building_level": "0", "recommended_level": "210", "recommended_power": "900",
        "gathering_family": "", "profession_code": "", "is_active": "on",
    }
    form.update(overrides)
    return form


class AdminMissionConfigurationTests(unittest.TestCase):
    def test_current_level_bands_and_difficulties_are_accepted(self):
        parsed = parse_mission_form(mission_form())
        self.assertEqual(parsed["level_band"], "201-250")
        self.assertEqual(parsed["difficulty"], "heroic")
        self.assertEqual(parsed["recommended_level"], 210)

    def test_long_missions_always_use_one_to_five_party(self):
        parsed = parse_mission_form(mission_form(
            mission_type="long_idle", min_party_size="2", max_party_size="2",
        ))
        self.assertEqual((parsed["min_party_size"], parsed["max_party_size"]), (1, 5))
        self.assertIsNone(parsed["gathering_family"])

    def test_heroic_endgame_dungeon_and_tier_eight_are_accepted(self):
        form = {
            "name": "Masmorra de teste", "description": "Teste", "content_type": "boss",
            "difficulty": "legendary", "level_band": "301-350", "recommended_level": "320",
            "biome": "abyss", "duration_hours": "2", "duration_minutes": "0", "duration_seconds": "0",
            "base_gold_reward": "1000", "base_xp_reward": "2000", "base_success_chance": "40",
            "min_party_size": "3", "max_party_size": "5", "required_guild_level": "1",
            "required_min_mercenary_level": "301", "required_building_type": "scouts",
            "required_building_level": "1", "required_total_power": "5000", "required_class_code": "",
            "required_tank_count": "1", "required_support_count": "1", "required_damage_count": "1",
            "required_equipment_tier": "8", "is_active": "on",
        }
        parsed = parse_dungeon_form(form)
        self.assertEqual(parsed["difficulty"], "legendary")
        self.assertEqual(parsed["level_band"], "301-350")
        self.assertEqual(parsed["required_equipment_tier"], 8)


class AdminFormCoverageTests(unittest.TestCase):
    def test_gameplay_forms_expose_all_editable_fields(self):
        forms = {
            "mission": ("edit_mission.html", {
                "name", "description", "difficulty", "level_band", "mission_type", "recommended_level",
                "recommended_power", "gathering_family", "profession_code", "duration_hours",
                "duration_minutes", "duration_seconds", "base_gold_reward", "base_xp_reward",
                "base_success_chance", "min_party_size", "max_party_size", "required_guild_level",
                "required_min_mercenary_level", "required_building_type", "required_building_level", "is_active",
            }),
            "item": ("item_form.html", {
                "name", "description", "item_type", "rarity", "level_band", "material_family",
                "favored_class_code", "favored_attribute", "icon_group", "item_level", "tier",
                "base_sell_value", "equipment_slot", "required_level", "bonus_power", "bonus_vitality",
                "bonus_agility", "bonus_intelligence", "bonus_luck", "bonus_armor", "rng_bonus_min",
                "rng_bonus_max", "is_active",
            }),
            "dungeon": ("dungeon_form.html", {
                "name", "description", "content_type", "difficulty", "level_band", "recommended_level",
                "biome", "duration_hours", "duration_minutes", "duration_seconds", "base_gold_reward",
                "base_xp_reward", "base_success_chance", "min_party_size", "max_party_size",
                "required_guild_level", "required_min_mercenary_level", "required_building_type",
                "required_building_level", "required_total_power", "required_class_code",
                "required_tank_count", "required_support_count", "required_damage_count",
                "required_equipment_tier", "is_active",
            }),
        }
        for label, (filename, expected) in forms.items():
            source = (ROOT / "app" / "templates" / "admin" / filename).read_text(encoding="utf-8")
            names = set(re.findall(r'name=["\']([^"\']+)', source))
            self.assertEqual(expected - names, set(), label)


if __name__ == "__main__":
    unittest.main()
