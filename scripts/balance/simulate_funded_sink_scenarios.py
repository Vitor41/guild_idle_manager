"""Apply illustrative recurring gold sinks to funded 1–50 trajectories."""
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

from scripts.balance.funded_progression_simulation import run_funded_simulation, wilson_interval_95

POLICIES = {
    "none": None,
    "wallet_dues_2pct": {"type": "wallet_dues", "rate": 0.02,
                          "label": "2% do saldo no início de cada Vigília elegível"},
    "earnings_levy_5pct": {"type": "earnings_levy", "rate": 0.05,
                           "label": "5% da renda bruta diária (contratos + passivo)"},
    "roster_payroll_25": {"type": "roster_payroll", "gold_per_mercenary_day": 25,
                          "label": "25 ouro por mercenário no roster por dia"},
}
MILESTONES = ("apprentice_2", "housing_2", "contract_office_1", "training_ground_1")


def _distribution(values: list[float | int | None]) -> dict[str, float | int | None]:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return {"n": 0, "min": None, "p50": None, "max": None}
    return {"n": len(clean), "min": clean[0], "p50": median(clean), "max": clean[-1]}


def _summarize(report: dict[str, object]) -> dict[str, object]:
    summaries = {}
    for profile, group in report["strategies"].items():
        rows = [row for row in report["raw_trajectories"] if row["strategy"] == profile]
        reached = [row for row in rows if row["level_50_day"] is not None]
        complete = [row for row in rows if row["target_plan_complete"]]
        stall_rows = [row for row in rows if row["modeled_no_route_stall_14d_observed"] is not None]
        stall_events = sum(row["modeled_no_route_stall_14d_observed"] is True for row in stall_rows)
        shortfall_rows = []
        later_purchase_rows = []
        for row in rows:
            shortfall_days = [
                int(day["day"]) for day in row["daily_ledger"]
                if day.get("next_purchase_requirements")
                and int(day["next_purchase_requirements"].get("gold_shortfall", 0)) > 0
            ]
            if shortfall_days:
                shortfall_rows.append(row)
                if any(int(purchase["day"]) > min(shortfall_days) for purchase in row["purchases"]):
                    later_purchase_rows.append(row)
        milestones = {}
        for milestone in MILESTONES:
            purchases = [next((p for p in row["purchases"] if p["item"] == milestone), None) for row in rows]
            bought = [purchase for purchase in purchases if purchase is not None]
            milestones[milestone] = {
                "purchased": len(bought), "total": len(rows),
                "purchase_rate_wilson_95": wilson_interval_95(len(bought), len(rows)),
                "purchase_day_p50": _distribution([p["day"] for p in bought])["p50"],
                "purchase_day_by_seed": {str(row["seed"]): next(
                    (int(p["day"]) for p in row["purchases"] if p["item"] == milestone), None
                ) for row in rows},
            }
        summaries[profile] = {
            "trajectories": len(rows),
            "level_50_reached": len(reached),
            "level_50_reached_wilson_95": wilson_interval_95(len(reached), len(rows)),
            "level_50_day_p50": _distribution([row["level_50_day"] for row in rows])["p50"],
            "target_plan_completed": len(complete),
            "target_plan_completed_wilson_95": wilson_interval_95(len(complete), len(rows)),
            "modeled_no_route_stall_14d": {
                "events": stall_events, "observed": len(stall_rows),
                "rate_wilson_95": wilson_interval_95(stall_events, len(stall_rows)),
                "whole_game_hard_softlock": "not_measured",
            },
            "gold_shortfall_later_purchase": {
                "shortfall_trajectories": len(shortfall_rows),
                "trajectories_with_later_purchase": len(later_purchase_rows),
                "rate_wilson_95": wilson_interval_95(len(later_purchase_rows), len(shortfall_rows)),
            },
            "milestones": milestones,
            "ending_gold_p50": _distribution([row["balances_at_end"]["gold"] for row in rows])["p50"],
            "sink_paid_gold_p50": _distribution([row.get("sink_paid_gold", 0) for row in rows])["p50"],
            "sink_unpaid_gold_p50": _distribution([row.get("sink_unpaid_gold", 0) for row in rows])["p50"],
            "late_game_net_14d_p50": _distribution([
                row["late_game_last_14_day_net_gold_surplus_deficit"] for row in rows
            ])["p50"],
        }
    return summaries


