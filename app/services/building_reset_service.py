from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, joinedload

from app.models import (
    ClassChangeRun,
    DungeonRun,
    GatheringAssignment,
    Guild,
    GuildBuilding,
    GuildBuildingInvestment,
    GuildBuildingReset,
    GuildBuildingResetState,
    GuildInventoryItem,
    GuildResources,
    GuildSalvageJob,
    ItemTemplate,
    MarketSale,
    Mercenary,
    MissionRun,
    RegionalGuildState,
    RegionalOffer,
    SupplyWorkshopJob,
)
from app.repositories.item_repository import (
    RESOURCE_MATERIAL_FAMILIES,
    consume_inventory_resource,
    get_inventory_resource_totals,
    sync_inventory_resource_totals,
)
from app.services.building_balance_service import housing_capacity
from app.services.inventory_capacity_service import (
    BASE_WAREHOUSE_CAPACITY,
    GUILD_CAPACITY_PER_LEVEL,
    get_inventory_usage,
)


LEGACY_ESTIMATE_BASIS = (
    "Estimativa congelada na migração: tabela oficial de custos e multiplicador por nível; "
    "madeira, minério e cristais são representados por materiais comuns de menor nível da família; "
    "nenhum uso de reserva de Cristais foi presumido. Não é histórico comprovado."
)


class BuildingResetError(ValueError):
    def __init__(self, message: str, *, preview: dict[str, Any] | None = None):
        super().__init__(message)
        self.preview = preview


class StaleBuildingResetPreview(BuildingResetError):
    pass


class BlockedBuildingReset(BuildingResetError):
    pass


