"""Catalog and service audit of recovery sources omitted from funded paths."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.game_balance import MARKET_RARITY_SECONDS
from app.database.connection import Base, create_database_engine
from app.models.dungeon import DungeonTemplate
from app.models.building import BuildingTemplate
from app.models.item import DungeonTemplateItemDrop, MissionTemplateItemDrop
from app.repositories.item_repository import RESOURCE_MATERIAL_FAMILIES
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services.building_balance_service import market_values
from app.services.economy_pricing_service import market_sale_unit_value
from app.services.market_service import _sale_duration_seconds
from app.services.regional_cycle_service import REGIONS
from app.services.salvage_service import SALVAGE_SLOT_RULES, salvage_duration_seconds, salvage_material_family
from scripts.balance.funded_progression_simulation import STRATEGIES
from scripts.balance.simulate_guild_progression_profiles import Profile, _eligible_templates


def _profile(strategy: dict[str, object]) -> Profile:
    return Profile(
        name=str(strategy["name"]), mode=str(strategy["mode"]),
        online_hours_per_day=float(strategy["online_hours"]), slots=int(strategy["teams"]),
        party_size=int(strategy["party_size"]), party_selection_policy="selectable",
    )


def _audit(db) -> dict[str, object]:
    market_bonus = market_values(1)["value_bonus_percent"]
    building_templates = list(db.scalars(select(BuildingTemplate).where(BuildingTemplate.is_active.is_(True))))
    building_costs = [{
        "building": row.effect_type,
        "base_crystals_cost": int(row.base_upgrade_crystals_cost),
        "base_wood_cost": int(row.base_upgrade_wood_cost),
        "base_ore_cost": int(row.base_upgrade_ore_cost),
    } for row in sorted(building_templates, key=lambda item: item.effect_type)]
    required_drop_families = {
        resource: tuple(families) for resource, families in RESOURCE_MATERIAL_FAMILIES.items()
    }
    profiles = {}
    for strategy in STRATEGIES:
        profile = _profile(strategy)
        material_sources = {}
        equipment_sources = {}
        for guild_level in range(1, 51):
            available = _eligible_templates(db, profile, guild_level)
            for mission in available:
                if mission.required_min_mercenary_level > guild_level:
                    continue
                drops = list(db.scalars(select(MissionTemplateItemDrop).where(
                    MissionTemplateItemDrop.mission_template_id == mission.id,
                    MissionTemplateItemDrop.is_active.is_(True),
                ).options(selectinload(MissionTemplateItemDrop.item_template))))
                for drop in drops:
                    item = drop.item_template
                    common = {
                        "first_eligible_at_guild_level": guild_level,
                        "mission_name": mission.name,
                        "mission_type": mission.mission_type,
                        "mission_success_chance_base_percent": int(mission.base_success_chance),
                        "drop_chance_base_percent": int(drop.drop_chance),
                        "quantity_min": int(drop.min_quantity), "quantity_max": int(drop.max_quantity),
                        "guild_level_required": int(mission.required_guild_level),
                        "mercenary_level_required": int(mission.required_min_mercenary_level),
                        "party_size_min": int(mission.min_party_size), "party_size_max": int(mission.max_party_size),
                    }
                    if item.item_type == "equipment":
                        equipment_sources.setdefault((mission.id, drop.id), {
                            **common, "item_name": item.name, "equipment_tier": int(item.tier),
                            "base_sell_value": int(item.base_sell_value),
                        })
                    elif item.item_type == "material" and item.material_family:
                        material_sources.setdefault(item.material_family, {
                            **common, "item_name": item.name, "item_type": item.item_type,
                        })
        profiles[str(strategy["name"])] = {
            "first_eligible_mission_material_drop_by_family": material_sources,
            "building_material_mission_drop_coverage": {
                "required_families": ["wood", "ore", "crystals"],
                "families_with_any_eligible_mission_drop": sorted(
                    resource for resource, families in required_drop_families.items()
                    if any(family in material_sources for family in families)
                ),
                "families_without_eligible_mission_drop_in_catalog_scan": sorted(
                    resource for resource, families in required_drop_families.items()
                    if not any(family in material_sources for family in families)
                ),
                "resource_aliases": {resource: list(families) for resource, families in required_drop_families.items()},
                "raw_mission_material_families": sorted(material_sources),
                "scope": "Current seeded mission catalog, guild levels 1–50 and this profile's planned party size; not a global game-source audit.",
            },
            "first_eligible_equipment_drops": sorted(
                equipment_sources.values(), key=lambda row: (row["first_eligible_at_guild_level"],
                    row["mission_success_chance_base_percent"], row["drop_chance_base_percent"]),
            )[:5],
            "explicitly_not_modeled_in_funded_path": [
                "Mission material/equipment rolls and actual inventory additions",
                "Market sale scheduling and collection",
                "Salvage of unassigned equipment",
                "Dungeon completion rewards and item drops",
            ],
        }

    dungeon_candidates = list(db.scalars(select(DungeonTemplate).options(
        selectinload(DungeonTemplate.item_drops).selectinload(DungeonTemplateItemDrop.item_template),
    ).where(DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "dungeon",
            DungeonTemplate.required_guild_level <= 1)))
    dungeon_rows = []
    for template in dungeon_candidates:
        drops = [drop for drop in template.item_drops if drop.is_active and drop.item_template]
        dungeon_rows.append({
            "name": template.name,
            "required_guild_level": int(template.required_guild_level),
            "required_mercenary_level": int(template.required_min_mercenary_level),
            "party_size_min": int(template.min_party_size), "party_size_max": int(template.max_party_size),
            "required_building": (f"{template.required_building_type} {template.required_building_level}"
                                   if template.required_building_type else None),
            "success_base_percent": int(template.base_success_chance),
            "duration_minutes": round(int(template.duration_seconds) / 60, 1),
            "drops": [{
                "name": drop.item_template.name, "type": drop.item_template.item_type,
                "family": drop.item_template.material_family, "chance_percent": int(drop.drop_chance),
                "quantity_min": int(drop.min_quantity), "quantity_max": int(drop.max_quantity),
            } for drop in drops[:5]],
        })

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "region_assumption": f"Seeded initial content; home region {REGIONS[0][1]}",
        "mission_recovery_sources_by_profile": profiles,
        "building_resource_reachability": {
            "resource_inventory_family_aliases": {resource: list(families)
                                                   for resource, families in RESOURCE_MATERIAL_FAMILIES.items()},
            "active_seeded_building_base_costs": building_costs,
            "any_nonzero_crystal_base_cost": any(row["base_crystals_cost"] > 0 for row in building_costs),
            "interpretation": (
                "O catálogo consultado não exige cristais de prédio em custos-base; a ausência de drops de `crystal` não prova softlock de cristal. `gem`, `essence` e `crystal` são aliases reais para pagar o recurso crystals, que também é concedido ao atingir o limite offline."
                if not any(row["base_crystals_cost"] > 0 for row in building_costs) else
                "Há custo-base de cristais em prédios; investigar as rotas `gem`/`essence`/`crystal` e os demais sistemas antes de concluir alcance global."
            ),
        },
        "market_route": {
            "required_building": "Market 1",
            "slots_at_level_1": market_values(1)["slots"],
            "value_bonus_percent_at_level_1": market_bonus,
            "sale_unit_formula": "max(1, floor(max(1, base_sell_value) * (100 + market bonus percent) / 100))",
            "unit_value_examples": {
                str(base): market_sale_unit_value(base, market_bonus) for base in (1, 5, 10, 25, 50, 100)
            },
            "sale_duration_seconds_by_rarity_tier1_unit": {
                rarity: _sale_duration_seconds(rarity, 1, 1, market_values(1)["time_reduction_percent"])
                for rarity in sorted(MARKET_RARITY_SECONDS)
            },
            "operational_gates": ["Build Market 1", "Have an unsold item/material in inventory", "Wait for timer", "Collect proceeds"],
            "recovery_limit": "A sale is not an immediate bailout: it consumes an item, requires prior access to Market 1 and a free slot, and only pays after its timer is collected.",
        },
        "salvage_route": {
            "required_building": "Blacksmith 1",
            "level_1_unit_gold_cost": int(SALVAGE_SLOT_RULES[1]["unit_cost"]),
            "level_1_slots": 1,
            "yield_per_equipment_unit": "1–3 unidades do material compatível, sorteadas por SystemRandom na coleta",
            "material_family_by_icon_group": "Code mapping in salvage_service.salvage_material_family; fallback by equipment slot, then ore",
            "duration_seconds_by_rarity_tier1_unit": {
                rarity: salvage_duration_seconds(rarity, 1, 1) for rarity in sorted(MARKET_RARITY_SECONDS)
            },
            "operational_gates": ["Build Blacksmith 1", "Own an unassigned unsold equipment item", "Have 50 gold per item", "Wait and collect result"],
            "recovery_limit": "Requires equipment and 50 gold, so it cannot guarantee recovery from an empty-cash shortfall; output also shares capped inventory.",
        },
        "dungeon_routes_catalog_candidates": sorted(
            dungeon_rows, key=lambda row: (row["required_guild_level"], row["required_mercenary_level"], row["name"]),
        )[:10],
        "hard_softlock_scope": "Estes canais existem nos serviços/conteúdo atuais, mas a auditoria não simula rota de campanha, escolha do jogador, venda, desmontagem, rolagem de saque nem resultado de recuperação de ponta a ponta. Permanecem fora da evidência e são risco residual; a auditoria não prova que evitam hard softlock.",
        "limits": [
            "Drops de missão são chances de catálogo condicionadas a uma missão bem-sucedida; não incluem ações por dia nem probabilidade acumulada.",
            "Ouro, XP e drops de missão não são combinados no ledger da progressão financiada.",
            "A auditoria não afirma que um drop listado corresponda à próxima falta de material da trajetória simulada.",
            "Masmorra ainda requer Exploradores 1 e grupo válido; recompensas listadas exigem conclusão e são probabilísticas.",
            "Mercado e desmontagem são serviços opcionais ativos que dependem de melhorias próprias e ações do jogador.",
        ],
    }


def render_markdown(data: dict[str, object]) -> str:
    lines = [
        "# Fontes de recuperação fora da progressão financiada — Stage 5", "",
        f"Auditoria do catálogo/serviços seedados · {data['generated_at_utc']} · {data['region_assumption']}.", "",
        "Este relatório identifica canais reais que o simulador financiado não percorre. Elegibilidade e chance-base não demonstram que o jogador obtenha o recurso necessário a tempo.", "",
        "## Drops de missão elegíveis durante a progressão 1–50", "",
        "A tabela mostra a primeira faixa de guilda com missão de catálogo elegível por perfil e família. Os valores são condicionais à conclusão bem-sucedida; sem número de ações nem seed de saque por trajetória, não se estima dia do primeiro drop ou probabilidade acumulada.", "",
        "| Perfil | Família do item | Nível elegível | Missão | Sucesso base | Drop base | Quantidade |",
        "|---|---|---:|---|---:|---:|---:|",
    ]
    for profile, row in data["mission_recovery_sources_by_profile"].items():
        for family, drop in sorted(row["first_eligible_mission_material_drop_by_family"].items()):
            lines.append(f"| {profile} | {family} | {drop['first_eligible_at_guild_level']} | {drop['mission_name']} | {drop['mission_success_chance_base_percent']}% | {drop['drop_chance_base_percent']}% | {drop['quantity_min']}–{drop['quantity_max']} |")
    lines.extend(["", "Cobertura dos recursos exigidos por prédios após mapear famílias de inventário: madeira aceita `wood`; minério aceita `ore`/`stone`; cristais aceitam `gem`/`essence`/`crystal`."])
    lines.extend(
        f"- {profile}: drops de {', '.join(row['building_material_mission_drop_coverage']['families_with_any_eligible_mission_drop']) or 'nenhum'}; sem drop de missão elegível de {', '.join(row['building_material_mission_drop_coverage']['families_without_eligible_mission_drop_in_catalog_scan']) or 'nenhuma'} entre os níveis 1–50 para o party assumido."
        for profile, row in data["mission_recovery_sources_by_profile"].items()
    )
    lines.extend(["", "A lista acima mede apenas drops de missão. A ausência de drop de madeira/minério em algum party não significa ausência global: gathering de madeira/minério existe e a [simulação integrada financiada](integrated_funded_stage5_2026-10-29.md) conecta essa fonte ao estoque/custos. O relatório não inclui venda, desmontagem nem conclusão de masmorra.", ""])
    reach = data["building_resource_reachability"]
    lines.extend(["## Materiais exigidos por prédios e aliases reais", "",
                  reach["interpretation"], "",
                  "| Recurso usado no custo | Famílias de inventário aceitas | Custo-base de cristal em prédios ativos |",
                  "|---|---|---|"])
    for resource, aliases in reach["resource_inventory_family_aliases"].items():
        crystal_costs = sorted({row["base_crystals_cost"] for row in reach["active_seeded_building_base_costs"]})
        lines.append(f"| {resource} | {', '.join(aliases)} | {', '.join(map(str, crystal_costs)) if resource == 'crystals' else 'não se aplica'} |")
    market, salvage = data["market_route"], data["salvage_route"]
    lines.extend(["", "## Venda e desmontagem", "",
                  f"Mercado: precisa de {market['required_building']}, tem {market['slots_at_level_1']} vaga(s) e, no nível 1, bônus de preço {market['value_bonus_percent_at_level_1']}%. Unidade vendida = `{market['sale_unit_formula']}`. A venda exige item no inventário, aguardar o timer e coletar; não é caixa imediato.", "",
                  f"Desmontagem: precisa de {salvage['required_building']}; nível 1 custa {salvage['level_1_unit_gold_cost']} ouro por item e rende {salvage['yield_per_equipment_unit']}. Exige equipamento sem uso, espaço de desmontagem e tempo; por cobrar ouro, não garante saída de uma falta de caixa.", "",
                  "## Masmorras", "",
                  "O catálogo seedado lista candidatas abaixo. Todas continuam condicionadas a Exploradores 1, composição/nível legal, chance de sucesso e drops; a política financiada atual não compra Exploradores nem executa runs.", "",
                  "| Masmorra | Guilda/mercenário mínimo | Grupo | Sucesso base | Duração | Drops listados (chance-base) |",
                  "|---|---:|---:|---:|---:|---|"])
    for dungeon in data["dungeon_routes_catalog_candidates"]:
        drops = ", ".join(f"{drop['name']} {drop['chance_percent']}%" for drop in dungeon["drops"]) or "nenhum no recorte"
        lines.append(f"| {dungeon['name']} | {dungeon['required_guild_level']}/{dungeon['required_mercenary_level']} | {dungeon['party_size_min']}–{dungeon['party_size_max']} | {dungeon['success_base_percent']}% | {dungeon['duration_minutes']} min | {drops} |")
    lines.extend(["", "## Risco residual", "", data["hard_softlock_scope"], "",
                  "Limites adicionais:", ""])
    lines.extend(f"- {item}" for item in data["limits"])
    lines.extend(["", "## Reprodução", "", "```powershell",
                  ".venv\\Scripts\\python.exe scripts\\balance\\audit_stage5_recovery_routes.py",
                  "```", ""])
    return "\n".join(lines)


def main() -> None:
    with TemporaryDirectory(prefix="gim-stage5-recovery-") as temp_dir:
        engine = create_database_engine(f"sqlite:///{(Path(temp_dir) / 'stage5-recovery.sqlite3').as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with factory() as db:
                apply_initial_campaign_content(db)
                report = _audit(db)
        finally:
            engine.dispose()
    stem = ROOT / "reports" / "stage5_recovery_routes_2026-10-29"
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {stem.with_suffix('.json')}")
    print(f"Markdown: {stem.with_suffix('.md')}")


if __name__ == "__main__":
    main()
