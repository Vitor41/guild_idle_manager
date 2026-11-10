"""Write deterministic ML-038 rank-power and chance-delta evidence."""

from __future__ import annotations

import csv
from math import ceil
from pathlib import Path

from app.services.balance_service import power_success_adjustment
from app.services.mission_power_service import (
    REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS,
    common_apprentice_reference_power,
    recommended_regional_contract_power,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "reports"
LEVELS = (1, 5, 17, 18, 50, 75, 200, 350)
OLD = {"E": 0.700, "D": 0.735, "C": 0.770, "B": 0.840, "A": 0.945, "S": 1.085}


def main() -> None:
    rows: list[dict[str, int | float | str]] = []
    for level in LEVELS:
        member_power = common_apprentice_reference_power(level)
        for rank, new_multiplier in REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS.items():
            old_recommended = max(1, ceil(member_power * OLD[rank] * 2))
            new_recommended = recommended_regional_contract_power(
                level, rank, 2, fallback_power=old_recommended,
            )
            party_power = member_power * 2
            old_adjustment = power_success_adjustment(party_power, old_recommended)
            new_adjustment = power_success_adjustment(party_power, new_recommended)
            rows.append({
                "level": level,
                "rank": rank,
                "group_size": 2,
                "common_power_each": member_power,
                "old_multiplier": OLD[rank],
                "old_recommended_power": old_recommended,
                "old_power_chance_adjustment_pp": old_adjustment,
                "new_multiplier": new_multiplier,
                "new_recommended_power": new_recommended,
                "new_power_chance_adjustment_pp": new_adjustment,
                "delta_adjustment_pp": new_adjustment - old_adjustment,
            })

    csv_path = OUTPUT / "ml038_rank_power_scenarios_2026-11-09.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    at_17 = [row for row in rows if row["level"] == 17]
    report = [
        "# ML-038 — calibração de poder recomendado por rank",
        "",
        "A tabela foi aplicada apenas ao cálculo de novos snapshots de contratos regionais de combate. A curva de referência usa o Aprendiz Comum sem equipamento; o poder recomendado é `ceil(poder de referência × multiplicador × tamanho máximo do grupo)`. O CSV traz níveis inicial, intermediário, avançado e o caso nível 17.",
        "",
        "| Rank | Multiplicador | Poder nível 17, grupo 2 | Ajuste de chance pelo poder antes → depois | Delta |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in at_17:
        report.append(
            f"| {row['rank']} | {row['new_multiplier']:.3f} | {row['new_recommended_power']} "
            f"| {row['old_power_chance_adjustment_pp']} → {row['new_power_chance_adjustment_pp']} pp "
            f"| {row['delta_adjustment_pp']:+} pp |"
        )
    report += [
        "",
        "## Caso S nível 17",
        "",
        "A referência Comum nível 17 tem poder 87 por mercenário. Para grupo máximo 2, o novo poder recomendado S é `ceil(87 × 1,800 × 2) = 314`; a tabela anterior resultava em 189. Para dois Aprendizes Comuns sem modificadores, o termo de chance ligado ao poder passa de −4 pp para −21 pp. A chance final depende da chance-base do contrato, atributos reais, raridade, equipamento, classe, skills e preparação; este cálculo não afirma a chance final do exemplo com mercenários Raro nível 10 e Comum nível 15, cujos atributos/equipamentos não foram informados.",
        "",
        "## Escopo e limitação da medição",
        "",
        "O snapshot existente permanece imutável; gathering, long idle, masmorras, chefes e poder configurado no template seguem fora da mudança. Os cinco testes direcionados de `tests/test_ml029_mission_power.py` passaram.",
        "",
        "A comparação pareada da CPU em cinco campanhas descartáveis não foi produzida. O comando usado foi `python -c \"import os,runpy,sys; os.environ['APP_MODE']='desktop'; sys.path.insert(0,os.getcwd()); sys.argv=['scripts/balance/compare_ml029_cpu_balance.py','--limit','1','--label','ml038-rank-table-debug']; runpy.run_path(sys.argv[0],run_name='__main__')\"`. Ele falhou em `CampaignService.create_campaign` → `run_massive_content_seed` → `_insert_missing(ItemTemplate, ...)`, com `sqlite3.OperationalError: unable to open database file` durante o insert de `item_templates`. Uma pasta recém-criada sob `%TEMP%` também foi verificada e um `sqlite3.connect(<pasta>\\probe-elevated.db)` mínimo falhou com o mesmo erro. Sem esse resultado, este lote ainda não mede efeitos em XP/ouro, ações/sucessos da CPU ou eventos regionais. Nenhum save/perfil instalado foi consultado.",
        "",
        f"CSV reproduzível: `{csv_path.name}`. Gerador: `scripts/balance/report_ml038_rank_power.py`.",
    ]
    report_path = OUTPUT / "ml038_rank_power_2026-11-09.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(report_path)
    print(csv_path)


if __name__ == "__main__":
    main()
