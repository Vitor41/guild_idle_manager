from __future__ import annotations

from collections import defaultdict
from math import ceil, floor, prod
from random import Random

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop
from app.services.balance_service import power_success_adjustment
from app.services.prd3_dungeon_balance_service import LEVEL_BANDS, RARITY_ORDER


SCENARIOS = {
    "Fraco": {"power_ratio": 0.65, "class": 0, "rarity": (0, 0, 0, 0, 0, 0, 0, 0), "skill": 0, "synergy": 0, "scouts_success": 0, "drop_bonus": 0},
    "No nível": {"power_ratio": 1.0, "class": 2, "rarity": (0, 0, 2, 3, 5, 8, 10, 12), "skill": 2, "synergy": 4, "scouts_success": 0, "drop_bonus": 10},
    "Forte": {"power_ratio": 1.5, "class": 6, "rarity": (0, 0, 4, 6, 10, 14, 16, 20), "skill": 8, "synergy": 6, "scouts_success": 2, "drop_bonus": 32},
    "Máximo": {"power_ratio": 2.0, "class": 8, "rarity": (0, 0, 6, 9, 15, 20, 20, 20), "skill": 20, "synergy": 6, "scouts_success": 2, "drop_bonus": 55},
}

BOSS_COMPLETION_CAPS = (80, 72, 65, 58, 50, 45, 40, 35)
DUNGEON_COMPLETION_CAPS = (92, 90, 88, 85, 82, 80, 78, 75)
BOSS_EQUIPMENT_ROLL = (48, 44, 40, 34, 28, 22, 16, 10)
DUNGEON_EQUIPMENT_ROLL = (38, 36, 34, 31, 28, 25, 23, 20)
BOSS_RARE_PLUS_SHARE = (5, 12, 25, 40, 55, 68, 78, 88)
DUNGEON_RARE_PLUS_SHARE = (2, 6, 12, 20, 32, 45, 58, 70)
BOSS_MYTHIC_SHARE = (0, 0, 0, 0, 0.5, 1, 2, 3)
DUNGEON_MYTHIC_SHARE = (0, 0, 0, 0, 0, 0, 0.25, 0.75)
BOSS_CANDIDATES = (4, 5, 6, 7, 8, 9, 10, 12)
DUNGEON_CANDIDATES_BY_DIFFICULTY = {"normal": 2, "hard": 3, "heroic": 4, "legendary": 5, "elite": 5}


def _catalog(db: Session) -> list[dict[str, object]]:
    templates = list(db.scalars(
        select(DungeonTemplate)
        .options(selectinload(DungeonTemplate.item_drops).selectinload(DungeonTemplateItemDrop.item_template))
        .where(DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type.in_(("dungeon", "boss")))
        .order_by(DungeonTemplate.level_band, DungeonTemplate.content_type, DungeonTemplate.recommended_level, DungeonTemplate.id)
    ))
    return [{
        "id": template.id, "name": template.name, "type": template.content_type,
        "band": template.level_band, "band_index": LEVEL_BANDS.index(template.level_band),
        "level": template.recommended_level, "difficulty": template.difficulty,
        "duration": template.duration_seconds, "base_chance": template.base_success_chance,
        "power": template.required_total_power,
        "roles": template.required_tank_count + template.required_support_count + template.required_damage_count,
        "drops": [{
            "type": drop.item_template.item_type, "rarity": drop.item_template.rarity,
            "base_chance": drop.drop_chance,
        } for drop in template.item_drops if drop.is_active],
    } for template in templates]


def _completion_chance(record: dict[str, object], scenario_name: str, proposed: bool) -> float:
    scenario = SCENARIOS[scenario_name]
    band_index = int(record["band_index"])
    recommended_power = max(1, int(record["power"]))
    party_power = floor(recommended_power * float(scenario["power_ratio"]))
    power_bonus = power_success_adjustment(party_power, recommended_power)
    synergy = int(scenario["synergy"]) if int(record["roles"]) else 0
    chance = (
        int(record["base_chance"]) + power_bonus + int(scenario["class"])
        + int(scenario["rarity"][band_index]) + int(scenario["skill"])
        + synergy + int(scenario["scouts_success"])
    )
    chance = max(5, min(95, chance))
    if proposed:
        caps = BOSS_COMPLETION_CAPS if record["type"] == "boss" else DUNGEON_COMPLETION_CAPS
        chance = min(chance, caps[band_index])
    return chance / 100


