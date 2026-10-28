from datetime import datetime, timezone
from hashlib import sha256
from math import floor
import random

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.gathering import GatheringAssignment
from app.models.guild import Guild
from app.models.item import ItemTemplate
from app.models.mercenary import Mercenary
from app.services.inventory_capacity_service import add_inventory_quantity_capped, get_inventory_capacity, get_inventory_usage


CYCLE_SECONDS = 60
OFFLINE_CAP_SECONDS = 8 * 60 * 60
RESOURCE_FAMILIES = {"wood": "wood", "ore": "ore", "leather": "leather"}
NODE_CODES = {"wood": "forest", "ore": "quarry", "leather": "hunting_ground"}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def list_assignments(db: Session, guild_id: int) -> list[GatheringAssignment]:
    return list(db.scalars(
        select(GatheringAssignment)
        .options(joinedload(GatheringAssignment.mercenary), joinedload(GatheringAssignment.mercenary, Mercenary.profession))
        .where(GatheringAssignment.guild_id == guild_id)
        .order_by(GatheringAssignment.resource_family)
    ))


def _material_template(db: Session, family: str, guild_level: int) -> ItemTemplate | None:
    return db.scalar(
        select(ItemTemplate)
        .where(
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family == family,
            ItemTemplate.is_active.is_(True),
            ItemTemplate.item_level <= max(1, guild_level),
        )
        .order_by(ItemTemplate.item_level.desc(), ItemTemplate.tier.desc(), ItemTemplate.id)
    ) or db.scalar(
        select(ItemTemplate)
        .where(ItemTemplate.item_type == "material", ItemTemplate.material_family == family, ItemTemplate.is_active.is_(True))
        .order_by(ItemTemplate.item_level, ItemTemplate.tier, ItemTemplate.id)
    )


def assign_worker(
    db: Session,
    guild: Guild,
    mercenary_id: int,
    resource_family: str,
    *,
    now: datetime | None = None,
) -> GatheringAssignment:
    if resource_family not in RESOURCE_FAMILIES:
        raise ValueError("Escolha madeira, minério ou couro para a coleta.")
    mercenary = db.scalar(select(Mercenary).where(Mercenary.id == mercenary_id, Mercenary.guild_id == guild.id))
    if mercenary is None:
        raise ValueError("Este mercenário não pertence à guilda.")
    existing_worker = db.scalar(select(GatheringAssignment).where(GatheringAssignment.mercenary_id == mercenary.id))
    existing_family = db.scalar(select(GatheringAssignment).where(
        GatheringAssignment.guild_id == guild.id,
        GatheringAssignment.resource_family == resource_family,
    ))
    if existing_worker or mercenary.status != "available":
        raise ValueError("O mercenário precisa estar disponível e sem outra designação.")
    if existing_family:
        raise ValueError("Já há um trabalhador designado para este recurso.")
    timestamp = _utc(now or datetime.now(timezone.utc))
    seed_bytes = sha256(f"{guild.campaign_id}:{mercenary.id}:{resource_family}:{timestamp.isoformat()}".encode()).digest()[:4]
    assignment = GatheringAssignment(
        guild_id=guild.id,
        mercenary_id=mercenary.id,
        resource_family=resource_family,
        node_code=NODE_CODES[resource_family],
        progress_seconds=0,
        cycle_count=0,
        extra_chance=min(45, max(0, mercenary.profession.bonus_percent if mercenary.profession and mercenary.profession.material_family == resource_family else 0)),
        rng_seed=int.from_bytes(seed_bytes, "big"),
        started_at_utc=timestamp,
        checkpoint_at_utc=timestamp,
    )
    mercenary.status = "gathering"
    db.add(assignment)
    db.add(mercenary)
    return assignment


def release_worker(db: Session, guild: Guild, assignment_id: int, *, now: datetime | None = None) -> dict[str, int | str]:
    assignment = db.scalar(select(GatheringAssignment).where(
        GatheringAssignment.id == assignment_id,
        GatheringAssignment.guild_id == guild.id,
    ).options(joinedload(GatheringAssignment.mercenary)))
    if assignment is None:
        raise ValueError("A designação não foi encontrada.")
    summary = advance_assignment(db, guild, assignment, now=now)
    assignment.mercenary.status = "available"
    db.delete(assignment)
    return summary


def advance_assignment(
    db: Session,
    guild: Guild,
    assignment: GatheringAssignment,
    *,
    now: datetime | None = None,
    max_seconds: int | None = None,
) -> dict[str, int | str]:
    timestamp = _utc(now or datetime.now(timezone.utc))
    elapsed = max(0, floor((timestamp - _utc(assignment.checkpoint_at_utc)).total_seconds()))
    if max_seconds is not None:
        elapsed = min(elapsed, max(0, max_seconds))
    accrued = max(0, assignment.progress_seconds) + elapsed
    cycles, remainder = divmod(accrued, CYCLE_SECONDS)
    template = _material_template(db, assignment.resource_family, guild.level)
    produced = 0
    stored = 0
    if cycles and template is not None:
        for cycle in range(assignment.cycle_count, assignment.cycle_count + cycles):
            quantity = 1
            cycle_rng = random.Random(f"{assignment.rng_seed}:{cycle}")
            if cycle_rng.randrange(100) < min(45, max(0, assignment.extra_chance)):
                quantity += 1
            produced += quantity
        stored, _discarded = add_inventory_quantity_capped(db, guild, template.id, produced)
    assignment.cycle_count += cycles
    assignment.progress_seconds = remainder
    assignment.checkpoint_at_utc = timestamp
    db.add(assignment)
    return {
        "cycles": cycles,
        "produced": produced,
        "stored": stored,
        "discarded": produced - stored,
        "extra_chance": min(45, max(0, assignment.extra_chance)),
        "capacity": get_inventory_capacity(db, guild),
        "used": get_inventory_usage(db, guild.id),
    }


def advance_all_assignments(
    db: Session,
    guild: Guild,
    *,
    now: datetime | None = None,
    max_seconds: int | None = None,
) -> dict[str, dict[str, int | str]]:
    timestamp = _utc(now or datetime.now(timezone.utc))
    result: dict[str, dict[str, int | str]] = {}
    for assignment in list_assignments(db, guild.id):
        result[assignment.resource_family] = advance_assignment(
            db, guild, assignment, now=timestamp, max_seconds=max_seconds,
        )
    return result
