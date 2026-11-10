from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.dependencies import DbSession, get_current_user
from app.models.guild import Guild
from app.models.user import User
from app.services.navigation_work_status_service import get_navigation_work_status


router = APIRouter(prefix="/api/navigation")


@router.get("/work-status")
def navigation_work_status(request: Request, db: DbSession):
    campaign_id: str | None = None
    if getattr(request.app.state, "app_mode", "web") == "desktop":
        active_campaign = getattr(request.app.state, "active_campaign", None)
        campaign_id = getattr(active_campaign, "campaign_id", None)
        if not campaign_id:
            return JSONResponse({"detail": "Campanha indisponível."}, status_code=401)
        guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
    else:
        current_user: User | None = get_current_user(request, db)
        if current_user is None:
            return JSONResponse({"detail": "Sessão indisponível."}, status_code=401)
        guild = db.scalar(select(Guild).where(Guild.user_id == current_user.id))

    if guild is None:
        return JSONResponse({"detail": "Guilda indisponível."}, status_code=401)
    return {"menus": get_navigation_work_status(db, guild.id, campaign_id=campaign_id)}
