from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.guild import Guild
from app.models.campaign import CampaignMetadata
from app.models.user import User
from app.repositories.guild_repository import get_guild_by_user_id
from app.repositories.user_repository import get_user_by_id
from app.repositories.market_repository import get_guild_activity
from app.services.session_service import (
    SESSION_GLOBAL_SECONDS,
    SESSION_IDLE_SECONDS,
    adopt_legacy_session,
    get_session_expiry,
    start_offline_period,
    touch_online_session,
    utc_now,
)


DbSession = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class CampaignPlayer:
    id: str
    username: str
    is_admin: bool = False
    tutorial_status: str = "pending"
    confirmation_preferences: str = "{}"


def get_current_campaign(request: Request, db: DbSession) -> CampaignMetadata | None:
    if getattr(request.app.state, "app_mode", "web") != "desktop":
        return None
    campaign = getattr(request.app.state, "active_campaign", None)
    if campaign is None:
        return None
    return db.get(CampaignMetadata, campaign.campaign_id)


def get_current_user(request: Request, db: DbSession) -> User | None:
    if getattr(request.app.state, "app_mode", "web") == "desktop":
        return None
    request.state.offline_summary = request.session.pop("offline_summary", None)
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    user = get_user_by_id(db, int(user_id))
    if user is None:
        request.session.clear()
        return None
    guild = get_guild_by_user_id(db, user.id)
    if guild is not None:
        now = utc_now()
        activity = get_guild_activity(db, guild.id)
        session_token = request.session.get("session_token")
        if session_token is None or activity is None:
            session_token = adopt_legacy_session(db, guild, now)
            request.session["session_token"] = session_token
            request.session["session_started_at"] = int(now.timestamp())
        elif not activity.is_online or activity.session_token != session_token:
            request.session.clear()
            request.session["session_expired_reason"] = "replaced"
            return None
        else:
            expires_at, reason = get_session_expiry(activity)
            if expires_at is not None and now >= expires_at:
                start_offline_period(db, guild, expires_at, str(session_token))
                request.session.clear()
                request.session["session_expired_reason"] = reason or "expired"
                return None
            touch_online_session(db, activity, now)
        request.session["last_activity_at"] = int(now.timestamp())
        request.session["session_global_seconds"] = SESSION_GLOBAL_SECONDS
        request.session["session_idle_seconds"] = SESSION_IDLE_SECONDS
    return user


def get_current_player(request: Request, db: DbSession) -> User | CampaignPlayer | None:
    if getattr(request.app.state, "app_mode", "web") != "desktop":
        return get_current_user(request, db)
    campaign = get_current_campaign(request, db)
    if campaign is None:
        return None
    pending_migration = getattr(request.app.state, "pending_campaign_migration", None)
    if pending_migration and pending_migration.get("campaign_id") == campaign.campaign_id:
        request.state.save_migration_notice = pending_migration["notice"]
        request.app.state.pending_campaign_migration = None
    return CampaignPlayer(
        id=campaign.campaign_id,
        username=campaign.campaign_name,
        tutorial_status=campaign.tutorial_status,
        confirmation_preferences=campaign.confirmation_preferences,
    )


def get_current_guild(db: Session, current_user: User | CampaignPlayer) -> Guild | None:
    if isinstance(current_user, CampaignPlayer):
        from sqlalchemy import select

        return db.scalar(select(Guild).where(Guild.campaign_id == current_user.id))
    return get_guild_by_user_id(db, current_user.id)
