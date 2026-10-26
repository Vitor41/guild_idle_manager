from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from random import Random

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.content import ContentSeedRun
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop
from app.models.mission import MissionTemplate
from app.services.prd3_dungeon_balance_service import (
    LEVEL_BANDS, PRD3_PACK_KEY, PRD3_VERSION, RARITY_LABELS, RARITY_ORDER,
    dungeon_identity,
)


GROUP_SCENARIOS = {"Fraco": -12, "Médio": 0, "Forte": 15}
PLAYER_PROFILES = {"Ativo": 6.0, "Híbrido": 2.0, "Casual/idle": 0.75}
TECHNICAL_NAME_RE = re.compile(r"(?:\b\d{1,4}\b|\d+-\d{2,4}$|(?:Masmorra|Chefe|Cripta|Caverna)\s+\d+)", re.I)


def _expected_rates(record: dict[str, object], chance_adjustment: int = 0) -> dict[str, float]:
    chance = max(5, min(95, int(record["chance"]) + chance_adjustment)) / 100
    hours = max(1, int(record["duration"])) / 3600
    expected_xp = int(record["xp"]) * (chance + (1 - chance) * 0.25)
    expected_gold = int(record["gold"]) * chance
    materials = 0.0
    equipment = 0.0
    loot_value = 0.0
    rarity_probabilities = {rarity: 0.0 for rarity in RARITY_ORDER}
    for drop in record.get("drops", []):
        quantity = (int(drop["min"]) + int(drop["max"])) / 2
        probability = chance * int(drop["chance"]) / 100
        if drop["type"] == "equipment":
            equipment += probability * quantity
            rarity_probabilities[str(drop["rarity"])] += probability
        else:
            materials += probability * quantity
        loot_value += probability * quantity * max(1, int(drop.get("value", 1)))
    result = {
        "success": chance, "xp_h": expected_xp / hours, "gold_h": expected_gold / hours,
        "materials_h": materials / hours, "equipment_h": equipment / hours,
        "loot_value_run": loot_value, "loot_value_h": loot_value / hours,
        "failure_rate": 1 - chance,
    }
    for threshold in ("rare", "epic", "legendary"):
        start = RARITY_ORDER.index(threshold)
        probability = sum(rarity_probabilities[rarity] for rarity in RARITY_ORDER[start:])
        result[f"hours_{threshold}_plus"] = hours / probability if probability else 0.0
    return result


def _live_catalog(db: Session) -> list[dict[str, object]]:
    templates = list(db.scalars(
        select(DungeonTemplate)
        .options(selectinload(DungeonTemplate.item_drops).selectinload(DungeonTemplateItemDrop.item_template))
        .where(DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type.in_(("dungeon", "boss")))
        .order_by(DungeonTemplate.level_band, DungeonTemplate.content_type, DungeonTemplate.recommended_level, DungeonTemplate.id)
    ))
    records = []
    for template in templates:
        identity = dungeon_identity(template)
        records.append({
            "id": template.id, "name": template.name, "active": True, "type": template.content_type,
            "band": template.level_band, "level": template.recommended_level, "duration": template.duration_seconds,
            "chance": template.base_success_chance, "xp": template.base_xp_reward, "gold": template.base_gold_reward,
            "power": template.required_total_power, "party": [template.min_party_size, template.max_party_size],
            "roles": [template.required_tank_count, template.required_support_count, template.required_damage_count],
            "role": identity["role"],
            "drops": [{
                "type": drop.item_template.item_type, "rarity": drop.item_template.rarity,
                "chance": drop.drop_chance, "min": drop.min_quantity, "max": drop.max_quantity,
                "value": drop.item_template.base_sell_value,
            } for drop in template.item_drops if drop.is_active],
        })
    return records


