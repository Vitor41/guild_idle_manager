"""Campaign manager pages and local-only campaign actions."""

from pathlib import Path
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.desktop.lifecycle import open_campaign, open_campaign_with_migration, suspend_campaign
from app.desktop.gameplay_diagnostics import log_gameplay_action


router = APIRouter(prefix="/desktop")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


class CampaignCreate(BaseModel):
    guild_name: str = Field(min_length=1, max_length=120)


class CampaignRename(BaseModel):
    guild_name: str = Field(min_length=1, max_length=120)


def _services(request: Request):
    campaigns = getattr(request.app.state, "campaign_service", None)
    clock_guard = getattr(request.app.state, "clock_guard", None)
    if campaigns is None or clock_guard is None:
        raise HTTPException(status_code=503, detail="O gerenciador de campanhas ainda não está pronto.")
    return campaigns, clock_guard


@router.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.post("/api/diagnostics/client-error")
@router.post("/api/diagnostics/client-event")
async def report_gameplay_client_error(request: Request) -> JSONResponse:
    diagnostic_id = request.headers.get("x-gim-diagnostic-id", "")
    if not re.fullmatch(r"[a-fA-F0-9-]{16,40}", diagnostic_id):
        return JSONResponse({"recorded": False}, status_code=400)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"recorded": False}, status_code=400)
    route = payload.get("route") if isinstance(payload, dict) else None
    if not isinstance(route, str) or len(route) > 200 or "?" in route:
        return JSONResponse({"recorded": False}, status_code=400)
    if route == "/gathering/assign":
        action = "gathering.assign"
    elif re.fullmatch(r"/regional/offers/\d+/(start|prepare|supply-quote)", route):
        action = "regional.offer"
    elif route in {"/missions/start", "/dungeons/start"}:
        action = route.strip("/").replace("/", ".")
    elif (building_match := re.fullmatch(r"/buildings/(\d+)/upgrade", route)):
        action = f"buildings.{building_match.group(1)}.upgrade"
    elif route in {"/tavern/hire-apprentice", "/tavern/hire-apprentices-bulk", "/tavern/refresh-special", "/tavern/hire-special"}:
        action = route.strip("/").replace("/", ".")
    else:
        return JSONResponse({"recorded": False}, status_code=400)
    payload_phase = payload.get("phase") if isinstance(payload, dict) else None
    if payload_phase not in {None, "click_received", "submit_started", "client_request_failed"}:
        return JSONResponse({"recorded": False}, status_code=400)
    phase = "click" if payload_phase == "click_received" else "start" if payload_phase == "submit_started" else "client_error"
    outcome = "client_click_received" if phase == "click" else "client_submit_started" if phase == "start" else "client_request_failed"
    log_gameplay_action(
        action=action,
        route=route,
        diagnostic_id=diagnostic_id,
        status_code=0,
        outcome=outcome,
        event=phase,
    )
    return JSONResponse({"recorded": True})


@router.get("/api/stamina-status")
def stamina_status(request: Request) -> JSONResponse:
    _campaigns, clock_guard = _services(request)
    active = getattr(request.app.state, "active_campaign", None)
    if active is None:
        return JSONResponse({"available": False}, status_code=409)
    status = clock_guard.preview_active_stamina(
        active.campaign_id,
        active.stamina_seconds,
        active.stamina_recharge_remainder_seconds,
    )
    return JSONResponse({"available": True, **status})


@router.get("/campaigns", response_class=HTMLResponse, include_in_schema=False)
def campaigns_page(request: Request):
    campaigns, _ = _services(request)
    listing = campaigns.list_campaigns()
    return templates.TemplateResponse(
        request=request,
        name="desktop/campaigns.html",
        context={"campaigns": listing, "unavailable_campaigns": listing.unavailable},
    )


@router.post("/api/campaigns")
def create_campaign(payload: CampaignCreate, request: Request):
    campaigns, clock_guard = _services(request)
    if getattr(request.app.state, "active_campaign", None) is not None:
        raise HTTPException(status_code=409, detail="Volte ao menu de campanhas antes de criar outra.")
    try:
        info = campaigns.create_campaign(payload.guild_name, payload.guild_name)
        clock_guard.initialize_campaign(info.campaign_id)
        info, summary = open_campaign(request.app, campaigns, clock_guard, info.campaign_id)
        return {"campaign_id": info.campaign_id, "redirect": "/dashboard", "offline_summary": summary}
    except (ValueError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/campaigns/{campaign_id}/open")
def open_existing_campaign(campaign_id: str, request: Request):
    campaigns, clock_guard = _services(request)
    try:
        info, summary, migration = open_campaign_with_migration(
            request.app, campaigns, clock_guard, campaign_id
        )
        notice = migration.notice_payload() if migration else None
        if notice:
            request.app.state.pending_campaign_migration = {
                "campaign_id": info.campaign_id,
                "notice": notice,
            }
        return {
            "campaign_id": info.campaign_id,
            "redirect": "/dashboard",
            "offline_summary": summary,
            "migration_notice": notice,
        }
    except (ValueError, FileNotFoundError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/return-to-campaigns", include_in_schema=False)
def return_to_campaigns(request: Request):
    campaigns, clock_guard = _services(request)
    try:
        suspend_campaign(request.app, campaigns, clock_guard)
        return RedirectResponse("/desktop/campaigns", status_code=303)
    except (ValueError, FileNotFoundError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class OfflineReportAcknowledgement(BaseModel):
    report_id: str = Field(min_length=1, max_length=64)


@router.post("/api/offline-report/acknowledge")
def acknowledge_offline_report(payload: OfflineReportAcknowledgement, request: Request):
    _campaigns, clock_guard = _services(request)
    active = getattr(request.app.state, "active_campaign", None)
    if active is None:
        raise HTTPException(status_code=409, detail="Abra uma campanha antes de confirmar o relatório.")
    if not clock_guard.acknowledge_offline_report(active.campaign_id, payload.report_id):
        raise HTTPException(status_code=409, detail="Este relatório já foi confirmado ou não corresponde à campanha.")
    return {"acknowledged": True}


@router.patch("/api/campaigns/{campaign_id}")
def rename_campaign(campaign_id: str, payload: CampaignRename, request: Request):
    campaigns, _ = _services(request)
    try:
        info = campaigns.rename_guild(campaign_id, payload.guild_name)
        active = getattr(request.app.state, "active_campaign", None)
        if active and active.campaign_id == info.campaign_id:
            request.app.state.active_campaign = info
        return {"campaign_id": info.campaign_id, "guild_name": info.guild_name}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/campaigns/{campaign_id}/backup")
def backup_campaign(campaign_id: str, request: Request):
    campaigns, _ = _services(request)
    try:
        path = campaigns.create_manual_backup(campaign_id)
        return {"message": "Cópia de segurança criada com sucesso.", "backup_name": path.name}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, request: Request):
    campaigns, _ = _services(request)
    active = getattr(request.app.state, "active_campaign", None)
    try:
        backup_path = campaigns.delete_campaign(campaign_id, active.campaign_id if active else None)
        getattr(request.app.state, "suspended_campaigns", set()).discard(campaign_id)
        return {"message": "Campanha excluída. Uma cópia de segurança foi mantida.", "backup_name": backup_path.name}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
