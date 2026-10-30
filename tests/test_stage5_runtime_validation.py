import json
import random
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import (
    CampaignMetadata, DungeonRun, DungeonTemplate, Guild, GuildInventoryItem, GuildResources, MarketSale,
    GuildItemInstance, ItemTemplate, Mercenary, MercenaryClass, MissionTemplate, ProfessionTemplate, GuildBuilding,
)
from app.models.skill import MercenarySkill, SkillTemplate
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_VERSION
from app.repositories.item_repository import add_inventory_quantity, get_inventory_item, list_active_drops_for_mission
from app.repositories.dungeon_repository import list_active_drops_for_dungeon
from app.services import dungeon_service, equipment_service, market_service, mission_service, salvage_service
from app.services.building_service import (
    BuildingError, ensure_guild_buildings, get_mercenary_limit, upgrade_guild_building,
)
from app.services.dungeon_service import (
    claim_dungeon_loot, get_advanced_dungeon_chance, get_dungeon_supply_quote,
    get_final_dungeon_chance, start_dungeon,
)
from app.services.crafting_service import craft_recipe, list_rotating_recipes
from app.services.equipment_service import (
    can_class_equip_item, create_equipment_instance_from_template, get_party_power_score,
)
from app.services.gathering_service import advance_assignment, assign_worker
from app.services.inventory_capacity_service import get_inventory_capacity, get_inventory_usage
from app.services.inventory_capacity_service import add_inventory_quantity_capped
from app.services.market_service import (
    MarketError, collect_market_sale, get_material_sale_quota, start_material_sale,
)
from app.services.mercenary_service import equip_mercenary_item
from app.services.mission_service import claim_mission_loot, mission_is_unlocked, start_mission
from app.services.salvage_service import collect_salvage, start_salvage
from app.services.result_detail_service import parse_result_details


