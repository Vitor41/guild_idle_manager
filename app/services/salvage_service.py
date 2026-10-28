from datetime import datetime, timedelta, timezone

from app.core.time import prepare_timer_context
from random import SystemRandom

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.game_balance import MARKET_RARITY_SECONDS
from app.models.guild import Guild, GuildResources
from app.models.item import ItemTemplate
from app.models.salvage import GuildSalvageJob
from app.repositories.item_repository import (
    delete_item_instance,
    list_available_item_instances_by_guild,
    list_available_item_instances_for_template,
)
from app.repositories.salvage_repository import (
    create_salvage_job,
    get_active_salvage_job_for_slot,
    get_salvage_job_by_guild,
    list_salvage_jobs_by_guild,
)
from app.services.inventory_capacity_service import add_inventory_quantity_capped
from app.services.building_service import get_building_level
from app.services.display_service import clean_generated_name


SALVAGE_SLOT_RULES = {
    1: {"required_level": 1, "unit_cost": 50},
    2: {"required_level": 25, "unit_cost": 150},
    3: {"required_level": 50, "unit_cost": 300},
}

# Equipment composition stays code-driven so new templates only need an icon group.
SALVAGE_MATERIAL_BY_ICON_GROUP = {
    "bow": "wood", "staff": "wood", "wand": "wood",
    "book": "cloth", "robe": "cloth",
    "light_armor": "leather", "boots": "leather", "gloves": "leather", "belt": "leather",
    "sword": "ore", "axe": "ore", "dagger": "ore", "mace": "ore", "spear": "ore",
    "shield": "ore", "helmet": "ore", "heavy_armor": "ore", "medium_armor": "ore", "chest": "ore",
    "ring": "gem", "earring": "gem", "necklace": "gem",
}

SALVAGE_FALLBACK_BY_SLOT = {
    "main_hand": "ore", "off_hand": "cloth", "shield": "ore", "helmet": "ore",
    "chest": "leather", "gloves": "leather", "boots": "leather", "belt": "leather",
    "ring": "gem", "earring": "gem", "necklace": "gem",
}


class SalvageError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def salvage_slot_count(blacksmith_level: int) -> int:
    return sum(1 for rule in SALVAGE_SLOT_RULES.values() if blacksmith_level >= rule["required_level"])


def salvage_duration_seconds(rarity: str, tier: int, quantity: int) -> int:
    return MARKET_RARITY_SECONDS.get(rarity, 30) * max(1, tier) * max(1, quantity)


def salvage_material_family(item_template: ItemTemplate) -> str:
    icon_group = (item_template.icon_group or "").lower()
    return SALVAGE_MATERIAL_BY_ICON_GROUP.get(
        icon_group,
        SALVAGE_FALLBACK_BY_SLOT.get(item_template.equipment_slot or "", "ore"),
    )


def _select_salvage_material(db: Session, item_template: ItemTemplate) -> ItemTemplate:
    family = salvage_material_family(item_template)
    candidate = db.scalar(
        select(ItemTemplate)
        .where(
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family == family,
            ItemTemplate.is_active.is_(True),
            ItemTemplate.tier <= max(1, item_template.tier),
            ItemTemplate.item_level <= max(1, item_template.item_level),
        )
        .order_by(ItemTemplate.tier.desc(), ItemTemplate.item_level.desc(), ItemTemplate.base_sell_value.asc())
    )
    if candidate is None:
        candidate = db.scalar(
            select(ItemTemplate)
            .where(
                ItemTemplate.item_type == "material",
                ItemTemplate.material_family == family,
                ItemTemplate.is_active.is_(True),
            )
            .order_by(ItemTemplate.item_level, ItemTemplate.base_sell_value, ItemTemplate.id)
        )
    if candidate is None:
        raise SalvageError("Nenhum material compatível foi encontrado para este equipamento.")
    return candidate


