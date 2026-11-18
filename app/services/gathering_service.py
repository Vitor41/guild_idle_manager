from datetime import datetime, timezone
from hashlib import sha256
from math import floor
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.gathering import GatheringAssignment
from app.models.guild import Guild
from app.models.item import GuildInventoryItem, ItemTemplate
from app.models.mercenary import Mercenary
from app.services.inventory_capacity_service import add_inventory_quantity_capped, get_inventory_capacity, get_inventory_usage


CYCLE_SECONDS = 60
OFFLINE_CAP_SECONDS = 8 * 60 * 60
RESOURCE_FAMILIES = {
    "wood": "wood", "ore": "ore", "leather": "leather", "essence": "essence",
    "gem": "gem", "herb": "herb", "relic": "relic", "cloth": "cloth", "meat": "meat",
}
CANONICAL_GATHERING_MATERIAL_SLUGS = {
    "wood": "material_wood_1_001",
    "ore": "material_ore_2_002",
    "leather": "material_leather_1_001",
    "essence": "material_essence_1_001",
    "gem": "material_gem_1_001",
    "herb": "material_herb_1_001",
    "relic": "material_relic_1_001",
    "cloth": "material_cloth_1_001",
    "meat": "material_meat_1_001",
}
NODE_CODES = {
    "wood": "forest", "ore": "quarry", "leather": "hunting_ground",
    "essence": "leyline", "gem": "crystal_cavern", "herb": "herb_garden",
    "relic": "ruins", "cloth": "loom_grove", "meat": "hunting_ground",
}
FAMILY_LABELS = {
    "wood": "Madeira", "ore": "Minério", "leather": "Couro", "essence": "Essências",
    "gem": "Gemas", "herb": "Ervas", "relic": "Relíquias", "cloth": "Fibras", "meat": "Carne",
}
NODE_LABELS = {
    "wood": "Bosque", "ore": "Pedreira", "leather": "Terras de caça", "essence": "Veios arcanos",
    "gem": "Caverna de cristais", "herb": "Horta silvestre", "relic": "Ruínas antigas", "cloth": "Bosque de linho", "meat": "Terras de caça",
}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def list_assignments(db: Session, guild_id: int) -> list[GatheringAssignment]:
    return list(db.scalars(
        select(GatheringAssignment)
        .options(
            joinedload(GatheringAssignment.mercenary),
            joinedload(GatheringAssignment.mercenary, Mercenary.profession),
            joinedload(GatheringAssignment.target_item_template),
        )
        .where(GatheringAssignment.guild_id == guild_id)
        .order_by(GatheringAssignment.resource_family)
    ))


def _material_template(db: Session, family: str, guild_level: int) -> ItemTemplate | None:
    """Return the fixed common target for a gathering family at every guild level."""
    slug = CANONICAL_GATHERING_MATERIAL_SLUGS.get(family)
    if slug is None:
        return None
    template = db.scalar(select(ItemTemplate).where(
        ItemTemplate.slug == slug,
        ItemTemplate.item_type == "material",
        ItemTemplate.material_family == family,
        ItemTemplate.is_active.is_(True),
    ))
    if template is None or template.rarity != "common":
        return None
    return template


def preview_material_for_family(db: Session, family: str, guild_level: int) -> ItemTemplate | None:
    """Return the same active common target regardless of guild level."""
    if family not in RESOURCE_FAMILIES:
        return None
    return _material_template(db, family, guild_level)


def freeze_legacy_assignment_targets(db: Session, *, now: datetime | None = None) -> int:
    """Freeze only active common targets and discard elapsed time before cutover."""
    frozen = 0
    cutoff = _utc(now or datetime.now(timezone.utc))
    assignments = db.scalars(
        select(GatheringAssignment)
        .where(GatheringAssignment.target_item_template_id.is_(None))
        .order_by(GatheringAssignment.id)
    )
    for assignment in assignments:
        guild = db.get(Guild, assignment.guild_id)
        if guild is None:
            continue
        template = _material_template(db, assignment.resource_family, guild.level)
        if template is None:
            continue
        assignment.target_item_template_id = template.id
        assignment.target_item_template = template
        assignment.checkpoint_at_utc = cutoff
        db.add(assignment)
        frozen += 1
    if frozen:
        db.flush()
    return frozen


def migrate_assignments_to_common_targets(db: Session, *, now: datetime | None = None) -> int:
    """Retarget legacy gathering jobs without granting or resetting progress."""
    migrated = 0
    cutoff = _utc(now or datetime.now(timezone.utc))
    assignments = list(db.scalars(
        select(GatheringAssignment).order_by(GatheringAssignment.id)
    ))
    for assignment in assignments:
        guild = db.get(Guild, assignment.guild_id)
        if guild is None:
            continue
        common = _material_template(db, assignment.resource_family, guild.level)
        if common is None:
            # Keep the saved target and checkpoint untouched. The gathering
            # service will mark this assignment unavailable without crediting
            # production until its canonical common material is active again.
            continue
        if assignment.target_item_template_id == common.id:
            continue

        # Start the canonical target at the migration boundary. Fractional
        # progress remains saved, while pre-cutover time is never credited to
        # either the retired target or its replacement.
        assignment.target_item_template = common
        assignment.target_item_template_id = common.id
        assignment.checkpoint_at_utc = cutoff
        db.add(assignment)
        migrated += 1
    if migrated:
        db.flush()
    return migrated


