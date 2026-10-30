"""Paired comparison of two funded upgrade paths across five play profiles."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.balance.funded_progression_simulation import (
    STRATEGIES, bootstrap_median_ci_95, run_funded_simulation, wilson_interval_95,
)

PATHS = {
    "roster_first": "Complete o roster-alvo, depois o Contract Office e o Campo de Treino.",
    "office_after_minimum_party": "Forme o grupo mínimo, evolua o Contract Office até o alvo, complete o roster e então o Campo de Treino.",
}


def _milestone_day(row: dict[str, object], item: str) -> int | None:
    return next((int(purchase["day"]) for purchase in row["purchases"]
                 if purchase["item"] == item), None)


def _profile_summary(rows: list[dict[str, object]], strategy: dict[str, object], *, seed: int) -> dict[str, object]:
    total = len(rows)
    reached = [row for row in rows if row["level_50_day"] is not None]
    complete = [row for row in rows if row["target_plan_complete"]]
    stall_observed = [row for row in rows if row["modeled_no_route_stall_14d_observed"] is not None]
    stall_count = sum(row["modeled_no_route_stall_14d_observed"] is True for row in stall_observed)
    office_target = int(strategy["office_target"])
    final_office_item = f"contract_office_{office_target}"
    return {
        "trajectories": total,
        "level_50_reached": len(reached),
        "level_50_rate_wilson_95": wilson_interval_95(len(reached), total),
        "level_50_day_p50": median([float(row["level_50_day"]) for row in reached]) if reached else None,
        "target_plan_completed": len(complete),
        "target_plan_rate_wilson_95": wilson_interval_95(len(complete), total),
        "modeled_no_route_stall_14d": {
            "events": stall_count, "observed": len(stall_observed),
            "rate_wilson_95": wilson_interval_95(stall_count, len(stall_observed)),
            "whole_game_hard_softlock": "not_measured",
        },
        "office_1_day_p50": median([float(day) for row in rows
                                    if (day := _milestone_day(row, "contract_office_1")) is not None])
        if any(_milestone_day(row, "contract_office_1") is not None for row in rows) else None,
        "office_target_item": final_office_item,
        "office_target_day_p50": median([float(day) for row in rows
                                         if (day := _milestone_day(row, final_office_item)) is not None])
        if any(_milestone_day(row, final_office_item) is not None for row in rows) else None,
        "ending_gold_p50": median([float(row["balances_at_end"]["gold"]) for row in rows]),
        "late_game_net_14d_p50": median([
            float(row["late_game_last_14_day_net_gold_surplus_deficit"])
            for row in rows if row["late_game_last_14_day_net_gold_surplus_deficit"] is not None
        ]) if any(row["late_game_last_14_day_net_gold_surplus_deficit"] is not None for row in rows) else None,
        "offline_credit_hours_per_day_p50": median([
            float(row["offline_credited_hours_per_day_mean"]) for row in rows
        ]),
        "seeds": sorted(int(row["seed"]) for row in rows),
        "level_50_day_by_seed": {str(row["seed"]): row["level_50_day"] for row in rows},
    }


def build_report(*, runs_per_profile: int, seed_start: int, reports: dict[str, dict[str, object]]) -> dict[str, object]:
    by_profile = {}
    for index, strategy in enumerate(STRATEGIES):
        profile = str(strategy["name"])
        variants = {}
        for path_name, report in reports.items():
            rows = [row for row in report["raw_trajectories"] if row["strategy"] == profile]
            variants[path_name] = _profile_summary(
                rows, strategy, seed=seed_start + index * 100_000,
            )
        baseline = variants["roster_first"]
        alternative = variants["office_after_minimum_party"]
        if baseline["seeds"] != alternative["seeds"]:
            raise ValueError(f"Paired path seed mismatch for profile {profile}")
        baseline_by_seed = baseline["level_50_day_by_seed"]
        alternative_by_seed = alternative["level_50_day_by_seed"]
        paired_delta = [float(alternative_by_seed[seed]) - float(baseline_by_seed[seed])
                        for seed in baseline_by_seed
                        if baseline_by_seed[seed] is not None and alternative_by_seed[seed] is not None]
        variants["paired_delta_alternative_minus_roster_first"] = {
            "level_50_day_n": len(paired_delta),
            "level_50_day_p50": median(paired_delta) if paired_delta else None,
            "level_50_day_ci_95": bootstrap_median_ci_95(
                paired_delta, seed=seed_start + index * 100_000 + 77,
            ),
        }
        for summary in (baseline, alternative):
            summary.pop("level_50_day_by_seed", None)
            summary.pop("seeds", None)
        by_profile[profile] = {
            **variants,
            "paired_seeds": {
                "first": seed_start + index * 100_000,
                "last": seed_start + index * 100_000 + runs_per_profile - 1,
                "n": runs_per_profile,
            },
        }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": "funded fresh-save progression, no recurring sink",
        "runs_per_profile_path": runs_per_profile,
        "seed_start": seed_start,
        "paths": PATHS,
        "profiles": by_profile,
        "source": "funded_progression_simulation.py; current seeded catalog/services; paired seeds per profile across paths",
        "limitations": [
            "Purchase paths are deterministic policies; contract and offline outcomes retain their modeled seeded variability.",
            "Finite mandatory plan is not all viable gameplay routes; optional buildings, mission drops/sales, equipment, dungeons and events are omitted.",
            "The 14-day no-route stall is a narrow model observation, not proof of whole-game hard softlock absence.",
            "N=10 paired seeds gives wide uncertainty; compare as preliminary sensitivity only.",
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    def rate(entry: dict[str, object]) -> str:
        value = entry.get("rate_percent")
        low, high = entry.get("lower_percent"), entry.get("upper_percent")
        return "—" if value is None else f"{value:.0f}% ({low:.0f}–{high:.0f})"

    lines = [
        "# Estratégias financiadas de progressão — Stage 5", "",
        f"Execução {report['generated_at_utc']} · N={report['runs_per_profile_path']} por perfil/rota · seeds pareadas · sem sink recorrente.", "",
        "Seeds por perfil: " + "; ".join(
            f"{profile} {entry['paired_seeds']['first']}–{entry['paired_seeds']['last']}"
            for profile, entry in report["profiles"].items()
        ) + ".", "",
        "As duas estratégias começam no mesmo setup mínimo de campanha e usam a economia e as cotações atuais. Apenas a ordem dos investimentos muda.", "",
        "| Rota | Prioridade de compras |", "|---|---|",
    ]
    for name, definition in PATHS.items():
        lines.append(f"| {name} | {definition} |")
    lines.extend(["", "## Resultados por perfil", "",
                  "| Perfil | Rota | Nível 50 (IC95%) | Dia 50 p50 | Plano finito (IC95%) | Stall sem rota ≥14d | Office 1 dia p50 | Office alvo dia p50 | Ouro final p50 | Líquido 14d pós-50 p50 | Crédito offline h/d p50 |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for profile, payload in report["profiles"].items():
        for path_name in PATHS:
            row = payload[path_name]
            stall = row["modeled_no_route_stall_14d"]
            lines.append(
                f"| {profile} | {path_name} | {row['level_50_reached']}/{row['trajectories']} ({rate(row['level_50_rate_wilson_95'])}) | "
                f"{row['level_50_day_p50'] if row['level_50_day_p50'] is not None else '—'} | "
                f"{row['target_plan_completed']}/{row['trajectories']} ({rate(row['target_plan_rate_wilson_95'])}) | "
                f"{stall['events']}/{stall['observed']} ({rate(stall['rate_wilson_95'])}) | "
                f"{row['office_1_day_p50'] if row['office_1_day_p50'] is not None else '—'} | "
                f"{row['office_target_day_p50'] if row['office_target_day_p50'] is not None else '—'} | "
                f"{row['ending_gold_p50']:,.0f} | {row['late_game_net_14d_p50'] if row['late_game_net_14d_p50'] is not None else '—'} | "
                f"{row['offline_credit_hours_per_day_p50']:.1f} |"
            )
        delta = payload["paired_delta_alternative_minus_roster_first"]
        ci = delta["level_50_day_ci_95"]
        interval = f"{ci['lower_95']}–{ci['upper_95']}" if ci["lower_95"] is not None else "—"
    lines.extend(["", "## Diferença pareada no dia de nível 50", "",
                  "Diferença = Office após party mínima menos roster-first; valores negativos indicam nível 50 mais cedo na alternativa.", "",
                  "| Perfil | N pareado | Diferença mediana em dias | IC95% bootstrap |", "|---|---:|---:|---:|"])
    for profile, payload in report["profiles"].items():
        delta = payload["paired_delta_alternative_minus_roster_first"]
        ci = delta["level_50_day_ci_95"]
        interval = f"{ci['lower_95']}–{ci['upper_95']}" if ci["lower_95"] is not None else "—"
        lines.append(f"| {profile} | {delta['level_50_day_n']} | {delta['level_50_day_p50']} | {interval} |")
    lines.extend(["", "## Leitura e limites", "",
                  "O grupo mínimo é o tamanho de party declarado no perfil; a rota alternativa espera esse grupo antes de priorizar Contract Office. A rota roster-first preserva a fila usada no relatório funded anterior. O simulador aplica limites de presença e stamina persistente; o perfil casual representa sessão de 2h/dia e crédito offline de 8h no primeiro retorno, depois 4h por retorno. A tabela mostra o crédito médio diário observado no ledger.", "",
                  "‘Stall sem rota’ significa bloqueio contínuo por 14 dias na próxima compra obrigatória desta fila finita, sem fonte de ouro, coleta possível para materiais faltantes ou ação que dê XP. A ausência de evento nesta amostra não prova ausência de softlock no jogo inteiro.", "",
                  "O runner ainda não materializa drops de missão, venda no Mercado, salvage, compras discricionárias, masmorras nem eventos regionais dentro do ledger. A disponibilidade desses caminhos e seus gates são auditados separadamente; timing e recuperação efetiva por essas fontes permanecem risco residual. N=10 é exploração pareada, não aceite de balanceamento.", "",
                  "## Reprodução", "", "```powershell",
                  f".venv\\Scripts\\python.exe scripts\\balance\\compare_funded_path_strategies.py --runs-per-profile {report['runs_per_profile_path']} --seed-start {report['seed_start']}",
                  "```", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two funded progression paths with paired seeds.")
    parser.add_argument("--runs-per-profile", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=2026102900)
    args = parser.parse_args()
    reports = {}
    for path_name in PATHS:
        print(f"Running funded path {path_name}...", flush=True)
        reports[path_name] = run_funded_simulation(
            runs_per_strategy=args.runs_per_profile, seed_start=args.seed_start,
            path_variant=path_name,
        )
    report = build_report(runs_per_profile=args.runs_per_profile, seed_start=args.seed_start, reports=reports)
    stem = ROOT / "reports" / "funded_path_strategy_comparison_2026-10-29"
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {stem.with_suffix('.json')}")
    print(f"Markdown: {stem.with_suffix('.md')}")


if __name__ == "__main__":
    main()
