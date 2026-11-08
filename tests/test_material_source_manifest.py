import unittest

from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.seeds.massive_content import run_massive_content_seed
from app.services.crafting_service import seed_crafting_recipes
from app.services.material_source_manifest import build_material_source_manifest


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
                self.assertEqual(manifest["gaps"], [])
                types = {source["type"] for row in manifest["materials"] for source in row["sources"]}
                self.assertTrue({"mission", "dungeon_or_boss", "docks_possible_offer", "gathering",
                    "salvage", "workshop_input", "workshop_output"}.issubset(types))
                dock_rows = [s for row in manifest["materials"] for s in row["sources"]
                    if s["type"] == "docks_possible_offer"]
                self.assertTrue(dock_rows)
                self.assertTrue(all("weight" in source and "probability_percent" not in source for source in dock_rows))
                gathering = [s for row in manifest["materials"] for s in row["sources"]
                    if s["type"] == "gathering"]
                self.assertTrue(all("guild_level" in source and "condition" in source for source in gathering))
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