def get_inventory_quantity_by_family(db: Session, guild_id: int) -> dict[str, int]:
    rows = db.execute(
        select(ItemTemplate.material_family, func.sum(GuildInventoryItem.quantity))
        .join(GuildInventoryItem, GuildInventoryItem.item_template_id == ItemTemplate.id)
        .where(
            GuildInventoryItem.guild_id == guild_id,
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family.is_not(None),
        )
        .group_by(ItemTemplate.material_family)
    )
    return {str(family): int(quantity or 0) for family, quantity in rows}


def assign_worker(
    db: Session,
    guild: Guild,
    mercenary_id: int,
    resource_family: str,
    *,
    now: datetime | None = None,
    target_quantity: int | None = None,
) -> GatheringAssignment:
    from app.services.building_reset_service import _lock_guild_for_building_mutation

    guild = _lock_guild_for_building_mutation(db, guild.id)
    if guild is None:
        raise ValueError("Guilda não encontrada.")
    if resource_family not in RESOURCE_FAMILIES:
        raise ValueError("Escolha uma família de recurso disponível para coleta.")
    target_template = _material_template(db, resource_family, guild.level)
    if target_template is None:
        raise ValueError(
            f"O material de {FAMILY_LABELS[resource_family]} não está disponível no catálogo. "
            "Nenhum trabalhador foi designado; verifique Atualizações ou contate o suporte."
        )
    if target_quantity is not None and (int(target_quantity) < 1 or int(target_quantity) > 100_000):
        raise ValueError("A meta de coleta deve ficar entre 1 e 100.000 unidades.")
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
        target_item_template_id=target_template.id,
        resource_family=resource_family,
        node_code=NODE_CODES[resource_family],
        progress_seconds=0,
        cycle_count=0,
        target_quantity=int(target_quantity) if target_quantity is not None else None,
        quantity_collected=0,
        extra_chance=min(45, max(0, mercenary.profession.bonus_percent if mercenary.profession and mercenary.profession.material_family == resource_family else 0)),
        rng_seed=int.from_bytes(seed_bytes, "big"),
        started_at_utc=timestamp,
        checkpoint_at_utc=timestamp,
    )
    mercenary.status = "gathering"
    db.add(assignment)
    db.add(mercenary)
    return assignment


