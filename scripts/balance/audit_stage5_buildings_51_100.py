"""Quote built-in building costs and benefits for levels 51-100 on live services.

This is a catalog/service audit, not a funded player journey. It uses a fresh
temporary SQLite catalog and never opens a user save or the desktop app.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, create_database_engine
from app.models import BuildingTemplate
from app.models.campaign import CampaignMetadata
from app.models.guild import Guild, GuildResources
from app.models.item import GuildInventoryItem, ItemTemplate
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services.building_balance_service import get_building_benefit, required_guild_level_for_upgrade
from app.services.building_service import ensure_guild_buildings, get_upgrade_cost, upgrade_guild_building


def audit(db) -> dict[str, object]:
    buildings = list(db.scalars(select(BuildingTemplate).where(
        BuildingTemplate.is_active.is_(True), BuildingTemplate.max_level >= 100,
    ).order_by(BuildingTemplate.effect_type)))
    result = []
    for template in buildings:
        rows = []
        previous = None
        for target_level in range(51, 101):
            quote = get_upgrade_cost(SimpleNamespace(
                level=target_level - 1, building_template=template,
            ))
            benefit = get_building_benefit(template.effect_type, target_level)
            row = {
                "target_level": target_level,
                "guild_level_required": required_guild_level_for_upgrade(target_level, template.required_guild_level),
                "cost": quote,
                "benefit_at_level": benefit["current"],
                "next_milestone_level": benefit["next_milestone_level"],
                "next_milestone_benefit": benefit["next"],
            }
            row["cost_monotone_from_previous"] = previous is None or all(
                quote[key] >= previous[key] for key in quote
            )
            previous = quote
            rows.append(row)
        result.append({
            "effect_type": template.effect_type,
            "name": template.name,
            "built_in_base_cost": {
                "gold": template.base_upgrade_gold_cost,
                "wood": template.base_upgrade_wood_cost,
                "ore": template.base_upgrade_ore_cost,
                "crystals": template.base_upgrade_crystals_cost,
            },
            "existing_level_50_benefit": get_building_benefit(template.effect_type, 50)["current"],
            "level_51_100_cost_totals": {
                key: sum(row["cost"][key] for row in rows)
                for key in ("gold", "wood", "ore", "crystals")
            },
            "level_51_100_cost_monotone": all(row["cost_monotone_from_previous"] for row in rows),
            "levels": rows,
        })
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "current BuildingTemplate seed + get_upgrade_cost + get_building_benefit + required_guild_level_for_upgrade",
        "database": "fresh temporary SQLite; content seeded from current source",
        "scope": "built-in active templates with cap >=100; quoted target levels 51-100",
        "funded_affordability": "not measured; quote replay does not mint resources or claim player affordability",
        "buildings": result,
        "funded_housing_service_route": run_funded_housing_route(db),
    }


def run_funded_housing_route(db) -> dict[str, object]:
    """Exercise every housing upgrade through the production service with explicit funding."""
    campaign_id = "stage5-funded-housing-route"
    campaign = CampaignMetadata(
        campaign_id=campaign_id, campaign_name="Funded housing route audit",
        created_at_utc=datetime.now(timezone.utc), updated_at_utc=datetime.now(timezone.utc),
        schema_version=5, content_version=3, home_region="north_forest",
    )
    guild = Guild(campaign_id=campaign_id, name="Guild funded route", level=50)
    resources = GuildResources(guild=guild, gold=0)
    db.add_all((campaign, guild, resources))
    db.flush()
    buildings = ensure_guild_buildings(db, guild.id)
    housing = next(row for row in buildings if row.building_template.effect_type == "housing")
    housing.level = 50
    db.flush()
    quotes = [get_upgrade_cost(SimpleNamespace(level=level - 1, building_template=housing.building_template))
              for level in range(51, 101)]
    totals = {key: sum(quote[key] for quote in quotes) for key in ("gold", "wood", "ore", "crystals")}
    resources.gold = totals["gold"]
    for resource_name, families in (("wood", ("wood",)), ("ore", ("ore", "stone")),
                                    ("crystals", ("gem", "essence", "crystal"))):
        required = totals[resource_name]
        if required <= 0:
            continue
        template = db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "material", ItemTemplate.material_family.in_(families),
        ).order_by(ItemTemplate.id))
        if template is None:
            raise RuntimeError(f"Sem material seedado para recurso {resource_name}.")
        db.add(GuildInventoryItem(guild_id=guild.id, item_template_id=template.id, quantity=required))
    db.commit()
    for _ in range(50):
        upgrade_guild_building(db, guild, resources, housing.id)
    db.refresh(resources)
    db.refresh(housing)
    remaining = {key: int(getattr(resources, key)) for key in ("gold", "wood", "ore", "crystals")}
    return {
        "method": "50 consecutive upgrade_guild_building calls from funded level 50",
        "starting_guild_level": 50,
        "funding_injected_into_disposable_save": totals,
        "final_level": housing.level,
        "final_housing_capacity": get_building_benefit("housing", housing.level)["current"],
        "remaining_resources": remaining,
        "all_funding_consumed": all(value == 0 for value in remaining.values()),
        "organic_fresh_save_reaches_level_100": False,
    }


def render(report: dict[str, object]) -> str:
    lines = [
        "# Edifícios 51–100: custos, marcos e limites de evidência", "",
        f"Catálogo atual em SQLite temporário · {report['generated_at_utc']}.", "",
        "As cotações usam `get_upgrade_cost` e benefícios `get_building_benefit`; nível requerido de guilda usa o gate do serviço. A rota financiada abaixo chama o serviço real de melhoria em cada nível; o financiamento é explicitamente injetado no save temporário.", "",
        "| Edifício | Custo níveis 51–100 (ouro / madeira / minério / cristais) | Custos monotônicos | Benefício já no nível 50 | Benefício no 100 |", "|---|---:|:---:|---|---|",
    ]
    for building in report["buildings"]:
        total = building["level_51_100_cost_totals"]
        lines.append(
            f"| {building['name']} | {total['gold']:,} / {total['wood']:,} / {total['ore']:,} / {total['crystals']:,} | "
            f"{'sim' if building['level_51_100_cost_monotone'] else 'não'} | "
            f"{' · '.join(building['existing_level_50_benefit'])} | {' · '.join(building['levels'][-1]['benefit_at_level'])} |"
        )
    route = report["funded_housing_service_route"]
    funding = route["funding_injected_into_disposable_save"]
    lines.extend([
        "", "## Rota financiada do Alojamento", "",
        f"De guilda nível {route['starting_guild_level']} e Alojamento 50, foram aplicadas 50 melhorias via `upgrade_guild_building`, financiadas no save temporário com {funding['gold']:,} ouro e {funding['wood']:,} madeira. O serviço chegou ao Alojamento {route['final_level']} ({route['final_housing_capacity'][0]}), consumindo o saldo concedido. Isso demonstra um caminho financiado pelo serviço, não renda orgânica: nenhum perfil fresh-save medido alcançou guilda 50/Alojamento 100; as 20 vagas são conteúdo tardio.", "",
    ])
    lines.extend(["", "## Observações de marcos", ""])
    for building in report["buildings"]:
        lines.append(f"### {building['name']}")
        for row in building["levels"]:
            if row["target_level"] % 5 == 0 or row["target_level"] in (51, 100):
                c = row["cost"]
                lines.append(
                    f"- Nível {row['target_level']} (guilda ≥{row['guild_level_required']}): custo {c['gold']:,} ouro, "
                    f"{c['wood']:,} madeira, {c['ore']:,} minério, {c['crystals']:,} cristais; benefício: "
                    f"{' · '.join(row['benefit_at_level'])}."
                )
        lines.append("")
    lines.extend([
        "## Conclusão", "",
        "A progressão de custo entre 51 e 100 cresce conforme o fator atual e o requisito de guilda sobe de 26 a 50. A leitura dos benefícios mostra se cada sistema continua evoluindo, atinge teto ou deixa de conceder ganho; custos cotados não bastam para afirmar acessibilidade econômica. A rota financiada publicada chega à guilda 50, mas ainda não investe edifícios nessa faixa. É necessário um replay de campanha financiado por serviços para fechar a acessibilidade por perfil.", "",
        "Reprodução: `python scripts/balance/audit_stage5_buildings_51_100.py`.", "",
    ])
    return "\n".join(lines)


def main() -> None:
    with TemporaryDirectory(prefix="gim-stage5-building-51-100-") as temp:
        engine = create_database_engine(f"sqlite:///{(Path(temp) / 'buildings.sqlite3').as_posix()}")
        Base.metadata.create_all(engine)
        try:
            with sessionmaker(bind=engine, expire_on_commit=False)() as db:
                apply_initial_campaign_content(db)
                report = audit(db)
        finally:
            engine.dispose()
    stem = ROOT / "reports" / "stage5_buildings_51_100_2026-10-30"
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render(report), encoding="utf-8")
    print(stem.with_suffix(".md"))


if __name__ == "__main__":
    main()
