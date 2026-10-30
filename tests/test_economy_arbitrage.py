import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.database.connection import Base, create_database_engine
from app.seeds.campaign_content import apply_initial_campaign_content
from app.models.crafting import CraftingRecipe
from app.services.crafting_service import _effective_recipe_gold_cost
from app.services.building_balance_service import market_values
from app.services.economy_pricing_service import market_sale_unit_value
from scripts.balance.audit_economy_arbitrage import audit, render_markdown


class EconomyArbitrageTests(unittest.TestCase):
    def test_seeded_direct_and_salvage_market_loops_have_no_positive_ev(self):
        no_input_recipe = SimpleNamespace(
            materials=[], gold_cost=100,
            output_item_template=SimpleNamespace(base_sell_value=1000), output_quantity=1,
        )
        self.assertEqual(
            _effective_recipe_gold_cost(None, no_input_recipe, docks_level=0),
            market_sale_unit_value(1000, market_values(100)["value_bonus_percent"]) + 1,
        )
        with TemporaryDirectory(prefix="gim_economy_arbitrage_test_") as temp_dir:
            engine = create_database_engine(f"sqlite:///{Path(temp_dir) / 'audit.sqlite3'}")
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            try:
                with factory() as db:
                    apply_initial_campaign_content(db)
                    result = audit(db)
                    protected_row = next(
                        row for row in result["docks_to_crafting_to_market"]["rows"]
                        if row["configured_net_gold"] > 0
                        and not row["materials_unavailable_from_docks_or_salvage"]
                    )
                    recipe = db.scalar(select(CraftingRecipe).where(CraftingRecipe.id == protected_row["recipe_id"]))
                    no_docks_cost = _effective_recipe_gold_cost(db, recipe, docks_level=0)
                    low_docks_cost = _effective_recipe_gold_cost(db, recipe, docks_level=1)
                    max_docks_cost = _effective_recipe_gold_cost(db, recipe, docks_level=100)
                    blacksmith_template = (Path(__file__).resolve().parents[1] / "app/templates/blacksmith/index.html").read_text(encoding="utf-8")
            finally:
                engine.dispose()

        self.assertEqual(result["result"], "PASS")
        direct = result["direct_dock_to_market"]
        self.assertGreater(direct["templates_scanned"], 0)
        self.assertTrue(all(row["net_gold_per_unit"] <= -1 for row in direct["rows"]))
        salvage = result["docks_to_salvage_to_market"]
        self.assertGreater(salvage["equipment_templates_scanned"], 0)
        self.assertTrue(all(row["expected_net_gold"] <= 0 for row in salvage["rows"]))
        self.assertTrue(all(outcome["net_gold"] <= 0 for row in salvage["rows"] for outcome in row["rng_outcomes"]))
        crafting = result["docks_to_crafting_to_market"]
        self.assertGreater(crafting["active_recipes_scanned"], 0)
        self.assertEqual(crafting["unmodeled_recipe_chain_edges"], 0)
        self.assertTrue(all(row["net_gold"] <= -1 for row in crafting["rows"]
                            if not row["materials_unavailable_from_docks_or_salvage"]))
        crafted_salvage = result["crafted_equipment_to_salvage_to_market"]
        self.assertGreater(crafted_salvage["closed_loops_scanned"], 0)
        self.assertTrue(all(row["expected_net_gold"] <= 0 for row in crafted_salvage["rows"]))
        self.assertEqual(crafted_salvage["positive_best_rng_outcome_loops"], 0)
        self.assertIn("Crafting→desmontagem→Market", render_markdown(result))
        self.assertEqual(no_docks_cost, int(recipe.gold_cost))
        self.assertGreaterEqual(low_docks_cost, int(recipe.gold_cost))
        self.assertEqual(max_docks_cost, protected_row["effective_craft_gold_cost"])
        self.assertGreater(max_docks_cost, int(recipe.gold_cost))
        self.assertIn("{{ recipe.effective_gold_cost }}", blacksmith_template)
        self.assertIn("Total ao fabricar", blacksmith_template)


if __name__ == "__main__":
    unittest.main()
