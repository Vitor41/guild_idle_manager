import unittest
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.models import BuildingTemplate
from app.seeds.massive_content import _ensure_docks_template
from app.services.building_balance_service import BUILDING_MAX_LEVEL
from app.services.building_service import INITIAL_BUILDING_TEMPLATES, seed_initial_building_templates


class BuildingTemplateCapTests(unittest.TestCase):
    def setUp(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(get_engine())

    def tearDown(self):
        configure_database("sqlite:///:memory:")

    def test_new_initial_templates_use_level_100(self):
        with SessionLocal() as db:
            seed_initial_building_templates(db)
            templates = list(db.scalars(select(BuildingTemplate)))

        self.assertEqual(len(templates), len(INITIAL_BUILDING_TEMPLATES))
        self.assertTrue(all(template.max_level == BUILDING_MAX_LEVEL for template in templates))

    def test_seed_never_changes_existing_caps_or_custom_fields(self):
        with SessionLocal() as db:
            legacy = BuildingTemplate(
                name="Alojamento", description="Descrição ajustada pelo admin.", effect_type="housing",
                base_upgrade_gold_cost=777, max_level=50,
            )
            custom = BuildingTemplate(
                name="Campo de Treino", description="Limite ajustado pelo admin.", effect_type="training_ground",
                base_upgrade_gold_cost=888, max_level=73,
            )
            db.add_all([legacy, custom])
            db.commit()

            seed_initial_building_templates(db)
            db.refresh(legacy)
            db.refresh(custom)

            self.assertEqual(legacy.max_level, 50)
            self.assertEqual(legacy.description, "Descrição ajustada pelo admin.")
            self.assertEqual(legacy.base_upgrade_gold_cost, 777)
            self.assertEqual(custom.max_level, 73)
            self.assertEqual(custom.base_upgrade_gold_cost, 888)

    def test_docks_seed_creates_new_template_and_leaves_existing_base_untouched(self):
        with SessionLocal() as db:
            self.assertEqual(_ensure_docks_template(db).max_level, 100)

        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(get_engine())
        with SessionLocal() as db:
            db.add_all([
                BuildingTemplate(name="Docas", description="", effect_type="docks", max_level=50),
            ])
            db.commit()
            self.assertEqual(_ensure_docks_template(db).max_level, 50)

    def test_migration_updates_builtin_legacy_default_and_preserves_other_caps(self):
        migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "c0d1e2f3a4b5_expand_building_caps_to_100.py"
        spec = importlib.util.spec_from_file_location("building_cap_migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE building_templates (id INTEGER PRIMARY KEY, effect_type VARCHAR(80), max_level INTEGER)"
            )
            connection.exec_driver_sql(
                "INSERT INTO building_templates VALUES "
                "(1, 'housing', 50), (2, 'warehouse', 73), (3, 'custom_building', 50), (4, 'docks', 50)"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            rows = connection.exec_driver_sql(
                "SELECT id, max_level FROM building_templates ORDER BY id"
            ).all()
            self.assertEqual(rows, [(1, 100), (2, 73), (3, 50), (4, 100)])

            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            rows = connection.exec_driver_sql(
                "SELECT id, max_level FROM building_templates ORDER BY id"
            ).all()
            self.assertEqual(rows, [(1, 50), (2, 73), (3, 50), (4, 50)])

            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            connection.exec_driver_sql("UPDATE building_templates SET max_level = 72 WHERE id IN (1, 4)")
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            rows = connection.exec_driver_sql(
                "SELECT id, max_level FROM building_templates ORDER BY id"
            ).all()
            self.assertEqual(rows, [(1, 72), (2, 73), (3, 50), (4, 72)])
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
