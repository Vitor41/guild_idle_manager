import unittest

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.crafting import CraftingRecipe, CraftingRecipeMaterial
from app.database.connection import Base, create_database_engine
from app.models.item import ItemTemplate
from app.seeds.massive_content import run_massive_content_seed
from app.services.crafting_service import seed_crafting_recipes
from app.services.material_source_manifest import build_material_source_manifest
from app.services.crafting_service import _obtainable_material_template_ids


class MaterialSourceManifestTests(unittest.TestCase):
    def test_seeded_live_catalog_has_explicit_sources_and_no_active_gaps(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                run_massive_content_seed(db)
                seed_crafting_recipes(db)
                db.commit()
                manifest = build_material_source_manifest(db)
                self.assertEqual(manifest["schema_version"], 1)
                self.assertEqual(manifest["scope"]["gathering_level_range"], [1, 350])
                self.assertEqual(manifest["gaps"], [])
                active_families = {row["item"]["family"] for row in manifest["materials"]
                    if row["item"]["active"] and row["item"]["family"]}
                self.assertEqual(active_families, {"wood", "ore", "stone", "leather", "cloth", "herb", "meat",
                    "essence", "gem", "beast", "relic", "catalyst", "insignia", "supply_kit"})
                obtainable_ids = {row["item"]["id"] for row in manifest["materials"] if row["sources"]}
                active_ingredient_ids = set(db.scalars(select(CraftingRecipeMaterial.item_template_id)
                    .join(CraftingRecipe, CraftingRecipe.id == CraftingRecipeMaterial.recipe_id)
                    .where(CraftingRecipe.is_active.is_(True))))
                self.assertTrue(active_ingredient_ids)
                self.assertTrue(active_ingredient_ids.issubset(obtainable_ids))
                types = {source["type"] for row in manifest["materials"] for source in row["sources"]}
                self.assertTrue({"mission", "dungeon_or_boss", "docks_possible_offer", "gathering",
                    "salvage", "workshop_output"}.issubset(types))
                self.assertNotIn("workshop_input", types)
                meat_row = next(row for row in manifest["materials"] if row["item"]["family"] == "meat")
                self.assertTrue(any(dependency["type"] == "workshop_input" for dependency in meat_row["dependencies"]))
                dock_rows = [s for row in manifest["materials"] for s in row["sources"]
                    if s["type"] == "docks_possible_offer"]
                self.assertTrue(dock_rows)
                self.assertTrue(all("weight" in source and "probability_percent" not in source for source in dock_rows))
                gathering = [s for row in manifest["materials"] for s in row["sources"]
                    if s["type"] == "gathering"]
                self.assertTrue(all("guild_level_range" in source and "condition" in source for source in gathering))

                late_variant = ItemTemplate(name="Minério desbloqueado no 350", description="", item_type="material",
                    rarity="common", material_family="ore", item_level=350, required_level=350,
                    level_band="301-350", tier=99, is_active=True)
                stranded_variant = ItemTemplate(name="Erva sem rota no catálogo", description="", item_type="material",
                    rarity="common", material_family="herb", item_level=351, required_level=351,
                    level_band="301-350", tier=99, is_active=True)
                db.add_all([late_variant, stranded_variant])
                db.commit()
                expanded = build_material_source_manifest(db)
                late_row = next(row for row in expanded["materials"] if row["item"]["id"] == late_variant.id)
                self.assertTrue(any(source["type"] == "gathering" and source["guild_level_range"] == [350, 350]
                    for source in late_row["sources"]))
                self.assertNotIn(late_variant.id, {item["id"] for item in expanded["gaps"]})
                self.assertIn(stranded_variant.id, {item["id"] for item in expanded["gaps"]})
                stranded_row = next(row for row in expanded["materials"] if row["item"]["id"] == stranded_variant.id)
                self.assertEqual(stranded_row["sources"], [])
                self.assertTrue(any(dep["type"] == "workshop_input" for dep in stranded_row["dependencies"]))
                self.assertNotIn(stranded_variant.id, _obtainable_material_template_ids(db))
        finally:
            engine.dispose()

    def test_workshop_input_dependency_does_not_count_as_obtainment_source(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                input_only = ItemTemplate(name="Carne sem rota", description="", item_type="material",
                    rarity="common", material_family="meat", item_level=400, required_level=400,
                    level_band="301-350", tier=99, is_active=True)
                db.add(input_only)
                db.commit()
                manifest = build_material_source_manifest(db)
                row = manifest["materials"][0]
                self.assertEqual(row["sources"], [])
                self.assertTrue(any(dep["type"] == "workshop_input" for dep in row["dependencies"]))
                self.assertEqual([item["id"] for item in manifest["gaps"]], [input_only.id])
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
