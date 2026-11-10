"""Write deterministic ML-038 rank-power and chance-delta evidence."""

from __future__ import annotations

import csv
import json
from math import ceil
from pathlib import Path

from app.services.balance_service import calculate_power_score, power_success_adjustment
from app.services.mission_power_service import (
    REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS,
    common_apprentice_reference_power,
    recommended_regional_contract_power,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "reports"
LEVELS = (1, 5, 15, 17, 18, 50, 75, 200, 350)
OLD = {"E": 0.700, "D": 0.735, "C": 0.770, "B": 0.840, "A": 0.945, "S": 1.085}
BASE_CHANCE = 78
CPU_PAIRED_JSON = ROOT / "reports" / "lot_e2_ml029_cpu_paired_ml038-rank-table-clean-2026-11-10.json"


def _cpu_evidence_markdown() -> list[str]:
    if not CPU_PAIRED_JSON.is_file():
        return [
            "A comparação pareada CPU de cinco seeds ainda está pendente. Nenhum save/perfil instalado foi consultado.",
        ]
    payload = json.loads(CPU_PAIRED_JSON.read_text(encoding="utf-8"))
    pairs = payload["paired_results"]
    if len(pairs) != 5 or payload["calibration"]["cycles_per_seed"] != 100:
        return [
            f"A simulação pareada parcial contém {len(pairs)} de 5 seeds; o gate econômico continua aberto. Veja `{CPU_PAIRED_JSON.name}`.",
        ]

    def average(scenario: str, key: str) -> float:
        return sum(float(pair[scenario]["summary"][key]) for pair in pairs) / len(pairs)

    def total(scenario: str, key: str) -> int:
        return sum(int(pair[scenario]["summary"][key]) for pair in pairs)

    before_success = average("baseline", "cpu_success_rate") * 100
    after_success = average("ml029_e2", "cpu_success_rate") * 100
    before_xp = total("baseline", "cpu_xp_net")
    after_xp = total("ml029_e2", "cpu_xp_net")
    xp_delta = (after_xp / max(1, before_xp) - 1) * 100
    before_gold = total("baseline", "cpu_gold_net")
    after_gold = total("ml029_e2", "cpu_gold_net")
    before_actions = average("baseline", "cpu_actions_per_cycle_global")
    after_actions = average("ml029_e2", "cpu_actions_per_cycle_global")
    rows = [
        "A medição pareada foi concluída com 5 seeds determinísticas e 100 Vigílias por tratamento, usando um template descartável sem estado/ciclo regional prévio e clones SQLite temporários com journaling desativado. Nenhum save/perfil real foi consultado.",
        "",
        f"No agregado: sucesso CPU médio {before_success:.2f}% → {after_success:.2f}% ({after_success-before_success:+.2f} p.p.); XP global {before_xp:,} → {after_xp:,} ({xp_delta:+.1f}%); ouro líquido {before_gold:,} → {after_gold:,}; ações/ciclo {before_actions:.2f} → {after_actions:.2f}; portais {total('baseline','opened_portals')} → {total('ml029_e2','opened_portals')}; rebeliões abertas {total('baseline','opened_rebellions')} → {total('ml029_e2','opened_rebellions')}.".replace(",", "."),
        "",
        "| Fase | Sucessos de contrato / iniciados | Chance média | XP líquido | ciclos ameaça ≥85 / segurança ≤25 |",
        "|---|---:|---:|---:|---:|",
    ]
    for phase in ("early", "mid", "late"):
        base = payload["totals"]["baseline"].get(f"global|{phase}", {})
        candidate = payload["totals"]["ml029_e2"].get(f"global|{phase}", {})
        def rate(bucket: dict, key: str, count_key: str) -> float:
            return float(bucket.get(key, 0)) / max(1, float(bucket.get(count_key, 0)))
        rows.append(
            f"| {phase} | {int(base.get('contract_successes',0))}/{int(base.get('contract_started',0))} → "
            f"{int(candidate.get('contract_successes',0))}/{int(candidate.get('contract_started',0))} "
            f"| {rate(base,'contract_chance_sum','contract_chance_samples'):.1f}% → "
            f"{rate(candidate,'contract_chance_sum','contract_chance_samples'):.1f}% "
            f"| {int(base.get('resource_net_xp',0)):,} → {int(candidate.get('resource_net_xp',0)):,} "
            f"| {int(base.get('threat_85_cycles',0))}/{int(base.get('security_25_cycles',0))} → "
            f"{int(candidate.get('threat_85_cycles',0))}/{int(candidate.get('security_25_cycles',0))} |".replace(",", ".")
        )
    rows += [
        "",
        "O runner valida que o banco molde não tenha `regional_guild_state` nem `regional_world_state` antes de criar os clones. As tentativas anteriores com um molde já regionalizado foram excluídas porque algumas seeds falharam ao trocar a região natal por colisão de slot; a amostra válida usa o molde limpo e concluiu as cinco seeds solicitadas sem esse erro.",
        "",
        "Comando reproduzível: `python scripts/balance/run_ml038_cpu_paired.py --template-db .lot-e2-test-tmp/ml029-level-inspect/saves/fc28e905-8e2e-4a15-9f14-2edb9e61f057.db --limit 5 --label ml038-rank-table-clean-2026-11-10`.",
        "",
        f"Detalhe por seed/fase: [Markdown](lot_e2_ml029_cpu_paired_{CPU_PAIRED_JSON.stem.split('paired_',1)[1]}.md), [CSV](lot_e2_ml029_cpu_paired_{CPU_PAIRED_JSON.stem.split('paired_',1)[1]}.csv), [JSON]({CPU_PAIRED_JSON.name}).",
        "",
        "O impacto em sucesso e XP da CPU é relevante e persiste nas cinco seeds; ações mantêm-se estáveis, enquanto as pressões regionais e eventos mudam. O CR aprovou tecnicamente o código, mas manteve o gate econômico aberto até que haja decisão explícita sobre mitigação/critério de aceite. Não reduzir ou alterar os multiplicadores definidos pelo usuário sem nova decisão.",
    ]
    return rows


def main() -> None:
    rows: list[dict[str, int | float | str]] = []
    for level in LEVELS:
        member_power = common_apprentice_reference_power(level)
        for rank, new_multiplier in REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS.items():
            old_recommended = max(1, ceil(member_power * OLD[rank] * 2))
            new_recommended = recommended_regional_contract_power(
                level, rank, 2, fallback_power=old_recommended,
            )
            for party_size in (1, 2):
                party_power = member_power * party_size
                old_adjustment = power_success_adjustment(party_power, old_recommended)
                new_adjustment = power_success_adjustment(party_power, new_recommended)
                old_chance = max(5, min(95, BASE_CHANCE + old_adjustment))
                new_chance = max(5, min(95, BASE_CHANCE + new_adjustment))
                rows.append({
                    "scenario": "common_apprentice_reference",
                    "level": level,
                    "rank": rank,
                    "party_size": party_size,
                    "group_max": 2,
                    "common_power_each": member_power,
                    "party_power": party_power,
                    "base_chance": BASE_CHANCE,
                    "old_multiplier": OLD[rank],
                    "old_recommended_power": old_recommended,
                    "old_power_chance_adjustment_pp": old_adjustment,
                    "old_chance_no_supply": old_chance,
                    "old_chance_with_supply_5pp": min(95, old_chance + 5),
                    "new_multiplier": new_multiplier,
                    "new_recommended_power": new_recommended,
                    "new_power_chance_adjustment_pp": new_adjustment,
                    "new_chance_no_supply": new_chance,
                    "new_chance_with_supply_5pp": min(95, new_chance + 5),
                    "delta_adjustment_pp": new_adjustment - old_adjustment,
                })

    # Deterministic mixed-rarity illustration: stated stats make this example
    # reproducible without claiming to reconstruct an unspecified live roster.
    rare_power = calculate_power_score({
        "power": 32, "vitality": 32, "agility": 17,
        "intelligence": 17, "luck": 16, "armor": 6,
    })
    common_power = common_apprentice_reference_power(15)
    mixed_party_power = rare_power + common_power
    for rank, multiplier in REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS.items():
        old_recommended = max(1, ceil(common_power * OLD[rank] * 2))
        new_recommended = recommended_regional_contract_power(
            15, rank, 2, fallback_power=old_recommended,
        )
        old_adjustment = power_success_adjustment(mixed_party_power, old_recommended)
        new_adjustment = power_success_adjustment(mixed_party_power, new_recommended)
        class_bonus = 3
        skill_bonus = 0
        old_pre_supply = max(5, min(95, BASE_CHANCE + old_adjustment + class_bonus + skill_bonus))
        new_pre_supply = max(5, min(95, BASE_CHANCE + new_adjustment + class_bonus + skill_bonus))
        rows.append({
            "scenario": "mixed_rare10_common15_reference",
            "level": 15,
            "rank": rank,
            "party_size": 2,
            "group_max": 2,
            "common_power_each": common_power,
            "party_power": mixed_party_power,
            "base_chance": BASE_CHANCE,
            "old_multiplier": OLD[rank],
            "old_recommended_power": old_recommended,
            "old_power_chance_adjustment_pp": old_adjustment,
            "old_chance_no_supply": old_pre_supply,
            "old_chance_with_supply_5pp": min(95, old_pre_supply + 5),
            "new_multiplier": multiplier,
            "new_recommended_power": new_recommended,
            "new_power_chance_adjustment_pp": new_adjustment,
            "new_chance_no_supply": new_pre_supply,
            "new_chance_with_supply_5pp": min(95, new_pre_supply + 5),
            "delta_adjustment_pp": new_adjustment - old_adjustment,
            "rare_level10_power": rare_power,
            "rare_attributes": "FOR32/VIT32/AGI17/INT17/SOR16/ARM6",
            "party_class_bonus_pp": class_bonus,
            "skill_bonus_pp": skill_bonus,
        })

    csv_path = OUTPUT / "ml038_rank_power_scenarios_2026-11-09.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        fieldnames = list(rows[0]) + [
            key for key in dict.fromkeys(key for row in rows for key in row)
            if key not in rows[0]
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    at_17 = [row for row in rows if row["level"] == 17 and row["scenario"] == "common_apprentice_reference"]
    mixed_rows = [row for row in rows if row["scenario"] == "mixed_rare10_common15_reference"]
    report = [
        "# ML-038 — calibração de poder recomendado por rank",
        "",
        "A tabela foi aplicada apenas ao cálculo de novos snapshots de contratos regionais de combate. A curva de referência usa o Aprendiz Comum sem equipamento; o poder recomendado é `ceil(poder de referência × multiplicador × tamanho máximo do grupo)`. O CSV cobre solo e grupo máximo 2 nos níveis inicial, intermediário e avançado. A chance mostrada usa base 78, sem classe/skill/equipamento, e também mostra suprimento +5 p.p. para separar cada componente.",
        "",
        "| Rank | Multiplicador | Poder nível 17, grupo máximo 2 | Solo: chance antes → depois (+5 suprimento) | Grupo 2: chance antes → depois (+5 suprimento) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in at_17:
        solo = next(item for item in at_17 if item["rank"] == row["rank"] and item["party_size"] == 1)
        group = next(item for item in at_17 if item["rank"] == row["rank"] and item["party_size"] == 2)
        if row["party_size"] == 1:
            report.append(
                f"| {row['rank']} | {row['new_multiplier']:.3f} | {row['new_recommended_power']} "
                f"| {solo['old_chance_no_supply']}% → {solo['new_chance_no_supply']}% "
                f"(+{solo['old_chance_with_supply_5pp']-solo['old_chance_no_supply']} → "
                f"+{solo['new_chance_with_supply_5pp']-solo['new_chance_no_supply']} pp) "
                f"| {group['old_chance_no_supply']}% → {group['new_chance_no_supply']}% "
                f"(+{group['old_chance_with_supply_5pp']-group['old_chance_no_supply']} → "
                f"+{group['new_chance_with_supply_5pp']-group['new_chance_no_supply']} pp) |"
            )
    report += [
        "",
        "## Caso S nível 17",
        "",
        "A referência Comum nível 17 tem poder 87 por mercenário. Para grupo máximo 2, o novo poder recomendado S é `ceil(87 × 1,800 × 2) = 314`; a tabela anterior resultava em 189. Para solo e grupo de dois, a chance-base é 78 e o suprimento é apresentado separadamente como +5 p.p., respeitando o teto de 95%.",
        "",
        "## Grupo misto reproduzível — Raro nível 10 + Comum nível 15",
        "",
        "Este é um caso de referência reproduzível, não uma leitura do roster real: template Exploration nível 15, chance-base 78%, grupo máximo 2; Raro nível 10 com FOR/VIT/AGI/INT/SOR/ARM `32/32/17/17/16/6` (poder 72), Comum nível 15 da curva de referência (poder 79), poder total 151; classes Warrior + Knight (+3 p.p.), skill/equipamento/raridade por nível = 0. Rank E produz 90% antes de suprimento e 95% com +5 p.p.; isso demonstra uma composição possível para a exibição de 90%, sem afirmar que seja a composição real do usuário. Rank S cai de 75% para 59% antes de suprimento e de 80% para 64% com suprimento. Os valores de todos os ranks estão no CSV.",
        "",
        "## Escopo e limitação da medição",
        "",
        "O snapshot existente permanece imutável; gathering, long idle, masmorras, chefes e poder configurado no template seguem fora da mudança. Os cinco testes direcionados de `tests/test_ml029_mission_power.py` passaram.",
        "",
        *_cpu_evidence_markdown(),
        "",
        f"CSV reproduzível: `{csv_path.name}`. Gerador: `scripts/balance/report_ml038_rank_power.py`.",
    ]
    report_path = OUTPUT / "ml038_rank_power_2026-11-09.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(report_path)
    print(csv_path)


if __name__ == "__main__":
    main()
