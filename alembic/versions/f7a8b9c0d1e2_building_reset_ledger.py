"""Add building investment history and reset state, freezing legacy estimates."""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_ESTIMATE_BASIS = (
    "Estimativa congelada na migração do reset: tabela oficial de custos e multiplicador por nível; "
    "madeira, minério e cristais são representados por materiais comuns de menor nível da família; "
    "nenhum uso de reserva de Cristais foi presumido. Não é histórico comprovado."
)
RESOURCE_FAMILIES = {
    "wood": ("wood",),
    "ore": ("ore", "stone"),
    "crystals": ("gem", "essence", "crystal"),
}


def _cost_factor_parts(level: int) -> tuple[int, int]:
    if level <= 10:
        return level, 1
    if level <= 25:
        return 20 + (level - 10) * 3, 2
    if level <= 40:
        return 65 + (level - 25) * 4, 2
    if level <= 50:
        return 125 + (level - 40) * 6, 2
    return 185 + (level - 50), 2


def _scaled_cost(base: int, level: int) -> int:
    numerator, denominator = _cost_factor_parts(level)
    value = max(0, int(base or 0)) * numerator
    return (value + denominator - 1) // denominator


def _legacy_template_id(connection, item_templates, resource: str) -> int | None:
    families = RESOURCE_FAMILIES[resource]
    family_order = sa.case(
        *[(item_templates.c.material_family == family, index) for index, family in enumerate(families)],
        else_=len(families),
    )
    rarity_order = sa.case(
        (sa.func.lower(item_templates.c.rarity) == "common", 0),
        else_=1,
    )
    row = connection.execute(
        sa.select(item_templates.c.id)
        .where(
            item_templates.c.item_type == "material",
            item_templates.c.material_family.in_(families),
            sa.func.lower(item_templates.c.rarity) == "common",
        )
        .order_by(family_order, item_templates.c.tier, rarity_order, item_templates.c.id)
        .limit(1)
    ).first()
    if row is None:
        return None
    return int(row[0])


