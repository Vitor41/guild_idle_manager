from contextlib import closing
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.database.connection import SessionLocal, configure_database, create_database_engine
from app.models.campaign import CampaignMetadata
from app.models.content import ContentSeedRun
from app.models.dock import MerchantTemplate
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.guild import Guild
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.content import ProfessionTemplate
from app.models.mission import MissionRun, MissionTemplate
from app.models.regional import RegionalCycle, RegionalOffer
from app.seeds.massive_content import PACK_KEY, PACK_VERSION
from app.services.campaign_service import CampaignService
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
                    board = get_regional_board(db, metadata, guild, metadata.created_at_utc + timedelta(minutes=1))
                    self.assertEqual(metadata.content_version, PACK_VERSION)
                    self.assertEqual(board["cycle"].content_version, PACK_VERSION)
            finally:
                campaigns.close_active_campaign(campaign.campaign_id)

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
