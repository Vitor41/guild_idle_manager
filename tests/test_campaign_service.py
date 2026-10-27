import gc
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select, text

from app.database.connection import SessionLocal, configure_database
from app.models import CampaignMetadata, MissionTemplate, User
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context


class CampaignServiceTests(unittest.TestCase):
    def test_two_campaigns_create_open_and_persist_in_isolation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                self._assert_campaigns_are_isolated(Path(temp_dir))
            finally:
                configure_database("sqlite:///:memory:")
                gc.collect()

    def _assert_campaigns_are_isolated(self, temp_path: Path) -> None:
        campaigns = CampaignService(temp_path / "saves")
        first = campaigns.create_campaign("Campanha Norte", "Guilda Norte")
        second = campaigns.create_campaign("Campanha Sul", "Guilda Sul")

        self.assertNotEqual(first.campaign_id, second.campaign_id)
        self.assertNotEqual(first.database_path, second.database_path)
        self.assertEqual(len(campaigns.list_campaigns()), 2)

        campaigns.activate_campaign(first.campaign_id)
        with SessionLocal() as db:
            guild, resources = get_current_guild_context(db, first.campaign_id)
            self.assertIsNotNone(guild)
            self.assertEqual(guild.name, "Guilda Norte")
            self.assertIsNotNone(resources)
            resources.gold = 321
            db.commit()
            self.assertEqual(db.scalar(select(func.count(User.id))), 0)
            self.assertEqual(db.scalar(select(func.count(CampaignMetadata.campaign_id))), 1)
            self.assertEqual(db.scalar(text("PRAGMA foreign_keys")), 1)
            content_count = db.scalar(select(func.count(MissionTemplate.id)))
            self.assertGreater(content_count, 0)

        campaigns.activate_campaign(second.campaign_id)
        with SessionLocal() as db:
            guild, resources = get_current_guild_context(db, second.campaign_id)
            self.assertIsNotNone(guild)
            self.assertEqual(guild.name, "Guilda Sul")
            self.assertIsNotNone(resources)
            self.assertEqual(resources.gold, 100)

        campaigns.activate_campaign(first.campaign_id)
        with SessionLocal() as db:
            guild, resources = get_current_guild_context(db, first.campaign_id)
            self.assertIsNotNone(guild)
            self.assertEqual(guild.name, "Guilda Norte")
            self.assertIsNotNone(resources)
            self.assertEqual(resources.gold, 321)
            self.assertEqual(db.scalar(select(func.count(MissionTemplate.id))), content_count)

        reopened = CampaignService(temp_path / "saves").inspect_campaign(first.campaign_id)
        self.assertEqual(reopened.campaign_id, first.campaign_id)
        self.assertEqual(reopened.campaign_name, "Campanha Norte")
        campaigns.close_active_campaign(first.campaign_id)
        closed = campaigns.inspect_campaign(first.campaign_id)
        self.assertEqual(closed.last_session_state, "closed")
        self.assertIsNotNone(closed.last_clean_shutdown_utc)


if __name__ == "__main__":
    unittest.main()