def upgrade() -> None:
    op.create_table(
        "guild_building_resets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("was_free", sa.Boolean(), nullable=False),
        sa.Column("crystal_cost", sa.Integer(), nullable=False),
        sa.Column("charge_json", sa.JSON(), nullable=False),
        sa.Column("refund_json", sa.JSON(), nullable=False),
        sa.Column("levels_before_json", sa.JSON(), nullable=False),
        sa.Column("has_estimated_refund", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("guild_id", "idempotency_key", name="uq_building_reset_idempotency"),
    )
    op.create_index("ix_guild_building_resets_guild_id", "guild_building_resets", ["guild_id"])

    op.create_table(
        "guild_building_reset_states",
        sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), primary_key=True),
        sa.Column("free_reset_used", sa.Boolean(), nullable=False),
        sa.Column("paid_reset_count", sa.Integer(), nullable=False),
        sa.Column("previous_paid_cost", sa.Integer(), nullable=False),
        sa.Column("reset_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "guild_building_investments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=36), nullable=False),
        sa.Column("guild_id", sa.Integer(), sa.ForeignKey("guilds.id"), nullable=False),
        sa.Column("guild_building_id", sa.Integer(), sa.ForeignKey("guild_buildings.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("effect_type", sa.String(length=80), nullable=False),
        sa.Column("from_level", sa.Integer(), nullable=False),
        sa.Column("to_level", sa.Integer(), nullable=False),
        sa.Column("gold_debited", sa.Integer(), nullable=False),
        sa.Column("crystal_reserve_debited", sa.Integer(), nullable=False),
        sa.Column("materials_json", sa.JSON(), nullable=False),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.Column("estimate_basis", sa.Text(), nullable=True),
        sa.Column("refunded_by_reset_id", sa.Integer(), sa.ForeignKey("guild_building_resets.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("transaction_id", name="uq_building_investment_transaction"),
        sa.UniqueConstraint("guild_building_id", "generation", "to_level", name="uq_building_investment_level"),
    )
    op.create_index("ix_guild_building_investments_guild_id", "guild_building_investments", ["guild_id"])

    connection = op.get_bind()
    metadata = sa.MetaData()
    guilds = sa.Table("guilds", metadata, autoload_with=connection)
    buildings = sa.Table("guild_buildings", metadata, autoload_with=connection)
    building_templates = sa.Table("building_templates", metadata, autoload_with=connection)
    item_templates = sa.Table("item_templates", metadata, autoload_with=connection)
    states = sa.Table("guild_building_reset_states", metadata, autoload_with=connection)
    investments = sa.Table("guild_building_investments", metadata, autoload_with=connection)
    now = datetime.now(timezone.utc)

    for guild in connection.execute(sa.select(guilds.c.id)).all():
        connection.execute(states.insert().values(
            guild_id=int(guild.id), free_reset_used=False, paid_reset_count=0,
            previous_paid_cost=0, reset_count=0, updated_at=now,
        ))

    rows = connection.execute(
        sa.select(
            buildings.c.id.label("building_id"),
            buildings.c.guild_id,
            buildings.c.level,
            building_templates.c.effect_type,
            building_templates.c.base_upgrade_gold_cost,
            building_templates.c.base_upgrade_wood_cost,
            building_templates.c.base_upgrade_ore_cost,
            building_templates.c.base_upgrade_crystals_cost,
        )
        .join(building_templates, building_templates.c.id == buildings.c.building_template_id)
        .where(buildings.c.level > 0)
        .order_by(buildings.c.id)
    ).mappings()

    template_ids: dict[str, int | None] = {}

    for building in rows:
        effect_type = str(building["effect_type"])
        final_level = min(100, max(0, int(building["level"])))
        for to_level in range(1, final_level + 1):
            if to_level == 1 and effect_type in {"housing", "tavern"}:
                gold = 10
                wood = ore = crystals = 0
            else:
                gold = _scaled_cost(building["base_upgrade_gold_cost"], to_level)
                wood = _scaled_cost(building["base_upgrade_wood_cost"], to_level)
                ore = _scaled_cost(building["base_upgrade_ore_cost"], to_level)
                crystals = _scaled_cost(building["base_upgrade_crystals_cost"], to_level)
            material_rows = []
            reserve_estimate = 0
            pending_resources: list[str] = []
            for resource, quantity in (("wood", wood), ("ore", ore), ("crystals", crystals)):
                if quantity <= 0:
                    continue
                if resource not in template_ids:
                    template_ids[resource] = _legacy_template_id(connection, item_templates, resource)
                template_id = template_ids[resource]
                if template_id is None and resource == "crystals":
                    reserve_estimate = quantity
                    continue
                if template_id is None:
                    material_rows.append({
                        "item_template_id": None,
                        "quantity": quantity,
                        "resource": resource,
                        "pending_common_template": True,
                    })
                    pending_resources.append(resource)
                    continue
                material_rows.append({"item_template_id": template_id, "quantity": quantity, "resource": resource})
            estimate_basis = LEGACY_ESTIMATE_BASIS
            if reserve_estimate:
                estimate_basis = (
                    "Estimativa congelada na migração: tabela oficial de custos e multiplicador por nível; "
                    "madeira e minério usam materiais comuns de menor nível; Cristais são estimados como reserva "
                    "por não haver material comum de Cristal no catálogo da campanha. Não é histórico comprovado."
                )
            if pending_resources:
                estimate_basis += (
                    " Quantidades estimadas de " + ", ".join(pending_resources) +
                    " preservadas pendentes; serão associadas ao material comum após a atualização do catálogo."
                )
            connection.execute(investments.insert().values(
                transaction_id=str(uuid4()),
                guild_id=int(building["guild_id"]),
                guild_building_id=int(building["building_id"]),
                generation=0,
                effect_type=effect_type,
                from_level=to_level - 1,
                to_level=to_level,
                gold_debited=gold,
                crystal_reserve_debited=reserve_estimate,
                materials_json=material_rows,
                estimated=True,
                estimate_basis=estimate_basis,
                refunded_by_reset_id=None,
                created_at=now,
            ))


def downgrade() -> None:
    op.drop_index("ix_guild_building_investments_guild_id", table_name="guild_building_investments")
    op.drop_table("guild_building_investments")
    op.drop_table("guild_building_reset_states")
    op.drop_index("ix_guild_building_resets_guild_id", table_name="guild_building_resets")
    op.drop_table("guild_building_resets")
