from pathlib import Path
import asyncio
import re
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.version import APP_VERSION
from app.desktop.gameplay_diagnostics import log_gameplay_action
from app.database.connection import SessionLocal
from app.routes import session_routes, update_routes
from app.routes import blacksmith_routes, building_routes, class_change_routes, class_routes, codex_routes, dashboard_routes, dock_routes, dungeon_routes, gathering_routes, guide_routes, home_routes, inventory_routes, market_routes, mercenary_routes, mission_routes, profession_routes, progress_routes, tavern_routes, tier_routes, tutorial_routes


BASE_DIR = Path(__file__).resolve().parent


async def _desktop_gameplay_ticks() -> None:
    while True:
        await asyncio.sleep(30)
        active = getattr(app.state, "active_campaign", None)
        guard = getattr(app.state, "clock_guard", None)
        if active is not None and guard is not None:
            guard.checkpoint_active_session(active.campaign_id)
            app.state.active_campaign = app.state.campaign_service.inspect_campaign(active.campaign_id)


app = FastAPI(
    title="Guild Idle Manager",
    description="Bootstrap local do Guild Idle Manager.",
    version=APP_VERSION,
    docs_url=None if settings.app_mode == "desktop" else "/docs",
    redoc_url=None if settings.app_mode == "desktop" else "/redoc",
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

app.state.app_mode = settings.app_mode


_GAMEPLAY_POST_PREFIXES = (
    "/gathering/", "/regional/", "/missions/", "/dungeons/", "/market/",
    "/blacksmith/", "/professions/", "/class-change/", "/tutorial/",
    "/buildings/", "/tavern/", "/mercenaries/", "/docks/", "/codex/",
)


def _gameplay_action_for_path(path: str) -> str:
    if path == "/gathering/assign":
        return "gathering.assign"
    if path.startswith("/regional/offers/"):
        return "regional.offer." + ("prepare" if path.endswith("/prepare") else "start" if path.endswith("/start") else "action")
    if path.startswith("/regional/"):
        return "regional.action"
    return path.strip("/").replace("/", ".") or "gameplay.action"


def _diagnostic_error_redirect(path: str, diagnostic_id: str) -> str:
    destination = "/gathering" if path.startswith("/gathering/") else "/regional" if path.startswith("/regional/") else "/dashboard"
    query = urlencode({
        "error": f"A ação não foi concluída. Consulte o log e informe a referência {diagnostic_id}.",
        "diagnostic": diagnostic_id,
    })
    return f"{destination}?{query}"


@app.middleware("http")
async def protect_desktop_loopback(request: Request, call_next):
    is_gameplay_post = (
        request.method.upper() == "POST"
        and request.url.path.startswith(_GAMEPLAY_POST_PREFIXES)
    )
    diagnostic_id = None
    action = None
    if request.app.state.app_mode == "desktop" and is_gameplay_post:
        supplied_id = request.headers.get("x-gim-diagnostic-id", "")
        diagnostic_id = supplied_id if re.fullmatch(r"[a-fA-F0-9-]{16,40}", supplied_id) else uuid.uuid4().hex
        request.state.diagnostic_id = diagnostic_id
        action = _gameplay_action_for_path(request.url.path)
    if request.app.state.app_mode == "desktop":
        allowed_host = getattr(request.app.state, "desktop_allowed_host", None)
        allowed_origin = getattr(request.app.state, "desktop_allowed_origin", None)
        if not allowed_host or not allowed_origin:
            return PlainTextResponse("O servidor desktop local nao foi inicializado pelo launcher.", status_code=503)
        if request.headers.get("host", "").lower() != allowed_host.lower():
            if diagnostic_id and action:
                log_gameplay_action(action=action, route=request.url.path, diagnostic_id=diagnostic_id,
                                    status_code=403, outcome="host_rejected", event="rejected")
            return PlainTextResponse("Origem local nao autorizada.", status_code=403)
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            if diagnostic_id and action:
                log_gameplay_action(action=action, route=request.url.path, diagnostic_id=diagnostic_id,
                                    status_code=403, outcome="cross_site_rejected", event="rejected")
            return PlainTextResponse("Acesso entre sites bloqueado.", status_code=403)
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") != allowed_origin:
                if diagnostic_id and action:
                    log_gameplay_action(action=action, route=request.url.path, diagnostic_id=diagnostic_id,
                                        status_code=403, outcome="origin_rejected", event="rejected")
                return PlainTextResponse("Requisicao sem origem local valida.", status_code=403)
    if request.app.state.app_mode == "desktop" and is_gameplay_post and diagnostic_id and action:
        log_gameplay_action(action=action, route=request.url.path, diagnostic_id=diagnostic_id,
                            status_code=0, outcome="request_received", event="start")
        try:
            response = await call_next(request)
        except Exception as error:
            log_gameplay_action(
                action=action, route=request.url.path, diagnostic_id=diagnostic_id,
                status_code=500, outcome="unexpected_exception", event="exception", exception=error,
            )
            response = RedirectResponse(_diagnostic_error_redirect(request.url.path, diagnostic_id), status_code=303)
        else:
            status_code = response.status_code
            location = urlsplit(response.headers.get("location", ""))
            redirected_with_error = "error" in parse_qs(location.query)
            outcome = "error" if status_code >= 400 or redirected_with_error else "redirect" if 300 <= status_code < 400 else "success"
            log_gameplay_action(
                action=action, route=request.url.path, diagnostic_id=diagnostic_id,
                status_code=status_code, outcome=outcome,
            )
            if status_code >= 400:
                response = RedirectResponse(_diagnostic_error_redirect(request.url.path, diagnostic_id), status_code=303)
        response.headers["X-GIM-Diagnostic-ID"] = diagnostic_id
    else:
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
app.include_router(gathering_routes.router)
app.include_router(inventory_routes.router)
app.include_router(market_routes.router)
app.include_router(blacksmith_routes.router)
app.include_router(progress_routes.router)
app.include_router(codex_routes.router)
app.include_router(guide_routes.router)
app.include_router(tutorial_routes.router)
app.include_router(update_routes.router)
if settings.app_mode != "desktop":
    app.include_router(admin_routes.router)
else:
    from app.desktop.routes import router as desktop_router
    from app.routes.regional_routes import router as regional_router

    app.include_router(desktop_router)
    app.include_router(regional_router)
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
        app.state.gameplay_tick_task = asyncio.get_running_loop().create_task(_desktop_gameplay_ticks())
        return

    db = SessionLocal()
    try:
        from app.seeds.campaign_content import apply_initial_campaign_content

        apply_initial_campaign_content(db)
    finally:
        db.close()


@app.on_event("shutdown")
def close_desktop_campaign() -> None:
    if settings.app_mode == "desktop":
        tick_task = getattr(app.state, "gameplay_tick_task", None)
        if tick_task is not None:
            tick_task.cancel()
    if settings.app_mode == "desktop" and (
        getattr(app.state, "active_campaign", None) is not None
        or getattr(app.state, "suspended_campaigns", set())
    ):
        from app.desktop.lifecycle import close_campaign, close_suspended_campaigns

        close_campaign(app, app.state.campaign_service, app.state.clock_guard)
        close_suspended_campaigns(app, app.state.campaign_service, app.state.clock_guard)