def render_markdown(result: dict[str, object]) -> str:
    def rate_text(row: dict[str, object] | None) -> str:
        if not row or row.get("rate_percent") is None:
            return "—"
        return f"{row['rate_percent']:.0f}% ({row['lower_percent']:.0f}–{row['upper_percent']:.0f})"

    lines = [
        "# Comparação de sinks dentro da progressão financiada 1–50", "",
        f"Execução em {result['generated_at_utc']} · N={result['runs_per_profile']} por perfil e cenário · seeds pareadas por cenário.", "",
        "Seeds por perfil: " + "; ".join(
            f"{profile} {bounds['first']}–{bounds['last']}" for profile, bounds in result["seed_ranges"].items()
        ) + ".", "",
        "Os três sinks são apenas sensibilidades, sem aprovação de regra ou preço. Cada opção é debitada durante a progressão, junto aos mesmos boards, cotações de serviços, renda passiva, coleta e prioridades de compra da simulação financiada. O cenário sem sink usa a mesma amostra de seeds.", "",
        "## Regras ilustrativas", "",
        "| Cenário | Regra |", "|---|---|",
    ]
    for key, policy in POLICIES.items():
        lines.append(f"| {key} | {policy['label'] if policy else 'Sem cobrança recorrente'} |")
    lines.extend(["", "## Progressão e caixa", "", "| Cenário | Perfil | Nível 50 (IC95%) | Dia 50 p50 | Plano concluído (IC95%) | Stall sem rota ≥14d (IC95%) | Compra posterior à falta de ouro | Ouro final p50 | Pago p50 | Não pago p50 | Saldo líquido 14d pós-50 p50 |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for scenario, payload in result["scenarios"].items():
        for profile, row in payload["profiles"].items():
            stall = row["modeled_no_route_stall_14d"]
            lines.append(
                f"| {scenario} | {profile} | {row['level_50_reached']}/{row['trajectories']} ({rate_text(row['level_50_reached_wilson_95'])}) | {row['level_50_day_p50'] if row['level_50_day_p50'] is not None else '—'} | "
                f"{row['target_plan_completed']}/{row['trajectories']} ({rate_text(row['target_plan_completed_wilson_95'])}) | {stall['events']}/{stall['observed']} ({rate_text(stall['rate_wilson_95'])}) | "
                f"{row['gold_shortfall_later_purchase']['trajectories_with_later_purchase']}/{row['gold_shortfall_later_purchase']['shortfall_trajectories']} | "
                f"{row['ending_gold_p50']:,.0f} | {row['sink_paid_gold_p50']:,.0f} | {row['sink_unpaid_gold_p50']:,.0f} | "
                f"{row['late_game_net_14d_p50'] if row['late_game_net_14d_p50'] is not None else '—'} |"
            )
    lines.extend(["", "## Marcos de compra", "", "Dia mediano entre trajetórias que realizaram cada compra. A coluna compra/total permite ver falhas de acesso no horizonte simulado.", "", "| Cenário | Perfil | Segundo aprendiz | Alojamento 2 | Office 1 | Campo de Treino 1 |", "|---|---|---:|---:|---:|---:|"])
    for scenario, payload in result["scenarios"].items():
        for profile, row in payload["profiles"].items():
            cells = []
            for milestone in MILESTONES:
                entry = row["milestones"][milestone]
                day = entry["purchase_day_p50"]
                delta = entry.get("paired_day_delta_vs_none")
                delta_text = (f"; Δ{delta['p50']:+.0f}d ({delta['min']:+.0f}…{delta['max']:+.0f})"
                              if delta and delta["p50"] is not None else "")
                cells.append(f"{entry['purchased']}/{entry['total']} · {day if day is not None else '—'}d{delta_text}")
            lines.append(f"| {scenario} | {profile} | " + " | ".join(cells) + " |")
    lines.extend([
        "", "## Interpretação e limites", "",
        "‘Stall sem rota’ significa que a próxima compra obrigatória da rota finita permaneceu bloqueada por 14 dias, sem ouro creditado, coleta possível para materiais faltantes nem ação para XP. Zero casos é evidência apenas contra esse stall observável nesta amostra; hard softlock econômico do jogo completo continua não mensurado porque a simulação exclui drops/vendas, mercado, equipamento, masmorras, eventos e outras rotas.",
        "",
        "A retenção de renda incide sobre ouro de contratos e passivo bruto no dia. A cobrança de saldo é feita antes de cada janela de Vigília ativa (janelas unattended não cobram). A folha é devida por mercenário no roster no início do dia; é limitada ao caixa disponível e o inadimplido fica registrado, sem dívida acumulada. Valores não representam decisões de design.",
        "",
        "A métrica de compra posterior registra apenas se houve qualquer compra depois do primeiro dia com falta de ouro; ela não identifica se o item bloqueado foi comprado e não comprova recuperação daquele bloqueio. O simulador não injeta perdão, empréstimo ou subsídio. Trajetórias que terminam sem nível 50 ou sem completar o plano ficam visíveis separadamente. Nenhum cenário, isoladamente, demonstra economia limitada nem valida justiça/percepção.",
        "",
        "## Reprodução", "", "```powershell",
        f".venv\\Scripts\\python.exe scripts\\balance\\simulate_funded_sink_scenarios.py --runs-per-profile {result['runs_per_profile']} --seed-start {result['seed_start']}",
        "```", "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare illustrative recurring sinks inside funded 1–50 trajectories.")
    parser.add_argument("--runs-per-profile", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=2026102900)
    args = parser.parse_args()
    baseline_path = ROOT / "reports" / "funded_upgrade_trajectories_2026-10-29.json"
    baseline_source = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    if int(baseline_source.get("seed_start", -1)) != args.seed_start:
        raise ValueError("The stored baseline seed_start must match --seed-start for paired comparison")
    baseline_raw = []
    for strategy_index, profile in enumerate(baseline_source["strategies"]):
        expected = {args.seed_start + strategy_index * 100_000 + i for i in range(args.runs_per_profile)}
        rows = [row for row in baseline_source["raw_trajectories"]
                if row["strategy"] == profile and int(row["seed"]) in expected]
        if len(rows) != args.runs_per_profile:
            raise ValueError(f"Stored baseline is missing paired seeds for profile {profile}")
        baseline_raw.extend(rows)
    scenarios = {
        "none": {
            "policy": None,
            "profiles": _summarize({"strategies": baseline_source["strategies"],
                                    "raw_trajectories": baseline_raw}),
        },
    }
    for profile_row in scenarios["none"]["profiles"].values():
        for milestone_row in profile_row["milestones"].values():
            milestone_row.pop("purchase_day_by_seed", None)
    print("Baseline paired from the stored funded simulation.", flush=True)
    for name, policy in list(POLICIES.items())[1:]:
        report = run_funded_simulation(runs_per_strategy=args.runs_per_profile,
                                       seed_start=args.seed_start, sink_policy=policy)
        scenarios[name] = {"policy": policy, "profiles": _summarize(report)}
        for profile, profile_row in scenarios[name]["profiles"].items():
            baseline_milestones = scenarios["none"]["profiles"][profile]["milestones"]
            for milestone, milestone_row in profile_row["milestones"].items():
                baseline_days = {
                    str(row["seed"]): next((int(p["day"]) for p in row["purchases"]
                                             if p["item"] == milestone), None)
                    for row in baseline_raw if row["strategy"] == profile
                }
                sink_days = milestone_row.pop("purchase_day_by_seed")
                deltas = [int(day) - int(baseline_days[seed])
                          for seed, day in sink_days.items()
                          if day is not None and baseline_days.get(seed) is not None]
                milestone_row["paired_day_delta_vs_none"] = {
                    "n": len(deltas), "min": min(deltas) if deltas else None,
                    "p50": median(deltas) if deltas else None,
                    "max": max(deltas) if deltas else None,
                }
        print(f"Completed {name}.", flush=True)
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs_per_profile": args.runs_per_profile, "seed_start": args.seed_start,
        "seed_ranges": {
            profile: {
                "first": args.seed_start + index * 100_000,
                "last": args.seed_start + index * 100_000 + args.runs_per_profile - 1,
                "n": args.runs_per_profile,
            }
            for index, profile in enumerate(baseline_source["strategies"])
        },
        "policies": POLICIES, "scenarios": scenarios,
        "baseline_source": baseline_path.name,
        "definitions": {
            "stall": "14 continuous days with the same blocked next purchase and no modeled gold, material or XP recovery route",
            "whole_game_hard_softlock": "not_measured",
            "sample_note": "Same seed ranges for each scenario; the sample is paired by profile and seed.",
        },
    }
    base = ROOT / "reports" / "funded_sink_scenarios_2026-10-29"
    base.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    base.with_suffix(".md").write_text(render_markdown(result), encoding="utf-8")
    print(f"JSON: {base.with_suffix('.json')}")
    print(f"Markdown: {base.with_suffix('.md')}")


if __name__ == "__main__":
    main()