class Stage5RuntimeValidationTests(unittest.TestCase):
    """Disposable SQLite integration checks for real economy service edges."""

    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        apply_initial_campaign_content(self.db)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.campaign = CampaignMetadata(
            campaign_id="00000000-0000-0000-0000-000000000001", campaign_name="Stage 5 runtime fixture",
            created_at_utc=now, updated_at_utc=now, schema_version=5,
            content_version=PACK_VERSION, home_region="Vale da Fronteira",
        )
        self.guild = Guild(campaign_id=self.campaign.campaign_id, name="Runtime fixture", level=1)
        self.resources = GuildResources(guild=self.guild, gold=1_000_000)
        self.db.add_all((self.campaign, self.guild, self.resources))
        self.db.flush()
        buildings = ensure_guild_buildings(self.db, self.guild.id)
        for building in buildings:
            if building.building_template.effect_type in {"market", "blacksmith", "scouts"}:
                building.level = 1
            elif building.building_template.effect_type in {"tavern", "housing"}:
                building.level = 10
            elif building.building_template.effect_type == "contract_office":
                building.level = 50
        apprentice = self.db.scalar(select(MercenaryClass).where(MercenaryClass.code == "apprentice"))
        self.members = []
        for index in range(5):
            member = Mercenary(
                guild_id=self.guild.id, class_id=apprentice.id, name=f"Runtime {index + 1}",
                level=1, xp=0, status="available", rarity="common", hire_cost=0,
                power=apprentice.base_power, vitality=apprentice.base_vitality,
                agility=apprentice.base_agility, intelligence=apprentice.base_intelligence,
                luck=apprentice.base_luck,
            )
            self.members.append(member)
        self.db.add_all(self.members)
        self.db.commit()
        self.now = now

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_housing_capacity_recalculates_without_removing_existing_mercenaries(self):
        housing = next(row for row in self.db.scalars(
            select(GuildBuilding).where(GuildBuilding.guild_id == self.guild.id)
        ) if row.building_template.effect_type == "housing")
        housing.level = 50
        self.db.commit()

        self.assertEqual(get_mercenary_limit(self.db, self.guild.id), 11)
        self.assertEqual(len(list(self.db.scalars(select(Mercenary).where(
            Mercenary.guild_id == self.guild.id,
            Mercenary.status != "dismissed",
        )))), 5)

    def test_funded_housing_service_reaches_level_100_and_twentieth_slot(self):
        housing = next(row for row in self.db.scalars(
            select(GuildBuilding).where(GuildBuilding.guild_id == self.guild.id)
        ) if row.building_template.effect_type == "housing")
        wood = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
        ).order_by(ItemTemplate.id))
        self.assertIsNotNone(wood)
        self.guild.level = 50
        self.resources.gold = 2_000_000
        housing.level = 50
        self.db.commit()
        add_inventory_quantity(self.db, self.guild.id, wood.id, 200_000)
        self.db.flush()

        for _ in range(50):
            housing = upgrade_guild_building(self.db, self.guild, self.resources, housing.id)

        self.assertEqual(housing.level, 100)
        self.assertEqual(get_mercenary_limit(self.db, self.guild.id), 20)
        self.assertEqual(len(list(self.db.scalars(select(Mercenary).where(
            Mercenary.guild_id == self.guild.id,
            Mercenary.status != "dismissed",
        )))), 5)
        with self.assertRaises(BuildingError):
            upgrade_guild_building(self.db, self.guild, self.resources, housing.id)

    def _set_inventory_usage(self, target: int, template: ItemTemplate) -> None:
        from sqlalchemy import delete

        self.db.execute(delete(GuildInventoryItem).where(GuildInventoryItem.guild_id == self.guild.id))
        self.db.add(GuildInventoryItem(
            guild_id=self.guild.id, item_template_id=template.id, quantity=max(0, int(target)),
        ))
        self.db.flush()

    def test_regional_supply_is_debited_once_at_start_and_failure_claim_keeps_cost(self):
        template = MissionTemplate(
            name="Supply transaction fixture", description="", mission_type="standard",
            level_band="1-20", recommended_level=1, recommended_power=10,
            duration_seconds=60, base_gold_reward=1_000, base_xp_reward=40,
            base_success_chance=5, min_party_size=1, max_party_size=1,
            required_guild_level=1, required_min_mercenary_level=1, is_active=True,
        )
        self.db.add(template)
        self.db.flush()
        self.resources.gold = 100
        self.db.commit()
        before = self.resources.gold

        with self.assertRaisesRegex(mission_service.MissionError, "apenas em contratos regionais"):
            start_mission(self.db, self.guild, str(template.id), [str(self.members[0].id)], supply_selected=True)
        self.assertEqual(self.resources.gold, before)

        with self.assertRaises(mission_service.MissionError):
            start_mission(self.db, self.guild, str(template.id), ["999999"], supply_selected=True,
                          supply_rank="E", allow_regional_supply=True)
        self.db.rollback()
        self.assertEqual(self.resources.gold, before)

        with patch.object(mission_service, "get_party_chance_details", return_value={"final_chance": 5}):
            run = start_mission(
                self.db, self.guild, str(template.id), [str(self.members[0].id)],
                supply_selected=True, supply_rank="E", allow_regional_supply=True,
            )
        snapshot = json.loads(run.preparation_snapshot_json)
        self.assertEqual(snapshot["cost_gold"], 1)
        self.assertEqual(snapshot["chance_bonus_pp"], 5)
        self.assertEqual(self.resources.gold, before - 1)
        self.assertEqual(run.run_multiplier, 1)

        run.ends_at = self.now - timedelta(seconds=1)  # finished while the campaign was closed
        self.db.commit()
        with patch.object(mission_service, "randint", return_value=100):
            resolved = claim_mission_loot(self.db, self.guild, self.resources, run.id)
        self.assertFalse(resolved.success)
        self.assertEqual(resolved.xp_reward, 10)
        self.assertEqual(self.resources.gold, before - 1)
        with self.assertRaisesRegex(mission_service.MissionError, "já foi resolvida"):
            claim_mission_loot(self.db, self.guild, self.resources, run.id)
        self.assertEqual(self.resources.gold, before - 1)

    def test_dungeon_supply_quote_snapshot_and_resolution_share_explorers_and_skill_chance(self):
        member = self.members[0]
        knight = self.db.scalar(select(MercenaryClass).where(MercenaryClass.code == "knight"))
        self.assertIsNotNone(knight)
        member.class_id = knight.id
        skill_template = SkillTemplate(
            class_id=knight.id, name="Chance de masmorra fixture", description="",
            effect_type="success_chance", effect_value=8, max_level=10, is_active=True,
        )
        self.db.add(skill_template)
        self.db.flush()
        self.db.add(MercenarySkill(mercenary_id=member.id, skill_template_id=skill_template.id, level=1))
        template = DungeonTemplate(
            name="Dungeon Supply Chance Fixture", description="", content_type="dungeon",
            level_band="1-20", recommended_level=1, duration_seconds=60,
            base_gold_reward=1_000, base_xp_reward=100, base_success_chance=50,
            min_party_size=1, max_party_size=1, required_guild_level=1,
            required_min_mercenary_level=1, required_building_type="scouts",
            required_building_level=1, is_active=True,
        )
        self.db.add(template)
        scouts = next(row for row in self.db.scalars(select(GuildBuilding))
                      if row.building_template.effect_type == "scouts")
        scouts.level = 50
        self.db.commit()

        member_ids = [str(member.id)]
        quote = get_dungeon_supply_quote(self.db, self.guild, str(template.id), member_ids, "2")
        quote_one_x = get_dungeon_supply_quote(self.db, self.guild, str(template.id), member_ids, "1")
        quote_other_party = get_dungeon_supply_quote(
            self.db, self.guild, str(template.id), [str(self.members[1].id)], "2",
        )
        self.assertTrue(quote["available"], quote)
        self.assertTrue(quote_one_x["available"], quote_one_x)
        self.assertTrue(quote_other_party["available"], quote_other_party)
        self.assertEqual(quote["cost_gold"], 2)
        self.assertEqual(quote_one_x["cost_gold"], 1)
        self.assertGreater(quote["base_final_chance"], quote_other_party["base_final_chance"])
        no_supply_chance = get_final_dungeon_chance(self.db, self.guild.id, template, [member])
        self.assertGreater(no_supply_chance, 50)  # skill + Scouts are included in the no-supply result
        self.assertEqual(quote["base_final_chance"], no_supply_chance)
        self.assertEqual(quote["final_chance"], min(95, no_supply_chance + quote["chance_bonus_pp"]))

        run = start_dungeon(
            self.db, self.guild, str(template.id), member_ids,
            run_multiplier="2", supply_selected=True, commit=False,
        )
        snapshot = json.loads(run.preparation_snapshot_json)
        self.assertEqual(snapshot["base_final_chance"], no_supply_chance)
        self.assertEqual(snapshot["base_final_chance"], quote["base_final_chance"])
        self.assertEqual(snapshot["chance_bonus_pp"], quote["chance_bonus_pp"])
        self.assertEqual(snapshot["cost_gold"], quote["cost_gold"])

        run.ends_at = self.now - timedelta(seconds=1)
        self.db.commit()
        with patch.object(dungeon_service, "randint", return_value=1):
            resolved = claim_dungeon_loot(self.db, self.guild, self.resources, run.id)
        details = parse_result_details(resolved.result_details)
        self.assertIn(
            f"Chance final: {quote['final_chance']}% (suprimento +{quote['chance_bonus_pp']} p.p.; custo registrado no início).",
            details["notes"],
        )

    def test_mission_start_and_claim_apply_real_mercenary_xp(self):
        from app.services.balance_service import xp_required_for_level

        member = self.members[0]
        member.xp = xp_required_for_level(member.level) - 1
        candidates = list(self.db.scalars(select(MissionTemplate).where(
            MissionTemplate.is_active.is_(True), MissionTemplate.mission_type != "long_idle",
            MissionTemplate.required_guild_level <= 1,
            MissionTemplate.required_min_mercenary_level <= 1,
            MissionTemplate.min_party_size <= 5,
            MissionTemplate.required_building_level <= 10,
        ).order_by(MissionTemplate.duration_seconds, MissionTemplate.id)))
        from app.repositories.item_repository import list_active_drops_for_mission

        template = next((candidate for candidate in candidates if any(
            drop.item_template.item_type == "material"
            for drop in list_active_drops_for_mission(self.db, candidate.id)
        )), None)
        self.assertIsNotNone(template)
        party = self.members[:template.min_party_size]
        wood = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.id))
        self._set_inventory_usage(get_inventory_capacity(self.db, self.guild), wood)
        mission_overflow = []
        original_add = add_inventory_quantity_capped

        def capture_mission_add(*args, **kwargs):
            result = original_add(*args, **kwargs)
            mission_overflow.append(result)
            return result

        clock = iter((self.now, self.now + timedelta(days=1)))
        with patch.object(mission_service, "add_inventory_quantity_capped", side_effect=capture_mission_add), \
                patch.object(mission_service, "utc_now", side_effect=lambda: next(clock)), \
                patch.object(mission_service, "randint", side_effect=lambda _a, _b: 1):
            run = start_mission(self.db, self.guild, str(template.id), [str(member.id) for member in party], commit=False)
            self.db.flush()
            claim_mission_loot(self.db, self.guild, self.resources, run.id, commit=False)
        self.db.refresh(member)
        self.assertEqual(run.status, "completed")
        self.assertTrue(run.success)
        self.assertGreater(member.level, 1)
        self.assertGreaterEqual(member.xp, 0)
        self.assertTrue(any(discarded > 0 for _stored, discarded in mission_overflow))

    def test_level_one_apprentice_can_start_and_claim_catalog_mission_without_office(self):
        office = next(row for row in self.db.scalars(select(GuildBuilding))
                      if row.guild_id == self.guild.id and row.building_template.effect_type == "contract_office")
        office.level = 0
        template = self.db.scalar(select(MissionTemplate).where(
            MissionTemplate.is_active.is_(True),
            MissionTemplate.mission_type != "long_idle",
            MissionTemplate.required_guild_level <= 1,
            MissionTemplate.required_min_mercenary_level <= 1,
            MissionTemplate.min_party_size <= 1,
            MissionTemplate.max_party_size >= 1,
            (MissionTemplate.required_building_type.is_(None) | (MissionTemplate.required_building_level == 0)),
        ).order_by(MissionTemplate.duration_seconds, MissionTemplate.id).limit(1))
        self.assertIsNotNone(template, "fresh catalog needs one mission available to guild/apprentice level 1")
        self.assertEqual(template.mission_type, "gathering")
        member = self.members[0]
        self.assertEqual((self.guild.level, member.level, office.level), (1, 1, 0))
        with patch.object(mission_service, "utc_now", side_effect=(self.now, self.now + timedelta(days=1))), \
                patch.object(mission_service, "randint", return_value=1):
            run = start_mission(self.db, self.guild, str(template.id), [str(member.id)], commit=False)
            run.ends_at = self.now - timedelta(seconds=1)
            resolved = claim_mission_loot(self.db, self.guild, self.resources, run.id, commit=False)
        self.assertEqual(resolved.status, "completed")
        self.assertTrue(resolved.success)

    def test_material_market_and_salvage_use_live_capacity_and_prices(self):
        wood = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.id))
        self.db.add(GuildInventoryItem(guild_id=self.guild.id, item_template_id=wood.id, quantity=20))
        self.db.commit()
        sale_start = self.now
        with patch.object(market_service, "utc_now", return_value=sale_start):
            sale = start_material_sale(self.db, self.guild, str(wood.id), "10")
        before_gold = self.resources.gold
        sale_end = sale.ends_at.replace(tzinfo=timezone.utc) if sale.ends_at.tzinfo is None else sale.ends_at
        with patch.object(market_service, "utc_now", return_value=sale_end + timedelta(seconds=1)):
            collect_market_sale(self.db, self.guild, self.resources, sale.id)
        self.db.refresh(self.resources)
        self.assertEqual(sale.status, "completed")
        self.assertEqual(self.resources.gold - before_gold, sale.total_value)

        equipment = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "equipment", ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.id))
        instance = create_equipment_instance_from_template(self.db, self.guild.id, equipment)
        self.db.commit()
        capacity = get_inventory_capacity(self.db, self.guild)
        usage = get_inventory_usage(self.db, self.guild.id)
        filler = max(0, capacity - usage - 1)
        wood_stack = self.db.scalar(select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == wood.id,
        ))
        wood_stack.quantity += filler
        self.db.commit()
        usage_before_salvage = get_inventory_usage(self.db, self.guild.id)
        salvage_start = self.now
        with patch.object(salvage_service, "utc_now", return_value=salvage_start):
            job = start_salvage(self.db, self.guild, self.resources, "1", str(equipment.id), "1")
        salvage_overflow = []
        original_add = add_inventory_quantity_capped

        def capture_salvage_add(*args, **kwargs):
            result = original_add(*args, **kwargs)
            salvage_overflow.append(result)
            return result

        seeded_rng = random.Random(0)
        salvage_end = job.ends_at.replace(tzinfo=timezone.utc) if job.ends_at.tzinfo is None else job.ends_at
        with patch.object(salvage_service, "add_inventory_quantity_capped", side_effect=capture_salvage_add), \
                patch.object(salvage_service, "utc_now", return_value=salvage_end + timedelta(seconds=1)), \
                patch.object(salvage_service, "SystemRandom", return_value=seeded_rng):
            collect_salvage(self.db, self.guild, str(job.id))
        self.db.refresh(job)
        usage_after_salvage = get_inventory_usage(self.db, self.guild.id)
        self.assertEqual(job.status, "completed")
        self.assertLessEqual(usage_after_salvage, capacity)
        self.assertLessEqual(usage_after_salvage - usage_before_salvage, job.result_quantity)
        self.assertTrue(any(discarded > 0 for _stored, discarded in salvage_overflow))

    def test_material_market_quota_counts_active_sales_and_reopens_after_24h(self):
        wood = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.id))
        self._set_inventory_usage(30, wood)
        first_start = self.now
        with patch.object(market_service, "MATERIAL_BASE_UNITS_PER_24H", 10), \
                patch.object(market_service, "utc_now", return_value=first_start):
            first = start_material_sale(self.db, self.guild, str(wood.id), "10")
            quota = get_material_sale_quota(self.db, self.guild.id, now=first_start)
        self.assertEqual({key: value for key, value in quota.items() if key != "next_release_at"},
                         {"limit": 10, "used": 10, "remaining": 0})
        self.assertIsNotNone(quota["next_release_at"])
        first_end = first.ends_at.replace(tzinfo=timezone.utc) if first.ends_at.tzinfo is None else first.ends_at
        with patch.object(market_service, "utc_now", return_value=first_end + timedelta(seconds=1)):
            collect_market_sale(self.db, self.guild, self.resources, first.id)
        # The completed sale still occupies rolling quota until its start time
        # leaves the 24-hour window; collection frees the only sale slot.
        with patch.object(market_service, "MATERIAL_BASE_UNITS_PER_24H", 10), \
                patch.object(market_service, "utc_now", return_value=first_end + timedelta(seconds=2)):
            with self.assertRaisesRegex(MarketError, "restam 0 de 10"):
                start_material_sale(self.db, self.guild, str(wood.id), "1")
        reopened_at = first_start + timedelta(hours=24)
        with patch.object(market_service, "MATERIAL_BASE_UNITS_PER_24H", 10), \
                patch.object(market_service, "utc_now", return_value=reopened_at):
            quota = get_material_sale_quota(self.db, self.guild.id, now=reopened_at)
            second = start_material_sale(self.db, self.guild, str(wood.id), "10")
        self.assertEqual({key: value for key, value in quota.items() if key != "next_release_at"},
                         {"limit": 10, "used": 0, "remaining": 10})
        self.assertEqual(second.quantity, 10)

    def test_material_market_quota_scales_with_slots(self):
        wood = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.id))
        market = next(row for row in ensure_guild_buildings(self.db, self.guild.id)
                      if row.building_template.effect_type == "market")
        market.level = 6
        self._set_inventory_usage(40, wood)
        with patch.object(market_service, "MATERIAL_BASE_UNITS_PER_24H", 10), \
                patch.object(market_service, "utc_now", return_value=self.now):
            first = start_material_sale(self.db, self.guild, str(wood.id), "15")
            quota = get_material_sale_quota(self.db, self.guild.id, now=self.now)
        self.assertEqual({key: value for key, value in quota.items() if key != "next_release_at"},
                         {"limit": 15, "used": 15, "remaining": 0})
        self.assertEqual(first.quantity, 15)

    def test_material_market_quota_starts_at_25_and_steps_at_five_level_milestones(self):
        market = next(row for row in ensure_guild_buildings(self.db, self.guild.id)
                      if row.building_template.effect_type == "market")
        self.assertEqual(get_material_sale_quota(self.db, self.guild.id, now=self.now)["limit"], 25)
        market.level = 4
        self.assertEqual(get_material_sale_quota(self.db, self.guild.id, now=self.now)["limit"], 25)
        market.level = 5
        self.assertEqual(get_material_sale_quota(self.db, self.guild.id, now=self.now)["limit"], 30)
        market.level = 9
        self.assertEqual(get_material_sale_quota(self.db, self.guild.id, now=self.now)["limit"], 30)
        market.level = 10
        self.assertEqual(get_material_sale_quota(self.db, self.guild.id, now=self.now)["limit"], 35)
        market.level = 100
        self.assertEqual(get_material_sale_quota(self.db, self.guild.id, now=self.now)["limit"], 125)

    def test_concurrent_material_sale_submissions_cannot_overbook_quota(self):
        with TemporaryDirectory(prefix="gim-market-quota-race-") as temp_dir:
            engine = create_database_engine(f"sqlite:///{(Path(temp_dir) / 'race.sqlite3').as_posix()}")
            Base.metadata.create_all(engine)
            try:
                with Session(engine, expire_on_commit=False) as db:
                    apply_initial_campaign_content(db)
                    campaign = CampaignMetadata(
                        campaign_id="00000000-0000-0000-0000-0000000000aa",
                        campaign_name="Market quota race", created_at_utc=self.now,
                        updated_at_utc=self.now, schema_version=5, content_version=PACK_VERSION,
                        home_region="Fronteira do Norte",
                    )
                    guild = Guild(campaign_id=campaign.campaign_id, name="Quota race", level=1)
                    resources = GuildResources(guild=guild, gold=10_000)
                    db.add_all((campaign, guild, resources))
                    db.flush()
                    market = next(row for row in ensure_guild_buildings(db, guild.id)
                                  if row.building_template.effect_type == "market")
                    market.level = 6  # two slots allow both submits to reach the quota check
                    wood = db.scalar(select(ItemTemplate).where(
                        ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
                        ItemTemplate.is_active.is_(True),
                    ).order_by(ItemTemplate.id))
                    db.add(GuildInventoryItem(
                        guild_id=guild.id, item_template_id=wood.id, quantity=30,
                    ))
                    db.commit()
                    campaign_id, wood_id, guild_id = campaign.campaign_id, wood.id, guild.id

                barrier = Barrier(2)

                def submit_sale():
                    with Session(engine, expire_on_commit=False) as db:
                        guild = db.scalar(select(Guild).where(Guild.id == guild_id))
                        barrier.wait(timeout=10)
                        try:
                            start_material_sale(db, guild, str(wood_id), "15")
                            return "accepted"
                        except MarketError:
                            db.rollback()
                            return "rejected"

                with patch.object(market_service, "MATERIAL_BASE_UNITS_PER_24H", 10):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        outcomes = list(executor.map(lambda _index: submit_sale(), range(2)))
                self.assertCountEqual(outcomes, ["accepted", "rejected"])
                with Session(engine) as db:
                    rows = list(db.scalars(select(MarketSale).where(MarketSale.guild_id == guild_id)))
                    stack = get_inventory_item(db, guild_id, wood_id)
                    with patch.object(market_service, "MATERIAL_BASE_UNITS_PER_24H", 10):
                        quota = get_material_sale_quota(db, guild_id)
                self.assertEqual(sum(row.quantity for row in rows), 15)
                self.assertEqual(stack.quantity, 15)
                self.assertEqual(quota["used"], 15)
            finally:
                engine.dispose()

    def test_crafted_equipment_can_flow_through_salvage_and_market_services(self):
        blacksmith = next(row for row in self.db.scalars(select(GuildBuilding))
                          if row.guild_id == self.guild.id and row.building_template.effect_type == "blacksmith")
        blacksmith.level = 100
        recipes = list_rotating_recipes(self.db, self.guild, blacksmith.level)[0]
        recipe = next((candidate for candidate in recipes
                       if candidate.output_item_template.item_type == "equipment"), None)
        self.assertIsNotNone(recipe, "the live recipe rotation should include an equipment recipe")
        for material in recipe.materials:
            stack = get_inventory_item(self.db, self.guild.id, material.item_template_id)
            if stack is None:
                stack = GuildInventoryItem(
                    guild_id=self.guild.id, item_template_id=material.item_template_id, quantity=0,
                )
                self.db.add(stack)
            stack.quantity += material.quantity
        self.db.commit()

        before_gold = self.resources.gold
        craft_recipe(self.db, self.guild, self.resources, str(recipe.id))
        gold_after_craft = self.resources.gold
        craft_gold_debit = before_gold - gold_after_craft
        instance = self.db.scalar(select(GuildItemInstance).where(
            GuildItemInstance.guild_id == self.guild.id,
            GuildItemInstance.item_template_id == recipe.output_item_template_id,
        ))
        self.assertIsNotNone(instance)
        with patch.object(salvage_service, "utc_now", return_value=self.now):
            job = start_salvage(
                self.db, self.guild, self.resources, "1", str(recipe.output_item_template_id), "1",
            )
        salvage_end = job.ends_at.replace(tzinfo=timezone.utc) if job.ends_at.tzinfo is None else job.ends_at
        with patch.object(salvage_service, "utc_now", return_value=salvage_end + timedelta(seconds=1)), \
                patch.object(salvage_service, "SystemRandom", return_value=random.Random(0)):
            collect_salvage(self.db, self.guild, str(job.id))
        material_stack = get_inventory_item(self.db, self.guild.id, job.material_template_id)
        self.assertIsNotNone(material_stack)
        self.assertGreaterEqual(material_stack.quantity, job.result_quantity)

        sale_start = self.now + timedelta(days=2)
        with patch.object(market_service, "utc_now", return_value=sale_start):
            sale = start_material_sale(self.db, self.guild, str(job.material_template_id), str(job.result_quantity))
        sale_end = sale.ends_at.replace(tzinfo=timezone.utc) if sale.ends_at.tzinfo is None else sale.ends_at
        with patch.object(market_service, "utc_now", return_value=sale_end + timedelta(seconds=1)):
            collect_market_sale(self.db, self.guild, self.resources, sale.id)

        self.assertEqual(sale.status, "completed")
        self.assertEqual(self.resources.gold, gold_after_craft - job.gold_cost + sale.total_value)
        self.assertGreaterEqual(craft_gold_debit, recipe.gold_cost)

    def test_dungeon_start_and_claim_resolve_real_loot_and_xp(self):
        templates = list(self.db.scalars(select(DungeonTemplate).where(
            DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "dungeon",
            DungeonTemplate.required_guild_level <= 1,
            DungeonTemplate.required_min_mercenary_level <= 1,
            DungeonTemplate.min_party_size <= len(self.members),
        ).order_by(DungeonTemplate.required_guild_level, DungeonTemplate.required_min_mercenary_level,
                   DungeonTemplate.id)))
        from app.repositories.dungeon_repository import list_active_drops_for_dungeon

        template = next((candidate for candidate in templates if any(
            drop.item_template.item_type == "material"
            for drop in list_active_drops_for_dungeon(self.db, candidate.id)
        )), templates[0] if templates else None)
        self.assertIsNotNone(template)
        party = self.members[:template.min_party_size]
        wood = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.id))
        self._set_inventory_usage(get_inventory_capacity(self.db, self.guild), wood)
        dungeon_overflow = []
        original_add = add_inventory_quantity_capped

        def capture_dungeon_add(*args, **kwargs):
            result = original_add(*args, **kwargs)
            dungeon_overflow.append(result)
            return result

        clock = iter((self.now, self.now + timedelta(days=1)))
        with patch.object(dungeon_service, "add_inventory_quantity_capped", side_effect=capture_dungeon_add), \
                patch.object(dungeon_service, "utc_now", side_effect=lambda: next(clock)), \
                patch.object(dungeon_service, "randint", side_effect=lambda _a, _b: 1):
            run = start_dungeon(self.db, self.guild, str(template.id), [str(member.id) for member in party], commit=False)
            self.db.flush()
            claim_dungeon_loot(self.db, self.guild, self.resources, run.id, commit=False)
        self.assertEqual(run.status, "completed")
        self.assertTrue(run.success)
        self.assertTrue(any(discarded > 0 for _stored, discarded in dungeon_overflow))

    def test_recent_mission_drop_equipped_changes_paired_dungeon_result_and_loot(self):
        party = self.members[:2]
        mission_candidates = self.db.scalars(select(MissionTemplate).where(
            MissionTemplate.is_active.is_(True),
            MissionTemplate.mission_type != "long_idle",
            MissionTemplate.required_guild_level <= self.guild.level,
            MissionTemplate.required_min_mercenary_level <= 1,
            MissionTemplate.min_party_size <= 1,
            MissionTemplate.max_party_size >= 1,
        ).order_by(MissionTemplate.id))
        mission_and_drop = next((
            (mission, drop)
            for mission in mission_candidates
            if mission_is_unlocked(self.db, self.guild, mission)
            for drop in list_active_drops_for_mission(self.db, mission.id)
            if drop.item_template.item_type == "equipment"
            and drop.drop_chance > 0
            and drop.item_template.required_level <= self.members[0].level
            and can_class_equip_item(self.members[0], drop.item_template)[0]
        ), None)
        self.assertIsNotNone(mission_and_drop, "fresh catalog needs a level-one-compatible mission gear drop")
        mission_template, mission_drop = mission_and_drop

        mission_clock = iter((self.now, self.now + timedelta(days=1)))
        with patch.object(mission_service, "utc_now", side_effect=lambda: next(mission_clock)), \
                patch.object(mission_service, "randint", return_value=1), \
                patch.object(equipment_service, "choice", return_value="power"), \
                patch.object(equipment_service, "randint", return_value=1):
            mission_run = start_mission(
                self.db, self.guild, str(mission_template.id), [str(self.members[0].id)], commit=False,
            )
            claimed_mission = claim_mission_loot(
                self.db, self.guild, self.resources, mission_run.id, commit=False,
            )
        self.assertTrue(claimed_mission.success)
        mission_result = parse_result_details(claimed_mission.result_details)
        mission_item = self.db.scalar(select(GuildItemInstance).where(
            GuildItemInstance.guild_id == self.guild.id,
            GuildItemInstance.item_template_id == mission_drop.item_template_id,
            GuildItemInstance.equipped_to_mercenary_id.is_(None),
        ).order_by(GuildItemInstance.id))
        self.assertIsNotNone(mission_item, "mission claim must materialize its equipment drop as an instance")
        self.assertTrue(mission_result["items"])

        dungeon_template = next(iter(self.db.scalars(select(DungeonTemplate).where(
            DungeonTemplate.is_active.is_(True),
            DungeonTemplate.content_type == "dungeon",
            DungeonTemplate.required_guild_level <= self.guild.level,
            DungeonTemplate.required_min_mercenary_level <= min(member.level for member in party),
            DungeonTemplate.min_party_size <= len(party),
            DungeonTemplate.max_party_size >= len(party),
        ).order_by(DungeonTemplate.required_guild_level, DungeonTemplate.required_min_mercenary_level,
                   DungeonTemplate.id))), None)
        self.assertIsNotNone(dungeon_template, "fresh catalog needs an accessible two-member dungeon")

        power_before = get_party_power_score(self.db, self.guild.id, party)
        chance_before = get_advanced_dungeon_chance(self.db, self.guild.id, dungeon_template, party)
        deterministic_roll = int(chance_before["final_chance"]) + 1
        self.assertLessEqual(deterministic_roll, 100)

        def resolve_dungeon() -> tuple[object, object]:
            state = {"outcome_checked": False}
            clock = iter((self.now, self.now + timedelta(days=1)))

            def roll(low: int, high: int) -> int:
                if not state["outcome_checked"]:
                    state["outcome_checked"] = True
                    return deterministic_roll
                return low

            with patch.object(dungeon_service, "utc_now", side_effect=lambda: next(clock)), \
                    patch.object(dungeon_service, "randint", side_effect=roll), \
                    patch.object(equipment_service, "choice", return_value="power"), \
                    patch.object(equipment_service, "randint", return_value=1):
                run = start_dungeon(
                    self.db, self.guild, str(dungeon_template.id),
                    [str(member.id) for member in party], commit=False,
                )
                claimed = claim_dungeon_loot(
                    self.db, self.guild, self.resources, run.id, commit=False,
                )
            return run, claimed

        baseline_savepoint = self.db.begin_nested()
        baseline_run, baseline_claim = resolve_dungeon()
        baseline_evidence = {
            "run_id": int(baseline_run.id),
            "status": str(baseline_claim.status),
            "success": bool(baseline_claim.success),
            "result": parse_result_details(baseline_claim.result_details),
        }
        self.assertEqual(baseline_evidence["status"], "failed")
        self.assertFalse(baseline_evidence["success"])
        baseline_savepoint.rollback()
        self.db.expire_all()

        # The baseline is rolled back so XP, guild progress, rewards and loot
        # cannot contaminate the equipment-only comparison.
        power_before_equip = get_party_power_score(self.db, self.guild.id, party)
        chance_before_equip = get_advanced_dungeon_chance(self.db, self.guild.id, dungeon_template, party)
        self.assertEqual(power_before_equip, power_before)
        self.assertEqual(chance_before_equip["final_chance"], chance_before["final_chance"])
        self.assertGreater(deterministic_roll, chance_before_equip["final_chance"])
        equip_mercenary_item(self.db, self.guild, self.members[0].id, str(mission_item.id))
        self.db.refresh(mission_item)
        power_after = get_party_power_score(self.db, self.guild.id, party)
        chance_after = get_advanced_dungeon_chance(self.db, self.guild.id, dungeon_template, party)
        self.assertGreater(power_after, power_before_equip)
        self.assertGreater(chance_after["final_chance"], chance_before_equip["final_chance"])
        self.assertLessEqual(deterministic_roll, chance_after["final_chance"])

        instance_ids_before_loot = set(self.db.scalars(select(GuildItemInstance.id).where(
            GuildItemInstance.guild_id == self.guild.id,
        )))
        post_run, post_claim = resolve_dungeon()
        self.assertTrue(post_claim.success)
        post_result = parse_result_details(post_claim.result_details)
        self.assertTrue(post_result["items"], "successful dungeon claim must record the seeded catalog loot")
        self.assertEqual(mission_item.equipped_to_mercenary_id, self.members[0].id)

        dungeon_drop_template_ids = {
            drop.item_template_id for drop in list_active_drops_for_dungeon(self.db, dungeon_template.id)
            if drop.item_template.item_type == "equipment"
        }
        dungeon_loot_instances = list(self.db.scalars(select(GuildItemInstance).where(
            GuildItemInstance.guild_id == self.guild.id,
            GuildItemInstance.id.not_in(instance_ids_before_loot),
            GuildItemInstance.item_template_id.in_(dungeon_drop_template_ids or {-1}),
        ).order_by(GuildItemInstance.id)))
        self.assertTrue(dungeon_loot_instances, "successful dungeon claim must materialize equipment loot instances")
        self.evidence = {
            "mission_template_id": mission_template.id,
            "mission_run_id": mission_run.id,
            "mission_drop_id": mission_drop.id,
            "item_template_id": mission_drop.item_template_id,
            "mission_item_instance_id": mission_item.id,
            "mercenary_id": self.members[0].id,
            "power_before": power_before,
            "power_before_equip": power_before_equip,
            "power_after": power_after,
            "dungeon_template_id": dungeon_template.id,
            "rolled_back_baseline_run_id": baseline_evidence["run_id"],
            "rolled_back_baseline_status": baseline_evidence["status"],
            "baseline_success": baseline_evidence["success"],
            "baseline_chance": chance_before["final_chance"],
            "chance_before_equip": chance_before_equip["final_chance"],
            "equipped_run_id": post_run.id,
            "equipped_status": post_claim.status,
            "equipped_success": bool(post_claim.success),
            "equipped_chance": chance_after["final_chance"],
            "deterministic_roll": deterministic_roll,
            "baseline_loot": baseline_evidence["result"]["items"],
            "equipped_loot": post_result["items"],
            "dungeon_loot_instances": [
                {"id": item.id, "item_template_id": item.item_template_id}
                for item in dungeon_loot_instances
            ],
        }
        self.assertEqual(self.evidence["baseline_success"], False)
        self.assertEqual(self.evidence["equipped_success"], True)
        self.assertEqual(self.evidence["equipped_status"], "completed")
        self.assertEqual(self.evidence["mission_item_instance_id"], mission_item.id)
        self.assertTrue(self.evidence["equipped_loot"])

    def test_gathering_reports_capacity_overflow_and_pause_resume(self):
        worker = self.members[-1]
        profession = self.db.scalar(select(ProfessionTemplate).where(
            ProfessionTemplate.material_family == "wood", ProfessionTemplate.is_active.is_(True),
        ).order_by(ProfessionTemplate.id))
        worker.profession_id = profession.id
        wood = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family == "wood",
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.id))
        stack = self.db.scalar(select(GuildInventoryItem).where(
            GuildInventoryItem.guild_id == self.guild.id,
            GuildInventoryItem.item_template_id == wood.id,
        ))
        if stack is None:
            stack = GuildInventoryItem(guild_id=self.guild.id, item_template_id=wood.id, quantity=0)
            self.db.add(stack)
        capacity = get_inventory_capacity(self.db, self.guild)
        stack.quantity += capacity - get_inventory_usage(self.db, self.guild.id) - 1
        self.db.commit()
        assignment = assign_worker(self.db, self.guild, worker.id, "wood", now=self.now)
        seed = next(
            candidate for candidate in range(1000)
            if random.Random(f"{candidate}:0").randrange(100) < assignment.extra_chance
        )
        assignment.rng_seed = seed
        first = advance_assignment(self.db, self.guild, assignment, now=self.now + timedelta(minutes=1))
        self.assertEqual((first["produced"], first["stored"], first["discarded"]), (2, 1, 1))
        self.assertTrue(first["paused"])

        stack.quantity -= 1
        resumed = advance_assignment(self.db, self.guild, assignment, now=self.now + timedelta(hours=1))
        next_cycle = advance_assignment(
            self.db, self.guild, assignment, now=self.now + timedelta(hours=1, minutes=1),
        )
        self.assertFalse(resumed["paused"])
        self.assertEqual(next_cycle["cycles"], 1)
        self.assertLessEqual(get_inventory_usage(self.db, self.guild.id), capacity)

    def test_regional_cycle_and_event_services_process_thresholded_portal(self):
        from app.services.regional_cycle_service import CYCLE_SECONDS, get_regional_board
        from app.models.regional import RegionalCycle, RegionalEvent, RegionalRegionState
        from app.services.regional_event_service import create_cycle_portals

        # Three closed cycles exercise normal service order without making the
        # integration suite replay a long campaign; the region is positioned
        # at the configured trigger threshold for this conditional gate check.
        horizon = self.now + timedelta(seconds=CYCLE_SECONDS * 3)
        board = get_regional_board(self.db, self.campaign, self.guild, horizon)
        self.assertTrue(board["regions"])
        regions = list(self.db.scalars(select(RegionalRegionState).where(
            RegionalRegionState.campaign_id == self.campaign.campaign_id,
        )))
        for region in regions:
            region.threat = 100
        self.db.flush()
        cycles = list(self.db.scalars(select(RegionalCycle).where(
            RegionalCycle.campaign_id == self.campaign.campaign_id,
        ).order_by(RegionalCycle.cycle_number)))
        for cycle in cycles:
            create_cycle_portals(self.db, self.campaign.campaign_id, cycle, regions)
            self.db.flush()
            if self.db.scalar(select(RegionalEvent.id).where(
                RegionalEvent.campaign_id == self.campaign.campaign_id,
                RegionalEvent.event_type == "portal", RegionalEvent.status == "active",
            )) is not None:
                break
        events = list(self.db.scalars(select(RegionalEvent).where(
            RegionalEvent.campaign_id == self.campaign.campaign_id,
            RegionalEvent.event_type.in_(("portal", "rebellion")),
        )))
        self.assertTrue(any(event.event_type == "portal" for event in events))

    def test_journey_runner_enters_claims_and_closes_an_active_portal_with_runtime_services(self):
        from app.models.regional import RegionalEvent, RegionalEventActivity, RegionalEventParticipant
        from app.services.regional_cycle_service import REGIONS, get_current_player_regional_guild, get_regional_board
        from app.services.regional_event_service import (
            build_portal_boss_snapshot, build_portal_loot_snapshot, expire_due_events,
        )
        from scripts.balance.simulate_stage5_service_journeys import _run_player_portal_if_available

        template = self.db.scalar(select(DungeonTemplate).where(
            DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "boss",
            DungeonTemplate.biome == "portal",
        ).order_by(DungeonTemplate.id))
        self.assertIsNotNone(template)
        home_code = next(code for code, name in REGIONS if name == self.campaign.home_region)
        get_regional_board(self.db, self.campaign, self.guild, self.now)
        player_state = get_current_player_regional_guild(self.db, self.campaign.campaign_id, self.guild.id)
        self.assertIsNotNone(player_state)
        snapshot = build_portal_boss_snapshot(template)
        snapshot.update({
            "min_party_size": 1, "max_party_size": 2, "required_guild_level": 1,
            "required_min_mercenary_level": 1, "required_building_type": None,
            "required_building_level": 0, "required_total_power": 0,
            "required_class_code": None, "required_tank_count": 0,
            "required_support_count": 0, "required_damage_count": 0,
            "required_equipment_tier": 0, "duration_seconds": 3600,
            "base_gold_reward": 100, "base_xp_reward": 100, "base_success_chance": 95,
        })
        event_seed = "runner-active-portal-service-check"
        event = RegionalEvent(
            campaign_id=self.campaign.campaign_id, event_type="portal", region_code=home_code,
            trigger_cycle_number=0, rules_version="regional-events-v1", seed=event_seed,
            status="active", dungeon_template_id=template.id, created_at_utc=self.now,
            expires_at_utc=self.now + timedelta(hours=3),
            summary_json=json.dumps({
                "portal_boss": {"version": "portal-boss-v1", "template": snapshot},
                "portal_loot": build_portal_loot_snapshot(self.db, template, event_seed),
            }),
        )
        self.db.add(event)
        self.db.flush()
        with patch.object(dungeon_service, "randint", return_value=1):
            result = _run_player_portal_if_available(
                self.db, self.campaign, self.guild, self.resources, player_state,
                home_code, self.members, self.now + timedelta(minutes=30), random.Random(0),
            )
        self.assertIsNotNone(result)
        self.assertTrue(result["success"])
        activity = self.db.scalar(select(RegionalEventActivity).where(
            RegionalEventActivity.event_id == event.id,
        ))
        participant = self.db.scalar(select(RegionalEventParticipant).where(
            RegionalEventParticipant.event_id == event.id,
        ))
        run = self.db.get(DungeonRun, activity.source_run_id)
        self.assertEqual(run.status, "completed")
        self.assertEqual(activity.status, "resolved")
        self.assertEqual(participant.status, "resolved")
        self.assertEqual(event.status, "active")  # Other guilds retain the portal window.
        expire_due_events(self.db, self.campaign.campaign_id, event.expires_at_utc)
        self.assertEqual(event.status, "resolved")
        self.assertEqual(json.loads(event.summary_json)["aggregate"]["successes"], 1)


if __name__ == "__main__":
    unittest.main()
