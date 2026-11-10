"""Persisted batch production for the supply workshop."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.guild import Guild
from app.models.item import GuildInventoryItem, ItemTemplate
from app.models.workshop import SupplyWorkshopJob
from app.repositories.item_repository import remove_inventory_quantity
from app.services.inventory_capacity_service import (
    add_inventory_quantity_capped, get_inventory_capacity, get_inventory_usage,
)

MEAT_PER_KIT = 3
HERBS_PER_KIT = 2
SECONDS_PER_KIT = 5
SUPPLY_KIT_FAMILY = "supply_kit"


class WorkshopError(ValueError):
    pass


class _WorkshopCapacityNotAvailable(Exception):
    """Roll back a delivery attempt while keeping its reservation active."""


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _materials(db: Session, family: str) -> list[ItemTemplate]:
    return list(db.scalars(select(ItemTemplate).where(
        ItemTemplate.item_type == "material", ItemTemplate.material_family == family,
        ItemTemplate.is_active.is_(True),
    ).order_by(ItemTemplate.item_level, ItemTemplate.tier, ItemTemplate.id)))


def _material_rows(db: Session, guild: Guild, family: str, *, lock: bool = False) -> list[GuildInventoryItem]:
    stmt = select(GuildInventoryItem).join(ItemTemplate).where(
        GuildInventoryItem.guild_id == guild.id, ItemTemplate.item_type == "material",
        ItemTemplate.material_family == family, ItemTemplate.is_active.is_(True),
    ).order_by(ItemTemplate.item_level, ItemTemplate.tier, ItemTemplate.id)
    return list(db.scalars(stmt.with_for_update() if lock else stmt))


def ensure_supply_kit(db: Session) -> ItemTemplate:
    item = db.scalar(select(ItemTemplate).where(ItemTemplate.slug == "supply_kit"))
    if item is None:
        item = ItemTemplate(slug="supply_kit", name="Kit de Suprimentos",
            description="Suprimentos preparados para fortalecer uma equipe regional.",
            item_type="material", rarity="common", item_level=1, level_band="1-20", tier=1,
            content_pack="workshops_v1", material_family=SUPPLY_KIT_FAMILY,
            base_sell_value=1, icon_group="resource-provisions", required_level=1, is_active=True)
        db.add(item)
        db.flush()
    return item


def _complete_due_job(db: Session, guild_id: int, now: datetime) -> SupplyWorkshopJob | None:
    job = db.scalar(select(SupplyWorkshopJob).where(
        SupplyWorkshopJob.guild_id == guild_id, SupplyWorkshopJob.status == "in_progress"
    ).with_for_update())
    if job is None or _utc(job.ends_at) > now:
        return job
    guild = db.get(Guild, guild_id)
    if guild is None or get_inventory_usage(db, guild_id) > get_inventory_capacity(db, guild):
        return job
    try:
        # Keep the reservation until delivery can replace it with stored kits.
        # A savepoint also protects the job if capacity changes after this check.
        with db.begin_nested():
            changed = db.execute(update(SupplyWorkshopJob).where(
                SupplyWorkshopJob.id == job.id, SupplyWorkshopJob.status == "in_progress",
                SupplyWorkshopJob.ends_at <= now,
            ).values(status="completed", completed_at=now, updated_at=now).execution_options(
                synchronize_session=False,
            ))
            if changed.rowcount != 1:
                return db.get(SupplyWorkshopJob, job.id)
            accepted, overflow = add_inventory_quantity_capped(
                db, guild, job.output_item_template_id, job.kit_quantity,
            )
            if overflow or accepted != job.kit_quantity:
                raise _WorkshopCapacityNotAvailable
            job.status, job.completed_at = "completed", now
            db.flush()
    except _WorkshopCapacityNotAvailable:
        db.expire_all()
        return db.get(SupplyWorkshopJob, job.id)
    return job


def get_supply_workshop_context(db: Session, guild: Guild, *, now: datetime | None = None) -> dict[str, object]:
    now = _utc(now or datetime.now(timezone.utc))
    kit = ensure_supply_kit(db)
    due_job = _complete_due_job(db, guild.id, now)
    meats, herbs = _materials(db, "meat"), _materials(db, "herb")
    meat_rows, herb_rows = _material_rows(db, guild, "meat"), _material_rows(db, guild, "herb")
    kit_row = db.scalar(select(GuildInventoryItem).where(
        GuildInventoryItem.guild_id == guild.id, GuildInventoryItem.item_template_id == kit.id))
    stock = {"meat": sum(int(r.quantity) for r in meat_rows),
             "herb": sum(int(r.quantity) for r in herb_rows),
             "kit": int(kit_row.quantity) if kit_row else 0}
    job = db.scalar(select(SupplyWorkshopJob).where(
        SupplyWorkshopJob.guild_id == guild.id, SupplyWorkshopJob.status == "in_progress")) or due_job
    capacity = get_inventory_capacity(db, guild)
    usage = get_inventory_usage(db, guild.id)
    completion_blocked = bool(
        due_job and due_job.status == "in_progress" and _utc(due_job.ends_at) <= now
    )
    input_max = min(stock["meat"] // MEAT_PER_KIT, stock["herb"] // HERBS_PER_KIT)
    # A batch consumes five slots and reserves one output slot per kit.
    if usage > capacity:
        input_max = min(input_max, max(0, (usage - capacity) // 4))
    can_start = bool(meats and herbs and input_max > 0 and job is None)
    return {"meat_item": meats[0] if meats else None, "herb_item": herbs[0] if herbs else None,
            "kit_item": kit, "stock": stock, "max_batch": input_max,
            "can_craft": can_start, "job": job, "seconds_per_kit": SECONDS_PER_KIT,
            "completed_job": due_job if due_job and due_job.status == "completed" else None,
            "completion_blocked": completion_blocked}


def craft_supply_kit(db: Session, guild: Guild, quantity: int = 1, *, now: datetime | None = None) -> SupplyWorkshopJob:
    now = _utc(now or datetime.now(timezone.utc))
    if isinstance(quantity, bool) or int(quantity) != quantity or int(quantity) < 1:
        raise WorkshopError("Informe uma quantidade inteira maior que zero.")
    quantity = int(quantity)
    kit = ensure_supply_kit(db)
    if db.scalar(select(SupplyWorkshopJob.id).where(
        SupplyWorkshopJob.guild_id == guild.id, SupplyWorkshopJob.status == "in_progress")):
        raise WorkshopError("Já existe uma produção em andamento nesta Oficina.")
    rows = {family: _material_rows(db, guild, family, lock=True) for family in ("meat", "herb")}
    stocks = {family: sum(int(row.quantity) for row in group) for family, group in rows.items()}
    if stocks["meat"] < quantity * MEAT_PER_KIT:
        raise WorkshopError(f"Faltam Carnes: cada Kit exige {MEAT_PER_KIT}.")
    if stocks["herb"] < quantity * HERBS_PER_KIT:
        raise WorkshopError(f"Faltam Ervas: cada Kit exige {HERBS_PER_KIT}.")
    ends = now + timedelta(seconds=quantity * SECONDS_PER_KIT)
    job = SupplyWorkshopJob(guild_id=guild.id, output_item_template_id=kit.id,
        kit_quantity=quantity, meat_per_kit=MEAT_PER_KIT, herb_per_kit=HERBS_PER_KIT,
        seconds_per_kit=SECONDS_PER_KIT, status="in_progress", started_at=now, ends_at=ends,
        created_at=now, updated_at=now)
    db.add(job)
    try:
        db.flush()
        for family, cost in (("meat", quantity * MEAT_PER_KIT), ("herb", quantity * HERBS_PER_KIT)):
            remaining = cost
            for row in rows[family]:
                used = min(remaining, int(row.quantity))
                if used:
                    remove_inventory_quantity(db, row, used)
                remaining -= used
                if not remaining:
                    break
        db.flush()
        # Reservations keep this output's warehouse space unavailable to other rewards.
        if get_inventory_usage(db, guild.id) > get_inventory_capacity(db, guild):
            raise WorkshopError("O resultado excederia a capacidade do Armazém.")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise WorkshopError("Já existe uma produção em andamento nesta Oficina.") from exc
    except Exception:
        db.rollback()
        raise
    return job
