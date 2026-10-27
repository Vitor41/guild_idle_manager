from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.database.connection import SessionLocal
from app.routes import session_routes
from app.routes import blacksmith_routes, building_routes, class_change_routes, class_routes, codex_routes, dashboard_routes, dock_routes, dungeon_routes, guide_routes, home_routes, inventory_routes, market_routes, mercenary_routes, mission_routes, profession_routes, progress_routes, tavern_routes, tier_routes, tutorial_routes


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

app.state.app_mode = settings.app_mode

if settings.app_mode != "desktop":
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site="lax",
        https_only=False,
    )

app.include_router(home_routes.router)
if settings.app_mode != "desktop":
    from app.routes import admin_routes, auth_routes, guild_routes

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
app.include_router(tutorial_routes.router)
if settings.app_mode != "desktop":
    app.include_router(admin_routes.router)
app.include_router(session_routes.router)


@app.on_event("startup")
def seed_global_catalogs() -> None:
    if settings.app_mode == "desktop":
        if settings.active_campaign_id:
            from app.services.campaign_service import CampaignService

            app.state.active_campaign = CampaignService().activate_campaign(settings.active_campaign_id)
        return

    db = SessionLocal()
    try:
        from app.seeds.campaign_content import apply_initial_campaign_content

        apply_initial_campaign_content(db)
    finally:
        db.close()


@app.on_event("shutdown")
def close_desktop_campaign() -> None:
    campaign = getattr(app.state, "active_campaign", None)
    if settings.app_mode == "desktop" and campaign is not None:
        from app.services.campaign_service import CampaignService

        CampaignService().close_active_campaign(campaign.campaign_id)
        app.state.active_campaign = None
