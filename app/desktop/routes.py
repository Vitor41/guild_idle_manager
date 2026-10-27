"""Campaign manager pages and local-only campaign actions."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.desktop.lifecycle import open_campaign, open_campaign_with_migration, suspend_campaign


router = APIRouter(prefix="/desktop")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


class CampaignCreate(BaseModel):
    campaign_name: str = Field(min_length=1, max_length=120)
    guild_name: str = Field(min_length=1, max_length=120)


class CampaignRename(BaseModel):
    campaign_name: str = Field(min_length=1, max_length=120)


def _services(request: Request):
    campaigns = getattr(request.app.state, "campaign_service", None)
    clock_guard = getattr(request.app.state, "clock_guard", None)
    if campaigns is None or clock_guard is None:
        raise HTTPException(status_code=503, detail="O gerenciador de campanhas ainda nao foi iniciado.")
    return campaigns, clock_guard


@router.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


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
        raise HTTPException(status_code=409, detail="Retorne ao menu de campanhas antes de criar outra.")
    try:
        info = campaigns.create_campaign(payload.campaign_name, payload.guild_name)
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


@router.patch("/api/campaigns/{campaign_id}")
def rename_campaign(campaign_id: str, payload: CampaignRename, request: Request):
    campaigns, _ = _services(request)
    try:
        info = campaigns.rename_campaign(campaign_id, payload.campaign_name)
        active = getattr(request.app.state, "active_campaign", None)
        if active and active.campaign_id == info.campaign_id:
            request.app.state.active_campaign = info
        return {"campaign_id": info.campaign_id, "campaign_name": info.campaign_name}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/campaigns/{campaign_id}/backup")
def backup_campaign(campaign_id: str, request: Request):
    campaigns, _ = _services(request)
    try:
        path = campaigns.create_manual_backup(campaign_id)
        return {"message": "Backup criado com sucesso.", "backup_name": path.name}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, request: Request):
    campaigns, _ = _services(request)
    active = getattr(request.app.state, "active_campaign", None)
    try:
        backup_path = campaigns.delete_campaign(campaign_id, active.campaign_id if active else None)
        return {"message": "Campanha excluida. Um backup de recuperacao foi mantido.", "backup_name": backup_path.name}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
