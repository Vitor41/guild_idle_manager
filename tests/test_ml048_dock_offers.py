import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.time import as_utc
from app.database.connection import Base, create_database_engine
from app.models.building import BuildingTemplate, GuildBuilding
from app.models.campaign import CampaignMetadata
from app.models.content import ContentSeedRun
from app.models.dock import (
    DockOffer,
    DockRotation,
    DockRotationMerchant,
    MerchantOfferTemplate,
    MerchantTemplate,
)
from app.models.gathering import GatheringAssignment
from app.models.guild import Guild, GuildResources
from app.models.item import (
    DungeonTemplateItemDrop,
    GuildInventoryItem,
    ItemTemplate,
    MissionTemplateItemDrop,
)
from app.models.mercenary import Mercenary, MercenaryClass
from app.seeds.massive_content import PACK_KEY, PACK_VERSION, run_massive_content_seed
from app.services.building_balance_service import docks_values, market_values, required_guild_level_for_upgrade
from app.services.campaign_service import CampaignService
from app.services.dock_service import buy_dock_offer, create_dock_rotation
from app.services.economy_pricing_service import effective_dock_unit_price, market_sale_unit_value
from app.services.guide_catalog_service import build_guide_catalog
from app.services.market_service import start_material_sale
from app.services.material_source_manifest import build_material_source_manifest, max_reachable_docks_catalog_level


