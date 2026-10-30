import json
import random
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models import CampaignMetadata, Guild, GuildBuilding, GuildResources, ItemTemplate
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_VERSION
from app.repositories.item_repository import add_inventory_quantity
from app.services.building_service import ensure_guild_buildings

from scripts.balance import simulate_stage5_service_journeys as journey_runner
from scripts.balance.simulate_stage5_service_journeys import (
    _gathering_schedule,
    _horizon_blocked_targets,
    _is_activated_rebellion,
    _marketable_surplus,
    _write_json_atomic,
)


class Stage5ServiceJourneyRunnerTests(unittest.TestCase):
    def test_hire_redirect_requotes_housing_and_records_precheck_refusal(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine, autoflush=False, expire_on_commit=False)
        try:
            apply_initial_campaign_content(db)
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            campaign = CampaignMetadata(
                campaign_id="00000000-0000-0000-0000-000000000092",
                campaign_name="Redirected purchase quote fixture", created_at_utc=now,
                updated_at_utc=now, schema_version=5, content_version=PACK_VERSION,
                home_region="Vale da Fronteira",
            )
            guild = Guild(campaign_id=campaign.campaign_id, name="Redirect fixture", level=100)
            resources = GuildResources(guild=guild, gold=100)
            db.add_all((campaign, guild, resources))
            db.flush()
            buildings = {row.building_template.effect_type: row
                         for row in ensure_guild_buildings(db, guild.id)}
            buildings["housing"].level = 20
            buildings["tavern"].level = 1
            db.commit()

            rejections = []
            with patch.object(journey_runner, "get_mercenary_limit", return_value=0):
                bought, blocked = journey_runner._buy_if_possible(
                    db, guild, resources, buildings, "hire", journey_runner.PROFILES[0],
                    random.Random(1), 32, [], service_rejections=rejections,
                    attempt="planned_target",
                )

            self.assertFalse(bought)
            self.assertGreater(blocked["gold_shortfall"], 0)
            self.assertEqual(len(rejections), 1)
            rejection = rejections[0]
            self.assertEqual(rejection["service"], "building_upgrade_precheck")
            self.assertFalse(rejection["service_called"])
            self.assertEqual(rejection["requested_target"], "hire")
            self.assertEqual(rejection["target"], "housing")
            self.assertEqual(rejection["target_item"], "housing_21")
            self.assertEqual(rejection["precheck"]["available_gold"], 100)
            self.assertEqual(rejection["precheck"]["required_gold"], 2_650)
        finally:
            db.close()
            engine.dispose()

    def test_failed_optional_upgrade_preserves_prior_passive_gold_credit(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine, autoflush=False, expire_on_commit=False)
        try:
            apply_initial_campaign_content(db)
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            campaign = CampaignMetadata(
                campaign_id="00000000-0000-0000-0000-000000000091",
                campaign_name="Stage 5 ledger rollback fixture", created_at_utc=now,
                updated_at_utc=now, schema_version=5, content_version=PACK_VERSION,
                home_region="Vale da Fronteira",
            )
            guild = Guild(campaign_id=campaign.campaign_id, name="Ledger fixture", level=100)
            resources = GuildResources(guild=guild, gold=0)
            db.add_all((campaign, guild, resources))
            db.flush()
            buildings = {row.building_template.effect_type: row
                         for row in ensure_guild_buildings(db, guild.id)}
            buildings["housing"].level = 10
            for family in ("wood", "ore"):
                template = db.scalar(select(ItemTemplate).where(
                    ItemTemplate.item_type == "material", ItemTemplate.material_family == family,
                ).order_by(ItemTemplate.id))
                add_inventory_quantity(db, guild.id, template.id, 100_000)
            db.commit()

            gold_start = int(resources.gold)
            passive_gold_credited = 1
            resources.gold += passive_gold_credited
            purchases = []
            rejections = []
            # Deliberately give the harness a stale, cheap quote. The live service
            # must reject its own current cost, and the rejection must show both.
            with patch.object(journey_runner, "get_upgrade_cost", return_value={"gold": 1, "wood": 0,
                                                                                  "ore": 0, "crystals": 0}):
                bought, _ = journey_runner._buy_if_possible(
                    db, guild, resources, buildings, "housing", journey_runner.PROFILES[0],
                    random.Random(1), 32, purchases, service_rejections=rejections,
                    attempt="planned_target",
                )

            self.assertFalse(bought)
            self.assertEqual(purchases, [])
            self.assertEqual(len(rejections), 1)
            self.assertEqual(rejections[0]["service"], "building_upgrade")
            self.assertEqual(rejections[0]["day"], 32)
            self.assertEqual(rejections[0]["attempt"], "planned_target")
            self.assertEqual(rejections[0]["target_item"], "housing_11")
            self.assertEqual(rejections[0]["precheck"]["required_gold"], 1)
            self.assertEqual(rejections[0]["precheck"]["gold_shortfall"], 0)
            self.assertGreater(rejections[0]["actual_can_pay"]["required"]["gold"],
                               rejections[0]["actual_can_pay"]["available_gold"])
            self.assertEqual(rejections[0]["actual_can_pay"]["available_gold"], gold_start + passive_gold_credited)
            self.assertEqual(int(resources.gold), gold_start + passive_gold_credited)
            db.commit()
            db.refresh(resources)
            gold_end = int(resources.gold)
            observed_delta = gold_end - gold_start
            self.assertEqual(observed_delta, passive_gold_credited)
            self.assertEqual(observed_delta - passive_gold_credited, 0)
        finally:
            db.close()
            engine.dispose()

    def test_rebellion_day_metric_ignores_roll_rows_that_did_not_activate(self):
        self.assertFalse(_is_activated_rebellion(SimpleNamespace(
            summary_json=json.dumps({"eligible": True, "generated_while_campaign_open": False}),
        )))
        self.assertFalse(_is_activated_rebellion(SimpleNamespace(
            summary_json=json.dumps({"eligible": True, "suppressed_by_global_limit": True}),
        )))
        self.assertTrue(_is_activated_rebellion(SimpleNamespace(
            summary_json=json.dumps({"eligible": True, "generated_while_campaign_open": True}),
        )))

    def test_market_sales_only_take_units_above_the_protected_material_reserve(self):
        self.assertEqual(_marketable_surplus(160, 70), 90)
        self.assertEqual(_marketable_surplus(70, 70), 0)
        self.assertEqual(_marketable_surplus(50, 70), 0)

    def test_gathering_schedule_uses_online_windows_and_offline_credit_not_24h(self):
        day_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scenarios = (
            ({0: 6.0, 1: 6.0}, 8 * 3600, 20 * 3600),
            ({0: 2.0}, 4 * 3600, 6 * 3600),
            ({0: 4.0, 2: 4.0}, 8 * 3600, 16 * 3600),
            ({0: 6.0, 1: 2.0}, 8 * 3600, 16 * 3600),
        )
        for online_windows, offline_seconds, expected in scenarios:
            with self.subTest(online_windows=online_windows):
                schedule = _gathering_schedule(day_start, online_windows, offline_seconds)
                self.assertEqual(sum(item["max_seconds"] for item in schedule), expected)
                self.assertLess(expected, 24 * 3600)
                self.assertEqual(
                    [item["at"] for item in schedule],
                    sorted(item["at"] for item in schedule),
                )
                self.assertEqual(schedule[-1]["kind"], "checkpoint")
                self.assertEqual(schedule[-1]["max_seconds"], 0)
                self.assertTrue(all(item["max_seconds"] > 0 for item in schedule[:-1]))

    def test_historical_block_is_not_reported_as_current_when_plan_is_complete(self):
        old_snapshot = {
            "item": "contract_office_10", "gold_shortfall": 596,
            "guild_level_shortfall": 0, "material_shortfalls": {"wood": 0, "ore": 0},
        }
        self.assertEqual(_horizon_blocked_targets((), old_snapshot), {})
        self.assertEqual(
            list(_horizon_blocked_targets(("contract_office",), old_snapshot)),
            ["contract_office_10"],
        )

    def test_checkpoint_json_is_replaced_atomically_with_parseable_content(self):
        with TemporaryDirectory(prefix="gim_stage5_checkpoint_test_") as temp_dir:
            target = Path(temp_dir) / "journey.json"
            target.write_text('{"old":true}\n', encoding="utf-8")
            _write_json_atomic(target, {"completed_seeds": 1, "journeys": [{"seed": 123}]})
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["completed_seeds"], 1)
            self.assertEqual(payload["journeys"][0]["seed"], 123)
            self.assertFalse(target.with_name(target.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