def _mission_comparison(db: Session, band: str) -> dict[str, object]:
    missions = list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.is_active.is_(True), MissionTemplate.level_band == band,
        MissionTemplate.mission_type != "long_idle",
    )))

    def rates(mission: MissionTemplate) -> tuple[float, float, float]:
        chance = mission.base_success_chance / 100
        hours = mission.duration_seconds / 3600
        xp_h = mission.base_xp_reward * (chance + (1 - chance) * 0.25) / hours
        gold_h = mission.base_gold_reward * chance / hours
        materials_h = sum(
            drop.drop_chance / 100 * (drop.min_quantity + drop.max_quantity) / 2 * chance / hours
            for drop in mission.item_drops if drop.is_active and drop.item_template.item_type != "equipment"
        )
        return xp_h, gold_h, materials_h

    normal = [mission for mission in missions if mission.mission_type != "gathering"]
    gathering = [mission for mission in missions if mission.mission_type == "gathering"]
    best_xp = max(normal, key=lambda mission: rates(mission)[0], default=None)
    best_gold = max(normal, key=lambda mission: rates(mission)[1], default=None)
    best_material = max(gathering, key=lambda mission: rates(mission)[2], default=None)
    return {
        "mission_xp_name": best_xp.name if best_xp else "-", "mission_xp_h": round(rates(best_xp)[0], 1) if best_xp else 0,
        "mission_gold_name": best_gold.name if best_gold else "-", "mission_gold_h": round(rates(best_gold)[1], 1) if best_gold else 0,
        "gathering_name": best_material.name if best_material else "-",
        "gathering_materials_h": round(rates(best_material)[2], 2) if best_material else 0,
    }


def _band_metrics(db: Session, catalog: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for band in LEVEL_BANDS:
        comparison = _mission_comparison(db, band)
        groups = {kind: [record for record in catalog if record["band"] == band and record["type"] == kind] for kind in ("dungeon", "boss")}
        row: dict[str, object] = {"band": band, **comparison}
        for kind, records in groups.items():
            prefix = "dungeon" if kind == "dungeon" else "boss"
            metrics = [(record, _expected_rates(record)) for record in records]
            row[f"{prefix}_count"] = len(records)
            for measure in ("xp_h", "gold_h", "materials_h", "equipment_h", "loot_value_h"):
                best = max(metrics, key=lambda pair: pair[1][measure], default=None)
                row[f"{prefix}_{measure}"] = round(best[1][measure], 2) if best else 0
                row[f"{prefix}_{measure}_name"] = best[0]["name"] if best else "-"
            row[f"{prefix}_success"] = round(sum(item[1]["success"] for item in metrics) / max(1, len(metrics)) * 100, 1)
        rows.append(row)
    return rows


def _rankings(catalog: list[dict[str, object]]) -> dict[str, dict[str, list[dict[str, object]]]]:
    result: dict[str, dict[str, list[dict[str, object]]]] = {}
    for band in LEVEL_BANDS:
        result[band] = {}
        for kind in ("dungeon", "boss"):
            records = [record for record in catalog if record["band"] == band and record["type"] == kind]
            for measure in ("xp_h", "gold_h", "loot_value_h"):
                ranked = sorted(records, key=lambda record: _expected_rates(record)[measure], reverse=True)[:3]
                result[band][f"{kind}_{measure}"] = [
                    {"name": record["name"], "value": round(_expected_rates(record)[measure], 2)} for record in ranked
                ]
    return result


def _redundancy(catalog: list[dict[str, object]]) -> dict[str, object]:
    signatures: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for record in catalog:
        signature = (
            record["type"], record["band"], record["duration"], record["chance"], record["xp"], record["gold"],
            tuple(record["party"]), record["power"], tuple(record["roles"]),
        )
        signatures[signature].append(record)
    groups = [records for records in signatures.values() if len(records) > 1]
    return {
        "equivalent_groups": len(groups),
        "equivalent_entries": sum(len(records) for records in groups),
        "technical_names": [record["name"] for record in catalog if TECHNICAL_NAME_RE.search(str(record["name"]))],
    }


def _simulate(catalog: list[dict[str, object]], executions: int = 1000) -> dict[str, dict[str, dict[str, int]]]:
    rng = Random(3067)
    result: dict[str, dict[str, dict[str, int]]] = {}
    for band in LEVEL_BANDS:
        result[band] = {}
        for kind in ("dungeon", "boss"):
            records = [record for record in catalog if record["band"] == band and record["type"] == kind]
            counts = Counter({rarity: 0 for rarity in RARITY_ORDER})
            successes = 0
            if records:
                for _ in range(executions):
                    record = records[rng.randrange(len(records))]
                    if rng.random() > int(record["chance"]) / 100:
                        continue
                    successes += 1
                    for drop in record.get("drops", []):
                        if drop["type"] == "equipment" and rng.random() <= int(drop["chance"]) / 100:
                            counts[str(drop["rarity"])] += 1
            result[band][kind] = {"successes": successes, **dict(counts)}
    return result


def _scenario_summary(catalog: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    result = {}
    for scenario, adjustment in GROUP_SCENARIOS.items():
        metrics = [_expected_rates(record, adjustment) for record in catalog]
        result[scenario] = {
            "success": round(sum(metric["success"] for metric in metrics) / max(1, len(metrics)) * 100, 1),
            "xp_h": round(sum(metric["xp_h"] for metric in metrics) / max(1, len(metrics)), 1),
            "gold_h": round(sum(metric["gold_h"] for metric in metrics) / max(1, len(metrics)), 1),
        }
    return result


def build_prd3_qa_report(db: Session) -> dict[str, object]:
    marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == PRD3_PACK_KEY, ContentSeedRun.version == PRD3_VERSION,
    ))
    balance = json.loads(marker.report_json) if marker else {}
    catalog = _live_catalog(db)
    before_catalog = balance.get("before_catalog", [])
    return {
        "balance": balance, "catalog": catalog,
        "bands": _band_metrics(db, catalog), "rankings": _rankings(catalog),
        "redundancy_before": _redundancy(before_catalog), "redundancy_after": _redundancy(catalog),
        "scenarios": _scenario_summary(catalog), "profiles": PLAYER_PROFILES,
        "simulation_runs": 1000, "drops_before": _simulate(before_catalog, 1000),
        "drops_after": _simulate(catalog, 1000),
    }