class ML048DockOfferTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _rotation_containing(db, guild, dock_level: int, item_template_id: int):
        collector = db.scalar(select(MerchantTemplate).where(
            MerchantTemplate.slug == "mercante_011",
        ))
        if collector is None:
            raise AssertionError("O Colecionador aprovado não está semeado.")

        def choose_offer(population, weights, k):
            target = next((offer for offer in population if offer.item_template_id == item_template_id), None)
            return [target or population[0]]

        # Keep rotation creation, merchant scoping, prices and stock production
        # real while making this possible-but-not-guaranteed offer reproducible.
        with patch("app.services.dock_service.sample", return_value=[collector]), patch(
            "app.services.dock_service.choices", side_effect=choose_offer,
        ):
            rotation = create_dock_rotation(db, guild, dock_level)
        offer = db.scalar(select(DockOffer).join(
            DockRotationMerchant,
            DockRotationMerchant.id == DockOffer.dock_rotation_merchant_id,
        ).where(
            DockOffer.item_template_id == item_template_id,
            DockRotationMerchant.dock_rotation_id == rotation.id,
        ))
        if offer is None:
            raise AssertionError(
                f"A oferta elegível {item_template_id} não foi gerada pelo Colecionador."
            )
        return 0, rotation, offer

    def test_approved_gap_material_offers_spawn_at_their_gates_and_purchase_exact_templates(self):
        with Session(self.engine) as db:
            run_massive_content_seed(db)
            guild = Guild(name="Docas ML-048", level=1)
            resources = GuildResources(guild=guild, gold=1_000_000)
            db.add_all([guild, resources])
            db.flush()
            docks = db.scalar(select(BuildingTemplate).where(BuildingTemplate.effect_type == "docks"))
            self.assertIsNotNone(docks)
            building = GuildBuilding(guild_id=guild.id, building_template_id=docks.id, level=1)
            db.add(building)
            db.flush()

            manifest = build_material_source_manifest(db)
            cases = (
                ("material_relic_2_002", 1, 1, 32),
                ("material_essence_4_020", 3, 11, 148),
            )
            self.assertGreaterEqual(max_reachable_docks_catalog_level(db), 3)
            self.assertEqual(docks.required_guild_level, 1)
            self.assertEqual(required_guild_level_for_upgrade(11, docks.required_guild_level), 6)
            self.assertGreater(docks.base_upgrade_wood_cost, 0)
            self.assertGreater(docks.base_upgrade_ore_cost, 0)
            wood = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_wood_1_001"))
            ore = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_ore_2_002"))
            for common in (wood, ore):
                row = next(row for row in manifest["materials"] if row["item"]["id"] == common.id)
                self.assertTrue(any(source["type"] == "gathering" for source in row["sources"]))

            for slug, catalog_level, building_level, unit_price in cases:
                with self.subTest(material=slug):
                    item = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == slug))
                    row = next(row for row in manifest["materials"] if row["item"]["id"] == item.id)
                    source = next(source for source in row["sources"] if source["type"] == "docks_possible_offer")
                    self.assertEqual(source["min_dock_level"], catalog_level)
                    self.assertEqual(source["effective_unit_price"], unit_price)
                    required_guild_level = required_guild_level_for_upgrade(
                        building_level, docks.required_guild_level,
                    )
                    self.assertLessEqual(required_guild_level, 6)
                    self.assertEqual(docks_values(building_level)["catalog_level"], catalog_level)

                    guild.level = max(guild.level, required_guild_level)
                    building.level = building_level
                    seed, _rotation, offer = self._rotation_containing(db, guild, building_level, item.id)
                    self.assertGreaterEqual(seed, 0)
                    self.assertEqual(offer.item_template_id, item.id)
                    self.assertEqual(offer.unit_price, unit_price)
                    starting_gold = resources.gold
                    buy_dock_offer(db, guild, resources, offer.id, 1)
                    self.assertEqual(starting_gold - resources.gold, unit_price)
                    purchased = db.scalar(select(GuildInventoryItem).where(
                        GuildInventoryItem.guild_id == guild.id,
                        GuildInventoryItem.item_template_id == item.id,
                    ))
                    self.assertIsNotNone(purchased)
                    self.assertEqual(purchased.quantity, 1)

            self.assertEqual(db.scalar(select(GuildInventoryItem.quantity).join(ItemTemplate).where(
                GuildInventoryItem.guild_id == guild.id,
                ItemTemplate.slug == "material_relic_2_002",
            )), 1)
            self.assertEqual(db.scalar(select(GuildInventoryItem.quantity).join(ItemTemplate).where(
                GuildInventoryItem.guild_id == guild.id,
                ItemTemplate.slug == "material_essence_4_020",
            )), 1)

    def test_stale_active_gap_offers_never_appear_under_other_merchants(self):
        with Session(self.engine) as db:
            run_massive_content_seed(db)
            collector = db.scalar(select(MerchantTemplate).where(
                MerchantTemplate.slug == "mercante_011",
            ))
            other_merchant = db.scalar(select(MerchantTemplate).where(
                MerchantTemplate.slug == "mercante_002",
            ))
            self.assertIsNotNone(collector)
            self.assertIsNotNone(other_merchant)
            for slug, price, minimum in (
                ("material_relic_2_002", 32, 1),
                ("material_essence_4_020", 148, 3),
            ):
                item = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == slug))
                stale_offer = MerchantOfferTemplate(
                    merchant_template_id=other_merchant.id, item_template_id=item.id,
                    base_price=price, min_stock=5, max_stock=30, min_dock_level=minimum,
                    weight=110, is_active=True,
                )
                db.add(stale_offer)
            guild = Guild(name="Rotação exclusiva ML-048", level=1)
            db.add(guild)
            db.flush()

            # Force a real rotation containing only a non-Colecionador merchant.
            with patch("app.services.dock_service.sample", return_value=[other_merchant]):
                rotation = create_dock_rotation(db, guild, 3)

            emitted_slugs = set(db.scalars(select(ItemTemplate.slug).join(
                DockOffer, DockOffer.item_template_id == ItemTemplate.id,
            ).join(
                DockRotationMerchant,
                DockRotationMerchant.id == DockOffer.dock_rotation_merchant_id,
            ).where(DockRotationMerchant.dock_rotation_id == rotation.id)))
            self.assertFalse({"material_relic_2_002", "material_essence_4_020"} & emitted_slugs)

    def test_v6_campaign_upgrade_adds_future_dock_sources_and_preserves_live_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            created = campaigns.create_campaign("Upgrade Docas ML-048", "Guilda Docas ML-048")
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            snapshot_values = None
            essence_snapshot_id = None
            try:
                with factory() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    relic = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_relic_2_002"))
                    essence = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_essence_4_020"))
                    old_wood = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_wood_1_025"))
                    merchant = db.scalar(select(MerchantTemplate).where(
                        MerchantTemplate.slug == "mercante_011",
                    ))
                    mercenary = db.scalar(select(Mercenary).where(Mercenary.guild_id == guild.id))
                    if mercenary is None:
                        apprentice = db.scalar(select(MercenaryClass).where(
                            MercenaryClass.code == "apprentice",
                        ))
                        mercenary = Mercenary(
                            guild_id=guild.id, class_id=apprentice.id, name="Coletor de teste",
                            level=1, status="available", rarity="common", hire_cost=0,
                            power=5, vitality=5, agility=5, intelligence=5, luck=5,
                        )
                        db.add(mercenary)
                        db.flush()

                    rotation = DockRotation(
                        guild_id=guild.id, status="active",
                        starts_at=datetime.now(timezone.utc),
                        ends_at=datetime.now(timezone.utc) + timedelta(hours=2),
                    )
                    db.add(rotation)
                    db.flush()
                    rotation_merchant = DockRotationMerchant(
                        rotation=rotation, merchant_template_id=merchant.id, slot=1,
                    )
                    db.add(rotation_merchant)
                    db.flush()
                    snapshot = DockOffer(
                        rotation_merchant=rotation_merchant, item_template_id=relic.id,
                        unit_price=777, initial_stock=8, remaining_stock=4,
                    )
                    essence_snapshot = DockOffer(
                        rotation_merchant=rotation_merchant, item_template_id=essence.id,
                        unit_price=148, initial_stock=1, remaining_stock=1,
                    )
                    db.add_all([snapshot, essence_snapshot])
                    db.add_all([
                        GuildInventoryItem(guild_id=guild.id, item_template_id=old_wood.id, quantity=5),
                        GatheringAssignment(
                            guild_id=guild.id, mercenary_id=mercenary.id,
                            target_item_template_id=old_wood.id, resource_family="wood", node_code="forest",
                            progress_seconds=0, cycle_count=4, target_quantity=100,
                            quantity_collected=7, extra_chance=0, rng_seed=17,
                            started_at_utc=datetime.now(timezone.utc),
                            checkpoint_at_utc=datetime.now(timezone.utc),
                        ),
                    ])
                    db.flush()
                    essence_snapshot_id = essence_snapshot.id
                    snapshot_values = (rotation.id, rotation_merchant.id, snapshot.id, snapshot.unit_price,
                        snapshot.initial_stock, snapshot.remaining_stock, rotation.ends_at)

                    target_ids = [relic.id, essence.id]
                    db.execute(delete(MerchantOfferTemplate).where(
                        MerchantOfferTemplate.item_template_id.in_(target_ids),
                    ))
                    db.execute(delete(MissionTemplateItemDrop).where(
                        MissionTemplateItemDrop.item_template_id.in_(target_ids),
                    ))
                    db.execute(delete(DungeonTemplateItemDrop).where(
                        DungeonTemplateItemDrop.item_template_id.in_(target_ids),
                    ))
                    db.execute(delete(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    ))
                    metadata.content_version = PACK_VERSION - 1
                    db.commit()

                upgraded, _migration = campaigns.activate_campaign_with_migration(
                    created.campaign_id, mark_active=False, prepare_content=True,
                )
                self.assertEqual(upgraded.content_version, PACK_VERSION)

                with factory() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    assignment = db.scalar(select(GatheringAssignment).where(
                        GatheringAssignment.guild_id == guild.id,
                        GatheringAssignment.resource_family == "wood",
                    ))
                    common_wood = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_wood_1_001"))
                    old_wood = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "material_wood_1_025"))
                    self.assertEqual(assignment.target_item_template_id, common_wood.id)
                    self.assertEqual(assignment.cycle_count, 4)
                    self.assertEqual(assignment.quantity_collected, 7)
                    self.assertEqual(db.scalar(select(GuildInventoryItem.quantity).where(
                        GuildInventoryItem.guild_id == guild.id,
                        GuildInventoryItem.item_template_id == old_wood.id,
                    )), 5)

                    for slug, catalog_level, price, stock, weight in (
                        ("material_relic_2_002", 1, 32, [5, 30], 110),
                        ("material_essence_4_020", 3, 148, [5, 50], 90),
                    ):
                        item = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == slug))
                        offer_rows = list(db.scalars(select(MerchantOfferTemplate).join(
                            MerchantTemplate,
                            MerchantTemplate.id == MerchantOfferTemplate.merchant_template_id,
                        ).where(
                            MerchantOfferTemplate.item_template_id == item.id,
                            MerchantOfferTemplate.is_active.is_(True),
                            MerchantOfferTemplate.min_dock_level <= catalog_level,
                            MerchantTemplate.is_active.is_(True),
                            MerchantTemplate.min_dock_level <= catalog_level,
                        )))
                        self.assertTrue(offer_rows)
                        self.assertEqual(len(offer_rows), 1)
                        self.assertEqual(offer_rows[0].merchant.slug, "mercante_011")
                        self.assertTrue(any(
                            offer.base_price == price
                            and [offer.min_stock, offer.max_stock] == stock
                            and offer.weight == weight
                            for offer in offer_rows
                        ), f"{slug}: {[(offer.base_price, offer.min_stock, offer.max_stock, offer.weight, offer.min_dock_level) for offer in offer_rows]}")
                        self.assertEqual(db.scalar(select(MissionTemplateItemDrop.id).where(
                            MissionTemplateItemDrop.item_template_id == item.id,
                        )), None)
                        self.assertEqual(db.scalar(select(DungeonTemplateItemDrop.id).where(
                            DungeonTemplateItemDrop.item_template_id == item.id,
                        )), None)

                    rotation_id, rotation_merchant_id, offer_id, snapshot_price, initial, remaining, ends_at = snapshot_values
                    preserved_rotation = db.get(DockRotation, rotation_id)
                    preserved_merchant = db.get(DockRotationMerchant, rotation_merchant_id)
                    preserved_offer = db.get(DockOffer, offer_id)
                    self.assertEqual(preserved_rotation.status, "active")
                    self.assertEqual(as_utc(preserved_rotation.ends_at), as_utc(ends_at))
                    self.assertEqual(preserved_merchant.slot, 1)
                    self.assertEqual(preserved_offer.unit_price, snapshot_price)
                    self.assertEqual(preserved_offer.initial_stock, initial)
                    self.assertEqual(preserved_offer.remaining_stock, remaining)

                    manifest = build_material_source_manifest(db, guild_id=guild.id)
                    for slug in ("material_relic_2_002", "material_essence_4_020"):
                        item = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == slug))
                        row = next(row for row in manifest["materials"] if row["item"]["id"] == item.id)
                        dock_source = next(source for source in row["sources"]
                            if source["type"] == "docks_possible_offer")
                        configured_price = 32 if slug == "material_relic_2_002" else 148
                        self.assertEqual(dock_source["base_price"], configured_price)
                        self.assertEqual(dock_source["effective_unit_price"],
                            effective_dock_unit_price(configured_price, item.base_sell_value))
                        self.assertEqual(dock_source["merchant"], "Mercante Colecionador 11")

                    essence = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_essence_4_020",
                    ))
                    guide_item = next(row for row in build_guide_catalog(db)["items"]
                        if row["id"] == essence.id)
                    guide_offer = next(source for source in guide_item["sources"]
                        if source["type"] == "docks_possible_offer")
                    self.assertEqual(guide_offer["price"], 183)

                    self.assertEqual(db.get(CampaignMetadata, created.campaign_id).last_session_state, "created")

                    dock_template = db.scalar(select(BuildingTemplate).where(
                        BuildingTemplate.effect_type == "docks",
                    ))
                    market_template = db.scalar(select(BuildingTemplate).where(
                        BuildingTemplate.effect_type == "market",
                    ))
                    dock_building = db.scalar(select(GuildBuilding).where(
                        GuildBuilding.guild_id == guild.id,
                        GuildBuilding.building_template_id == dock_template.id,
                    ))
                    market_building = db.scalar(select(GuildBuilding).where(
                        GuildBuilding.guild_id == guild.id,
                        GuildBuilding.building_template_id == market_template.id,
                    ))
                    if dock_building is None:
                        dock_building = GuildBuilding(
                            guild_id=guild.id, building_template_id=dock_template.id, level=11,
                        )
                        db.add(dock_building)
                    else:
                        dock_building.level = 11
                    if market_building is None:
                        market_building = GuildBuilding(
                            guild_id=guild.id, building_template_id=market_template.id, level=100,
                        )
                        db.add(market_building)
                    else:
                        market_building.level = 100
                    guild.level = max(
                        guild.level,
                        required_guild_level_for_upgrade(11, dock_template.required_guild_level),
                        required_guild_level_for_upgrade(100, market_template.required_guild_level),
                    )
                    resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild.id))
                    resources.gold = max(resources.gold, 100_000)
                    db.flush()
                    essence = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_essence_4_020",
                    ))
                    essence_offer = db.get(DockOffer, essence_snapshot_id)
                    self.assertEqual(essence_offer.unit_price, 148)
                    self.assertEqual(essence_offer.remaining_stock, 1)
                    configured_price = 148
                    effective_price = effective_dock_unit_price(configured_price, essence.base_sell_value)
                    self.assertEqual(effective_price, 183)
                    gold_before_purchase = resources.gold
                    buy_dock_offer(db, guild, resources, essence_offer.id, 1)
                    self.assertEqual(gold_before_purchase - resources.gold, effective_price)
                    self.assertEqual(essence_offer.unit_price, effective_price)
                    self.assertEqual(essence_offer.remaining_stock, 0)

                    sale = start_material_sale(db, guild, str(essence.id), "1")
                    market_max_price = market_sale_unit_value(
                        essence.base_sell_value,
                        market_values(100)["value_bonus_percent"],
                    )
                    self.assertEqual(sale.unit_value, market_max_price)
                    self.assertEqual(sale.total_value, market_max_price)
                    self.assertLess(sale.total_value, effective_price)

                    # The content marker makes retrying the pack seed idempotent.
                    count_before_retry = db.query(MerchantOfferTemplate).count()
                    run_massive_content_seed(db)
                    self.assertEqual(db.query(MerchantOfferTemplate).count(), count_before_retry)
            finally:
                engine.dispose()

    def test_v6_upgrade_skips_inactive_gap_offer_without_blocking_campaign_open(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            created = campaigns.create_campaign("Oferta inativa nas Docas")
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            try:
                with factory() as db:
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    essence = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_essence_4_020",
                    ))
                    relic = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_relic_2_002",
                    ))
                    self.assertIsNotNone(essence)
                    self.assertIsNotNone(relic)
                    essence.is_active = False
                    metadata.content_version = PACK_VERSION - 1
                    db.execute(delete(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    ))
                    db.commit()

                upgraded, _migration = campaigns.activate_campaign_with_migration(
                    created.campaign_id, mark_active=False, prepare_content=True,
                )
                self.assertEqual(upgraded.content_version, PACK_VERSION)

                with factory() as db:
                    essence = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_essence_4_020",
                    ))
                    relic = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_relic_2_002",
                    ))
                    self.assertFalse(essence.is_active)
                    self.assertEqual(db.scalar(select(MerchantOfferTemplate.id).where(
                        MerchantOfferTemplate.item_template_id == essence.id,
                        MerchantOfferTemplate.is_active.is_(True),
                    )), None)
                    self.assertTrue(db.scalar(select(MerchantOfferTemplate.id).where(
                        MerchantOfferTemplate.item_template_id == relic.id,
                        MerchantOfferTemplate.is_active.is_(True),
                    )))
                    marker = db.scalar(select(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    ))
                    report = json.loads(marker.report_json)
                    self.assertIn({
                        "code": "docks_offer_item_unavailable",
                        "item_slug": "material_essence_4_020",
                        "message": "Oferta das Docas ignorada porque o material está ausente ou inativo.",
                    }, report["warnings"])
            finally:
                engine.dispose()

    def test_v6_upgrade_opens_when_canonical_gathering_material_is_inactive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            created = campaigns.create_campaign("Coleta pausada por catálogo")
            engine = create_database_engine(f"sqlite:///{created.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            checkpoint = datetime(2026, 11, 17, 11, 0, tzinfo=timezone.utc)
            try:
                with factory() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    metadata = db.get(CampaignMetadata, created.campaign_id)
                    common_wood = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_wood_1_001",
                    ))
                    rare_wood = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_wood_1_025",
                    ))
                    worker = db.scalar(select(Mercenary).where(Mercenary.guild_id == guild.id))
                    self.assertIsNotNone(common_wood)
                    self.assertIsNotNone(rare_wood)
                    if worker is None:
                        apprentice = db.scalar(select(MercenaryClass).where(
                            MercenaryClass.code == "apprentice",
                        ))
                        worker = Mercenary(
                            guild_id=guild.id, class_id=apprentice.id, name="Coletor legado",
                            level=1, status="gathering", rarity="common", hire_cost=0,
                            power=5, vitality=5, agility=5, intelligence=5, luck=5,
                        )
                        db.add(worker)
                        db.flush()
                    common_wood.is_active = False
                    rare_wood.is_active = True
                    worker.status = "gathering"
                    assignment = GatheringAssignment(
                        guild_id=guild.id, mercenary_id=worker.id,
                        target_item_template_id=rare_wood.id, resource_family="wood", node_code="forest",
                        progress_seconds=30, cycle_count=4, target_quantity=100,
                        quantity_collected=7, extra_chance=0, rng_seed=17,
                        started_at_utc=checkpoint - timedelta(minutes=5), checkpoint_at_utc=checkpoint,
                    )
                    db.add_all([
                        assignment,
                        GuildInventoryItem(guild_id=guild.id, item_template_id=rare_wood.id, quantity=5),
                    ])
                    db.execute(delete(ContentSeedRun).where(
                        ContentSeedRun.pack_key == PACK_KEY,
                        ContentSeedRun.version == PACK_VERSION,
                    ))
                    metadata.content_version = PACK_VERSION - 1
                    db.commit()

                upgraded, _migration = campaigns.activate_campaign_with_migration(
                    created.campaign_id, mark_active=False, prepare_content=True,
                )
                self.assertEqual(upgraded.content_version, PACK_VERSION)

                with factory() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == created.campaign_id))
                    assignment = db.scalar(select(GatheringAssignment).where(
                        GatheringAssignment.guild_id == guild.id,
                        GatheringAssignment.resource_family == "wood",
                    ))
                    common_wood = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_wood_1_001",
                    ))
                    rare_wood = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.slug == "material_wood_1_025",
                    ))
                    self.assertFalse(common_wood.is_active)
                    self.assertTrue(rare_wood.is_active)
                    self.assertEqual(assignment.target_item_template_id, rare_wood.id)
                    self.assertEqual(as_utc(assignment.checkpoint_at_utc), checkpoint)
                    self.assertEqual((assignment.progress_seconds, assignment.cycle_count), (30, 4))
                    self.assertEqual(assignment.quantity_collected, 7)
                    self.assertEqual(db.scalar(select(GuildInventoryItem.quantity).where(
                        GuildInventoryItem.guild_id == guild.id,
                        GuildInventoryItem.item_template_id == rare_wood.id,
                    )), 5)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
