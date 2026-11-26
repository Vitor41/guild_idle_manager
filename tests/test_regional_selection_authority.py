import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.database.connection import create_database_engine
from app.models.guild import Guild
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.mission import MissionRun, MissionTemplate
from app.services.campaign_service import CampaignService
from app.services.mission_service import MissionError, start_mission


class RegionalSelectionAuthorityTests(unittest.TestCase):
    def test_server_rejects_team_below_regional_snapshot_minimum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Equipe fora do mínimo", "Guilda de teste")
            engine = create_database_engine(f"sqlite:///{campaign.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            try:
                with factory() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign.campaign_id))
                    template = db.scalar(select(MissionTemplate).where(
                        MissionTemplate.is_active.is_(True),
                        MissionTemplate.required_guild_level <= guild.level,
                        MissionTemplate.required_min_mercenary_level <= 1,
                    ).order_by(MissionTemplate.id))
                    self.assertIsNotNone(template)
                    mercenary_class = db.scalar(select(MercenaryClass).where(
                        MercenaryClass.is_active.is_(True),
                    ).order_by(MercenaryClass.id))
                    mercenary = Mercenary(
                        guild_id=guild.id,
                        class_id=mercenary_class.id,
                        name="Integrante válido",
                        level=1,
                        power=10,
                        vitality=10,
                        agility=10,
                        intelligence=10,
                        luck=10,
                    )
                    db.add(mercenary)
                    db.flush()

                    with self.assertRaisesRegex(MissionError, "Grupo menor que o mínimo"):
                        start_mission(
                            db,
                            guild,
                            str(template.id),
                            [str(mercenary.id)],
                            commit=False,
                            regional_party_bounds=(2, 3),
                            regional_required_guild_level=guild.level,
                        )
                    self.assertEqual(
                        db.scalar(select(func.count(MissionRun.id)).where(MissionRun.guild_id == guild.id)),
                        0,
                    )
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
