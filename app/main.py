from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.connection import SessionLocal
from app.routes import session_routes
from app.routes import blacksmith_routes, building_routes, class_change_routes, class_routes, codex_routes, dashboard_routes, dock_routes, dungeon_routes, guide_routes, home_routes, inventory_routes, market_routes, mercenary_routes, mission_routes, profession_routes, progress_routes, tavern_routes, tier_routes, tutorial_routes


BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(
    title="Guild Idle Manager",
    description="Bootstrap local do Guild Idle Manager.",
    version="0.1.0",
    docs_url=None if settings.app_mode == "desktop" else "/docs",
    redoc_url=None if settings.app_mode == "desktop" else "/redoc",
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

app.state.app_mode = settings.app_mode


@app.middleware("http")
async def protect_desktop_loopback(request: Request, call_next):
    if request.app.state.app_mode == "desktop":
        allowed_host = getattr(request.app.state, "desktop_allowed_host", None)
        allowed_origin = getattr(request.app.state, "desktop_allowed_origin", None)
        if not allowed_host or not allowed_origin:
            return PlainTextResponse("O servidor desktop local nao foi inicializado pelo launcher.", status_code=503)
        if request.headers.get("host", "").lower() != allowed_host.lower():
            return PlainTextResponse("Origem local nao autorizada.", status_code=403)
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            return PlainTextResponse("Acesso entre sites bloqueado.", status_code=403)
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") != allowed_origin:
                return PlainTextResponse("Requisicao sem origem local valida.", status_code=403)
    response = await call_next(request)
    if request.app.state.app_mode == "desktop":
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            # pywebview builds the JS API with `new Function`, which CSP blocks without unsafe-eval.
            # This policy is desktop-only and the renderer serves only this local application.
            "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
            "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response

if settings.app_mode != "desktop":
    from starlette.middleware.sessions import SessionMiddleware

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
else:
    from app.desktop.routes import router as desktop_router

    app.include_router(desktop_router)
app.include_router(session_routes.router)


@app.on_event("startup")
def seed_global_catalogs() -> None:
    if settings.app_mode == "desktop":
        from app.desktop.clock_guard import ClockGuard
        from app.desktop.lifecycle import open_campaign
        from app.services.campaign_service import CampaignService

        app.state.campaign_service = CampaignService()
        app.state.clock_guard = ClockGuard()
        app.state.suspended_campaigns = set()
        if settings.active_campaign_id:
            open_campaign(
                app,
                app.state.campaign_service,
                app.state.clock_guard,
                settings.active_campaign_id,
            )
        return

    db = SessionLocal()
    try:
        from app.seeds.campaign_content import apply_initial_campaign_content

        apply_initial_campaign_content(db)
    finally:
        db.close()


@app.on_event("shutdown")
def close_desktop_campaign() -> None:
    if settings.app_mode == "desktop" and (
        getattr(app.state, "active_campaign", None) is not None
        or getattr(app.state, "suspended_campaigns", set())
    ):
        from app.desktop.lifecycle import close_campaign, close_suspended_campaigns

        close_campaign(app, app.state.campaign_service, app.state.clock_guard)
        close_suspended_campaigns(app, app.state.campaign_service, app.state.clock_guard)
