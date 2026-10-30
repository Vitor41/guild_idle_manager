import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import BuildingTemplate, Guild, GuildBuilding, GuildInventoryItem, GuildResources, ItemTemplate, Mercenary, MercenaryClass
from app.services.gathering_service import advance_assignment, assign_worker
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage


class GatheringServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.guild = Guild(name="Guilda de teste", level=1)
        self.db.add(self.guild)
        self.db.flush()
        self.resources = GuildResources(guild_id=self.guild.id, gold=100)
        self.mercenary_class = MercenaryClass(
            name="Batedor", code="scout", description="", base_power=5,
            base_vitality=5, base_agility=5, base_intelligence=5, base_luck=5,
        )
        self.db.add_all([self.resources, self.mercenary_class])
        self.db.flush()
        self.worker = Mercenary(
            guild_id=self.guild.id, class_id=self.mercenary_class.id, name="Lina",
            level=1, power=5, vitality=5, agility=5, intelligence=5, luck=5,
        )
        self.db.add(self.worker)
        self.wood = ItemTemplate(
            name="Madeira", description="", item_type="material", rarity="common",
            material_family="wood", item_level=1, level_band="1-20", tier=1,
        )
        self.db.add(self.wood)
        self.db.commit()
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_assignment_is_exclusive_and_cycles_are_idempotent(self):
        assignment = assign_worker(self.db, self.guild, self.worker.id, "wood", now=self.start)
        with self.assertRaisesRegex(ValueError, "mercenário precisa estar disponível"):
            assign_worker(self.db, self.guild, self.worker.id, "wood", now=self.start)
        first = advance_assignment(self.db, self.guild, assignment, now=self.start + timedelta(seconds=125))
        self.db.commit()
        second = advance_assignment(self.db, self.guild, assignment, now=self.start + timedelta(seconds=125))
        inventory = self.db.scalar(select(GuildInventoryItem).where(GuildInventoryItem.guild_id == self.guild.id))
        self.assertEqual(first["cycles"], 2)
        self.assertEqual(first["stored"], 2)
        self.assertEqual(second["cycles"], 0)
        self.assertEqual(inventory.quantity, 2)

    def test_max_seconds_caps_24h_elapsed_and_advances_checkpoint(self):
        assignment = assign_worker(self.db, self.guild, self.worker.id, "wood", now=self.start)
        endpoint = self.start + timedelta(days=1)

        result = advance_assignment(
            self.db, self.guild, assignment, now=endpoint, max_seconds=2 * 60 * 60,
        )

        self.assertEqual(result["cycles"], 120)
        self.assertEqual(result["stored"], 120)
        self.assertEqual(assignment.checkpoint_at_utc, endpoint)
        self.assertEqual(assignment.progress_seconds, 0)
        repeated = advance_assignment(
            self.db, self.guild, assignment, now=endpoint, max_seconds=2 * 60 * 60,
        )
        self.assertEqual(repeated["cycles"], 0)

    def test_filling_cycle_loses_only_its_overflow_and_leaves_later_cycle_pending(self):
        self.assertEqual(get_inventory_capacity(self.db, self.guild), 1500)
        assignment = assign_worker(self.db, self.guild, self.worker.id, "wood", now=self.start)
        assignment.extra_chance = 45
        assignment.rng_seed = 4  # Cycle zero deterministically yields the extra unit.
        self.db.add(GuildInventoryItem(guild_id=self.guild.id, item_template_id=self.wood.id, quantity=1499))
        self.db.flush()
        first = advance_assignment(self.db, self.guild, assignment, now=self.start + timedelta(minutes=5))
        second = advance_assignment(self.db, self.guild, assignment, now=self.start + timedelta(minutes=6))
        self.db.commit()
        self.assertEqual(first["stored"], 1)
        self.assertEqual(first["produced"], 2)
        self.assertEqual(first["discarded"], 1)
        self.assertEqual(first["cycles"], 1)
        self.assertTrue(first["paused"])
        self.assertEqual(first["paused_seconds"], 240)
        self.assertEqual(assignment.cycle_count, 1)
        self.assertEqual(assignment.progress_seconds, 0)
        self.assertEqual(second["stored"], 0)
        self.assertEqual(second["discarded"], 0)
        self.assertEqual(second["cycles"], 0)
        self.assertEqual(assignment.cycle_count, 1)
        self.assertEqual(get_inventory_usage(self.db, self.guild.id), 1500)
        self.assertEqual(self.db.scalar(select(Mercenary).where(Mercenary.id == self.worker.id)).status, "gathering")

    def test_full_warehouse_keeps_worker_and_progress_paused(self):
        assignment = assign_worker(self.db, self.guild, self.worker.id, "wood", now=self.start)
        assignment.progress_seconds = 20
        self.db.add(GuildInventoryItem(guild_id=self.guild.id, item_template_id=self.wood.id, quantity=1500))
        self.db.flush()

        result = advance_assignment(self.db, self.guild, assignment, now=self.start + timedelta(minutes=4))

        self.assertTrue(result["paused"])
        self.assertEqual(result["paused_seconds"], 240)
        self.assertEqual(result["cycles"], 0)
        self.assertEqual(assignment.cycle_count, 0)
        self.assertEqual(assignment.progress_seconds, 20)
        self.assertEqual(self.db.scalar(select(Mercenary).where(Mercenary.id == self.worker.id)).status, "gathering")

    def test_freeing_space_resumes_from_now_without_duplicate_or_paused_backlog(self):
        assignment = assign_worker(self.db, self.guild, self.worker.id, "wood", now=self.start)
        inventory = GuildInventoryItem(guild_id=self.guild.id, item_template_id=self.wood.id, quantity=1500)
        self.db.add(inventory)
        self.db.flush()

        paused = advance_assignment(self.db, self.guild, assignment, now=self.start + timedelta(minutes=1))
        self.assertTrue(paused["paused"])
        inventory.quantity = 1499
        resumed = advance_assignment(self.db, self.guild, assignment, now=self.start + timedelta(hours=1))
        self.assertEqual(resumed["cycles"], 0)
        self.assertFalse(resumed["paused"])
        self.assertEqual(resumed["paused_seconds"], 59 * 60)
        self.assertEqual(assignment.cycle_count, 0)
        after_one_active_cycle = advance_assignment(
            self.db, self.guild, assignment, now=self.start + timedelta(hours=1, seconds=60)
        )
        self.assertEqual(after_one_active_cycle["cycles"], 1)
        self.assertEqual(after_one_active_cycle["stored"], 1)
        self.assertEqual(assignment.cycle_count, 1)
        self.assertEqual(get_inventory_usage(self.db, self.guild.id), 1500)

    def test_warehouse_and_guild_levels_expand_shared_capacity(self):
        self.guild.level = 11
        warehouse = BuildingTemplate(name="Armazém", effect_type="warehouse", max_level=100)
        self.db.add(warehouse)
        self.db.flush()
        self.db.add(GuildBuilding(guild_id=self.guild.id, building_template_id=warehouse.id, level=10))
        self.db.flush()
        self.assertEqual(get_inventory_capacity(self.db, self.guild), 2100)


if __name__ == "__main__":
    unittest.main()