def _current_equipment_probabilities(record: dict[str, object], scenario_name: str) -> dict[str, float]:
    completion = _completion_chance(record, scenario_name, proposed=False)
    bonus = int(SCENARIOS[scenario_name]["drop_bonus"])
    equipment = [drop for drop in record["drops"] if drop["type"] == "equipment"]
    chances = [min(100, int(drop["base_chance"]) + bonus) / 100 for drop in equipment]
    any_conditional = 1 - prod(1 - chance for chance in chances) if chances else 0
    rare_conditional = 1 - prod(
        1 - chance for chance, drop in zip(chances, equipment)
        if RARITY_ORDER.index(str(drop["rarity"])) >= RARITY_ORDER.index("rare")
    ) if equipment else 0
    mythic_conditional = 1 - prod(
        1 - chance for chance, drop in zip(chances, equipment) if drop["rarity"] == "mythic"
    ) if equipment else 0
    return {
        "completion": completion,
        "any_equipment": completion * any_conditional,
        "rare_plus": completion * rare_conditional,
        "mythic": completion * mythic_conditional,
    }


def _proposed_equipment_probabilities(record: dict[str, object], scenario_name: str) -> dict[str, float]:
    band_index = int(record["band_index"])
    completion = _completion_chance(record, scenario_name, proposed=True)
    base_rolls = BOSS_EQUIPMENT_ROLL if record["type"] == "boss" else DUNGEON_EQUIPMENT_ROLL
    bonus_multiplier = 1 + int(SCENARIOS[scenario_name]["drop_bonus"]) / 100
    conditional_roll = min(1, base_rolls[band_index] / 100 * bonus_multiplier)
    rare_shares = BOSS_RARE_PLUS_SHARE if record["type"] == "boss" else DUNGEON_RARE_PLUS_SHARE
    mythic_shares = BOSS_MYTHIC_SHARE if record["type"] == "boss" else DUNGEON_MYTHIC_SHARE
    return {
        "completion": completion,
        "any_equipment": completion * conditional_roll,
        "rare_plus": completion * conditional_roll * rare_shares[band_index] / 100,
        "mythic": completion * conditional_roll * mythic_shares[band_index] / 100,
    }


def _average_metrics(records: list[dict[str, object]], scenario_name: str, proposed: bool) -> dict[str, float]:
    calculator = _proposed_equipment_probabilities if proposed else _current_equipment_probabilities
    values = [calculator(record, scenario_name) for record in records]
    if not values:
        return {key: 0 for key in ("completion", "any_equipment", "rare_plus", "mythic", "hours_any", "hours_rare", "hours_mythic")}
    average_duration_hours = sum(int(record["duration"]) for record in records) / len(records) / 3600
    result = {key: sum(value[key] for value in values) / len(values) for key in ("completion", "any_equipment", "rare_plus", "mythic")}
    for source, target in (("any_equipment", "hours_any"), ("rare_plus", "hours_rare"), ("mythic", "hours_mythic")):
        result[target] = average_duration_hours / result[source] if result[source] else 0
    return result


def _simulate(records: list[dict[str, object]], scenario_name: str, proposed: bool, attempts: int, seed: int) -> dict[str, int]:
    rng = Random(seed)
    calculator = _proposed_equipment_probabilities if proposed else _current_equipment_probabilities
    totals = {"attempts": attempts, "successes": 0, "equipment": 0, "rare_plus": 0, "mythic": 0}
    if not records:
        return totals
    for _ in range(attempts):
        record = records[rng.randrange(len(records))]
        probabilities = calculator(record, scenario_name)
        totals["successes"] += int(rng.random() < probabilities["completion"])
        equipment_roll = rng.random()
        totals["equipment"] += int(equipment_roll < probabilities["any_equipment"])
        totals["rare_plus"] += int(equipment_roll < probabilities["rare_plus"])
        totals["mythic"] += int(equipment_roll < probabilities["mythic"])
    return totals


