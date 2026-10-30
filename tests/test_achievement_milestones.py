import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.models import (
    AchievementTemplate,
    CampaignMetadata,
    Guild,
    GuildAchievement,
    GuildItemInstance,
    GuildResources,
    ItemTemplate,
)
from app.services.achievement_service import (
    LEGENDARY_MILESTONES,
    AchievementError,
    claim_achievement,
    ensure_campaign_achievement_catalog,
)


class LegendaryAchievementTests(unittest.TestCase):
    def setUp(self):
        configure_database("sqlite:///:memory:")
        Base.metadata.create_all(bind=get_engine())
        self.campaign_id = str(uuid4())
        self.guild_id = None
        with SessionLocal() as db:
            db.add(CampaignMetadata(
                campaign_id=self.campaign_id,
                campaign_name="Marcos lendários",
                created_at_utc=datetime.now(timezone.utc),
            ))
            guild = Guild(campaign_id=self.campaign_id, name="Companhia dos Marcos")
            db.add(guild)
            db.flush()
            self.guild_id = guild.id
            db.add(GuildResources(guild_id=guild.id, gold=1234))
            for index, (_key, _title, _description, _criterion, _threshold, slot) in enumerate(LEGENDARY_MILESTONES):
                db.add(ItemTemplate(
                    name=f"Lendário de teste {slot}",
                    description="Recompensa lendária de teste.",
                    item_type="equipment",
                    rarity="legendary",
                    item_level=40,
                    level_band="21-50",
                    tier=5,
                    base_sell_value=1,
                    equipment_slot=slot,
                    required_level=40,
                    rng_bonus_min=2,
                    rng_bonus_max=5,
                    is_active=True,
                ))
            db.commit()

    def tearDown(self):
        configure_database("sqlite:///:memory:")

    def test_four_unique_slot_rewards_create_one_rng_instance_each_and_retries_do_not_duplicate(self):
        with SessionLocal() as db:
            ensure_campaign_achievement_catalog(db)
            milestones = [
                db.scalar(select(AchievementTemplate).where(AchievementTemplate.key == item[0]))
                for item in LEGENDARY_MILESTONES
            ]
            self.assertTrue(all(milestones))
            reward_ids = [item.reward_item_template_id for item in milestones]
            slots = [item.reward_item_template.equipment_slot for item in milestones]
            self.assertEqual(len(set(reward_ids)), 4)
            self.assertEqual(slots, [item[-1] for item in LEGENDARY_MILESTONES])

            resources = db.get(GuildResources, self.guild_id)
            gold_before = resources.gold
            claimed = []
            for template in milestones:
                achievement = GuildAchievement(
                    guild_id=self.guild_id,
                    achievement_template_id=template.id,
                    progress=template.threshold,
                    unlocked_at=datetime.now(timezone.utc),
                )
                db.add(achievement)
                db.flush()
                reward = claim_achievement(db, db.get(Guild, self.guild_id), resources, achievement.id)
                self.assertEqual(reward["item_rarity_label"], "Lendário")
                claimed.append((achievement.id, template.reward_item_template_id, template.reward_item_template.equipment_slot))

            instances = list(db.scalars(select(GuildItemInstance).where(
                GuildItemInstance.guild_id == self.guild_id,
                GuildItemInstance.item_template_id.in_(reward_ids),
            )))
            self.assertEqual(len(instances), 4)
            for instance in instances:
                template = next(row for row in milestones if row.reward_item_template_id == instance.item_template_id)
                self.assertEqual(instance.equipment_slot, template.reward_item_template.equipment_slot)
                self.assertIn(instance.rng_bonus_attribute, {"power", "vitality", "agility", "intelligence", "luck", "armor"})
                self.assertGreaterEqual(instance.rng_bonus_value, template.reward_item_template.rng_bonus_min)
                self.assertLessEqual(instance.rng_bonus_value, template.reward_item_template.rng_bonus_max)

            for achievement_id, item_id, _slot in claimed:
                with self.assertRaises(AchievementError):
                    claim_achievement(db, db.get(Guild, self.guild_id), resources, achievement_id)
                self.assertEqual(db.scalar(select(func.count(GuildItemInstance.id)).where(
                    GuildItemInstance.guild_id == self.guild_id,
                    GuildItemInstance.item_template_id == item_id,
                )), 1)
            self.assertEqual(resources.gold, gold_before)


if __name__ == "__main__":
    unittest.main()
