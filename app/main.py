from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.database.connection import SessionLocal
from app.routes import admin_routes, auth_routes, blacksmith_routes, building_routes, class_change_routes, class_routes, codex_routes, dashboard_routes, dock_routes, dungeon_routes, guild_routes, guide_routes, home_routes, inventory_routes, market_routes, mercenary_routes, mission_routes, profession_routes, progress_routes, session_routes, tavern_routes, tier_routes, tutorial_routes
from app.services.building_service import seed_initial_building_templates
from app.services.class_service import seed_class_tree
from app.services.dungeon_service import apply_introductory_boss_access_rule, seed_initial_dungeon_drops, seed_initial_dungeon_templates
from app.services.mercenary_service import cleanup_orphaned_dismissed_mercenaries, seed_initial_mercenary_classes
from app.services.mission_service import repair_long_idle_mission_catalog, seed_initial_mission_templates, seed_long_idle_missions
from app.services.item_service import seed_initial_items, seed_initial_mission_drops
from app.services.tavern_service import seed_tavern_config
from app.services.skill_service import seed_class_skills
from app.services.crafting_service import seed_crafting_recipes
from app.services.achievement_service import seed_achievements_and_codex
from app.seeds import run_massive_content_seed
from app.services.content_refinement_service import run_progression_refinement
from app.services.prd2_balance_service import apply_prd2_balance
from app.services.prd3_dungeon_balance_service import apply_dungeon_explorer_unlock_fix, apply_prd3_dungeon_balance


BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(
    title="Guild Idle Manager",
    description="Bootstrap local do Guild Idle Manager.",
    version="0.1.0",
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=False,
)

app.include_router(home_routes.router)
app.include_router(auth_routes.router)
app.include_router(guild_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(mercenary_routes.router)
app.include_router(tavern_routes.router)
app.include_router(class_routes.router)
app.include_router(tier_routes.router)
app.include_router(class_change_routes.router)
app.include_router(mission_routes.router)
app.include_router(dungeon_routes.router)
app.include_router(profession_routes.router)
app.include_router(dock_routes.router)
app.include_router(building_routes.router)
app.include_router(inventory_routes.router)
app.include_router(market_routes.router)
app.include_router(blacksmith_routes.router)
app.include_router(progress_routes.router)
app.include_router(codex_routes.router)
app.include_router(guide_routes.router)
app.include_router(admin_routes.router)
app.include_router(tutorial_routes.router)
app.include_router(session_routes.router)


@app.on_event("startup")
def seed_global_catalogs() -> None:
    db = SessionLocal()
    try:
        seed_initial_mercenary_classes(db)
        seed_class_tree(db)
        seed_initial_mission_templates(db)
        seed_initial_building_templates(db)
        seed_tavern_config(db)
        seed_initial_items(db)
        seed_initial_mission_drops(db)
        seed_initial_dungeon_templates(db)
        seed_initial_dungeon_drops(db)
        seed_class_skills(db)
        run_massive_content_seed(db)
        run_progression_refinement(db)
        seed_long_idle_missions(db)
        apply_prd2_balance(db)
        repair_long_idle_mission_catalog(db)
        apply_prd3_dungeon_balance(db)
        apply_dungeon_explorer_unlock_fix(db)
        apply_introductory_boss_access_rule(db)
        seed_crafting_recipes(db)
        seed_achievements_and_codex(db)
        cleanup_orphaned_dismissed_mercenaries(db)
    finally:
        db.close()
