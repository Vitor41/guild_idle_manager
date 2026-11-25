import asyncio
import gc
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from unittest.mock import patch

from sqlalchemy import event, select
from starlette.requests import Request

from app.database.connection import SessionLocal, configure_database
from app.main import app
from app.core.dependencies import CampaignPlayer
from app.models.campaign import CampaignMetadata
from app.models.guild import Guild, GuildResources
from app.models.mercenary import Mercenary
from app.models.tavern import GuildTavernState, TavernSpecialOffer
from app.repositories.mercenary_repository import count_mercenaries_by_guild, create_mercenary, get_mercenary_class_by_code
from app.services.building_service import ensure_guild_buildings, get_building_level, get_guild_building_by_effect, get_mercenary_limit
from app.services.campaign_service import CampaignService
from app.services.tavern_service import (
    TavernError,
    calculate_apprentice_search_cost,
    generate_apprentice_preview,
    get_discounted_hire_cost,
    get_or_create_tavern_config,
    get_or_create_tavern_state,
    get_tavern_page_context,
    hire_apprentice,
    next_apprentice_cost,
    search_apprentice,
    utc_now,
)
from app.routes.tavern_routes import (
    _get_apprentice_preview,
    hire_apprentice_submit,
    search_apprentice_submit,
    tavern_index,
)


class TavernApprenticeSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.campaigns = CampaignService(Path(self.temp_dir.name) / "saves")
        self.campaign = self.campaigns.create_campaign("Busca de Aprendiz", "Guilda da Busca")
        self.campaigns.activate_campaign(self.campaign.campaign_id)
        self.previous_app_mode = getattr(app.state, "app_mode", "web")
        app.state.app_mode = "desktop"
        with SessionLocal() as db:
            self.guild = db.scalar(select(Guild).where(Guild.campaign_id == self.campaign.campaign_id))
            self.assertIsNotNone(self.guild)
            ensure_guild_buildings(db, self.guild.id)
            tavern = get_guild_building_by_effect(db, self.guild.id, "tavern")
            tavern.level = 1
            housing = get_guild_building_by_effect(db, self.guild.id, "housing")
            housing.level = 1
            resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == self.guild.id))
            resources.gold = 100_000
            config = get_or_create_tavern_config(db)
            self.state = get_or_create_tavern_state(db, self.guild.id, config)
            metadata = db.get(CampaignMetadata, self.campaign.campaign_id)
            metadata.apprentice_preview = json.dumps(generate_apprentice_preview(config, 1))
            db.commit()
            self.guild_id = self.guild.id

    def tearDown(self):
        app.state.app_mode = self.previous_app_mode
        self.campaigns.close_active_campaign(self.campaign.campaign_id)
        configure_database("sqlite:///:memory:")
        self.temp_dir.cleanup()
        gc.collect()

    def _current_data(self, db):
        guild = db.get(Guild, self.guild_id)
        resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == self.guild_id))
        state = db.scalar(select(GuildTavernState).where(GuildTavernState.guild_id == self.guild_id))
        config = get_or_create_tavern_config(db)
        metadata = db.get(CampaignMetadata, self.campaign.campaign_id)
        preview = json.loads(metadata.apprentice_preview)
        tavern_level = get_building_level(db, self.guild_id, "tavern")
        final_hire_cost = get_discounted_hire_cost(
            state.current_apprentice_hire_cost,
            get_tavern_page_context(db, guild, resources, refresh_special=False)["apprentice_chances"]["hire_discount_percent"],
        )
        return guild, resources, state, config, metadata, preview, tavern_level, final_hire_cost

    @staticmethod
    def _post_request(body: dict[str, str], path: str = "/tavern/search-apprentice") -> Request:
        encoded = urlencode(body).encode("utf-8")
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
            "app": app,
        }

        async def receive():
            return {"type": "http.request", "body": encoded, "more_body": False}

        return Request(scope, receive)

    @staticmethod
    def _get_request() -> Request:
        return Request({
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/tavern",
            "raw_path": b"/tavern",
            "root_path": "",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
            "app": app,
        })

    def test_search_quote_uses_actual_discounted_hire_price(self):
        self.assertEqual(calculate_apprentice_search_cost(1), 1)
        self.assertEqual(calculate_apprentice_search_cost(50), 35)
        self.assertEqual(calculate_apprentice_search_cost(101), 71)
        self.assertEqual(calculate_apprentice_search_cost(0), 0)

    def test_tavern_page_shows_secondary_confirmed_search_and_affordability(self):
        with SessionLocal() as db:
            player = CampaignPlayer(self.campaign.campaign_id, "Guilda da Busca")
            response = tavern_index(self._get_request(), db, player)
            self.assertEqual(response.status_code, 200)
            html = response.body.decode("utf-8")
            self.assertIn('action="/tavern/search-apprentice"', html)
            self.assertIn('data-confirm-title="Buscar outro Aprendiz?"', html)
            self.assertIn('data-confirm-action="Buscar outro"', html)
            self.assertIn('type="submit" data-pending-label="Buscando…"', html)
            self.assertIn('data-tavern-candidate-price-mutation', html)
            self.assertIn('name="preview_id"', html)
            self.assertIn('name="expected_search_cost"', html)
            self.assertIn('name="expected_hire_cost"', html)
            self.assertIn("Buscar outro Aprendiz (", html)
            self.assertIn("Contratar Aprendiz", html)
            available_hire_form = html.split('action="/tavern/hire-apprentice"', 1)[1].split("</form>", 1)[0]
            self.assertNotIn("disabled", available_hire_form)
            resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == self.guild_id))
            housing = get_guild_building_by_effect(db, self.guild_id, "housing")
            housing.level = 100
            resources.gold = 0
            db.commit()
            blocked_html = tavern_index(self._get_request(), db, player).body.decode("utf-8")
            hire_form = blocked_html.split('action="/tavern/hire-apprentice"', 1)[1].split("</form>", 1)[0]
            self.assertIn("disabled", hire_form)
            self.assertIn("faltam", hire_form)
            bulk_form = blocked_html.split('action="/tavern/hire-apprentices-bulk"', 1)[1].split("</form>", 1)[0]
            self.assertIn("faltam", bulk_form)
            with patch(
                "app.routes.tavern_routes.get_current_guild_context",
                return_value=(db.get(Guild, self.guild_id), None),
            ):
                unknown_balance_html = tavern_index(self._get_request(), db, player).body.decode("utf-8")
            unknown_hire_form = unknown_balance_html.split('action="/tavern/hire-apprentice"', 1)[1].split("</form>", 1)[0]
            unknown_bulk_form = unknown_balance_html.split('action="/tavern/hire-apprentices-bulk"', 1)[1].split("</form>", 1)[0]
            self.assertIn("saldo de ouro não informado", unknown_hire_form)
            self.assertIn("saldo de ouro não informado", unknown_bulk_form)
            self.assertNotIn("faltam", unknown_hire_form)
            self.assertNotIn("faltam", unknown_bulk_form)

    def test_reload_keeps_preview_and_double_post_only_charges_once(self):
        with SessionLocal() as db:
            guild, resources, state, config, metadata, preview, level, hire_cost = self._current_data(db)
            player = SimpleNamespace(id=self.campaign.campaign_id)
            request = Request({"type": "http", "app": app})
            first_reload = _get_apprentice_preview(request, db, player, config, level)
            second_reload = _get_apprentice_preview(request, db, player, config, level)
            self.assertEqual(first_reload, second_reload)
            self.assertEqual(first_reload["preview_id"], preview["preview_id"])
            old_gold = resources.gold
            old_cost = state.current_apprentice_hire_cost
            old_hire_count = state.apprentice_hire_count
            old_xp = guild.xp
            old_mercenary_count = count_mercenaries_by_guild(db, guild.id)
            expected_search_cost = calculate_apprentice_search_cost(hire_cost)
            request_body = {
                "preview_id": preview["preview_id"],
                "expected_search_cost": str(expected_search_cost),
            }
            successful = asyncio.run(search_apprentice_submit(
                self._post_request(request_body), db, player,
            ))
            self.assertEqual(successful.status_code, 303)
            after_first_preview = json.loads(db.get(CampaignMetadata, self.campaign.campaign_id).apprentice_preview)
            after_first_gold = db.get(GuildResources, resources.id).gold
            after_first_cost = db.scalar(select(GuildTavernState).where(
                GuildTavernState.guild_id == self.guild_id,
            )).current_apprentice_hire_cost
            self.assertNotEqual(after_first_preview["preview_id"], preview["preview_id"])
            self.assertEqual(after_first_gold, old_gold - expected_search_cost)
            self.assertEqual(after_first_cost, next_apprentice_cost(old_cost, config))
            self.assertEqual(state.apprentice_hire_count, old_hire_count)
            self.assertEqual(guild.xp, old_xp)

            stale = asyncio.run(search_apprentice_submit(
                self._post_request(request_body), db, player,
            ))
            self.assertEqual(stale.status_code, 303)
            self.assertIn("error=", stale.headers["location"])
            self.assertIn("mudou", stale.headers["location"])
            self.assertEqual(db.get(GuildResources, resources.id).gold, after_first_gold)
            self.assertEqual(
                db.scalar(select(GuildTavernState).where(GuildTavernState.guild_id == self.guild_id)).current_apprentice_hire_cost,
                after_first_cost,
            )
            self.assertEqual(
                json.loads(db.get(CampaignMetadata, self.campaign.campaign_id).apprentice_preview)["preview_id"],
                after_first_preview["preview_id"],
            )

            stale_hire_response = asyncio.run(hire_apprentice_submit(
                self._post_request({
                    "name": "Contratação desatualizada",
                    "preview_id": preview["preview_id"],
                    "expected_hire_cost": str(hire_cost),
                }, path="/tavern/hire-apprentice"),
                db,
                player,
            ))
            self.assertEqual(stale_hire_response.status_code, 303)
            self.assertIn("candidato+mudou", stale_hire_response.headers["location"])
            self.assertEqual(db.get(GuildResources, resources.id).gold, after_first_gold)
            self.assertEqual(
                json.loads(db.get(CampaignMetadata, self.campaign.campaign_id).apprentice_preview)["preview_id"],
                after_first_preview["preview_id"],
            )
            self.assertEqual(count_mercenaries_by_guild(db, guild.id), old_mercenary_count)

            current_hire_cost = get_discounted_hire_cost(
                after_first_cost,
                get_tavern_page_context(db, guild, resources, refresh_special=False)["apprentice_chances"]["hire_discount_percent"],
            )
            current_hire_response = asyncio.run(hire_apprentice_submit(
                self._post_request({
                    "name": "Aprendiz sincronizado",
                    "preview_id": after_first_preview["preview_id"],
                    "expected_hire_cost": str(current_hire_cost),
                }, path="/tavern/hire-apprentice"),
                db,
                player,
            ))
            self.assertEqual(current_hire_response.status_code, 303)
            self.assertIn("message=", current_hire_response.headers["location"])
            self.assertEqual(db.get(GuildResources, resources.id).gold, after_first_gold - current_hire_cost)
            self.assertIsNone(db.get(CampaignMetadata, self.campaign.campaign_id).apprentice_preview)
            self.assertEqual(count_mercenaries_by_guild(db, guild.id), old_mercenary_count + 1)

    def test_hire_keeps_preview_created_by_desktop_reload_after_commit(self):
        with SessionLocal() as db:
            _guild, _resources, _state, _config, _metadata, preview, _level, hire_cost = self._current_data(db)
            player = CampaignPlayer(self.campaign.campaign_id, "Guilda da Busca")
            commits_on_hire_session = 0
            commits_after_hire = None
            reloaded_preview_id = None

            def count_hire_commit(_session):
                nonlocal commits_on_hire_session
                commits_on_hire_session += 1

            def hire_then_run_interleaved_get(*args, **kwargs):
                nonlocal commits_after_hire, reloaded_preview_id
                hire_apprentice(*args, **kwargs)
                commits_after_hire = commits_on_hire_session
                with SessionLocal() as reload_db:
                    page = tavern_index(self._get_request(), reload_db, player)
                    self.assertEqual(page.status_code, 200)
                    reloaded = json.loads(
                        reload_db.get(CampaignMetadata, self.campaign.campaign_id).apprentice_preview,
                    )
                    reloaded_preview_id = reloaded["preview_id"]
                    self.assertNotEqual(reloaded_preview_id, preview["preview_id"])

            event.listen(db, "before_commit", count_hire_commit)
            try:
                with patch(
                    "app.routes.tavern_routes.hire_apprentice",
                    side_effect=hire_then_run_interleaved_get,
                ):
                    response = asyncio.run(hire_apprentice_submit(
                        self._post_request({
                            "name": "Aprendiz intercalado",
                            "preview_id": preview["preview_id"],
                            "expected_hire_cost": str(hire_cost),
                        }, path="/tavern/hire-apprentice"),
                        db,
                        player,
                    ))
            finally:
                event.remove(db, "before_commit", count_hire_commit)

            self.assertEqual(response.status_code, 303)
            self.assertIn("message=", response.headers["location"])
            self.assertEqual(
                commits_on_hire_session,
                commits_after_hire,
                "the route must not issue a second desktop metadata commit",
            )
            with SessionLocal() as verify_db:
                persisted = json.loads(
                    verify_db.get(CampaignMetadata, self.campaign.campaign_id).apprentice_preview,
                )
            self.assertEqual(persisted["preview_id"], reloaded_preview_id)

    def test_search_commits_price_balance_and_preview_in_one_transaction(self):
        with SessionLocal() as db:
            guild, resources, state, config, _metadata, preview, level, hire_cost = self._current_data(db)
            event_count = 0

            def count_commit(_session):
                nonlocal event_count
                event_count += 1

            event.listen(db, "before_commit", count_commit)
            replacement = search_apprentice(
                db,
                guild,
                resources,
                preview,
                str(preview["preview_id"]),
                calculate_apprentice_search_cost(hire_cost),
            )
            event.remove(db, "before_commit", count_commit)
            self.assertEqual(event_count, 1)
            self.assertEqual(resources.gold, 100_000 - calculate_apprentice_search_cost(hire_cost))
            self.assertEqual(state.current_apprentice_hire_cost, next_apprentice_cost(50, config))
            self.assertEqual(state.apprentice_hire_count, 0)
            self.assertIsNotNone(replacement["preview_id"])

    def test_search_progression_crosses_configured_price_threshold_and_next_hire_uses_new_price(self):
        with SessionLocal() as db:
            guild, resources, state, config, metadata, _preview, level, _hire_cost = self._current_data(db)
            state.current_apprentice_hire_cost = 4_999
            config.apprentice_cost_threshold = 5_000
            config.apprentice_growth_before_threshold_percent = 5
            config.apprentice_growth_after_threshold_percent = 3
            first_preview = generate_apprentice_preview(config, level)
            metadata.apprentice_preview = json.dumps(first_preview)
            db.commit()
            first_context = get_tavern_page_context(db, guild, resources, refresh_special=False)
            first_hire_cost = first_context["current_apprentice_final_cost"]
            first_search_cost = calculate_apprentice_search_cost(first_hire_cost)
            replacement = search_apprentice(
                db, guild, resources, first_preview, first_preview["preview_id"], first_search_cost,
            )
            self.assertEqual(state.current_apprentice_hire_cost, 5_249)
            second_hire_cost = get_discounted_hire_cost(
                state.current_apprentice_hire_cost,
                first_context["apprentice_chances"]["hire_discount_percent"],
            )
            self.assertEqual(second_hire_cost, get_tavern_page_context(
                db, guild, resources, refresh_special=False,
            )["current_apprentice_final_cost"])
            hire_apprentice(db, guild, resources, "Aprendiz após busca", replacement)
            hired = db.scalar(select(Mercenary).where(
                Mercenary.guild_id == guild.id,
                Mercenary.name == "Aprendiz após busca",
            ))
            self.assertIsNotNone(hired)
            self.assertEqual(hired.hire_cost, second_hire_cost)
            self.assertEqual(resources.gold, 100_000 - first_search_cost - second_hire_cost)
            self.assertEqual(state.current_apprentice_hire_cost, next_apprentice_cost(5_249, config))
            self.assertEqual(state.apprentice_hire_count, 1)

    def test_search_works_with_full_roster_and_does_not_change_special_offer(self):
        with SessionLocal() as db:
            guild, resources, state, config, metadata, preview, level, hire_cost = self._current_data(db)
            apprentice_class = get_mercenary_class_by_code(db, "apprentice")
            warrior_class = get_mercenary_class_by_code(db, "warrior")
            for index in range(get_mercenary_limit(db, guild.id)):
                create_mercenary(db, guild.id, apprentice_class, f"Equipe cheia {index}")
            player = CampaignPlayer(self.campaign.campaign_id, "Guilda da Busca")
            page = tavern_index(self._get_request(), db, player)
            self.assertEqual(page.status_code, 200)
            html = page.body.decode("utf-8")
            search_form = html.split('action="/tavern/search-apprentice"', 1)[1].split("</form>", 1)[0]
            hire_form = html.split('action="/tavern/hire-apprentice"', 1)[1].split("</form>", 1)[0]
            bulk_form = html.split('action="/tavern/hire-apprentices-bulk"', 1)[1].split("</form>", 1)[0]
            self.assertNotIn("disabled", search_form, "candidate search remains available at the housing limit")
            self.assertIn("disabled", hire_form)
            self.assertIn("libere uma vaga", hire_form)
            self.assertIn("disabled", bulk_form)
            self.assertIn("libere 10 vagas", bulk_form)
            now = utc_now()
            state.next_special_check_at = now.replace(year=now.year + 1)
            special = TavernSpecialOffer(
                guild_id=guild.id,
                name="Visitante preservado",
                class_id=warrior_class.id,
                rarity="rare",
                level=20,
                power=20,
                vitality=20,
                agility=20,
                intelligence=20,
                luck=20,
                gold_cost=1_500,
                available_from=now,
                available_until=now.replace(year=now.year + 1),
                status="active",
            )
            db.add(special)
            db.commit()
            offer_id = special.id
            result = search_apprentice(
                db,
                guild,
                resources,
                preview,
                str(preview["preview_id"]),
                calculate_apprentice_search_cost(hire_cost),
            )
            self.assertNotEqual(result["preview_id"], preview["preview_id"])
            self.assertEqual(count_mercenaries_by_guild(db, guild.id), get_mercenary_limit(db, guild.id))
            unchanged = db.get(TavernSpecialOffer, offer_id)
            self.assertEqual(unchanged.name, "Visitante preservado")
            self.assertEqual(unchanged.status, "active")
            self.assertEqual(unchanged.gold_cost, 1_500)
            with self.assertRaisesRegex(TavernError, "Limite de mercenarios"):
                hire_apprentice(db, guild, resources, "Sem vaga", result)

    def test_insufficient_funds_preserve_candidate_balance_and_price(self):
        with SessionLocal() as db:
            guild, resources, state, config, metadata, preview, level, hire_cost = self._current_data(db)
            search_cost = calculate_apprentice_search_cost(hire_cost)
            resources.gold = search_cost - 1
            original_cost = state.current_apprentice_hire_cost
            original_preview = metadata.apprentice_preview
            db.commit()
            with self.assertRaisesRegex(TavernError, "Ouro insuficiente"):
                search_apprentice(
                    db, guild, resources, preview, preview["preview_id"], search_cost,
                )
            self.assertEqual(resources.gold, search_cost - 1)
            self.assertEqual(state.current_apprentice_hire_cost, original_cost)
            self.assertEqual(metadata.apprentice_preview, original_preview)


if __name__ == "__main__":
    unittest.main()
