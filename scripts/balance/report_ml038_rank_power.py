"""Write deterministic ML-038 rank-power and chance-delta evidence."""

from __future__ import annotations

import csv
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
        "A comparação completa de cinco seeds não terminou. A criação de campanha descartável pelo caminho normal falhou em `CampaignService.create_campaign` → `run_massive_content_seed` → `_insert_missing(ItemTemplate, ...)`, com `sqlite3.OperationalError: unable to open database file`; um SQLite mínimo sob `%TEMP%` também falhou. A alternativa usou uma campanha de teste existente como molde somente-leitura e desligou journaling apenas nos bancos clonados descartáveis. Uma seed pareada de 100 Vigílias concluiu: sucesso CPU 87,36% → 62,72% (−24,64 p.p.), XP global 1.962.551 → 1.549.955 (−21,0%), ouro líquido 21.600 → 21.600, ações/ciclo 50,79 → 50,80, portais 5 → 6 e rebeliões 0 → 0. Detalhes: [relatório da seed pareada](lot_e2_ml029_cpu_paired_ml038-rank-table-2026-11-09.md), com dados [CSV](lot_e2_ml029_cpu_paired_ml038-rank-table-2026-11-09.csv) e [JSON](lot_e2_ml029_cpu_paired_ml038-rank-table-2026-11-09.json). A tentativa de cinco seeds terminou após ~2 min 50 s, depois da primeira seed completa e durante o baseline da segunda; interrompi somente o processo descartável, sem erro/stacktrace nessa execução. Comando para reproduzir: `python scripts/balance/run_ml038_cpu_paired.py --template-db .lot-e2-test-tmp/ml029-seed-inspect/saves/259d3642-cb89-4932-b4fb-5fd7f2383276.db --limit 5 --label ml038-rank-table-followup-2026-11-10`. A evidência parcial sugere impacto forte no sucesso/XP da CPU, mas uma seed não é validação econômica robusta; falta uma simulação determinística menor do efeito CPU ou uma execução longa posterior. Não foram consultados saves/perfis reais.",
        "",
        f"CSV reproduzível: `{csv_path.name}`. Gerador: `scripts/balance/report_ml038_rank_power.py`.",
    ]
    report_path = OUTPUT / "ml038_rank_power_2026-11-09.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(report_path)
    print(csv_path)


if __name__ == "__main__":
    main()