def render_prd3_markdown(report: dict[str, object]) -> str:
    balance = report["balance"]
    before = balance.get("before", {"active_total": 0, "counts": {}})
    after = balance.get("after", {"active_total": len(report["catalog"]), "counts": {}})
    lines = [
        "# Relatório QA de Masmorras e Chefes", "", "## Sumário executivo", "",
        f"O catálogo ativo foi reduzido de **{before.get('active_total', 0)}** para **{after.get('active_total', 0)}** desafios, preservando históricos e desativando excedentes de forma não destrutiva.",
        "Masmorras agora se dividem por função (XP, ouro, equipamento, material, risco e transição). Chefes concentram raridades altas, composição e risco, sem dominar simultaneamente o farm básico.",
        "", "## Quantidade antes/depois", "",
        "| Faixa | Masmorras antes | Masmorras depois | Chefes antes | Chefes depois |",
        "|---|---:|---:|---:|---:|",
    ]
    for band in LEVEL_BANDS:
        lines.append(
            f"| {band} | {before.get('counts', {}).get('dungeon', {}).get(band, 0)} | {after.get('counts', {}).get('dungeon', {}).get(band, 0)} | "
            f"{before.get('counts', {}).get('boss', {}).get(band, 0)} | {after.get('counts', {}).get('boss', {}).get(band, 0)} |"
        )
    lines.extend(["", "## Eficiência por faixa", "", "| Faixa | Masm. | Chefes | XP/h missão | XP/h masmorra | XP/h chefe | Ouro/h missão | Ouro/h masmorra | Ouro/h chefe | Mat./h coleta | Mat./h masmorra | Loot/h masmorra | Loot/h chefe |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in report["bands"]:
        lines.append(
            f"| {row['band']} | {row['dungeon_count']} | {row['boss_count']} | {row['mission_xp_h']} | {row['dungeon_xp_h']} | {row['boss_xp_h']} | "
            f"{row['mission_gold_h']} | {row['dungeon_gold_h']} | {row['boss_gold_h']} | {row['gathering_materials_h']} | {row['dungeon_materials_h']} | {row['dungeon_loot_value_h']} | {row['boss_loot_value_h']} |"
        )
    lines.extend(["", "## Grupos simulados", "", "| Força do grupo | Sucesso médio | XP/h médio | Ouro/h médio |", "|---|---:|---:|---:|"])
    for scenario, values in report["scenarios"].items():
        lines.append(f"| {scenario} | {values['success']}% | {values['xp_h']} | {values['gold_h']} |")
    lines.extend(["", "Perfis de uso considerados: **Ativo** (6h/dia), **Híbrido** (2h/dia) e **Casual/idle** (0,75h/dia). A duração dos desafios limita naturalmente a quantidade diária sem alterar a recompensa offline.", "", "## Rankings de eficiência", ""])
    for band in LEVEL_BANDS:
        rank = report["rankings"][band]
        lines.append(f"### Nível {band}")
        for kind, label in (("dungeon", "Masmorras"), ("boss", "Chefes")):
            for measure, measure_label in (("xp_h", "XP/h"), ("gold_h", "ouro/h"), ("loot_value_h", "loot/h")):
                entries = ", ".join(f"{item['name']} ({item['value']})" for item in rank[f"{kind}_{measure}"])
                lines.append(f"- **{label} por {measure_label}:** {entries or '-'}")
        lines.append("")
    lines.extend(["## Distribuição de loot simulada", "", f"Simulação determinística de {report['simulation_runs']} execuções por tipo e faixa após os ajustes.", "", "| Faixa | Tipo | Sucessos | Comum | Incomum | Raro | Épico | Lendário | Mítico |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"])
    for band in LEVEL_BANDS:
        for kind, label in (("dungeon", "Masmorra"), ("boss", "Chefe")):
            values = report["drops_after"][band][kind]
            lines.append(f"| {band} | {label} | {values['successes']} | " + " | ".join(str(values[rarity]) for rarity in RARITY_ORDER) + " |")
    before_red = report["redundancy_before"]
    after_red = report["redundancy_after"]
    lines.extend([
        "", "## Análise de redundância", "",
        f"- Grupos funcionalmente equivalentes: **{before_red['equivalent_groups']} antes** e **{after_red['equivalent_groups']} depois**.",
        f"- Entradas em grupos equivalentes: **{before_red['equivalent_entries']} antes** e **{after_red['equivalent_entries']} depois**.",
        f"- Nomes técnicos/sequenciais ativos depois: **{len(after_red['technical_names'])}**.",
        f"- Conteúdos desativados: **{len(balance.get('deactivated', []))}**; conteúdos curados: **{len(balance.get('kept', []))}**.",
        "", "## Conteúdos mantidos e alterados", "",
    ])
    role_counts = Counter(entry.get("role", "Sem função") for entry in balance.get("kept", []))
    for role, count in sorted(role_counts.items()):
        lines.append(f"- **{role}:** {count} desafios.")
    lines.extend(["", "## Conteúdos desativados", ""])
    by_band_type = Counter((entry["band"], entry["type"]) for entry in balance.get("deactivated", []))
    for (band, kind), count in sorted(by_band_type.items()):
        lines.append(f"- Nível {band}: {count} {'Chefes' if kind == 'boss' else 'Masmorras'} redundantes desativados.")
    lines.extend([
        "", "## Gargalos e validações", "",
        "- Falhas concedem somente 25% do XP e nenhum ouro; o risco continua relevante.",
        "- Masmorras têm melhor expectativa de equipamento intermediário; Chefes elevam raro+ e mantêm mítico raro.",
        "- Missões continuam como referência de XP/ouro básico e Coletas seguem como rota previsível de materiais.",
        "- O poder, a composição, as habilidades, a raridade e os equipamentos do grupo continuam alterando a chance final no backend.",
        "- Uma Masmorra ou Chefe em exploração permanece fechado para outro grupo da mesma guilda até a coleta.",
        "", "## Recomendações finais", "",
        "- Acompanhar telemetria real por desafio antes de uma nova redução do catálogo.",
        "- Ajustar pontualmente desafios dominantes sem reexecutar o pacote versionado sobre edições administrativas.",
        "- Reservar itens exclusivos de Chefe para uma evolução futura com regras próprias de coleção.",
        "", "## Pendências futuras", "",
        "- Telemetria agregada de escolha, abandono e repetição ainda não faz parte deste MVP.",
        "- Itens especiais exclusivos por Chefe permanecem candidatos a conteúdo futuro; o pacote atual usa raridade e valor esperado.",
        "",
    ])
    return "\n".join(lines)