def _lock_guild_for_building_mutation(db: Session, guild_id: int) -> Guild | None:
    """Serialize building mutations; SQLite's write lock starts before blocker checks."""
    dialect = db.get_bind().dialect.name
    db.flush()
    if dialect == "sqlite":
        statement = update(Guild).where(Guild.id == guild_id).values(updated_at=Guild.updated_at)
        try:
            db.execute(statement)
        except OperationalError as error:
            if not any(token in str(error).lower() for token in ("locked", "busy")):
                raise
            # The request may have read the guild before another writer acquired SQLite's lock.
            # Drop that stale read snapshot and retry against the committed state.
            db.rollback()
            db.execute(statement)
    else:
        db.scalar(
            select(Guild)
            .where(Guild.id == guild_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    db.expire_all()
    return db.get(Guild, guild_id)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _factor_for_level(level: int) -> Decimal:
    level = max(1, min(100, int(level)))
    if level <= 10:
        return Decimal(level)
    if level <= 25:
        return Decimal(20 + (level - 10) * 3) / Decimal(2)
    if level <= 40:
        return Decimal(65 + (level - 25) * 4) / Decimal(2)
    if level <= 50:
        return Decimal(125 + (level - 40) * 6) / Decimal(2)
    return Decimal(185 + level - 50) / Decimal(2)


def _scaled_cost(base: int, level: int) -> int:
    return int((Decimal(max(0, int(base or 0)) * _factor_for_level(level)).quantize(
        Decimal("1"), rounding=ROUND_CEILING
    )))


def _lowest_common_material(db: Session, resource: str) -> ItemTemplate:
    families = RESOURCE_MATERIAL_FAMILIES[resource]
    family_order = {family: index for index, family in enumerate(families)}
    rows = list(db.scalars(
        select(ItemTemplate).where(
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family.in_(families),
            ItemTemplate.rarity.ilike("common"),
        )
    ))
    rows.sort(key=lambda row: (family_order.get(row.material_family, len(family_order)), row.tier, row.id))
    if not rows:
        raise BuildingResetError(
            f"Não há material comum da família {resource} para estimar investimentos antigos."
        )
    return rows[0]


def _estimate_material_rows(db: Session, costs: dict[str, int]) -> tuple[list[dict[str, Any]], int, str]:
    rows: list[dict[str, Any]] = []
    reserve_estimate = 0
    basis = LEGACY_ESTIMATE_BASIS
    for resource in ("wood", "ore", "crystals"):
        quantity = max(0, int(costs.get(resource, 0)))
        if quantity:
            try:
                template = _lowest_common_material(db, resource)
            except BuildingResetError:
                if resource != "crystals":
                    raise
                reserve_estimate = quantity
                basis = (
                    "Estimativa congelada: tabela oficial por nível; madeira e minério usam materiais comuns "
                    "de menor nível; Cristais são estimados como reserva porque não há material comum de Cristal. "
                    "Não é histórico comprovado."
                )
                continue
            rows.append({
                "item_template_id": template.id,
                "item_name": template.name,
                "quantity": quantity,
                "resource": resource,
            })
    return rows, reserve_estimate, basis


def _legacy_upgrade_cost(building: GuildBuilding, to_level: int) -> dict[str, int]:
    template = building.building_template
    if to_level == 1 and template.effect_type in {"housing", "tavern"}:
        return {"gold": 10, "wood": 0, "ore": 0, "crystals": 0}
    return {
        "gold": _scaled_cost(template.base_upgrade_gold_cost, to_level),
        "wood": _scaled_cost(template.base_upgrade_wood_cost, to_level),
        "ore": _scaled_cost(template.base_upgrade_ore_cost, to_level),
        "crystals": _scaled_cost(template.base_upgrade_crystals_cost, to_level),
    }


def _blocking_operations(db: Session, guild_id: int) -> list[dict[str, Any]]:
    checks = (
        (MarketSale, MarketSale.guild_id, "in_progress", "Vendas em andamento", "/market"),
        (MissionRun, MissionRun.guild_id, "in_progress", "Missões em andamento", "/missions"),
        (DungeonRun, DungeonRun.guild_id, "in_progress", "Masmorras ou portais em andamento", "/dungeons"),
        (ClassChangeRun, ClassChangeRun.guild_id, "in_progress", "Trocas de classe em andamento", "/class-change"),
        (GuildSalvageJob, GuildSalvageJob.guild_id, "in_progress", "Desmontagens aguardando coleta", "/blacksmith"),
        (SupplyWorkshopJob, SupplyWorkshopJob.guild_id, "in_progress", "Lotes de oficina aguardando entrega", "/workshops"),
    )
    blockers: list[dict[str, Any]] = []
    for model, guild_column, status, label, href in checks:
        rows = list(db.execute(
            select(model.id, model.status).where(guild_column == guild_id, model.status == status)
        ))
        if rows:
            blockers.append({
                "code": model.__tablename__, "label": label, "count": len(rows), "href": href,
                "items": [{"id": int(row.id), "status": str(row.status)} for row in rows],
            })

    assignments = list(db.execute(
        select(GatheringAssignment.id, GatheringAssignment.capacity_paused).where(
            GatheringAssignment.guild_id == guild_id
        )
    ))
    if assignments:
        blockers.append({
            "code": "gathering_assignments", "label": "Designações de coleta", "count": len(assignments),
            "href": "/gathering",
            "items": [{"id": int(row.id), "capacity_paused": bool(row.capacity_paused)} for row in assignments],
        })

    regional_offers = list(db.execute(
        select(RegionalOffer.id, RegionalOffer.status)
        .join(RegionalGuildState, RegionalGuildState.id == RegionalOffer.reserved_by_guild_state_id)
        .where(
            RegionalGuildState.guild_id == guild_id,
            RegionalOffer.status == "supply_preparing",
            RegionalOffer.reserved_by_guild_state_id.is_not(None),
        )
    ))
    if regional_offers:
        blockers.append({
            "code": "regional_supply_preparing", "label": "Ofertas regionais em preparo", "count": len(regional_offers),
            "href": "/regional",
            "items": [{"id": int(row.id), "status": str(row.status)} for row in regional_offers],
        })
    return blockers


def _next_paid_cost(state: GuildBuildingResetState | None) -> int:
    if state is None or state.paid_reset_count <= 0:
        return 50
    return (int(state.previous_paid_cost) * 130 + 99) // 100


def _crystal_stack_snapshot(db: Session, guild_id: int) -> list[dict[str, Any]]:
    families = RESOURCE_MATERIAL_FAMILIES["crystals"]
    rows = db.execute(
        select(GuildInventoryItem.item_template_id, GuildInventoryItem.quantity, ItemTemplate.name)
        .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
        .where(
            GuildInventoryItem.guild_id == guild_id,
            GuildInventoryItem.quantity > 0,
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family.in_(families),
        )
        .order_by(GuildInventoryItem.quantity.desc(), GuildInventoryItem.id)
    )
    return [
        {"item_template_id": int(row.item_template_id), "quantity": int(row.quantity), "item_name": str(row.name)}
        for row in rows
    ]


def _charge_quote(db: Session, resources: GuildResources | None, cost: int) -> dict[str, Any]:
    if resources is None or cost <= 0:
        return {"crystal_cost": max(0, cost), "crystal_reserve": 0, "items": [], "uncovered": 0}
    stacks = _crystal_stack_snapshot(db, resources.guild_id)
    remaining = cost
    items: list[dict[str, Any]] = []
    for stack in stacks:
        quantity = min(remaining, stack["quantity"])
        if quantity:
            items.append({**stack, "quantity": quantity})
            remaining -= quantity
        if not remaining:
            break
    reserve = min(remaining, max(0, int(resources.crystal_reserve or 0)))
    remaining -= reserve
    return {"crystal_cost": cost, "crystal_reserve": reserve, "items": items, "uncovered": remaining}


def _collect_investments_and_estimates(
    db: Session,
    guild_id: int,
    generation: int,
    buildings: list[GuildBuilding],
) -> tuple[list[GuildBuildingInvestment], list[dict[str, Any]]]:
    investments = list(db.scalars(
        select(GuildBuildingInvestment)
        .where(GuildBuildingInvestment.guild_id == guild_id)
        .order_by(GuildBuildingInvestment.id)
    ))
    existing_levels = {
        (row.guild_building_id, row.generation, row.to_level)
        for row in investments
    }
    missing_estimates: list[dict[str, Any]] = []
    for building in buildings:
        for to_level in range(1, max(0, int(building.level)) + 1):
            key = (building.id, generation, to_level)
            if key in existing_levels:
                continue
            cost = _legacy_upgrade_cost(building, to_level)
            estimated_materials, reserve_estimate, estimate_basis = _estimate_material_rows(db, cost)
            missing_estimates.append({
                "transaction_id": str(uuid4()),
                "guild_id": guild_id,
                "guild_building_id": building.id,
                "generation": generation,
                "effect_type": building.building_template.effect_type,
                "from_level": to_level - 1,
                "to_level": to_level,
                "gold_debited": cost["gold"],
                "crystal_reserve_debited": reserve_estimate,
                "materials_json": estimated_materials,
                "estimated": True,
                "estimate_basis": estimate_basis,
                "refunded_by_reset_id": None,
                "created_at": _now(),
            })
    return investments, missing_estimates


def _investment_refund(
    db: Session,
    investments: list[GuildBuildingInvestment],
    missing_estimates: list[dict[str, Any]],
) -> dict[str, Any]:
    estimated_gold = 0
    exact_gold = 0
    estimated_reserve = 0
    exact_reserve = 0
    items: dict[tuple[int, bool], dict[str, Any]] = {}
    estimate_bases: set[str] = set()
    for row in investments:
        if row.refunded_by_reset_id is not None:
            continue
        estimated = bool(row.estimated)
        if estimated:
            if row.estimate_basis:
                estimate_bases.add(str(row.estimate_basis))
            estimated_gold += max(0, int(row.gold_debited))
            estimated_reserve += max(0, int(row.crystal_reserve_debited))
        else:
            exact_gold += max(0, int(row.gold_debited))
            exact_reserve += max(0, int(row.crystal_reserve_debited))
        for item in (row.materials_json or []):
            item_id = int(item["item_template_id"])
            key = (item_id, estimated)
            entry = items.setdefault(key, {"item_template_id": item_id, "quantity": 0, "estimated": estimated})
            entry["quantity"] += max(0, int(item["quantity"]))
    for row in missing_estimates:
        if row.get("estimate_basis"):
            estimate_bases.add(str(row["estimate_basis"]))
        estimated_gold += max(0, int(row["gold_debited"]))
        estimated_reserve += max(0, int(row["crystal_reserve_debited"]))
        for item in row["materials_json"]:
            item_id = int(item["item_template_id"])
            key = (item_id, True)
            entry = items.setdefault(key, {"item_template_id": item_id, "quantity": 0, "estimated": True})
            entry["quantity"] += max(0, int(item["quantity"]))
    names = {
        int(row.id): str(row.name)
        for row in db.scalars(select(ItemTemplate).where(ItemTemplate.id.in_({key[0] for key in items})))
    } if items else {}
    item_rows = [
        {**value, "item_name": names.get(value["item_template_id"], "Material sem nome")}
        for _, value in sorted(items.items(), key=lambda pair: (names.get(pair[0][0], ""), pair[0][1]))
        if value["quantity"] > 0
    ]
    return {
        "gold": {"exact": exact_gold, "estimated": estimated_gold},
        "crystal_reserve": {"exact": exact_reserve, "estimated": estimated_reserve},
        "items": item_rows,
        "estimate_basis": " ".join(sorted(estimate_bases)) or None,
        "has_estimated": bool(
            any(row.estimated for row in investments if row.refunded_by_reset_id is None)
            or missing_estimates
        ),
    }


def _snapshot_fingerprint(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_building_reset_preview(db: Session, guild_id: int) -> dict[str, Any]:
    guild = db.get(Guild, guild_id)
    if guild is None:
        raise BuildingResetError("Guilda não encontrada.")
    resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))
    buildings = list(db.scalars(
        select(GuildBuilding)
        .options(joinedload(GuildBuilding.building_template))
        .where(GuildBuilding.guild_id == guild_id)
        .order_by(GuildBuilding.id)
    ))
    state = db.get(GuildBuildingResetState, guild_id)
    generation = int(state.reset_count) if state else 0
    investments, missing_estimates = _collect_investments_and_estimates(db, guild_id, generation, buildings)
    refund = _investment_refund(db, investments, missing_estimates)
    blockers = _blocking_operations(db, guild_id)
    has_levels = any(int(building.level) > 0 for building in buildings)
    first_free_available = state is None or not state.free_reset_used
    eligible_for_first_free = first_free_available and int(guild.level) >= 10
    if first_free_available:
        was_free = eligible_for_first_free
        crystal_cost = 0
        eligibility_message = "" if was_free else "O primeiro reset gratuito fica disponível no nível 10 da guilda."
    else:
        was_free = False
        crystal_cost = _next_paid_cost(state)
        eligibility_message = ""

    balances = get_inventory_resource_totals(db, guild_id)
    balances["crystals"] = int(balances.get("crystals", 0)) + max(0, int(resources.crystal_reserve or 0)) if resources else 0
    balances["gold"] = int(resources.gold) if resources else 0
    charge_quote = _charge_quote(db, resources, crystal_cost)
    if resources is None:
        blockers.append({"code": "resources", "label": "Recursos da guilda indisponíveis", "count": 1, "href": "/inventory", "items": []})
    if not has_levels:
        blockers.append({"code": "no_buildings_to_reset", "label": "Não há construções acima do nível 0", "count": 0, "href": "/buildings", "items": []})
    if eligibility_message:
        blockers.append({"code": "guild_level", "label": eligibility_message, "count": 1, "href": "/guild/progress", "items": []})
    if crystal_cost and balances["crystals"] < crystal_cost:
        blockers.append({
            "code": "insufficient_crystals", "label": f"Cristais insuficientes: {balances['crystals']} disponíveis de {crystal_cost}",
            "count": 1, "href": "/inventory", "items": [],
        })

    usage = get_inventory_usage(db, guild_id)
    projected_charge_quantity = sum(int(item["quantity"]) for item in charge_quote["items"])
    projected_refund_quantity = sum(int(item["quantity"]) for item in refund["items"])
    projected_usage = max(0, usage - projected_charge_quantity) + projected_refund_quantity
    post_reset_warehouse_capacity = BASE_WAREHOUSE_CAPACITY + max(0, int(guild.level) - 1) * GUILD_CAPACITY_PER_LEVEL
    active_mercenaries = len(list(db.scalars(select(Mercenary.id).where(
        Mercenary.guild_id == guild_id, Mercenary.status != "dismissed"
    ))))
    levels_before = {str(building.id): int(building.level) for building in buildings}
    token_payload = {
        "guild_id": guild_id,
        "guild_level": int(guild.level),
        "state": {
            "free_reset_used": bool(state.free_reset_used) if state else False,
            "paid_reset_count": int(state.paid_reset_count) if state else 0,
            "previous_paid_cost": int(state.previous_paid_cost) if state else 0,
            "reset_count": generation,
        },
        "balances": balances,
        "reserve": max(0, int(resources.crystal_reserve or 0)) if resources else 0,
        "capacity_after": {
            "housing_slots": housing_capacity(0),
            "active_mercenaries": active_mercenaries,
            "warehouse_capacity": post_reset_warehouse_capacity,
            "inventory_usage": projected_usage,
            "inventory_over_capacity": max(0, projected_usage - post_reset_warehouse_capacity),
        },
        "inventory": _crystal_stack_snapshot(db, guild_id),
        "buildings": [
            {
                "id": int(building.id), "level": int(building.level),
                "effect_type": building.building_template.effect_type,
                "gold": int(building.building_template.base_upgrade_gold_cost),
                "wood": int(building.building_template.base_upgrade_wood_cost),
                "ore": int(building.building_template.base_upgrade_ore_cost),
                "crystals": int(building.building_template.base_upgrade_crystals_cost),
            }
            for building in buildings
        ],
        "investments": [
            {
                "id": int(row.id), "generation": int(row.generation), "building": int(row.guild_building_id),
                "to_level": int(row.to_level), "gold": int(row.gold_debited),
                "reserve": int(row.crystal_reserve_debited), "materials": row.materials_json or [],
                "estimated": bool(row.estimated), "refunded": row.refunded_by_reset_id,
            }
            for row in investments
        ],
        "missing_estimates": [
            {key: value for key, value in row.items() if key not in {"transaction_id", "created_at"}}
            for row in missing_estimates
        ],
        "blockers": blockers,
    }
    can_confirm = not blockers
    return {
        "guild": guild,
        "resources": resources,
        "buildings": buildings,
        "was_free": was_free,
        "crystal_cost": crystal_cost,
        "paid_reset_count": int(state.paid_reset_count) if state else 0,
        "blockers": blockers,
        "can_confirm": can_confirm,
        "refund": refund,
        "missing_estimates": missing_estimates,
        "charge_quote": charge_quote,
        "has_estimated_refund": refund["has_estimated"],
        "estimate_basis": refund["estimate_basis"],
        "levels_before": levels_before,
        "capacity_after": {
            "housing_slots": housing_capacity(0),
            "active_mercenaries": active_mercenaries,
            "warehouse_capacity": post_reset_warehouse_capacity,
            "inventory_usage": projected_usage,
            "inventory_over_capacity": max(0, projected_usage - post_reset_warehouse_capacity),
        },
        "fingerprint": _snapshot_fingerprint(token_payload),
        "idempotency_key": str(uuid4()),
    }


def _inventory_quantities(db: Session, guild_id: int, resource: str) -> dict[int, int]:
    families = RESOURCE_MATERIAL_FAMILIES[resource]
    rows = db.execute(
        select(GuildInventoryItem.item_template_id, GuildInventoryItem.quantity)
        .join(ItemTemplate, ItemTemplate.id == GuildInventoryItem.item_template_id)
        .where(
            GuildInventoryItem.guild_id == guild_id,
            ItemTemplate.item_type == "material",
            ItemTemplate.material_family.in_(families),
        )
    )
    return {int(row.item_template_id): int(row.quantity) for row in rows}


def record_building_investment(
    db: Session,
    guild: Guild,
    building: GuildBuilding,
    resources: GuildResources,
    cost: dict[str, int],
    before_items: dict[str, dict[int, int]],
    before_reserve: int,
) -> GuildBuildingInvestment:
    db.flush()
    state = db.get(GuildBuildingResetState, guild.id)
    generation = int(state.reset_count) if state else 0
    after_items = {resource: _inventory_quantities(db, guild.id, resource) for resource in ("wood", "ore", "crystals")}
    materials: list[dict[str, Any]] = []
    for resource in ("wood", "ore", "crystals"):
        for item_template_id, quantity in before_items[resource].items():
            consumed = max(0, quantity - after_items[resource].get(item_template_id, 0))
            if consumed:
                materials.append({
                    "item_template_id": item_template_id,
                    "quantity": consumed,
                    "resource": resource,
                })
    reserve_debited = max(0, before_reserve - int(resources.crystal_reserve or 0))
    investment = GuildBuildingInvestment(
        transaction_id=str(uuid4()),
        guild_id=guild.id,
        guild_building_id=building.id,
        generation=generation,
        effect_type=building.building_template.effect_type,
        from_level=int(building.level) - 1,
        to_level=int(building.level),
        gold_debited=int(cost.get("gold", 0)),
        crystal_reserve_debited=reserve_debited,
        materials_json=materials,
        estimated=False,
        estimate_basis=None,
    )
    db.add(investment)
    return investment


def perform_building_reset(
    db: Session,
    guild_id: int,
    *,
    expected_fingerprint: str,
    idempotency_key: str,
) -> GuildBuildingReset:
    try:
        key = str(UUID(idempotency_key))
    except (ValueError, AttributeError) as exc:
        raise BuildingResetError("A confirmação expirou. Abra uma nova prévia.") from exc
    try:
        guild = _lock_guild_for_building_mutation(db, guild_id)
        if guild is None:
            raise BuildingResetError("Guilda não encontrada.")
        existing = db.scalar(select(GuildBuildingReset).where(
            GuildBuildingReset.guild_id == guild_id,
            GuildBuildingReset.idempotency_key == key,
        ))
        if existing is not None:
            db.rollback()
            return existing

        preview = get_building_reset_preview(db, guild_id)
        if preview["fingerprint"] != expected_fingerprint:
            raise StaleBuildingResetPreview(
                "O estado da guilda mudou desde a prévia. Confira os valores atualizados antes de confirmar.",
                preview=preview,
            )
        if preview["blockers"]:
            raise BlockedBuildingReset(
                "Conclua as pendências listadas antes de resetar as construções.", preview=preview
            )

        resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))
        if resources is None:
            raise BuildingResetError("Recursos da guilda indisponíveis.", preview=preview)
        sync_inventory_resource_totals(db, resources)
        crystal_cost = int(preview["crystal_cost"])
        if resources.crystals < crystal_cost:
            raise StaleBuildingResetPreview(
                "O saldo de Cristais mudou. Confira a prévia atualizada antes de confirmar.", preview=preview
            )

        reset = GuildBuildingReset(
            guild_id=guild_id,
            idempotency_key=key,
            was_free=bool(preview["was_free"]),
            crystal_cost=crystal_cost,
            charge_json={},
            refund_json={},
            levels_before_json=preview["levels_before"],
            has_estimated_refund=bool(preview["has_estimated_refund"]),
        )
        db.add(reset)
        db.flush()

        for estimate in preview["missing_estimates"]:
            db.add(GuildBuildingInvestment(**estimate))
        db.flush()

        current_buildings = list(db.scalars(
            select(GuildBuilding)
            .options(joinedload(GuildBuilding.building_template))
            .where(GuildBuilding.guild_id == guild_id)
            .order_by(GuildBuilding.id)
        ))
        investments = list(db.scalars(
            select(GuildBuildingInvestment)
            .where(GuildBuildingInvestment.guild_id == guild_id)
            .order_by(GuildBuildingInvestment.id)
        ))
        refund = _investment_refund(db, investments, [])

        crystal_items_before = _inventory_quantities(db, guild_id, "crystals")
        reserve_before = max(0, int(resources.crystal_reserve or 0))
        if crystal_cost and not consume_inventory_resource(db, resources, "crystals", crystal_cost):
            raise StaleBuildingResetPreview(
                "O saldo disponível mudou. Confira a prévia atualizada antes de confirmar.", preview=preview
            )
        if crystal_cost:
            db.flush()
        crystal_items_after = _inventory_quantities(db, guild_id, "crystals")
        charge_items = []
        names = {int(row.id): str(row.name) for row in db.scalars(
            select(ItemTemplate).where(ItemTemplate.id.in_(set(crystal_items_before) | set(crystal_items_after)))
        )} if crystal_items_before or crystal_items_after else {}
        for item_template_id, quantity in crystal_items_before.items():
            consumed = max(0, quantity - crystal_items_after.get(item_template_id, 0))
            if consumed:
                charge_items.append({
                    "item_template_id": item_template_id,
                    "item_name": names.get(item_template_id, "Cristal"),
                    "quantity": consumed,
                })
        reserve_charged = max(0, reserve_before - int(resources.crystal_reserve or 0))

        refund_items = [dict(item) for item in refund["items"]]
        aggregate_credit: dict[int, int] = {}
        for item in refund_items:
            item_template_id = int(item["item_template_id"])
            aggregate_credit[item_template_id] = aggregate_credit.get(item_template_id, 0) + int(item["quantity"])
        for item_template_id, quantity in aggregate_credit.items():
            inventory_item = db.scalar(select(GuildInventoryItem).where(
                GuildInventoryItem.guild_id == guild_id,
                GuildInventoryItem.item_template_id == item_template_id,
            ).with_for_update())
            if inventory_item is None:
                db.add(GuildInventoryItem(
                    guild_id=guild_id, item_template_id=item_template_id, quantity=quantity,
                ))
            else:
                inventory_item.quantity += quantity
        resources.gold += int(refund["gold"]["exact"]) + int(refund["gold"]["estimated"])
        resources.crystal_reserve += int(refund["crystal_reserve"]["exact"]) + int(refund["crystal_reserve"]["estimated"])
        for building in current_buildings:
            building.level = 0
            db.add(building)
        for investment in investments:
            if investment.refunded_by_reset_id is None:
                investment.refunded_by_reset_id = reset.id
                db.add(investment)
        db.flush()

        state = db.get(GuildBuildingResetState, guild_id)
        if state is None:
            state = GuildBuildingResetState(
                guild_id=guild_id, free_reset_used=False, paid_reset_count=0,
                previous_paid_cost=0, reset_count=0,
            )
            db.add(state)
            db.flush()
        if reset.was_free:
            state.free_reset_used = True
        else:
            state.paid_reset_count += 1
            state.previous_paid_cost = crystal_cost
        state.reset_count += 1
        state.updated_at = _now()
        db.add(state)
        db.add(resources)
        sync_inventory_resource_totals(db, resources)

        reset.charge_json = {
            "crystal_cost": crystal_cost,
            "crystal_reserve": reserve_charged,
            "items": charge_items,
        }
        reset.refund_json = refund
        reset.has_estimated_refund = bool(refund["has_estimated"])
        db.add(reset)
        db.flush()
        db.commit()
        db.refresh(reset)
        return reset
    except Exception:
        db.rollback()
        raise