def release_worker(db: Session, guild: Guild, assignment_id: int, *, now: datetime | None = None) -> dict[str, int | str | bool]:
    assignment = db.scalar(select(GatheringAssignment).where(
        GatheringAssignment.id == assignment_id,
        GatheringAssignment.guild_id == guild.id,
    ).options(joinedload(GatheringAssignment.mercenary)))
    if assignment is None:
        raise ValueError("A designação não foi encontrada.")
    summary = advance_assignment(db, guild, assignment, now=now)
    if summary.get("catalog_missing"):
        assignment.mercenary.status = "available"
        db.add(assignment.mercenary)
        db.delete(assignment)
        summary["released_without_credit"] = True
        return summary
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
) -> dict[str, int | str | bool]:
    timestamp = _utc(now or datetime.now(timezone.utc))
    elapsed = max(0, floor((timestamp - _utc(assignment.checkpoint_at_utc)).total_seconds()))
    if max_seconds is not None:
        elapsed = min(elapsed, max(0, max_seconds))
    template = _material_template(db, assignment.resource_family, guild.level)
    if template is not None and assignment.target_item_template_id != template.id:
        # A legacy target is never paid after the cutover. If the canonical
        # common target exists, switch to it and let this normal clock advance
        # account for elapsed production exactly once.
        assignment.target_item_template = template
        assignment.target_item_template_id = template.id
        db.add(assignment)
    produced = 0
    stored = 0
    discarded = 0
    paused_seconds = 0
    db.flush()
    capacity = get_inventory_capacity(db, guild)
    used = get_inventory_usage(db, guild.id)

    if template is None:
        # Drop the elapsed interval while unavailable so reactivation later
        # cannot turn blocked online/offline time into a backlog of rewards.
        checkpoint = _utc(assignment.checkpoint_at_utc)
        assignment.checkpoint_at_utc = max(checkpoint, timestamp)
        db.add(assignment)
        return {
            "cycles": 0,
            "produced": 0,
            "stored": 0,
            "discarded": 0,
            "paused_seconds": 0,
            "extra_chance": min(45, max(0, assignment.extra_chance)),
            "capacity": capacity,
            "used": used,
            "paused": assignment.capacity_paused,
            "completed": False,
            "target_quantity": assignment.target_quantity or 0,
            "quantity_collected": assignment.quantity_collected,
            "catalog_missing": True,
            "catalog_message": (
                f"Coleta de {FAMILY_LABELS.get(assignment.resource_family, assignment.resource_family)} pausada: "
                "o material comum não está disponível no catálogo. Nenhum ciclo ou item será concedido "
                "durante a pausa; o inventário e o progresso já registrado foram preservados."
            ),
        }

    # Time spent while full is paused. On the first call after space is freed,
    # restart the clock there so that paused time cannot become backlog.
    if assignment.capacity_paused:
        if used < capacity:
            assignment.capacity_paused = False
        assignment.checkpoint_at_utc = timestamp
        db.add(assignment)
        return {
            "cycles": 0,
            "produced": 0,
            "stored": 0,
            "discarded": 0,
            "paused_seconds": elapsed,
            "extra_chance": min(45, max(0, assignment.extra_chance)),
            "capacity": capacity,
            "used": used,
            "paused": assignment.capacity_paused,
        }

    if used >= capacity:
        assignment.capacity_paused = True
        assignment.checkpoint_at_utc = timestamp
        db.add(assignment)
        return {
            "cycles": 0,
            "produced": 0,
            "stored": 0,
            "discarded": 0,
            "paused_seconds": elapsed,
            "extra_chance": min(45, max(0, assignment.extra_chance)),
            "capacity": capacity,
            "used": used,
            "paused": True,
        }

    accrued = max(0, assignment.progress_seconds) + elapsed
    cycles_available, remainder = divmod(accrued, CYCLE_SECONDS)
    cycles_processed = 0
    progress = remainder
    if cycles_available and template is not None:
        if assignment.target_quantity is not None:
            remaining_target = max(0, assignment.target_quantity - assignment.quantity_collected)
            # Every cycle yields at least one unit, so a finite job never needs
            # to process more cycles than units remaining toward its target.
            cycles_available = min(cycles_available, remaining_target)
        remaining_capacity = max(0, capacity - used)
        for cycle in range(assignment.cycle_count, assignment.cycle_count + cycles_available):
            quantity = 1
            cycle_rng = random.Random(f"{assignment.rng_seed}:{cycle}")
            if cycle_rng.randrange(100) < min(45, max(0, assignment.extra_chance)):
                quantity += 1
            if assignment.target_quantity is not None:
                quantity = min(quantity, max(0, assignment.target_quantity - assignment.quantity_collected - produced))
                if quantity <= 0:
                    break
            produced += quantity
            remaining_capacity -= quantity
            cycles_processed += 1
            assignment.cycle_count += 1
            if remaining_capacity <= 0:
                # The cycle that fills the warehouse is completed (its own
                # overflow is lost); later cycles remain unprocessed.
                assignment.capacity_paused = True
                paused_seconds = max(0, accrued - cycles_processed * CYCLE_SECONDS)
                progress = 0
                break
        if produced:
            stored, _discarded = add_inventory_quantity_capped(db, guild, template.id, produced)
            discarded = produced - stored
            if stored < produced:
                # Re-check the cap at write time in case another inventory
                # transaction used space after this assignment was measured.
                assignment.capacity_paused = True
                paused_seconds = max(0, accrued - cycles_processed * CYCLE_SECONDS)
                progress = 0
    assignment.progress_seconds = progress
    assignment.checkpoint_at_utc = timestamp
    if assignment.target_quantity is not None:
        assignment.quantity_collected += stored
    if cycles_processed:
        from app.services.achievement_service import record_guild_stat

        record_guild_stat(
            db, guild.id, f"gathering_cycles_{assignment.resource_family}", cycles_processed,
        )
    completed = assignment.target_quantity is not None and assignment.quantity_collected >= assignment.target_quantity
    if completed:
        assignment.mercenary.status = "available"
        db.add(assignment.mercenary)
        db.delete(assignment)
    else:
        db.add(assignment)
    return {
        "cycles": cycles_processed,
        "produced": produced,
        "stored": stored,
        "discarded": discarded,
        "paused_seconds": paused_seconds,
        "extra_chance": min(45, max(0, assignment.extra_chance)),
        "capacity": capacity,
        "used": get_inventory_usage(db, guild.id),
        "paused": assignment.capacity_paused,
        "completed": completed,
        "target_quantity": assignment.target_quantity or 0,
        "quantity_collected": assignment.quantity_collected,
    }


def advance_all_assignments(
    db: Session,
    guild: Guild,
    *,
    now: datetime | None = None,
    max_seconds: int | None = None,
) -> dict[str, dict[str, int | str | bool]]:
    timestamp = _utc(now or datetime.now(timezone.utc))
    result: dict[str, dict[str, int | str | bool]] = {}
    for assignment in list_assignments(db, guild.id):
        result[assignment.resource_family] = advance_assignment(
            db, guild, assignment, now=timestamp, max_seconds=max_seconds,
        )
    return result
