from contextlib import closing
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.database.connection import SessionLocal, configure_database, create_database_engine
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.desktop.lifecycle import close_campaign, open_campaign_with_migration
from app.models.campaign import CampaignMetadata
from app.models.class_change import ClassTransitionOption
from app.models.content import ContentSeedRun
from app.models.dock import MerchantOfferTemplate, MerchantTemplate
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import DungeonTemplateItemDrop, GuildInventoryItem, ItemTemplate, MissionTemplateItemDrop
from app.models.content import ProfessionTemplate
from app.models.mission import MissionRun, MissionTemplate
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.regional import RegionalCycle, RegionalOffer
from app.seeds.massive_content import PACK_KEY, PACK_VERSION
from app.services.campaign_service import (
    CLASS_TREE_REPAIR_PACK_KEY,
    CLASS_TREE_REPAIR_VERSION,
    CampaignService,
)
from app.services.economy_pricing_service import equipment_base_sell_value
from app.services.class_change_service import get_class_change_page_context
from app.services.gathering_service import advance_assignment, assign_worker
from app.services.regional_cycle_service import CYCLE_SECONDS, get_regional_board


class CampaignContentVersioningTests(unittest.TestCase):
    def tearDown(self):
        configure_database("sqlite:///:memory:")

    def test_new_campaign_uses_pack_version_for_future_cycle_snapshots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Versão de catálogo", "Guilda Versão")
            self.assertEqual(campaign.content_version, PACK_VERSION)

            campaigns.activate_campaign(campaign.campaign_id)
            try:
                with SessionLocal() as db:
                    metadata = db.get(CampaignMetadata, campaign.campaign_id)
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign.campaign_id))
                    self.assertFalse(db.scalar(select(MissionTemplate.is_active).where(
                        MissionTemplate.name == "Cacar lobos",
                    )))
                    self.assertIsNotNone(db.scalar(select(ItemTemplate.id).where(
                        ItemTemplate.item_type == "material",
                        ItemTemplate.material_family == "meat",
                        ItemTemplate.is_active.is_(True),
                    )))
                    worker_class = db.scalar(select(MercenaryClass).order_by(MercenaryClass.id))
                    worker = Mercenary(
                        guild_id=guild.id, class_id=worker_class.id, name="Coletora de Carne",
                        level=1, power=5, vitality=5, agility=5, intelligence=5, luck=5,
                    )
                    db.add(worker)
                    db.flush()
                    started_at = datetime(2026, 11, 3, tzinfo=timezone.utc)
                    assignment = assign_worker(db, guild, worker.id, "meat", now=started_at)
                    db.flush()
                    produced = advance_assignment(
                        db, guild, assignment, now=started_at + timedelta(seconds=60),
                    )
                    self.assertEqual(produced["cycles"], 1)
                    self.assertEqual(produced["stored"], 1)
                    db.commit()
                    meat_stack = db.scalar(
                        select(GuildInventoryItem)
                        .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
                        .where(
                            GuildInventoryItem.guild_id == guild.id,
                            ItemTemplate.item_type == "material",
                            ItemTemplate.material_family == "meat",
                        )
                    )
                    self.assertIsNotNone(meat_stack)
                    self.assertEqual(meat_stack.quantity, 1)
                    board = get_regional_board(db, metadata, guild, metadata.created_at_utc + timedelta(minutes=1))
                    self.assertEqual(metadata.content_version, PACK_VERSION)
                    self.assertEqual(board["cycle"].content_version, PACK_VERSION)
            finally:
                campaigns.close_active_campaign(campaign.campaign_id)

    def test_v6_class_tree_backfill_preserves_economy_snapshots_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            created = campaigns.create_campaign("Árvore v6", "Guilda Árvore v6")
            self.assertEqual(created.content_version, 6)
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            app = SimpleNamespace(state=SimpleNamespace(active_campaign=None, suspended_campaigns=set()))
            clock_guard = ClockGuard(
                anchor_store=MemoryAnchorStore(),
                wall_clock=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc),
                monotonic_clock=lambda: 1.0,
            )
            active = False
            try:
                with factory() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    self.assertEqual(metadata.content_version, 6)
                    self.assertTrue(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY, ContentSeedRun.version == 6,
                    )))
                    self.assertFalse(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY, ContentSeedRun.version == 7,
                    )))
                    self.assertIsNone(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == CLASS_TREE_REPAIR_PACK_KEY,
                        ContentSeedRun.version == CLASS_TREE_REPAIR_VERSION,
                    )))

                    equipment_candidates = db.scalars(select(ItemTemplate).where(
                        ItemTemplate.content_pack == PACK_KEY,
                        ItemTemplate.item_type == "equipment",
                    ))
                    equipment = next((item for item in equipment_candidates
                        if max(2, int((item.item_level + 4) * max(1, item.tier) * 1.8))
                        != equipment_base_sell_value(item.equipment_slot, item.rarity)), None)
                    self.assertIsNotNone(equipment, "v6 fixture needs an equipment whose legacy price is re-priced by the v7 seed")
                    legacy_price = max(2, int((equipment.item_level + 4) * max(1, equipment.tier) * 1.8))
                    self.assertNotEqual(legacy_price, equipment_base_sell_value(equipment.equipment_slot, equipment.rarity))
                    equipment.base_sell_value = legacy_price

                    merchant_offer = db.scalar(select(MerchantOfferTemplate).where(
                        MerchantOfferTemplate.item_template_id == equipment.id,
                    ).order_by(MerchantOfferTemplate.id))
                    self.assertIsNotNone(merchant_offer)
                    merchant_offer.base_price = 4321
                    offer_price = merchant_offer.base_price

                    cycle = RegionalCycle(
                        campaign_id=created.campaign_id, cycle_number=999,
                        starts_at_utc=datetime(2026, 11, 1, tzinfo=timezone.utc),
                        ends_at_utc=datetime(2026, 11, 2, tzinfo=timezone.utc),
                        seed="legacy-v6-snapshot", rules_version="v6-fixture", content_version=6,
                        player_level_snapshot=17, player_power_snapshot=314, rank_weights_json="{}",
                    )
                    db.add(cycle)
                    db.flush()
                    offer = RegionalOffer(
                        campaign_id=created.campaign_id, cycle_id=cycle.id, cycle_number=cycle.cycle_number,
                        region_code="vale-fronteira", offer_type="contract", slot=999,
                        rank="S", name_snapshot="Contrato v6 congelado", description_snapshot="Descrição original.",
                        level_band_snapshot="1-20", recommended_level_snapshot=17,
                        recommended_power_snapshot=314, duration_seconds_snapshot=7200,
                        gold_reward_snapshot=1234, xp_reward_snapshot=456, success_chance_snapshot=67,
                        status="in_progress",
                    )
                    db.add(offer)
                    db.flush()
                    offer_id = offer.id
                    offer_snapshot = (
                        offer.name_snapshot, offer.description_snapshot, offer.recommended_power_snapshot,
                        offer.duration_seconds_snapshot, offer.gold_reward_snapshot,
                        offer.xp_reward_snapshot, offer.success_chance_snapshot,
                    )

                    db.execute(delete(ClassTransitionOption))
                    for mercenary_class in db.scalars(select(MercenaryClass)):
                        mercenary_class.parent_class_id = None
                    db.commit()
                    equipment_id = equipment.id
                    transition_count_before = db.scalar(select(func.count()).select_from(ClassTransitionOption))
                    self.assertEqual(transition_count_before, 0)

                activated, summary, _migration = open_campaign_with_migration(
                    app, campaigns, clock_guard, created.campaign_id,
                )
                active = True
                self.assertIsNone(summary)
                self.assertEqual(activated.content_version, 6)
                with factory() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    self.assertEqual(metadata.content_version, 6)
                    self.assertTrue(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY, ContentSeedRun.version == 6,
                    )))
                    self.assertFalse(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY, ContentSeedRun.version == 7,
                    )))
                    self.assertEqual(db.scalar(select(func.count()).select_from(ContentSeedRun).where(
                        ContentSeedRun.pack_key == CLASS_TREE_REPAIR_PACK_KEY,
                        ContentSeedRun.version == CLASS_TREE_REPAIR_VERSION,
                    )), 1)
                    transitions = list(db.scalars(select(ClassTransitionOption)))
                    self.assertGreater(len(transitions), 0)
                    self.assertGreater(db.scalar(select(func.count()).select_from(MercenaryClass).where(
                        MercenaryClass.parent_class_id.is_not(None),
                    )), 0)
                    equipment = db.get(ItemTemplate, equipment_id)
                    self.assertEqual(equipment.base_sell_value, legacy_price)
                    self.assertEqual(db.scalar(select(MerchantOfferTemplate.base_price).where(
                        MerchantOfferTemplate.item_template_id == equipment_id,
                    ).order_by(MerchantOfferTemplate.id)), offer_price)
                    offer = db.get(RegionalOffer, offer_id)
                    self.assertEqual((
                        offer.name_snapshot, offer.description_snapshot, offer.recommended_power_snapshot,
                        offer.duration_seconds_snapshot, offer.gold_reward_snapshot,
                        offer.xp_reward_snapshot, offer.success_chance_snapshot,
                    ), offer_snapshot)
                    transition_count_after = len(transitions)

                close_campaign(app, campaigns, clock_guard)
                active = False
                reopened, summary, _migration = open_campaign_with_migration(
                    app, campaigns, clock_guard, created.campaign_id,
                )
                active = True
                self.assertIsNone(summary)
                self.assertEqual(reopened.content_version, 6)
                with factory() as db:
                    self.assertEqual(db.scalar(select(func.count()).select_from(ClassTransitionOption)), transition_count_after)
                    self.assertEqual(db.scalar(select(func.count()).select_from(ContentSeedRun).where(
                        ContentSeedRun.pack_key == CLASS_TREE_REPAIR_PACK_KEY,
                        ContentSeedRun.version == CLASS_TREE_REPAIR_VERSION,
                    )), 1)
                    self.assertEqual(db.get(ItemTemplate, equipment_id).base_sell_value, legacy_price)
                    offer = db.get(RegionalOffer, offer_id)
                    self.assertEqual((
                        offer.name_snapshot, offer.description_snapshot, offer.recommended_power_snapshot,
                        offer.duration_seconds_snapshot, offer.gold_reward_snapshot,
                        offer.xp_reward_snapshot, offer.success_chance_snapshot,
                    ), offer_snapshot)
            finally:
                if active:
                    close_campaign(app, campaigns, clock_guard)
                engine.dispose()

    def test_v5_campaign_still_runs_content_pack_upgrade_before_class_tree_repair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            created = campaigns.create_campaign("Conteúdo v5", "Guilda Conteúdo v5")
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            active = False
            try:
                with factory() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    metadata.content_version = 5
                    db.execute(delete(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    ))
                    db.add(ContentSeedRun(
                        pack_key=PACK_KEY, version=5, report_json='{"fixture":"v5"}',
                        applied_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
                    ))
                    db.execute(delete(ClassTransitionOption))
                    for mercenary_class in db.scalars(select(MercenaryClass)):
                        mercenary_class.parent_class_id = None
                    db.commit()

                activated = campaigns.activate_campaign(created.campaign_id)
                active = True
                self.assertEqual(activated.content_version, PACK_VERSION)
                with factory() as db:
                    self.assertEqual(db.get(CampaignMetadata, created.campaign_id).content_version, PACK_VERSION)
                    self.assertTrue(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    )))
                    self.assertTrue(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY, ContentSeedRun.version == 5,
                    )))
                    self.assertTrue(db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == CLASS_TREE_REPAIR_PACK_KEY,
                        ContentSeedRun.version == CLASS_TREE_REPAIR_VERSION,
                    )))
                    self.assertGreater(db.scalar(select(func.count()).select_from(ClassTransitionOption)), 0)
            finally:
                if active:
                    campaigns.close_active_campaign(created.campaign_id)
                engine.dispose()

    def test_legacy_campaign_restores_missing_class_paths_without_rewriting_existing_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            created = campaigns.create_campaign("Transições legadas", "Guilda Transições")
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            preserved_id = None
            transition_count = 0
            custom_class_id = None
            active = False
            try:
                with factory() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    apprentice = db.scalar(select(MercenaryClass).where(MercenaryClass.code == "apprentice"))
                    custom = MercenaryClass(
                        code="qa_custom_unlinked", name="Classe personalizada sem rota",
                        display_name="Classe personalizada sem rota", description="Fixture isolado.",
                        tier=1, parent_class_id=apprentice.id, required_level=20,
                        allowed_weapon_profile="any", role_type="balanced",
                        base_power=5, base_vitality=5, base_agility=5, base_intelligence=5, base_luck=5,
                    )
                    db.add(custom)
                    db.flush()
                    custom_class_id = custom.id
                    transitions = list(db.scalars(select(ClassTransitionOption).order_by(ClassTransitionOption.id)))
                    self.assertGreater(len(transitions), 1)
                    self.assertEqual({row.to_class.tier for row in transitions}, {1, 2, 3})
                    preserved = transitions[0]
                    preserved_id = preserved.id
                    preserved.required_guild_level = 13
                    preserved.required_training_ground_level = 17
                    preserved.gold_cost = 4321
                    preserved.duration_seconds = 9876
                    preserved.is_active = False
                    db.execute(delete(ClassTransitionOption).where(ClassTransitionOption.id != preserved.id))
                    metadata.content_version = PACK_VERSION - 1
                    db.commit()

                activated = campaigns.activate_campaign(created.campaign_id)
                active = True
                self.assertEqual(activated.content_version, PACK_VERSION)
                with factory() as db:
                    restored = list(db.scalars(select(ClassTransitionOption).order_by(ClassTransitionOption.id)))
                    transition_count = len(restored)
                    self.assertGreater(len(restored), 1)
                    tiers = {row.to_class.tier for row in restored}
                    self.assertEqual(tiers, {1, 2, 3})
                    preserved = next(row for row in restored if row.id == preserved_id)
                    self.assertEqual(preserved.required_guild_level, 13)
                    self.assertEqual(preserved.required_training_ground_level, 17)
                    self.assertEqual(preserved.gold_cost, 4321)
                    self.assertEqual(preserved.duration_seconds, 9876)
                    self.assertFalse(preserved.is_active)
                    self.assertFalse(any(row.to_class_id == custom_class_id for row in restored))
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild.id))
                    page_context = get_class_change_page_context(db, guild, resources)
                    self.assertEqual(
                        [step["label"] for step in page_context["requirement_steps"]],
                        ["1ª troca", "2ª troca", "3ª troca"],
                    )
                    self.assertTrue(all(step["eligible_count"] == 0 for step in page_context["requirement_steps"]))
                    self.assertTrue(all(step["state"] == "Faltam requisitos" for step in page_context["requirement_steps"]))
                    db.get(CampaignMetadata, created.campaign_id).content_version = PACK_VERSION - 1
                    db.commit()

                # Simulate retry after class rows committed but campaign metadata did not.
                campaigns.activate_campaign(created.campaign_id)
                with factory() as db:
                    self.assertEqual(
                        db.scalar(select(func.count()).select_from(ClassTransitionOption)),
                        transition_count,
                    )
                    self.assertFalse(db.scalar(select(ClassTransitionOption.id).where(
                        ClassTransitionOption.to_class_id == custom_class_id,
                    )))
            finally:
                if active:
                    campaigns.close_active_campaign(created.campaign_id)
                engine.dispose()

    def test_legacy_migration_reactivates_only_required_meat_gathering_material(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            created = campaigns.create_campaign("Carne legada", "Guilda Carne")
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            canonical_slug = "material_meat_1_001"
            sibling_slug = "material_meat_1_002"
            high_level_slug = None
            try:
                with factory() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    canonical = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == canonical_slug))
                    sibling = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.material_family == "meat",
                        ItemTemplate.slug != canonical_slug,
                    ).order_by(ItemTemplate.slug).limit(1))
                    self.assertIsNotNone(canonical)
                    self.assertIsNotNone(sibling)
                    sibling_slug = sibling.slug
                    for material in db.scalars(select(ItemTemplate).where(
                        ItemTemplate.item_type == "material",
                        ItemTemplate.material_family == "meat",
                    )):
                        material.is_active = False
                    high_level = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.item_type == "material",
                        ItemTemplate.material_family == "meat",
                        ItemTemplate.item_level > 1,
                        ItemTemplate.slug != sibling_slug,
                    ).order_by(ItemTemplate.item_level).limit(1))
                    self.assertIsNotNone(high_level)
                    high_level.is_active = True
                    high_level_slug = high_level.slug
                    canonical.is_active = False
                    canonical.name = "Carne inicial personalizada"
                    canonical.description = "Descrição mantida durante a atualização."
                    canonical.base_sell_value = 77
                    sibling.is_active = False
                    metadata.content_version = PACK_VERSION - 1
                    db.commit()

                activated = campaigns.activate_campaign(created.campaign_id)
                self.assertEqual(activated.content_version, PACK_VERSION)
                with factory() as db:
                    canonical_rows = list(db.scalars(select(ItemTemplate).where(ItemTemplate.slug == canonical_slug)))
                    canonical = canonical_rows[0]
                    sibling = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == sibling_slug))
                    self.assertEqual(len(canonical_rows), 1)
                    self.assertTrue(canonical.is_active)
                    self.assertEqual(canonical.name, "Carne inicial personalizada")
                    self.assertEqual(canonical.description, "Descrição mantida durante a atualização.")
                    self.assertEqual(canonical.base_sell_value, 77)
                    self.assertFalse(sibling.is_active)
                    high_level = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == high_level_slug))
                    self.assertTrue(high_level.is_active)
                    self.assertTrue(canonical.item_level <= 1)
                    self.assertEqual(db.get(CampaignMetadata, created.campaign_id).content_version, PACK_VERSION)
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    worker_class = db.scalar(select(MercenaryClass).order_by(MercenaryClass.id))
                    worker = Mercenary(
                        guild_id=guild.id, class_id=worker_class.id, name="Coletor legada",
                        level=1, power=5, vitality=5, agility=5, intelligence=5, luck=5,
                    )
                    db.add(worker)
                    db.flush()
                    started_at = datetime(2026, 11, 3, tzinfo=timezone.utc)
                    assignment = assign_worker(db, guild, worker.id, "meat", now=started_at)
                    db.flush()
                    produced = advance_assignment(
                        db, guild, assignment, now=started_at + timedelta(seconds=60),
                    )
                    self.assertEqual(produced["cycles"], 1)
                    self.assertEqual(produced["stored"], 1)
                    db.commit()
                    stack = db.scalar(
                        select(GuildInventoryItem)
                        .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
                        .where(
                            GuildInventoryItem.guild_id == guild.id,
                            ItemTemplate.material_family == "meat",
                            ItemTemplate.item_level <= 1,
                        )
                    )
                    self.assertIsNotNone(stack)
                    self.assertEqual(stack.quantity, 1)
            finally:
                campaigns.close_active_campaign(created.campaign_id)
                engine.dispose()

    def test_current_version_activation_repairs_missing_or_inactive_meat_material(self):
        for canonical_is_missing in (False, True):
            with self.subTest(canonical_is_missing=canonical_is_missing), tempfile.TemporaryDirectory() as temp_dir:
                campaigns = CampaignService(Path(temp_dir) / "saves")
                created = campaigns.create_campaign("Carne v5", "Guilda Carne v5")
                engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
                factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
                try:
                    with factory() as db:
                        metadata = db.get(CampaignMetadata, created.campaign_id)
                        self.assertEqual(metadata.content_version, PACK_VERSION)
                        canonical = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_meat_1_001"))
                        self.assertIsNotNone(canonical)
                        canonical.name = "Carne inicial personalizada"
                        canonical.description = "Descrição de administrador preservada."
                        canonical.base_sell_value = 77
                        for material in db.scalars(select(ItemTemplate).where(
                            ItemTemplate.item_type == "material",
                            ItemTemplate.material_family == "meat",
                        )):
                            material.is_active = False
                        if canonical_is_missing:
                            canonical.slug = "legacy_material_meat_1_001"
                        db.commit()

                    activated = campaigns.activate_campaign(created.campaign_id)
                    self.assertEqual(activated.content_version, PACK_VERSION)
                    with factory() as db:
                        canonical_rows = list(db.scalars(select(ItemTemplate).where(
                            ItemTemplate.slug == "material_meat_1_001",
                        )))
                        self.assertEqual(len(canonical_rows), 1)
                        self.assertTrue(canonical_rows[0].is_active)
                        self.assertEqual(canonical_rows[0].material_family, "meat")
                        self.assertEqual(canonical_rows[0].item_type, "material")
                        if not canonical_is_missing:
                            self.assertEqual(canonical_rows[0].name, "Carne inicial personalizada")
                            self.assertEqual(canonical_rows[0].description, "Descrição de administrador preservada.")
                            self.assertEqual(canonical_rows[0].base_sell_value, 77)
                        self.assertEqual(db.get(CampaignMetadata, created.campaign_id).content_version, PACK_VERSION)
                finally:
                    campaigns.close_active_campaign(created.campaign_id)
                    engine.dispose()

    def test_legacy_campaign_upgrade_backs_up_and_preserves_materialized_offers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saves = Path(temp_dir) / "saves"
            campaigns = CampaignService(saves)
            created = campaigns.create_campaign("Save legado", "Guilda Legado")
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            missing_slug = None
            missing_required_min_level = None
            missing_dungeon_slug = None
            missing_meat_slug = None
            old_offer_id = None
            old_offer_snapshot = None
            old_cycle_id = None
            old_cycle_seed = None
            old_cycle_weights = None
            legacy_mission_id = None
            in_progress_legacy_mission_id = None
            admin_enabled_legacy_mission_id = None
            in_progress_offer_id = None
            materialized_pack_offer_id = None
            materialized_pack_offer_snapshot = None
            pack_mission_id = None
            mission_drop_snapshot = None
            dungeon_drop_snapshot = None
            customized_rows = []
            try:
                with factory() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    metadata.content_version = PACK_VERSION - 1
                    db.execute(delete(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    ))
                    missing_meat = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.item_type == "material",
                        ItemTemplate.material_family == "meat",
                        ItemTemplate.is_active.is_(True),
                    ).order_by(ItemTemplate.item_level, ItemTemplate.id))
                    self.assertIsNotNone(missing_meat)
                    missing_meat_slug = missing_meat.slug
                    missing_meat.slug = f"legacy_{missing_meat.slug}"
                    missing_meat.name = "Carne Legada preservada"
                    db.flush()
                    board = get_regional_board(
                        db, metadata, guild, metadata.created_at_utc + timedelta(minutes=1),
                    )
                    old_cycle = board["cycle"]
                    old_cycle_id = old_cycle.id
                    old_cycle_seed = old_cycle.seed
                    old_cycle_weights = old_cycle.rank_weights_json

                    legacy = db.scalar(select(MissionTemplate).where(MissionTemplate.name == "Cacar lobos"))
                    self.assertIsNotNone(legacy)
                    legacy.is_active = True
                    legacy_mission_id = legacy.id
                    old_offers = [row for row in board["offers"]["contract"] if row.status == "available"]
                    self.assertGreaterEqual(len(old_offers), 2)
                    old_offer = old_offers[0]
                    old_offer.mission_template_id = legacy.id
                    old_offer.name_snapshot = "Snapshot legado preservado"
                    old_offer_id = old_offer.id
                    old_offer_snapshot = {
                        "mission_template_id": old_offer.mission_template_id,
                        "name": old_offer.name_snapshot,
                        "description": old_offer.description_snapshot,
                        "rank": old_offer.rank,
                        "duration": old_offer.duration_seconds_snapshot,
                        "gold": old_offer.gold_reward_snapshot,
                        "xp": old_offer.xp_reward_snapshot,
                        "chance": old_offer.success_chance_snapshot,
                    }

                    in_progress_legacy = db.scalar(select(MissionTemplate).where(
                        MissionTemplate.name == "Patrulhar estrada",
                    ))
                    self.assertIsNotNone(in_progress_legacy)
                    in_progress_legacy.is_active = True
                    in_progress_legacy_mission_id = in_progress_legacy.id
                    in_progress_offer = old_offers[1]
                    in_progress_offer.mission_template_id = in_progress_legacy.id
                    in_progress_offer.status = "in_progress"
                    in_progress_offer_id = in_progress_offer.id
                    db.add(MissionRun(
                        guild_id=guild.id,
                        mission_template_id=in_progress_legacy.id,
                        regional_offer_id=in_progress_offer.id,
                        status="in_progress",
                        run_multiplier=1,
                        started_at=metadata.created_at_utc,
                        ends_at=metadata.created_at_utc + timedelta(hours=2),
                    ))
                    admin_enabled_legacy = db.scalar(select(MissionTemplate).where(
                        MissionTemplate.name == "Escoltar comerciante",
                    ))
                    self.assertIsNotNone(admin_enabled_legacy)
                    admin_enabled_legacy.is_active = True
                    admin_enabled_legacy_mission_id = admin_enabled_legacy.id
                    self.assertIsNone(db.scalar(select(RegionalOffer.id).where(
                        RegionalOffer.mission_template_id == admin_enabled_legacy.id,
                    ).limit(1)))

                    def customize(model, row, **fields):
                        for field, value in fields.items():
                            setattr(row, field, value)
                        customized_rows.append((model, row.id, fields.copy()))

                    pack_mission = db.scalar(select(MissionTemplate).where(
                        MissionTemplate.content_pack == PACK_KEY,
                    ).order_by(MissionTemplate.id))
                    equipment_template = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.content_pack == PACK_KEY,
                        ItemTemplate.item_type == "equipment",
                    ).order_by(ItemTemplate.id))
                    profession = db.scalar(select(ProfessionTemplate).where(
                        ProfessionTemplate.code == "woodcutter",
                    ))
                    if profession is None:
                        profession = db.scalar(select(ProfessionTemplate).where(
                            ProfessionTemplate.name == "Lenhador",
                        ))
                        if profession is None:
                            profession = ProfessionTemplate(
                                code="woodcutter", name="Lenhador",
                                description="Especialista em coletas da família madeiras.",
                                material_family="wood", bonus_percent=15, training_gold_cost=250,
                                training_duration_seconds=3600, is_active=True,
                            )
                            db.add(profession)
                            db.flush()
                    dungeon = db.scalar(select(DungeonTemplate).where(
                        DungeonTemplate.content_pack == PACK_KEY,
                    ).order_by(DungeonTemplate.id))
                    merchant = db.scalar(select(MerchantTemplate).where(
                        MerchantTemplate.content_pack == PACK_KEY,
                    ).order_by(MerchantTemplate.id))
                    self.assertIsNotNone(pack_mission, "missing preexisting pack mission")
                    self.assertIsNotNone(equipment_template, "missing preexisting equipment template")
                    self.assertIsNotNone(profession, "missing preexisting profession")
                    self.assertIsNotNone(dungeon, "missing preexisting dungeon template")
                    self.assertIsNotNone(merchant, "missing preexisting merchant template")
                    mission_drop = db.scalar(select(MissionTemplateItemDrop).where(
                        MissionTemplateItemDrop.mission_template_id == pack_mission.id,
                    ).order_by(MissionTemplateItemDrop.id))
                    dungeon_drop = db.scalar(select(DungeonTemplateItemDrop).where(
                        DungeonTemplateItemDrop.dungeon_template_id == dungeon.id,
                    ).order_by(DungeonTemplateItemDrop.id))
                    self.assertIsNotNone(mission_drop, "missing preexisting mission drop")
                    self.assertIsNotNone(dungeon_drop, "missing preexisting dungeon drop")
                    customize(MissionTemplate, pack_mission,
                        description="Contrato de edição personalizada preservada.", is_active=False,
                        duration_seconds=12345, base_gold_reward=987,
                        required_min_mercenary_level=7, required_guild_level=9)
                    customize(ItemTemplate, equipment_template,
                        description="Equipamento personalizado preservado.", is_active=False,
                        bonus_power=777, base_sell_value=4321)
                    customize(ProfessionTemplate, profession,
                        description="Especialista em coletas da família: texto personalizado.",
                        is_active=False, bonus_percent=77, training_gold_cost=8765)
                    customize(DungeonTemplate, dungeon,
                        description="Desafio personalizado preservado.", is_active=False,
                        duration_seconds=54321, base_xp_reward=876)
                    customize(MerchantTemplate, merchant,
                        name="Mercante Ferreiro 01", is_active=False, rotation_weight=777)
                    customize(MissionTemplateItemDrop, mission_drop,
                        drop_chance=37, min_quantity=2, max_quantity=9, is_active=False)
                    customize(DungeonTemplateItemDrop, dungeon_drop,
                        drop_chance=43, min_quantity=3, max_quantity=11, is_active=False)

                    pack_mission_id = pack_mission.id
                    materialized_pack_offer = RegionalOffer(
                        campaign_id=created.campaign_id,
                        cycle_id=old_cycle.id,
                        cycle_number=old_cycle.cycle_number,
                        region_code="vale-fronteira",
                        offer_type="contract",
                        slot=99,
                        mission_template_id=pack_mission.id,
                        rank="A",
                        name_snapshot=pack_mission.name,
                        description_snapshot=pack_mission.description,
                        level_band_snapshot=pack_mission.level_band,
                        recommended_level_snapshot=pack_mission.recommended_level,
                        recommended_power_snapshot=pack_mission.recommended_power,
                        min_party_size_snapshot=pack_mission.min_party_size,
                        max_party_size_snapshot=pack_mission.max_party_size,
                        duration_seconds_snapshot=pack_mission.duration_seconds,
                        gold_reward_snapshot=pack_mission.base_gold_reward,
                        xp_reward_snapshot=pack_mission.base_xp_reward,
                        success_chance_snapshot=pack_mission.base_success_chance,
                        status="in_progress",
                    )
                    db.add(materialized_pack_offer)
                    db.flush()
                    materialized_pack_offer_id = materialized_pack_offer.id
                    materialized_pack_offer_snapshot = {
                        "name": materialized_pack_offer.name_snapshot,
                        "description": materialized_pack_offer.description_snapshot,
                        "rank": materialized_pack_offer.rank,
                        "duration": materialized_pack_offer.duration_seconds_snapshot,
                        "gold": materialized_pack_offer.gold_reward_snapshot,
                        "xp": materialized_pack_offer.xp_reward_snapshot,
                        "chance": materialized_pack_offer.success_chance_snapshot,
                    }
                    db.add(MissionRun(
                        guild_id=guild.id,
                        mission_template_id=pack_mission.id,
                        regional_offer_id=materialized_pack_offer.id,
                        status="in_progress",
                        run_multiplier=1,
                        started_at=metadata.created_at_utc,
                        ends_at=metadata.created_at_utc + timedelta(hours=3),
                    ))

                    def mission_loot_rows(mission_template_id):
                        return tuple((row.item_template_id, row.drop_chance, row.min_quantity,
                            row.max_quantity, row.is_active) for row in db.scalars(
                                select(MissionTemplateItemDrop).where(
                                    MissionTemplateItemDrop.mission_template_id == mission_template_id,
                                ).order_by(MissionTemplateItemDrop.id)
                            ))

                    def dungeon_loot_rows(dungeon_template_id):
                        return tuple((row.item_template_id, row.drop_chance, row.min_quantity,
                            row.max_quantity, row.is_active) for row in db.scalars(
                                select(DungeonTemplateItemDrop).where(
                                    DungeonTemplateItemDrop.dungeon_template_id == dungeon_template_id,
                                ).order_by(DungeonTemplateItemDrop.id)
                            ))

                    mission_drop_snapshot = mission_loot_rows(pack_mission.id)
                    dungeon_drop_snapshot = dungeon_loot_rows(dungeon.id)

                    referenced_ids = set(db.scalars(select(RegionalOffer.mission_template_id).where(
                        RegionalOffer.campaign_id == created.campaign_id,
                        RegionalOffer.mission_template_id.is_not(None),
                    )))
                    missing = db.scalar(select(MissionTemplate).where(
                        MissionTemplate.content_pack == PACK_KEY,
                        ~MissionTemplate.id.in_(referenced_ids),
                    ).order_by(MissionTemplate.id.desc()).limit(1))
                    self.assertIsNotNone(missing)
                    missing_slug = missing.slug
                    missing_required_min_level = missing.required_min_mercenary_level
                    self.assertIsNone(db.scalar(select(MissionRun.id).where(
                        MissionRun.mission_template_id == missing.id,
                    ).limit(1)))
                    db.execute(delete(MissionTemplateItemDrop).where(
                        MissionTemplateItemDrop.mission_template_id == missing.id,
                    ))
                    db.delete(missing)
                    missing_dungeon = db.scalar(select(DungeonTemplate).where(
                        DungeonTemplate.content_pack == PACK_KEY,
                        DungeonTemplate.id != dungeon.id,
                    ).order_by(DungeonTemplate.id.desc()).limit(1))
                    self.assertIsNotNone(missing_dungeon)
                    missing_dungeon_slug = missing_dungeon.slug
                    self.assertIsNone(db.scalar(select(DungeonRun.id).where(
                        DungeonRun.dungeon_template_id == missing_dungeon.id,
                    ).limit(1)))
                    db.execute(delete(DungeonTemplateItemDrop).where(
                        DungeonTemplateItemDrop.dungeon_template_id == missing_dungeon.id,
                    ))
                    db.delete(missing_dungeon)
                    db.commit()
            finally:
                engine.dispose()

            activated = campaigns.activate_campaign(created.campaign_id)
            self.assertEqual(activated.content_version, PACK_VERSION)
            backup_dir = Path(temp_dir) / "backups" / created.campaign_id
            backups = list(backup_dir.glob(f"pre-migration-content-{PACK_VERSION - 1}-to-{PACK_VERSION}-*.db"))
            self.assertEqual(len(backups), 1)
            with closing(sqlite3.connect(backups[0])) as backup:
                self.assertEqual(
                    backup.execute("SELECT content_version FROM campaign_metadata").fetchone()[0],
                    PACK_VERSION - 1,
                )
                self.assertEqual(
                    backup.execute(
                        "SELECT COUNT(*) FROM content_seed_runs WHERE pack_key = ? AND version = ?",
                        (PACK_KEY, PACK_VERSION),
                    ).fetchone()[0],
                    0,
                )

            try:
                with SessionLocal() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    self.assertEqual(metadata.content_version, PACK_VERSION)
                    self.assertIsNotNone(db.scalar(select(ContentSeedRun.id).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    )))
                    restored_mission = db.scalar(select(MissionTemplate).where(
                        MissionTemplate.slug == missing_slug,
                    ))
                    self.assertIsNotNone(restored_mission)
                    self.assertEqual(restored_mission.required_min_mercenary_level, missing_required_min_level)
                    self.assertIsNotNone(db.scalar(select(ItemTemplate.id).where(
                        ItemTemplate.slug == missing_meat_slug,
                        ItemTemplate.material_family == "meat",
                        ItemTemplate.is_active.is_(True),
                    )))
                    self.assertIsNotNone(db.scalar(select(ItemTemplate.id).where(
                        ItemTemplate.slug == f"legacy_{missing_meat_slug}",
                        ItemTemplate.name == "Carne Legada preservada",
                    )))
                    self.assertGreater(db.scalar(select(func.count(MissionTemplateItemDrop.id)).where(
                        MissionTemplateItemDrop.mission_template_id == restored_mission.id,
                    )) or 0, 0)
                    restored_dungeon = db.scalar(select(DungeonTemplate).where(
                        DungeonTemplate.slug == missing_dungeon_slug,
                    ))
                    self.assertIsNotNone(restored_dungeon)
                    self.assertGreater(db.scalar(select(func.count(DungeonTemplateItemDrop.id)).where(
                        DungeonTemplateItemDrop.dungeon_template_id == restored_dungeon.id,
                    )) or 0, 0)
                    self.assertIsNotNone(db.scalar(select(MissionTemplate).where(
                        MissionTemplate.id == legacy_mission_id,
                        MissionTemplate.is_active.is_(True),
                    )))
                    for model, row_id, fields in customized_rows:
                        row = db.get(model, row_id)
                        self.assertIsNotNone(row)
                        self.assertEqual({field: getattr(row, field) for field in fields}, fields)
                    # The additive catalog upgrade does not rerun refinement or
                    # rewrite existing admin-set mission gates.
                    self.assertEqual(db.get(MissionTemplate, pack_mission_id).required_min_mercenary_level, 7)
                    self.assertEqual(db.get(MissionTemplate, pack_mission_id).required_guild_level, 9)
                    migrated_old_offer = db.get(RegionalOffer, old_offer_id)
                    self.assertEqual({
                        "mission_template_id": migrated_old_offer.mission_template_id,
                        "name": migrated_old_offer.name_snapshot,
                        "description": migrated_old_offer.description_snapshot,
                        "rank": migrated_old_offer.rank,
                        "duration": migrated_old_offer.duration_seconds_snapshot,
                        "gold": migrated_old_offer.gold_reward_snapshot,
                        "xp": migrated_old_offer.xp_reward_snapshot,
                        "chance": migrated_old_offer.success_chance_snapshot,
                    }, old_offer_snapshot)
                    migrated_old_cycle = db.get(RegionalCycle, old_cycle_id)
                    self.assertEqual(migrated_old_cycle.seed, old_cycle_seed)
                    self.assertEqual(migrated_old_cycle.rank_weights_json, old_cycle_weights)
                    self.assertEqual(migrated_old_cycle.content_version, PACK_VERSION - 1)
                    self.assertEqual(mission_loot_rows(pack_mission_id), mission_drop_snapshot)
                    self.assertEqual(dungeon_loot_rows(dungeon.id), dungeon_drop_snapshot)
                    materialized_pack_offer = db.get(RegionalOffer, materialized_pack_offer_id)
                    self.assertEqual(materialized_pack_offer.status, "in_progress")
                    self.assertEqual(materialized_pack_offer.mission_template_id, pack_mission_id)
                    self.assertEqual({
                        "name": materialized_pack_offer.name_snapshot,
                        "description": materialized_pack_offer.description_snapshot,
                        "rank": materialized_pack_offer.rank,
                        "duration": materialized_pack_offer.duration_seconds_snapshot,
                        "gold": materialized_pack_offer.gold_reward_snapshot,
                        "xp": materialized_pack_offer.xp_reward_snapshot,
                        "chance": materialized_pack_offer.success_chance_snapshot,
                    }, materialized_pack_offer_snapshot)
                    self.assertIsNotNone(db.scalar(select(MissionRun.id).where(
                        MissionRun.regional_offer_id == materialized_pack_offer_id,
                        MissionRun.status == "in_progress",
                    )))

                    # Isolate offer expiry from CPU outcomes so this assertion
                    # measures only the old board's availability transition.
                    with patch(
                        "app.services.regional_cycle_service.regional_cpu_action_probability",
                        return_value=0,
                    ), patch(
                        "app.services.regional_cycle_service._cpu_offer_party",
                        return_value=None,
                    ):
                        next_board = get_regional_board(
                            db, metadata, guild,
                            metadata.created_at_utc + timedelta(seconds=CYCLE_SECONDS + 3600),
                        )
                    self.assertEqual(next_board["cycle"].cycle_number, 1)
                    self.assertEqual(next_board["cycle"].content_version, PACK_VERSION)
                    self.assertEqual(migrated_old_offer.status, "expired")
                    self.assertTrue(db.get(MissionTemplate, legacy_mission_id).is_active)
                    self.assertEqual(db.get(RegionalOffer, in_progress_offer_id).status, "in_progress")
                    self.assertTrue(db.get(MissionTemplate, in_progress_legacy_mission_id).is_active)
                    self.assertTrue(db.get(MissionTemplate, admin_enabled_legacy_mission_id).is_active)
                    self.assertIsNotNone(db.scalar(select(MissionRun.id).where(
                        MissionRun.regional_offer_id == in_progress_offer_id,
                        MissionRun.status == "in_progress",
                    )))
            finally:
                campaigns.close_active_campaign(created.campaign_id)


if __name__ == "__main__":
    unittest.main()
