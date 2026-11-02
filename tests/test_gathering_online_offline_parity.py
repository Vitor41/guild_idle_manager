import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.models import (
    CampaignMetadata,
    DungeonTemplate,
    GatheringAssignment,
    Guild,
    GuildInventoryItem,
    GuildResources,
    ItemTemplate,
    MissionTemplate,
    Mercenary,
    MercenaryClass,
    ProfessionTemplate,
)
from app.services.gathering_service import advance_assignment, assign_worker
from app.services.dungeon_service import seed_initial_dungeon_templates
from app.services.mission_service import seed_initial_mission_templates


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
OFFLINE_CAP = 8 * 60 * 60
SCENARIOS = (("5min", 5 * 60), ("6h", 6 * 60 * 60), ("8h", 8 * 60 * 60), ("24h", 24 * 60 * 60))


class GatheringOnlineOfflineParityTests(unittest.TestCase):
    def setUp(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(get_engine())
        self.anchor_store = MemoryAnchorStore()
        with SessionLocal() as db:
            self.mercenary_class = MercenaryClass(
                name="Batedor pareado", code="parity-scout", description="Fixture.",
                base_power=5, base_vitality=5, base_agility=5, base_intelligence=5, base_luck=5,
            )
            self.profession = ProfessionTemplate(
                code="parity-woodcutter", name="Lenhador pareado", description="Fixture.",
                material_family="wood", bonus_percent=15,
            )
            self.material = ItemTemplate(
                name="Madeira pareada", description="Fixture.", item_type="material", rarity="common",
                material_family="wood", item_level=1, level_band="1-20", tier=1,
            )
            db.add_all([self.mercenary_class, self.profession, self.material])
            db.commit()
            # Vigília catch-up materializes contracts, dungeons, and a boss before
            # ClockGuard completes the offline return. Seed the real starter
            # catalogs so these parity fixtures exercise that production path.
            seed_initial_mission_templates(db)
            seed_initial_dungeon_templates(db)
            self.assertGreater(db.scalar(select(func.count(MissionTemplate.id)).where(
                MissionTemplate.is_active.is_(True),
                ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
            )), 0)
            self.assertGreater(db.scalar(select(func.count(DungeonTemplate.id)).where(
                DungeonTemplate.is_active.is_(True),
                DungeonTemplate.content_type == "dungeon",
            )), 0)
            self.assertGreater(db.scalar(select(func.count(DungeonTemplate.id)).where(
                DungeonTemplate.is_active.is_(True),
                DungeonTemplate.content_type == "boss",
            )), 0)
            self.class_id = self.mercenary_class.id
            self.profession_id = self.profession.id
            self.material_id = self.material.id

    def tearDown(self):
        configure_database("sqlite:///:memory:")

    def _create_campaign(self, mode: str, seed: int) -> str:
        campaign_id = f"{mode}-{uuid4()}"
        with SessionLocal() as db:
            metadata = CampaignMetadata(
                campaign_id=campaign_id,
                campaign_name=f"Parity {mode}",
                schema_version=4,
                last_session_state="offline" if mode == "offline" else "active",
                last_clean_shutdown_utc=START,
                stamina_seconds=OFFLINE_CAP,
            )
            guild = Guild(campaign_id=campaign_id, name=f"Guild {mode}", level=1)
            guild.resources = GuildResources(gold=100, wood=0, ore=0, crystals=0)
            db.add_all([metadata, guild])
            db.flush()
            worker = Mercenary(
                guild_id=guild.id, class_id=self.class_id, profession_id=self.profession_id,
                name=f"Worker {mode}", level=1, power=5, vitality=5, agility=5, intelligence=5, luck=5,
            )
            db.add(worker)
            db.flush()
            assignment = assign_worker(db, guild, worker.id, "wood", now=START)
            assignment.rng_seed = seed
            db.commit()
        return campaign_id

    def _snapshot(self, campaign_id: str) -> tuple[int, int, int]:
        with SessionLocal() as db:
            guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
            assignment = db.scalar(select(GatheringAssignment).where(GatheringAssignment.guild_id == guild.id))
            inventory = db.scalar(select(GuildInventoryItem).where(
                GuildInventoryItem.guild_id == guild.id,
                GuildInventoryItem.item_template_id == self.material_id,
            ))
            return (inventory.quantity if inventory else 0, assignment.cycle_count, assignment.progress_seconds)

    def test_seeded_online_cycles_match_clock_guard_offline_credited_time(self):
        guard = ClockGuard(self.anchor_store, wall_clock=lambda: START)
        for scenario_index, (label, requested_seconds) in enumerate(SCENARIOS):
            with self.subTest(duration=label):
                online_id = self._create_campaign("online", 73_000 + scenario_index)
                offline_id = self._create_campaign("offline", 73_000 + scenario_index)
                credited_seconds = min(requested_seconds, OFFLINE_CAP)

                online_time = START
                for _ in range(credited_seconds // 60):
                    online_time += timedelta(seconds=60)
                    with SessionLocal() as db:
                        guild = db.scalar(select(Guild).where(Guild.campaign_id == online_id))
                        assignment = db.scalar(select(GatheringAssignment).where(GatheringAssignment.guild_id == guild.id))
                        advance_assignment(db, guild, assignment, now=online_time)
                        db.commit()

                offline_time = START + timedelta(seconds=requested_seconds)
                self.anchor_store.save(offline_id, START)
                guard.wall_clock = lambda now=offline_time: now
                summary = guard.activate_campaign(offline_id)

                self.assertEqual(summary["credited_seconds"], credited_seconds)
                self.assertEqual(summary["materials"]["wood_total"], 0)
                self.assertEqual(summary["materials"]["ore_total"], 0)
                self.assertEqual(self._snapshot(online_id), self._snapshot(offline_id))
                self.assertEqual(summary["gathering"]["wood"]["cycles"], credited_seconds // 60)


if __name__ == "__main__":
    unittest.main()
