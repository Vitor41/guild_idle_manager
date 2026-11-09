import unittest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.game_balance import GUILD_MAX_LEVEL
from app.database.connection import Base, create_database_engine
from app.models.building import BuildingTemplate
from app.models.crafting import CraftingRecipe, CraftingRecipeMaterial
from app.models.dock import MerchantOfferTemplate, MerchantTemplate
from app.models.item import ItemTemplate
from app.seeds.massive_content import run_massive_content_seed
from app.services.crafting_service import _obtainable_material_template_ids, seed_crafting_recipes
from app.services.guide_catalog_service import build_guide_catalog
from app.services.material_source_manifest import build_material_source_manifest, max_reachable_docks_catalog_level


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

    def test_dock_offer_above_runtime_catalog_limit_is_gap_and_not_crafting_source(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                docks = BuildingTemplate(name="Docas", description="", effect_type="docks",
                    max_level=100, required_guild_level=1, is_active=True)
                material = ItemTemplate(name="Catalisador restrito", description="", item_type="material",
                    rarity="common", material_family="catalyst", item_level=1, required_level=1,
                    level_band="1-20", tier=1, is_active=True)
                output = ItemTemplate(name="Equipamento de teste", description="", item_type="equipment",
                    rarity="common", item_level=1, required_level=1, level_band="1-20", tier=1,
                    equipment_slot="main_hand", is_active=True)
                merchant = MerchantTemplate(slug="mercante-restrito", name="Mercante restrito",
                    merchant_type="rare", min_dock_level=1, is_active=True)
                db.add_all([docks, material, output, merchant])
                db.flush()
                db.add(MerchantOfferTemplate(merchant_template_id=merchant.id, item_template_id=material.id,
                    base_price=100, min_stock=1, max_stock=2, min_dock_level=21, is_active=True))
                db.commit()

                self.assertEqual(max_reachable_docks_catalog_level(db), 20)
                manifest = build_material_source_manifest(db)
                row = next(row for row in manifest["materials"] if row["item"]["id"] == material.id)
                self.assertEqual(row["sources"], [])
                self.assertIn(material.id, {item["id"] for item in manifest["gaps"]})
                self.assertNotIn(material.id, _obtainable_material_template_ids(db))
                catalog_item = next(item for item in build_guide_catalog(db)["items"] if item["id"] == material.id)
                self.assertEqual(catalog_item["sources"], [])
                seed_crafting_recipes(db)
                self.assertEqual(db.scalar(select(CraftingRecipe.id).where(CraftingRecipe.is_active.is_(True))), None)

                merchant_locked = MerchantTemplate(slug="mercante-fora-do-limite", name="Mercante fora do limite",
                    merchant_type="rare", min_dock_level=21, is_active=True)
                merchant_material = ItemTemplate(name="Material de mercante restrito", description="",
                    item_type="material", rarity="common", material_family="catalyst", item_level=1,
                    required_level=1, level_band="1-20", tier=1, is_active=True)
                db.add_all([merchant_locked, merchant_material])
                db.flush()
                db.add(MerchantOfferTemplate(merchant_template_id=merchant_locked.id,
                    item_template_id=merchant_material.id, base_price=100, min_stock=1, max_stock=2,
                    min_dock_level=1, is_active=True))
                db.flush()
                merchant_manifest = build_material_source_manifest(db)
                merchant_row = next(row for row in merchant_manifest["materials"] if row["item"]["id"] == merchant_material.id)
                self.assertEqual(merchant_row["sources"], [])
                self.assertNotIn(merchant_material.id, _obtainable_material_template_ids(db))

                docks.max_level = 50
                configured_material = ItemTemplate(name="Material além do cais configurado", description="",
                    item_type="material", rarity="common", material_family="catalyst", item_level=2,
                    required_level=2, level_band="1-20", tier=1, is_active=True)
                db.add(configured_material)
                db.flush()
                db.add(MerchantOfferTemplate(merchant_template_id=merchant.id, item_template_id=configured_material.id,
                    base_price=100, min_stock=1, max_stock=2, min_dock_level=11, is_active=True))
                db.flush()
                self.assertEqual(max_reachable_docks_catalog_level(db), 10)
                configured_manifest = build_material_source_manifest(db)
                configured_row = next(row for row in configured_manifest["materials"] if row["item"]["id"] == configured_material.id)
                self.assertEqual(configured_row["sources"], [])
                self.assertIn(configured_material.id, {item["id"] for item in configured_manifest["gaps"]})
                self.assertNotIn(configured_material.id, _obtainable_material_template_ids(db))
                seed_crafting_recipes(db)
                self.assertEqual(db.scalar(select(CraftingRecipe.id).where(CraftingRecipe.is_active.is_(True))), None)

                docks.required_guild_level = GUILD_MAX_LEVEL + 1
                self.assertEqual(max_reachable_docks_catalog_level(db), 0)
                guild_locked_manifest = build_material_source_manifest(db)
                guild_locked_row = next(row for row in guild_locked_manifest["materials"]
                    if row["item"]["id"] == material.id)
                self.assertEqual(guild_locked_row["sources"], [])
                self.assertNotIn(material.id, _obtainable_material_template_ids(db))
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
