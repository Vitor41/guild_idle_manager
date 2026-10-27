from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """Normalize database timestamps, including SQLite's naive UTC values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