def get_salvage_context(db: Session, guild: Guild, blacksmith_level: int) -> dict[str, object]:
    now = utc_now()
    jobs = list_salvage_jobs_by_guild(db, guild.id)
    active_by_slot = {job.slot_number: job for job in jobs if job.status == "in_progress"}
    for job in active_by_slot.values():
        prepare_timer_context(job, now)
    groups: dict[int, dict[str, object]] = {}
    for item in list_available_item_instances_by_guild(db, guild.id):
        if item.equipped_to_mercenary_id is not None:
            continue
        group = groups.setdefault(item.item_template_id, {
            "item_template": item.item_template,
            "quantity": 0,
            "display_name": clean_generated_name(item.item_template.name),
            "material_family": salvage_material_family(item.item_template),
            "unit_duration_seconds": salvage_duration_seconds(
                item.item_template.rarity, item.item_template.tier, 1
            ),
        })
        group["quantity"] = int(group["quantity"]) + 1
    slots = []
    for number, rule in SALVAGE_SLOT_RULES.items():
        slots.append({
            "number": number,
            "required_level": rule["required_level"],
            "unit_cost": rule["unit_cost"],
            "unlocked": blacksmith_level >= rule["required_level"],
            "job": active_by_slot.get(number),
        })
    return {
        "salvage_slots": slots,
        "salvage_equipment_groups": sorted(groups.values(), key=lambda group: str(group["display_name"])),
        "salvage_history": [job for job in jobs if job.status == "completed"][:8],
        "salvage_now": now,
    }


def start_salvage(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    slot_number: str,
    item_template_id: str,
    quantity: str,
) -> GuildSalvageJob:
    if resources is None:
        raise SalvageError("Recursos da guilda indisponíveis.")
    try:
        parsed_slot = int(slot_number)
        parsed_template = int(item_template_id)
        parsed_quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise SalvageError("Espaço, equipamento ou quantidade inválidos.") from exc
    if parsed_quantity < 1 or parsed_quantity > 100:
        raise SalvageError("A quantidade deve ficar entre 1 e 100.")
    rule = SALVAGE_SLOT_RULES.get(parsed_slot)
    blacksmith_level = get_building_level(db, guild.id, "blacksmith")
    if rule is None or blacksmith_level < rule["required_level"]:
        raise SalvageError("Este espaço de desmontagem ainda não foi liberado.")

    locked_resources = db.scalar(
        select(GuildResources).where(GuildResources.guild_id == guild.id).with_for_update()
    )
    if locked_resources is None:
        raise SalvageError("Recursos da guilda indisponíveis.")
    if get_active_salvage_job_for_slot(db, guild.id, parsed_slot, lock=True) is not None:
        raise SalvageError("Este espaço do Ferreiro já está ocupado.")
    items = list_available_item_instances_for_template(
        db, guild.id, parsed_template, lock=True
    )
    if len(items) < parsed_quantity:
        raise SalvageError("A quantidade escolhida não está mais disponível no inventário.")
    item_template = items[0].item_template
    material_template = _select_salvage_material(db, item_template)
    gold_cost = rule["unit_cost"] * parsed_quantity
    if locked_resources.gold < gold_cost:
        raise SalvageError(f"São necessários {gold_cost} de ouro para este serviço.")

    started_at = utc_now()
    job = create_salvage_job(db, {
        "guild_id": guild.id,
        "slot_number": parsed_slot,
        "item_template_id": item_template.id,
        "material_template_id": material_template.id,
        "quantity": parsed_quantity,
        "gold_cost": gold_cost,
        "status": "in_progress",
        "started_at": started_at,
        "ends_at": started_at + timedelta(seconds=salvage_duration_seconds(
            item_template.rarity, item_template.tier, parsed_quantity
        )),
    })
    locked_resources.gold -= gold_cost
    for item in items[:parsed_quantity]:
        delete_item_instance(db, item)
    db.add(locked_resources)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SalvageError("Este espaço acabou de ser ocupado. Atualize e tente outro.") from exc
    db.refresh(job)
    return job


def collect_salvage(db: Session, guild: Guild, job_id: str) -> GuildSalvageJob:
    try:
        parsed_job_id = int(job_id)
    except (TypeError, ValueError) as exc:
        raise SalvageError("Serviço de desmontagem inválido.") from exc
    job = get_salvage_job_by_guild(db, guild.id, parsed_job_id, lock=True)
    if job is None or job.status != "in_progress":
        raise SalvageError("Serviço não encontrado ou já coletado.")
    now = utc_now()
    ends_at = job.ends_at if job.ends_at.tzinfo else job.ends_at.replace(tzinfo=timezone.utc)
    if now < ends_at:
        raise SalvageError("O Ferreiro ainda não terminou a desmontagem.")

    result_quantity = sum(SystemRandom().randint(1, 3) for _ in range(job.quantity))
    stored_quantity, _discarded_quantity = add_inventory_quantity_capped(
        db, guild, job.material_template_id, result_quantity,
    )
    job.result_quantity = stored_quantity
    job.status = "completed"
    job.collected_at = now
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
