import asyncio
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from sqlalchemy.orm import Session

from app.database.connection import Base, create_database_engine
from app.models.guild import Guild, GuildResources
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.models.user import User
from app.routes.guide_routes import _catalog_markdown, export_guide_markdown, game_guide, guide_catalog_api, router
from app.seeds.massive_content import run_massive_content_seed
from app.services.crafting_service import seed_crafting_recipes


class GuideRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.user = User(id=1, username="guia-qa", password_hash="irrelevante", is_active=True,
            tutorial_status="complete", confirmation_preferences="{}")
        self.db = Session(self.engine, expire_on_commit=False)
        self.db.add(self.user)
        self.db.flush()
        self.guild = Guild(user_id=self.user.id, name="Guilda Segredo QA", level=1)
        self.db.add(self.guild)
        self.db.flush()
        self.db.add(GuildResources(guild_id=self.guild.id, gold=4321, wood=0, ore=0, crystals=0))
        run_massive_content_seed(self.db)
        seed_crafting_recipes(self.db)
        self.db.commit()

        app = FastAPI()
        app.state.app_mode = "web"
        app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parents[1] / "app/static"), name="static")
        app.include_router(router)

        self.app = app

    def _request(self, path: str) -> Request:
        scope = {"type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"",
            "headers": [], "client": ("testclient", 123), "server": ("testserver", 80), "app": self.app}
        return Request(scope)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_guide_html_exposes_global_search_local_filters_and_catalog_states(self):
        response = game_guide(self._request("/guide"), self.db, self.user)
        self.assertEqual(response.status_code, 200)
        html = response.body.decode("utf-8")
        self.assertIn('data-guide-search-form', html)
        self.assertIn('Baixar Guia em Markdown', html)
        self.assertIn('id="docas-mercado"', html)
        for duration in ("10 s", "25 s", "60 s", "180 s", "600 s", "1.200 s"):
            self.assertIn(duration, html)
        self.assertNotIn("Tempo base por raridade", html)
        self.assertIn('id="equipamentos-materiais"', html)
        self.assertIn('>Recomendação</th>', html)
        self.assertIn('>Requisito</th>', html)
        self.assertIn("O nível do mercenário aparece como recomendação", html)
        self.assertIn('data-filter-name', html)
        self.assertIn('data-filter-family', html)
        self.assertIn('data-filter-band', html)
        self.assertNotIn('data-filter-tier', html)
        self.assertNotIn("Tier ${item.tier}", (Path(__file__).resolve().parents[1] / "app/static/js/guide.js").read_text(encoding="utf-8"))
        self.assertNotIn("Tier", html)
        self.assertIn("guide-catalog-icon-fallback", (Path(__file__).resolve().parents[1] / "app/static/js/guide.js").read_text(encoding="utf-8"))
        self.assertIn('data-filter-source', html)
        self.assertIn('data-guide-catalog-retry', html)
        self.assertLess(html.index("/static/js/guide-utils.js"), html.index("/static/js/guide.js"))
        script = (Path(__file__).resolve().parents[1] / "app/static/js/guide.js").read_text(encoding="utf-8")
        self.assertIn("addEventListener(\"submit\"", script)
        self.assertIn("document.createTreeWalker", script)
        self.assertIn("range.surroundContents(mark)", script)
        self.assertIn("mark.scrollIntoView", script)
        self.assertIn("Nenhum resultado para", script)
        self.assertIn("catalogItems", script)
        self.assertIn('recommendationCell.dataset.label = "Recomendação"', script)
        self.assertIn('source.recommendation || "—"', script)

    def test_catalog_api_and_markdown_share_live_items_without_campaign_private_data(self):
        catalog_response = guide_catalog_api(self.db, self.user)
        self.assertEqual(catalog_response.status_code, 200)
        self.assertEqual(catalog_response.headers["cache-control"], "no-store")
        import json
        catalog = json.loads(catalog_response.body)
        self.assertTrue(catalog["items"])
        static_root = Path(__file__).resolve().parents[1] / "app/static"
        icon_rows = [row for row in catalog["items"] if row["icon"]]
        self.assertTrue(icon_rows)
        for row in icon_rows:
            self.assertTrue(row["icon"].startswith("/static/"), row["icon"])
            self.assertTrue((static_root / row["icon"].removeprefix("/static/")).is_file(), row["icon"])
        source_types = {source["type"] for row in catalog["items"] for source in row["sources"]}
        self.assertTrue({"mission", "dungeon_or_boss", "docks_possible_offer", "gathering", "salvage"}.issubset(source_types))
        equipment = next(row for row in catalog["items"] if row["item_type"] == "equipment" and row["sources"])
        material = next(row for row in catalog["items"] if row["item_type"] == "material" and row["sources"])
        self.assertTrue(equipment["equipment_slot"])
        self.assertTrue(any(source["price"] for row in catalog["items"] for source in row["sources"]
            if source["filter_key"] == "purchase"))
        mission_drop = self.db.query(MissionTemplateItemDrop).filter(MissionTemplateItemDrop.is_active.is_(True)).first()
        mission_drop.drop_chance = 13
        mission_drop.min_quantity = 7
        mission_drop.max_quantity = 9
        mission = self.db.get(MissionTemplate, mission_drop.mission_template_id)
        mission.required_min_mercenary_level = 17
        dungeon_drop = self.db.query(DungeonTemplateItemDrop).filter(
            DungeonTemplateItemDrop.is_active.is_(True),
            DungeonTemplateItemDrop.drop_chance > 0,
        ).first()
        self.assertIsNotNone(dungeon_drop)
        dungeon = self.db.get(DungeonTemplate, dungeon_drop.dungeon_template_id)
        dungeon.required_min_mercenary_level = 23
        self.db.flush()
        edited_catalog = json.loads(guide_catalog_api(self.db, self.user).body)
        edited_item = next(row for row in edited_catalog["items"] if row["id"] == mission_drop.item_template_id)
        edited_mission_source = next(source for source in edited_item["sources"]
            if source["type"] == "mission" and source["chance"].startswith("13% base")
            and "7–9" in source["quantity"])
        self.assertEqual(edited_mission_source["recommendation"], "mercenário nível 17+")
        self.assertNotIn("mercenário nível", edited_mission_source["requirement"])
        dungeon_item = next(row for row in edited_catalog["items"] if row["id"] == dungeon_drop.item_template_id)
        edited_dungeon_source = next(source for source in dungeon_item["sources"]
            if source["type"] == "dungeon_or_boss" and source["recommendation"] == "mercenário nível 23+")
        self.assertEqual(edited_dungeon_source["recommendation"], "mercenário nível 23+")
        self.assertNotIn("mercenário nível", edited_dungeon_source["requirement"])
        markdown_response = export_guide_markdown(self._request("/guide/export.md"), self.db, self.user)
        self.assertEqual(markdown_response.status_code, 200)
        self.assertIn("text/markdown", markdown_response.headers["content-type"])
        self.assertIn("attachment; filename=\"guia-guild-idle-manager.md\"", markdown_response.headers["content-disposition"])
        markdown = markdown_response.body.decode("utf-8")
        self.assertIn("Versão: 0.9.0", markdown)
        self.assertIn("Gerado em:", markdown)
        self.assertIn("| Raridade | Tempo-base por unidade |", markdown)
        for rarity, duration in (("Comum", "10 s"), ("Incomum", "25 s"), ("Raro", "60 s"), ("Épico", "180 s"), ("Lendário", "600 s"), ("Mítico", "1.200 s")):
            self.assertIn(f"{rarity} | {duration}", markdown)
        self.assertIn(equipment["name"], markdown)
        self.assertIn(material["name"], markdown)
        self.assertIn("base por entrada de drop", markdown)
        self.assertIn("13% base por entrada de drop", markdown)
        self.assertIn("Recomendação: mercenário nível 17\\+", markdown)
        self.assertIn("Recomendação: mercenário nível 23\\+", markdown)
        self.assertNotIn("Requisito: mercenário nível", markdown)
        self.assertIn("Quantidade: 7–9 unidade\\(s\\)", markdown)
        self.assertIn("Preço unitário registrado:", markdown)
        self.assertIn(f"espaço {equipment['equipment_slot'].replace('_', chr(92) + '_')}", markdown)
        self.assertNotIn("Guilda Segredo QA", markdown)
        self.assertNotIn("campaign_id", markdown)
        self.assertNotIn("4321", markdown)
        self.assertNotIn("Bônus atual:", markdown)
        self.assertNotIn("Carregando catálogo", markdown)
        self.assertNotIn("Nenhum item corresponde aos filtros", markdown)
        self.assertNotIn("Fonte/atividade", markdown)
        self.assertNotIn("Tier ", markdown)

    def test_markdown_consolidates_equivalent_rarities_but_keeps_distinct_sources(self):
        base = {
            "name": "Espada Solar", "item_type": "equipment", "item_type_label": "Equipamento",
            "family": "", "equipment_slot": "sword", "level_band": "1-10", "item_level": 5,
            "tier": 2, "sources": [{
                "type": "dungeon_or_boss", "label": "Chefes", "name": "Dragão",
                "recommendation": "mercenário nível 5+", "requirement": "guilda nível 5+", "chance": "10% base", "quantity": "1 unidade",
                "price": None, "condition": "",
            }],
        }
        catalog = {"items": [
            {**base, "id": 1, "rarity": "Raro"},
            {**base, "id": 2, "rarity": "Épico", "sources": [{**base["sources"][0], "chance": "4% base", "recommendation": "mercenário nível 12+", "requirement": "guilda nível 12+"}]},
        ]}
        markdown = _catalog_markdown(catalog)
        self.assertEqual(markdown.count("### Espada Solar"), 1)
        self.assertIn("raridade: Raro, Épico", markdown)
        self.assertIn("10% base", markdown)
        self.assertIn("4% base", markdown)
        self.assertIn(r"guilda nível 5\+", markdown)
        self.assertIn(r"guilda nível 12\+", markdown)
        self.assertIn(r"Recomendação: mercenário nível 5\+", markdown)
        self.assertIn(r"Recomendação: mercenário nível 12\+", markdown)
        self.assertNotIn("Requisito: mercenário nível", markdown)
        self.assertNotIn("Tier 2", markdown)
        lines = [line for line in markdown.splitlines() if "base" in line]
        self.assertEqual(len(lines), 2)
        self.assertIn("Raridade(s): Raro", lines[0])
        self.assertIn("10% base", lines[0])
        self.assertIn("Raridade(s): Épico", lines[1])
        self.assertIn("4% base", lines[1])

    def test_catalog_icon_urls_are_served_by_the_static_mount(self):
        import json
        catalog = json.loads(guide_catalog_api(self.db, self.user).body)
        icon_urls = {row["icon"] for row in catalog["items"] if row["icon"]}
        self.assertTrue(icon_urls)
        async def get_static(path):
            messages = []
            request_sent = False
            async def receive():
                nonlocal request_sent
                if request_sent:
                    await asyncio.Event().wait()
                request_sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            async def send(message):
                messages.append(message)
            scope = {
                "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
                "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"",
                "headers": [], "client": ("testclient", 123), "server": ("testserver", 80), "app": self.app,
            }
            await self.app(scope, receive, send)
            response = next(message for message in messages if message["type"] == "http.response.start")
            body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
            return response["status"], dict(response["headers"]), body
        for icon_url in icon_urls:
            with self.subTest(icon_url=icon_url):
                status, headers, body = asyncio.run(get_static(icon_url))
                content_type = dict((key.decode().lower(), value.decode()) for key, value in headers.items()).get("content-type", "")
                self.assertEqual(status, 200, icon_url)
                self.assertTrue(content_type.startswith("image/"), icon_url)
                self.assertTrue(body, icon_url)


if __name__ == "__main__":
    unittest.main()
