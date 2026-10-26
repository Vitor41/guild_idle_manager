from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.guild import Guild
from app.models.market import GuildActivity
from app.repositories.market_repository import create_guild_activity, get_guild_activity


SESSION_GLOBAL_SECONDS = settings.session_global_seconds
SESSION_IDLE_SECONDS = settings.session_idle_seconds


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def get_or_create_activity(db: Session, guild_id: int) -> GuildActivity:
    activity = get_guild_activity(db, guild_id)
    if activity is None:
        activity = create_guild_activity(db, guild_id)
        db.flush()
    return activity


def get_session_expiry(activity: GuildActivity) -> tuple[datetime | None, str | None]:
    expirations: list[tuple[datetime, str]] = []
    if activity.session_started_at is not None:
        expirations.append((aware(activity.session_started_at) + timedelta(seconds=SESSION_GLOBAL_SECONDS), "global"))
    if activity.last_activity_at is not None:
        expirations.append((aware(activity.last_activity_at) + timedelta(seconds=SESSION_IDLE_SECONDS), "idle"))
    return min(expirations, key=lambda value: value[0]) if expirations else (None, None)


def start_online_session(db: Session, guild: Guild, now: datetime | None = None) -> str:
    current_time = now or utc_now()
    activity = get_or_create_activity(db, guild.id)
    token = token_urlsafe(32)
    activity.is_online = True
    activity.session_token = token
    activity.session_started_at = current_time
    activity.last_activity_at = current_time
    activity.offline_started_at = None
    activity.last_seen_at = current_time
    db.add(activity)
    db.commit()
    return token


def adopt_legacy_session(db: Session, guild: Guild, now: datetime | None = None) -> str:
    return start_online_session(db, guild, now)


def touch_online_session(db: Session, activity: GuildActivity, now: datetime | None = None) -> None:
    activity.last_activity_at = now or utc_now()
    activity.is_online = True
    db.add(activity)
    db.commit()


def start_offline_period(
    db: Session,
    guild: Guild,
    when: datetime | None = None,
    expected_token: str | None = None,
) -> bool:
    activity = get_or_create_activity(db, guild.id)
    if expected_token is not None and activity.session_token != expected_token:
        return False
    started_at = when or utc_now()
    activity.is_online = False
    activity.session_token = None
    activity.session_started_at = None
    activity.last_activity_at = None
    activity.offline_started_at = started_at
    activity.last_seen_at = started_at
    db.add(activity)
    db.commit()
    return True


def expire_stale_online_session(db: Session, guild: Guild, now: datetime | None = None) -> tuple[bool, str | None]:
    activity = get_or_create_activity(db, guild.id)
    if not activity.is_online:
        return False, None
    current_time = now or utc_now()
    expires_at, reason = get_session_expiry(activity)
    if expires_at is None or current_time < expires_at:
        return False, None
    start_offline_period(db, guild, expires_at, activity.session_token)
    return True, reason
