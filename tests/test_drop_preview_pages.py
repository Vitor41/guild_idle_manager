import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.config import settings
from app.database.connection import Base, create_database_engine
from app.models.building import BuildingTemplate, GuildBuilding
from app.models.dungeon import DungeonTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.models.user import User
from app.routes.dungeon_routes import dungeons_index
from app.routes.mission_routes import missions_index
from app.seeds.massive_content import run_massive_content_seed
from app.services.building_service import seed_initial_building_templates


class DropPreviewPageTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.user = User(
            id=1, username="drop-preview-qa", password_hash="irrelevante",
            is_active=True, tutorial_status="complete", confirmation_preferences="{}",
        )
        self.guild = Guild(user_id=self.user.id, name="Guilda de Drops", level=1)
        self.db.add_all([self.user, self.guild])
        self.db.flush()
        self.db.add(GuildResources(guild_id=self.guild.id, gold=1000, wood=0, ore=0, crystals=0))
        run_massive_content_seed(self.db)
        seed_initial_building_templates(self.db)
        self.db.flush()

        material = self.db.scalar(select(ItemTemplate).where(
            ItemTemplate.is_active.is_(True), ItemTemplate.item_type == "material",
        ).order_by(ItemTemplate.id))
        mission = self.db.scalar(select(MissionTemplate).where(
            MissionTemplate.is_active.is_(True), MissionTemplate.level_band == "1-20",
            MissionTemplate.mission_type == "combat",
        ).order_by(MissionTemplate.display_order, MissionTemplate.id))
        dungeon = self.db.scalar(select(DungeonTemplate).where(
            DungeonTemplate.is_active.is_(True), DungeonTemplate.level_band == "1-20",
            DungeonTemplate.content_type == "dungeon",
        ).order_by(DungeonTemplate.id))
        boss = self.db.scalar(select(DungeonTemplate).where(
            DungeonTemplate.is_active.is_(True), DungeonTemplate.level_band == "1-20",
            DungeonTemplate.content_type == "boss",
        ).order_by(DungeonTemplate.id))
        scouts = self.db.scalar(select(BuildingTemplate).where(BuildingTemplate.effect_type == "scouts"))
        self.assertTrue(material and mission and dungeon and boss and scouts)
        self._ensure_mission_drop(mission, material)
        self._ensure_dungeon_drop(dungeon, material)
        self._ensure_dungeon_drop(boss, material)
        self.db.add(GuildBuilding(guild_id=self.guild.id, building_template_id=scouts.id, level=1))
        self.db.commit()

        self.app = FastAPI()
        self.app.state.app_mode = "web"
        self.app.mount(
            "/static",
            StaticFiles(directory=Path(__file__).resolve().parents[1] / "app" / "static"),
            name="static",
        )
        self.assertEqual(settings.app_mode, "web")

    def _ensure_mission_drop(self, mission: MissionTemplate, item: ItemTemplate) -> None:
        if any(drop.is_active for drop in mission.item_drops):
            return
        self.db.add(MissionTemplateItemDrop(
            mission_template_id=mission.id, item_template_id=item.id,
            drop_chance=23, min_quantity=1, max_quantity=2, is_active=True,
        ))

    def _ensure_dungeon_drop(self, dungeon: DungeonTemplate, item: ItemTemplate) -> None:
        if any(drop.is_active for drop in dungeon.item_drops):
            return
        self.db.add(DungeonTemplateItemDrop(
            dungeon_template_id=dungeon.id, item_template_id=item.id,
            drop_chance=27, min_quantity=1, max_quantity=2, is_active=True,
        ))

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _request(self, path: str) -> Request:
        path_only, _, query = path.partition("?")
        return Request({
            "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path_only, "raw_path": path_only.encode(), "root_path": "",
            "query_string": query.encode(), "headers": [], "client": ("testclient", 123),
            "server": ("testserver", 80), "app": self.app,
        })

    def test_missions_dungeons_and_bosses_render_resolver_drop_previews_in_web_mode(self):
        mission_response = missions_index(self._request("/missions"), self.db, self.user)
        mission_html = mission_response.body.decode("utf-8")
        self.assertIn('data-app-mode="web"', mission_html)
        self.assertIn("data-drop-preview", mission_html)
        self.assertIn("Chance-base por item/entrada", mission_html)
        self.assertIn("% base", mission_html)

        dungeon_response = dungeons_index(self._request("/dungeons"), self.db, self.user)
        dungeon_html = dungeon_response.body.decode("utf-8")
        self.assertIn("data-drop-preview", dungeon_html)
        self.assertIn("Chance-base por item/entrada", dungeon_html)

        boss_response = dungeons_index(self._request("/dungeons?type=boss"), self.db, self.user)
        boss_html = boss_response.body.decode("utf-8")
        self.assertIn("data-drop-preview", boss_html)
        self.assertIn("Chance-base por item/entrada", boss_html)


if __name__ == "__main__":
    unittest.main()
