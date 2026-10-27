from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """Normalize database timestamps, including SQLite's naive UTC values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def prepare_timer_context(run: object, now: datetime) -> None:
    """Expose UTC timer status and ISO values for page templates."""
    if isinstance(run, dict):
        ends_at = as_utc(run["ends_at"])
        run["ready_for_loot"] = ends_at <= as_utc(now)
        run["ends_at_iso"] = ends_at.isoformat()
        return
    ends_at = as_utc(run.ends_at)
    run.ready_for_loot = ends_at <= as_utc(now)
    run.ends_at_iso = ends_at.isoformat()
