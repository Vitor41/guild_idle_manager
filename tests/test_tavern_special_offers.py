import gc
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("APP_MODE", "desktop")

from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database
from app.models.guild import Guild
from app.models.mercenary import MercenaryClass
from app.services.campaign_service import CampaignService
from app.services.tavern_service import get_or_create_tavern_config, get_or_create_tavern_state, refresh_special_offer


class TavernSpecialOfferTests(unittest.TestCase):
    def test_generated_special_offer_starts_at_level_one_without_changing_offer_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Oferta especial nível 1", "Guilda Especial")
            campaigns.activate_campaign(campaign.campaign_id)
            try:
                now = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
                attributes = {"power": 31, "vitality": 19, "agility": 17, "intelligence": 13, "luck": 11}
                with SessionLocal() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign.campaign_id))
                    self.assertIsNotNone(guild)
                    config = get_or_create_tavern_config(db)
                    config.special_spawn_chance = 100
                    config.special_rare_chance = 100
                    config.special_epic_chance = 0
                    config.special_legendary_chance = 0
                    config.special_mythic_chance = 0
                    config.special_rare_cost = 4321
                    config.special_offer_duration_hours = 7
                    state = get_or_create_tavern_state(db, guild.id, config)
                    state.next_special_check_at = now - timedelta(seconds=1)
                    db.commit()

                    with (
                        patch("app.services.tavern_service.utc_now", return_value=now),
                        patch("app.services.tavern_service.randint", return_value=1),
                        patch("app.services.tavern_service.choice", return_value="warrior"),
                        patch("app.services.tavern_service.roll_attributes", return_value=attributes) as roll_attributes,
                    ):
                        offer = refresh_special_offer(db, guild, state, config)

                    warrior = db.scalar(select(MercenaryClass).where(MercenaryClass.code == "warrior"))
                    self.assertIsNotNone(offer)
                    self.assertIsNotNone(warrior)
                    self.assertEqual(offer.level, 1)
                    self.assertEqual(offer.rarity, "rare")
                    self.assertEqual(offer.class_id, warrior.id)
                    self.assertEqual(offer.gold_cost, 4321)
                    self.assertEqual(offer.available_from.replace(tzinfo=timezone.utc), now)
                    self.assertEqual(
                        offer.available_until.replace(tzinfo=timezone.utc),
                        now + timedelta(hours=7),
                    )
                    for attribute, value in attributes.items():
                        self.assertEqual(getattr(offer, attribute), value)
                    roll_attributes.assert_called_once_with("rare", warrior)
            finally:
                campaigns.close_active_campaign(campaign.campaign_id)
                configure_database("sqlite:///:memory:")
                gc.collect()


if __name__ == "__main__":
    unittest.main()
