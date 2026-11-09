from random import Random
from itertools import combinations
from contextlib import closing
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models.campaign import CampaignMetadata
from app.models.guild import Guild
from app.models.item import GuildItemInstance, ItemTemplate
from app.services.admin_service import save_admin_item
from app.services import equipment_service


class ML030BonusRulesTests(unittest.TestCase):
    def setUp(self):
        self.rng_patch = patch.object(equipment_service, "randint", side_effect=Random(3030).randint)
        self.choice_patch = patch.object(equipment_service, "choice", side_effect=Random(3031).choice)
        self.sample_patch = patch.object(equipment_service, "sample", side_effect=Random(3032).sample)
        self.create_patch = patch.object(
            equipment_service,
            "create_item_instance",
            side_effect=lambda _db, payload: SimpleNamespace(**payload),
        )
        for active_patch in (self.rng_patch, self.choice_patch, self.sample_patch, self.create_patch):
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def _item(self, rarity):
        template = SimpleNamespace(
            item_type="equipment", equipment_slot="main_hand", rarity=rarity,
            required_level=1, id=1,
            bonus_power=8, bonus_vitality=0, bonus_agility=0,
            bonus_intelligence=0, bonus_luck=0, bonus_armor=0,
            rng_bonus_min=1, rng_bonus_max=999,
        )
        return equipment_service.create_equipment_instance_from_template(None, 1, template)

    def test_rarity_counts_ranges_distinctness_and_strong_guarantees(self):
        for rarity, (minimum, maximum, point_min, point_max) in equipment_service.RARITY_BONUS_RULES.items():
            for _ in range(120):
                item = self._item(rarity)
                rolls = equipment_service.get_item_bonus_rolls(item)
                type_keys = [(roll["kind"], roll["attribute"]) for roll in rolls]
                self.assertEqual(len(type_keys), len(set(type_keys)))
                self.assertGreaterEqual(len(rolls), minimum)
                self.assertLessEqual(len(rolls), maximum)
                strong = [roll for roll in rolls if roll["kind"] == "strong"]
                normal = [roll for roll in rolls if roll["kind"] == "normal"]
                self.assertTrue(all(point_min <= roll["value"] <= point_max for roll in normal))
                self.assertTrue(all(10 <= roll["value"] <= 20 for roll in strong))
                if rarity in {"common", "uncommon", "rare", "epic"}:
                    self.assertEqual(strong, [])
                if rarity == "legendary" and len(rolls) == 7:
                    self.assertGreaterEqual(len(strong), 1)
                if rarity == "mythic":
                    self.assertGreaterEqual(len(strong), 2)
                    if len(rolls) == 10:
                        self.assertEqual({roll["attribute"] for roll in strong}, set(equipment_service.STRONG_BONUS_ATTRIBUTES))

    def test_legacy_pair_is_a_single_fallback_and_new_snapshot_is_not_duplicated(self):
        old = SimpleNamespace(bonus_rolls=[], rng_bonus_attribute="power", rng_bonus_value=4)
        self.assertEqual(equipment_service.get_item_bonus_rolls(old), [
            {"kind": "normal", "attribute": "power", "value": 4},
        ])
        current = self._item("mythic")
        current.bonus_power = 8
        totals = equipment_service.get_equipment_bonus_totals([current])
        expected = {key: 0 for key in equipment_service.EQUIPMENT_ATTRIBUTE_KEYS}
        expected["power"] = 8
        for roll in current.bonus_rolls:
            expected[roll["attribute"]] += roll["value"]
        self.assertEqual(totals, expected)
        self.assertEqual(equipment_service.get_item_power_score(current), equipment_service.calculate_power_score(expected))

    def test_roll_snapshot_and_legacy_mirror_match_without_mutating_on_view(self):
        item = self._item("legendary")
        before = [dict(roll) for roll in item.bonus_rolls]
        equipment_service.annotate_item_bonus_view(item)
        self.assertEqual(item.bonus_rolls, before)
        self.assertEqual(item.rng_bonus_attribute, next(roll["attribute"] for roll in before if roll["kind"] == "normal"))
        self.assertEqual(item.rng_bonus_value, next(roll["value"] for roll in before if roll["kind"] == "normal"))

    def test_extreme_bonus_points_and_effective_power_do_not_invert_adjacent_rarities(self):
        rarity_order = tuple(equipment_service.RARITY_BONUS_RULES)

        def extrema(rarity):
            min_count, max_count, min_points, max_points = equipment_service.RARITY_BONUS_RULES[rarity]
            candidates = []
            for count in range(min_count, max_count + 1):
                strong_counts = ([0] if rarity in {"common", "uncommon", "rare", "epic"}
                                 else [1] if rarity == "legendary"
                                 else range(max(2, count - 6), 5))
                for strong_count in strong_counts:
                    normal_count = count - strong_count
                    normal_choices = [set(("power", *others)) for others in combinations(
                        [key for key in equipment_service.EQUIPMENT_RNG_ATTRIBUTES if key != "power"],
                        normal_count - 1,
                    ) if len(set(others) & {"vitality", "agility", "intelligence", "armor"}) >= min(normal_count - 1, 4)]
                    strong_choices = [set(("power", *others)) for others in combinations(
                        [key for key in equipment_service.STRONG_BONUS_ATTRIBUTES if key != "power"],
                        strong_count - 1,
                    )] if strong_count else [set()]
                    for normal_attrs in normal_choices:
                        for strong_attrs in strong_choices:
                            for point in (min_points, max_points):
                                attributes = {key: (point if key in normal_attrs else 0) for key in equipment_service.EQUIPMENT_ATTRIBUTE_KEYS}
                                for key in strong_attrs:
                                    attributes[key] += 10 if point == min_points else 20
                                score = equipment_service.calculate_power_score(attributes)
                                points = len(normal_attrs) * point + len(strong_attrs) * (10 if point == min_points else 20)
                                candidates.append((points, score))
            return min(row[0] for row in candidates), max(row[0] for row in candidates), min(row[1] for row in candidates), max(row[1] for row in candidates)

        bounds = {rarity: extrema(rarity) for rarity in rarity_order}
        for rarity in rarity_order:
            self.assertEqual(
                equipment_service.get_bonus_roll_power_bounds(rarity),
                (bounds[rarity][2], bounds[rarity][3]),
            )
        for lower, upper in zip(rarity_order, rarity_order[1:]):
            self.assertLessEqual(bounds[lower][1], bounds[upper][0], (lower, upper, bounds))
            self.assertLessEqual(bounds[lower][3], bounds[upper][2], (lower, upper, bounds))

    def test_additive_migration_preserves_legacy_rng_snapshot(self):
        project_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(prefix="gim-ml030-migration-") as directory:
            database_path = Path(directory) / "legacy.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection:
                with connection:
                    connection.execute("CREATE TABLE guild_item_instances (id INTEGER PRIMARY KEY, rng_bonus_attribute VARCHAR(30), rng_bonus_value INTEGER NOT NULL DEFAULT 0)")
                    connection.execute("INSERT INTO guild_item_instances (id, rng_bonus_attribute, rng_bonus_value) VALUES (1, 'power', 8)")
                    connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
                    connection.execute("INSERT INTO alembic_version (version_num) VALUES ('f3b4c5d6e7f8')")
            migration_path = project_root / "alembic" / "versions" / "0a1b2c3d4e5f_add_multi_equipment_bonus_rolls.py"
            spec = spec_from_file_location("ml030_bonus_migration", migration_path)
            migration = module_from_spec(spec)
            spec.loader.exec_module(migration)
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            try:
                with engine.begin() as connection:
                    context = MigrationContext.configure(connection)
                    with Operations.context(context):
                        migration.upgrade()
                    connection.exec_driver_sql("UPDATE alembic_version SET version_num = '0a1b2c3d4e5f'")
            finally:
                engine.dispose()
            with closing(sqlite3.connect(database_path)) as connection:
                attribute, value, rolls = connection.execute(
                    "SELECT rng_bonus_attribute, rng_bonus_value, bonus_rolls FROM guild_item_instances WHERE id=1"
                ).fetchone()
            self.assertEqual((attribute, value, rolls), ("power", 8, "[]"))

    def test_template_base_stats_are_preserved_and_effective_power_is_floored_on_new_instances(self):
        self.create_patch.stop()
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine, expire_on_commit=False) as db:
                campaign = CampaignMetadata(campaign_id="ml030-base-campaign", campaign_name="ML030")
                guild = Guild(campaign_id=campaign.campaign_id, name="ML030")
                common = ItemTemplate(
                    name="ML030 Common Base", description="", item_type="equipment", rarity="common",
                    item_level=1, tier=1, base_sell_value=10, equipment_slot="weapon", required_level=1,
                    bonus_power=100,
                    rng_bonus_min=4, rng_bonus_max=8,
                )
                uncommon = ItemTemplate(
                    name="ML030 Uncommon Base", description="", item_type="equipment", rarity="uncommon",
                    item_level=1, tier=1, base_sell_value=10, equipment_slot="main_hand", required_level=1,
                    bonus_power=0,
                )
                legacy_armor = ItemTemplate(
                    name="ML030 Legacy Armor Base", description="", item_type="equipment", rarity="common",
                    item_level=1, tier=1, base_sell_value=10, equipment_slot="armor", required_level=1,
                    bonus_power=100,
                )
                modern_chest = ItemTemplate(
                    name="ML030 Modern Chest Base", description="", item_type="equipment", rarity="uncommon",
                    item_level=1, tier=1, base_sell_value=10, equipment_slot="chest", required_level=1,
                    bonus_power=0,
                )
                legacy_accessory = ItemTemplate(
                    name="ML030 Legacy Accessory Base", description="", item_type="equipment", rarity="common",
                    item_level=1, tier=1, base_sell_value=10, equipment_slot="accessory", required_level=1,
                    bonus_power=100,
                )
                modern_ring = ItemTemplate(
                    name="ML030 Modern Ring Base", description="", item_type="equipment", rarity="uncommon",
                    item_level=1, tier=1, base_sell_value=10, equipment_slot="ring", required_level=1,
                    bonus_power=0,
                )
                db.add_all((campaign, guild, common, uncommon, legacy_armor, modern_chest, legacy_accessory, modern_ring))
                db.flush()
                expected_floor = equipment_service._template_base_power(common) + equipment_service.get_bonus_roll_power_bounds("common")[1]
                instance = equipment_service.create_equipment_instance_from_template(db, guild.id, uncommon)
                db.commit()
                self.assertEqual(common.bonus_power, 100)
                self.assertEqual(uncommon.bonus_power, 0)
                save_admin_item(db, {
                    "name": common.name, "description": "", "item_type": "equipment", "rarity": "common",
                    "level_band": "1-20", "item_level": "1", "tier": "1", "base_sell_value": "10",
                    "equipment_slot": "main_hand", "required_level": "1", "bonus_power": "100",
                    "bonus_vitality": "0", "bonus_agility": "0", "bonus_intelligence": "0",
                    "bonus_luck": "0", "bonus_armor": "0", "rng_bonus_min": "1", "rng_bonus_max": "2",
                    "is_active": "on",
                }, common)
                self.assertEqual((common.rng_bonus_min, common.rng_bonus_max), (4, 8))
                self.assertGreaterEqual(equipment_service.get_item_power_score(instance), expected_floor)
                for lower_template, higher_template, expected_slot in (
                    (legacy_armor, modern_chest, "chest"),
                    (legacy_accessory, modern_ring, "ring"),
                ):
                    floor_power = equipment_service._template_base_power(lower_template) + equipment_service.get_bonus_roll_power_bounds("common")[1]
                    higher_instance = equipment_service.create_equipment_instance_from_template(db, guild.id, higher_template)
                    self.assertEqual(higher_instance.equipment_slot, expected_slot)
                    self.assertGreaterEqual(equipment_service.get_item_power_score(higher_instance), floor_power)
                saved_rolls = [dict(roll) for roll in instance.bonus_rolls]
                instance_id = instance.id
                db.expire_all()
                reloaded = db.get(GuildItemInstance, instance_id)
                self.assertEqual(reloaded.bonus_rolls, saved_rolls)
                self.assertEqual(equipment_service.get_item_bonus_rolls(reloaded), saved_rolls)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
