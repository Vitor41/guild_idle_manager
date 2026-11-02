import json
import unittest

from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models.guild import Guild, GuildResources
from app.models.item import GuildInventoryItem, ItemTemplate
from app.models.user import User
from app.routes.dashboard_routes import resource_totals


class ResourceTotalsRouteTests(unittest.TestCase):
    def test_authenticated_route_returns_current_single_crystal_balance(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                user = User(username="resource-reader", password_hash="hash")
                db.add(user)
                db.flush()
                guild = Guild(user_id=user.id, name="Guilda de teste")
                db.add(guild)
                db.flush()
                db.add(GuildResources(
                    guild_id=guild.id, gold=125, wood=0, ore=0, crystals=0, crystal_reserve=2,
                ))
                db.flush()
                for family, quantity in (("wood", 8), ("ore", 4), ("gem", 3)):
                    item = ItemTemplate(
                        name=f"Material {family}", description="", item_type="material", rarity="common",
                        material_family=family, item_level=1, level_band="1-20", tier=1,
                    )
                    db.add(item)
                    db.flush()
                    db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=item.id, quantity=quantity))
                db.flush()

                response = resource_totals(db, user)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(json.loads(response.body), {
                    "gold": 125, "wood": 8, "ore": 4, "crystal": 5,
                })
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