def build_dungeon_balance_study(db: Session, attempts: int = 100_000) -> dict[str, object]:
    catalog = _catalog(db)
    bands = []
    simulations: dict[str, object] = {}
    for band_index, band in enumerate(LEVEL_BANDS):
        row: dict[str, object] = {"band": band}
        simulations[band] = {}
        for content_type in ("dungeon", "boss"):
            records = [record for record in catalog if record["band"] == band and record["type"] == content_type]
            prefix = "dungeon" if content_type == "dungeon" else "boss"
            equipment_counts = [sum(drop["type"] == "equipment" for drop in record["drops"]) for record in records]
            material_counts = [sum(drop["type"] != "equipment" for drop in record["drops"]) for record in records]
            row[f"{prefix}_count"] = len(records)
            row[f"{prefix}_equipment_candidates_current"] = round(sum(equipment_counts) / max(1, len(equipment_counts)), 1)
            row[f"{prefix}_material_candidates_current"] = round(sum(material_counts) / max(1, len(material_counts)), 1)
            if content_type == "boss":
                row[f"{prefix}_equipment_candidates_proposed"] = BOSS_CANDIDATES[band_index]
            else:
                row[f"{prefix}_equipment_candidates_proposed"] = round(sum(
                    DUNGEON_CANDIDATES_BY_DIFFICULTY.get(str(record["difficulty"]), 2) for record in records
                ) / max(1, len(records)), 1)
            row[f"{prefix}_current"] = {name: _average_metrics(records, name, False) for name in SCENARIOS}
            row[f"{prefix}_proposed"] = {name: _average_metrics(records, name, True) for name in SCENARIOS}
            simulations[band][content_type] = {
                model: {
                    scenario: _simulate(records, scenario, model == "proposed", attempts, 9100 + band_index * 100 + len(scenario) + (1 if content_type == "boss" else 0))
                    for scenario in SCENARIOS
                }
                for model in ("current", "proposed")
            }
        bands.append(row)
    return {"attempts_per_case": attempts, "bands": bands, "simulations": simulations}


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_dungeon_balance_study(report: dict[str, object]) -> str:
    lines = [
        "# Estudo de Balanceamento: Masmorras e Chefes", "",
        "## Escopo e decisão pendente", "",
        "Este documento é **somente um estudo**. Nenhuma recomendação de chance ou loot foi aplicada.",
        "A única alteração efetiva deste pacote foi liberar o Chefe recomendado para nível 1 de requisitos rígidos de formação e equipamento.",
        "", "## Diagnóstico executivo", "",
        "- Masmorras e Chefes ativos possuem, em média, apenas **1 equipamento e 1 material possíveis** por card.",
        "- O sistema atual soma bônus de drop em pontos percentuais: Ferreiro +25, habilidades +20 e Exploradores +10, totalizando até **+55 p.p.**.",
        "- Um drop Mítico base de 3% pode chegar a 58% após uma vitória; isto torna bônus de endgame desproporcionais.",
        "- A chance de conclusão também pode receber Poder +15, Classe +8, Raridade +20, Habilidades +20, Sinergia +6 e Exploradores +2. Chefes tardios podem atingir o teto global de 95%.",
        "- Adicionar várias linhas de drop ao modelo atual faria rolagens independentes e permitiria múltiplos equipamentos na mesma coleta.",
        "", "## Modelo recomendado para análise", "",
        "1. Manter vários equipamentos visíveis como **pool de possibilidades**.",
        "2. Após uma vitória, realizar uma única rolagem para decidir se haverá equipamento.",
        "3. Se houver, escolher no máximo um equipamento do pool por pesos de raridade.",
        "4. Manter materiais em rolagens separadas.",
        "5. Aplicar bônus de drop como multiplicador percentual, não como pontos percentuais: `chance_base × (1 + bônus/100)`.",
        "6. Aplicar teto de conclusão específico para Chefes, decrescente por faixa.",
        "", "## Parâmetros simulados no cenário recomendado", "",
        "| Faixa | Teto Masmorra | Teto Chefe | Pool Masmorra médio | Pool Chefe | Roll equip. Masmorra | Roll equip. Chefe | Raro+ no pool Chefe | Mítico no pool Chefe |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(report["bands"]):
        lines.append(
            f"| {row['band']} | {DUNGEON_COMPLETION_CAPS[index]}% | {BOSS_COMPLETION_CAPS[index]}% | "
            f"{row['dungeon_equipment_candidates_proposed']} | {row['boss_equipment_candidates_proposed']} | "
            f"{DUNGEON_EQUIPMENT_ROLL[index]}% | {BOSS_EQUIPMENT_ROLL[index]}% | "
            f"{BOSS_RARE_PLUS_SHARE[index]}% | {BOSS_MYTHIC_SHARE[index]}% |"
        )
    lines.extend(["", "## Estado atual por faixa", "", "| Faixa | Masmorras | Chefes | Equip. possíveis/Masmorra | Equip. possíveis/Chefe | Materiais/Masmorra | Materiais/Chefe |", "|---|---:|---:|---:|---:|---:|---:|"])
    for row in report["bands"]:
        lines.append(
            f"| {row['band']} | {row['dungeon_count']} | {row['boss_count']} | "
            f"{row['dungeon_equipment_candidates_current']} | {row['boss_equipment_candidates_current']} | "
            f"{row['dungeon_material_candidates_current']} | {row['boss_material_candidates_current']} |"
        )
    for scenario in SCENARIOS:
        lines.extend(["", f"## Comparação: grupo {scenario}", "", "| Faixa | Conclusão atual Masm. | Conclusão prop. Masm. | Equip./tentativa atual | Equip./tentativa prop. | Conclusão atual Chefe | Conclusão prop. Chefe | Equip./tentativa atual Chefe | Equip./tentativa prop. Chefe | Mítico prop. Chefe |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
        for row in report["bands"]:
            dc, dp = row["dungeon_current"][scenario], row["dungeon_proposed"][scenario]
            bc, bp = row["boss_current"][scenario], row["boss_proposed"][scenario]
            lines.append(
                f"| {row['band']} | {_percent(dc['completion'])} | {_percent(dp['completion'])} | {_percent(dc['any_equipment'])} | {_percent(dp['any_equipment'])} | "
                f"{_percent(bc['completion'])} | {_percent(bp['completion'])} | {_percent(bc['any_equipment'])} | {_percent(bp['any_equipment'])} | {_percent(bp['mythic'])} |"
            )
    attempts_label = f"{report['attempts_per_case']:,}".replace(",", ".")
    lines.extend(["", "## Simulação Monte Carlo", "", f"Foram executadas **{attempts_label} tentativas por faixa, tipo de conteúdo, força de grupo e modelo**.", "A tabela abaixo resume o cenário Máximo, onde o risco de banalização é maior.", "", "| Faixa | Modelo | Sucessos Chefes | Equipamentos | Raro+ | Míticos | Tentativas por Mítico |", "|---|---|---:|---:|---:|---:|---:|"])
    for band in LEVEL_BANDS:
        for model, label in (("current", "Atual"), ("proposed", "Recomendado")):
            values = report["simulations"][band]["boss"][model]["Máximo"]
            per_mythic = ceil(values["attempts"] / values["mythic"]) if values["mythic"] else "—"
            lines.append(f"| {band} | {label} | {values['successes']} | {values['equipment']} | {values['rare_plus']} | {values['mythic']} | {per_mythic} |")
    lines.extend([
        "", "## Leitura de produto", "",
        "- **Missões:** fonte básica, normalmente 1 material + 1 equipamento possível.",
        "- **Masmorras:** maior variedade e frequência de equipamento intermediário; dificuldade aumenta o tamanho do pool.",
        "- **Chefes:** maior variedade e qualidade, mas conclusão e rolagem de equipamento diminuem fortemente no late game.",
        "- Um Chefe pode ser mais vantajoso para buscar um item forte sem ser a melhor fonte de equipamentos por hora.",
        "- O Chefe nível 1 funciona como apresentação da mecânica. O Chefe nível 16 mantém composição, poder e equipamento obrigatórios.",
        "", "## Decisões sugeridas para aprovação", "",
        "1. Aprovar ou ajustar os tetos de conclusão de Chefes por faixa.",
        "2. Aprovar o pool com no máximo um equipamento por vitória.",
        "3. Aprovar bônus de drop multiplicativos em vez de aditivos.",
        "4. Definir se Chefes devem entregar materiais garantidos ou apenas com chance alta.",
        "5. Definir os pesos exatos de Raro, Épico, Lendário e Mítico por faixa.",
        "", "## Alteração efetivamente aplicada", "",
        "- Chefe recomendado para nível 1: grupo 1–5, sem papéis obrigatórios, sem Tier obrigatório e sem bloqueio rígido por Poder.",
        "- Poder 60 permanece como referência para o cálculo de chance.",
        "- Chefe recomendado para nível 16 não foi alterado.",
        "- Nenhuma chance, recompensa ou tabela de loot foi modificada.", "",
    ])
    return "\n".join(lines)
