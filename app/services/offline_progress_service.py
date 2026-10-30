from datetime import datetime, timezone
from math import floor

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.guild import Guild
from app.models.item import ItemTemplate
from app.models.mercenary import Mercenary
from app.repositories.guild_repository import get_resources_by_guild_id
from app.repositories.market_repository import create_guild_activity, get_guild_activity
from app.services.building_service import get_building_level
from app.core.game_balance import OFFLINE_BASE_GOLD_PER_HOUR, OFFLINE_CAP_SECONDS, OFFLINE_MINIMUM_SECONDS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _format_elapsed(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}min" if hours else f"{minutes}min"


def get_passive_gold_rate(db: Session, guild: Guild) -> dict[str, int]:
    mercenary_count = db.scalar(
        select(func.count(Mercenary.id)).where(Mercenary.guild_id == guild.id)
    ) or 0
    warehouse_level = get_building_level(db, guild.id, "warehouse")
    base_rate = OFFLINE_BASE_GOLD_PER_HOUR
    guild_bonus = max(0, guild.level - 1)
    mercenary_bonus = mercenary_count * 2
    building_bonus = warehouse_level // 5
    return {
        "base": base_rate,
        "guild": guild_bonus,
        "mercenaries": mercenary_bonus,
        "building": building_bonus,
        "total": base_rate + guild_bonus + mercenary_bonus + building_bonus,
    }


def gold_reward_sources(rate: dict[str, int], credited_seconds: int) -> dict[str, int]:
    """Split credited gold into guild production and Warehouse, preserving the award."""
    credited_gold = floor(rate.get("total", 0) * credited_seconds / 3600)
    guild_rate = (
        rate.get("base", 0)
        + rate.get("guild", 0)
        + rate.get("mercenaries", 0)
    )
    guild_gold = floor(guild_rate * credited_seconds / 3600)
    return {
        "guild_production": guild_gold,
        # Assign any fractional rounding remainder so the breakdown sums exactly.
        "warehouse": credited_gold - guild_gold,
    }


def calculate_offline_material_rewards(
    gold_per_hour: int,
    credited_seconds: int,
    cap_seconds: int,
    warehouse_bonus: int = 0,
) -> dict[str, int]:
    return {
        "wood_rate": 0,
        "ore_rate": 0,
        "wood_base": 0,
        "ore_base": 0,
        "warehouse_bonus": 0,
        "wood_total": 0,
        "ore_total": 0,
        "crystals": 0,
        "special_crystals": 1 if credited_seconds >= cap_seconds else 0,
    }


def _canonical_material(db: Session, family: str) -> ItemTemplate | None:
    return db.scalar(
        select(ItemTemplate)
        .where(
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family == family,
            ItemTemplate.is_active.is_(True),
        )
        .order_by(ItemTemplate.item_level, ItemTemplate.tier, ItemTemplate.id)
    )


def process_offline_progress(db: Session, guild: Guild) -> dict[str, object] | None:
    now = utc_now()
    activity = get_guild_activity(db, guild.id)
    if activity is None:
        activity = create_guild_activity(db, guild.id)
        activity.last_seen_at = now
        activity.offline_started_at = None
        db.commit()
        return None

    if activity.is_online:
        return None

    offline_started_at = activity.offline_started_at
    if offline_started_at is None:
        return None
    elapsed_seconds = max(0, floor((now - _aware(offline_started_at)).total_seconds()))
    activity.last_seen_at = now
    activity.offline_started_at = None
    db.add(activity)
    if elapsed_seconds < OFFLINE_MINIMUM_SECONDS:
        db.commit()
        return None

    credited_seconds = min(elapsed_seconds, OFFLINE_CAP_SECONDS)
    rate = get_passive_gold_rate(db, guild)
    gold = floor(rate["total"] * credited_seconds / 3600)
    materials = calculate_offline_material_rewards(rate["total"], credited_seconds, OFFLINE_CAP_SECONDS)
    resources = get_resources_by_guild_id(db, guild.id)
    if resources is not None and gold > 0:
        resources.gold += gold
        db.add(resources)
    if resources is not None:
        resources.special_crystals += materials["special_crystals"]
        db.add(resources)
    db.commit()
    return {
        "elapsed_label": _format_elapsed(elapsed_seconds),
        "credited_label": _format_elapsed(credited_seconds),
        "gold": gold,
        "materials": materials,
        "special_crystals": materials["special_crystals"],
        "cap_reached": credited_seconds >= OFFLINE_CAP_SECONDS,
        "cap_hours": OFFLINE_CAP_SECONDS // 3600,
        "rate": rate,
        "gold_sources": gold_reward_sources(rate, credited_seconds),
    }
