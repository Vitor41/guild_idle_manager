"""Summarize the existing endgame guild-dues sensitivity without approving a rule."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "reports" / "guild_progression_profiles_1_50.json"
REPORT_JSON = ROOT / "reports" / "sink_candidate_sensitivity_2026-10-29.json"
REPORT_MD = ROOT / "reports" / "sink_candidate_sensitivity_2026-10-29.md"
PROFILE_ORDER = ("ativo", "casual", "offline", "produtor", "combate")
SINKS = (
    ("upkeep_2_percent", "Baixa — 2% do tesouro por Vigília"),
    ("upkeep_5_percent", "Média — 5% do tesouro por Vigília"),
    ("upkeep_10_percent", "Alta — 10% do tesouro por Vigília"),
)


def _median_change(baseline: float, candidate: float) -> float:
    return round((baseline - candidate) / baseline * 100, 2) if baseline else 0.0


def build_report(source: dict[str, object]) -> dict[str, object]:
    profile_data = source["regional_board_endgame_economy"]
    profiles: dict[str, object] = {}
    for name in PROFILE_ORDER:
        row = profile_data[name]
        baseline = row["no_spend_gold_balance"]["after_horizon_endgame_days"]
        candidate_rows = {}
        for key, label in SINKS:
            candidate = row["candidate_upkeep_sensitivity"]["rates"][key]
            ending = candidate["treasury_after_horizon_endgame_days"]
            paid = candidate["upkeep_paid_horizon_days"]
            candidate_rows[key] = {
                "label": label,
                "ending_treasury_gold": ending,
                "upkeep_paid_gold": paid,
                "median_ending_treasury_reduction_percent": _median_change(
                    baseline["p50"], ending["p50"],
                ),
                "still_positive_after_14_days": ending["p10"] > 0,
            }
        gross = row["endgame_daily_gross_gold"]
        baseline_by_quantile = {
            q: baseline[q] for q in ("p10", "p50", "p90")
        }
        earnings_fee = {
            q: round(gross[q] * row["horizon_days"] * 0.05, 2)
            for q in ("p10", "p50", "p90")
        }
        roster_size = int(row["profile_setup_costs"]["roster_size"])
        roster_fee_gold = roster_size * 25 * int(row["horizon_days"])
        candidate_types = {
            "treasury_dues_2pct_per_vigilia": {
                "mechanic": "Taxar 2% do saldo atual antes de cada Vigília, limitado ao ouro disponível.",
                "ending_treasury_gold": row["candidate_upkeep_sensitivity"]["rates"]["upkeep_2_percent"]["treasury_after_horizon_endgame_days"],
                "paid_gold": row["candidate_upkeep_sensitivity"]["rates"]["upkeep_2_percent"]["upkeep_paid_horizon_days"],
                "still_positive_after_14_days": row["candidate_upkeep_sensitivity"]["rates"]["upkeep_2_percent"]["treasury_after_horizon_endgame_days"]["p10"] > 0,
            },
            "earnings_levy_5pct": {
                "mechanic": "Reter 5% do ouro ganho no dia; a cobrança só existe quando há renda.",
                "ending_treasury_gold": {
                    q: round(baseline_by_quantile[q] - earnings_fee[q], 2)
                    for q in ("p10", "p50", "p90")
                },
                "paid_gold": earnings_fee,
                "still_positive_after_14_days": all(
                    baseline_by_quantile[q] - earnings_fee[q] > 0 for q in ("p10", "p50", "p90")
                ),
            },
            "roster_payroll_25_per_day": {
                "mechanic": "Cobrar 25 ouro por mercenário do roster-alvo por dia.",
                "roster_size": roster_size,
                "ending_treasury_gold": {
                    q: round(baseline_by_quantile[q] - roster_fee_gold, 2)
                    for q in ("p10", "p50", "p90")
                },
                "paid_gold": {q: roster_fee_gold for q in ("p10", "p50", "p90")},
                "still_positive_after_14_days": all(
                    baseline_by_quantile[q] - roster_fee_gold > 0 for q in ("p10", "p50", "p90")
                ),
            },
        }
        profiles[name] = {
            "trajectories": row["trajectories"],
            "horizon_days": row["horizon_days"],
            "daily_gross_gold": row["endgame_daily_gross_gold"],
            "no_sink_ending_treasury_gold": baseline,
            "candidate_rates": candidate_rows,
            "candidate_types": candidate_types,
        }
    return {
        "title": "Low-friction sink candidate sensitivity — endgame treasury dues",
        "date": "2026-10-29",
        "source_report": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "sample": {
            "profiles": list(PROFILE_ORDER),
            "trajectories_per_profile": 25,
            "horizon_days": 14,
            "vigilia_cycles_per_day": 4,
            "starting_point": "Level 50 after profile setup is treated as already funded; no subsequent building/roster purchases are modeled.",
        },
        "candidate_mechanics": {
            "treasury_dues_2pct_per_vigilia": "At each six-hour Vigília, charge min(current_treasury, ceil(current_treasury * 0.02)) before the next board's gold is credited; this exact model is reused from the source report.",
            "earnings_levy_5pct": "Sensitivity arithmetic on 5% of daily gross gold; charge is income-bounded and is not applied to the funded 1–50 trajectory.",
            "roster_payroll_25_per_day": "Sensitivity arithmetic on 25 gold per level-50 profile roster member per day; the roster size is taken from the modeled profile setup.",
            "status": "All three are hypothetical sensitivity options; none is implemented or approved.",
            "rebellion_chance_is_separate": True,
        },
        "profiles": profiles,
        "findings": {
            "all_candidate_p10_end_balances_positive_after_14_days": all(
                candidate["still_positive_after_14_days"]
                for profile in PROFILE_ORDER
                for candidate in profiles[profile]["candidate_types"].values()
            ),
            "bounded_economy_demonstrated": False,
            "hard_softlock_demonstrated_or_excluded": False,
            "recovery_measured_after_sink": False,
            "reason": "The candidate sensitivity starts at level 50 and does not model post-sink purchase choices or resource recovery. Positive 14-day balances do not establish a bounded treasury; capped or income-bounded charges avoid immediate debt but can still delay optional purchases.",
        },
        "limitations": [
            "As duas tarifas e o valor da folha são preços ilustrativos; nenhum preço de jogo foi aprovado.",
            "A amostra de origem tem 25 trajetórias de nível 50 por perfil, não rotas completas sob sink.",
            "O setup está pré-pago; as cobranças não se aplicam durante os níveis 1–50, portanto acessibilidade e hard softlock não são avaliados.",
            "Agenda de compras, materiais, recuperação por coleta, venda de itens e serviços opcionais não foram recalculados após uma cobrança.",
            "Nenhuma tarifa foi aprovada. Os 2% de chance de rebelião são uma regra separada e não determinam estas cobranças.",
        ],
    }


def render(report: dict[str, object]) -> str:
    lines = [
        "# Sensibilidade de sink de ouro no endgame",
        "",
        "Este resumo compara três mecânicas hipotéticas de contribuição recorrente da guilda. Os valores vêm da auditoria de endgame já materializada com boards do serviço regional; não são regras aprovadas.",
        "",
        "| Perfil | Sem sink p50 | Dues 2%/Vigília p50 (pago) | Retenção 5% renda p50 (pago) | Folha 25g/merc./dia p50 (pago) |",
        "|---|---:|---:|---:|---:|",
    ]
    for profile in PROFILE_ORDER:
        row = report["profiles"][profile]
        baseline = row["no_sink_ending_treasury_gold"]["p50"]
        cells = [profile, f"{baseline:,.0f}"]
        for key in ("treasury_dues_2pct_per_vigilia", "earnings_levy_5pct", "roster_payroll_25_per_day"):
            sink = row["candidate_types"][key]
            cells.append(
                f"{sink['ending_treasury_gold']['p50']:,.0f} "
                f"({sink['paid_gold']['p50']:,.0f})"
            )
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Resultado e limite",
        "",
        "Em todos os cinco perfis, as três opções mantêm saldo positivo no p10 após 14 dias. Nenhuma demonstra uma economia limitada: a renda continua superando os custos neste horizonte. As dues e a retenção só cobram até o ouro disponível/ganho; a folha é um custo fixo que pode pressionar perfis com roster maior. A simulação não reabre decisões de compra após a cobrança e não prova que a rota de campanha se recupera.",
        "",
        "As diferenças de caixa são maiores em termos absolutos para os perfis ativo/combate e menores para o casual; isso acompanha a renda, não mede justiça percebida. O perfil casual também termina com saldo positivo nas três opções, mas o modelo começa no nível 50 após setup pré-pago.",
        "",
        "## Conclusão técnica",
        "",
        "Nenhuma opção pode ser recomendada como solução para ‘sem economia infinita’: as três deixam saldo positivo no nível 50, e este horizonte curto não determina se qualquer uma se estabiliza. A retenção por renda parece menos regressiva ao caixa acumulado, enquanto a folha aumenta com o roster e as dues incidem repetidamente sobre o saldo. Antes de escolher qualquer sink, é necessário aplicar a cobrança nas rotas financiadas 1–50, medir atrasos/softlock por perfil e incluir uma forma observável de recuperação. Stage 5 permanece aberto.",
        "",
        "## Suposições e lacunas",
        "",
    ] + [f"- {item}" for item in report["limitations"]] + [
        "",
        f"Fonte: `{report['source_report']}`. Cada perfil usa 25 trajetórias por 14 dias (56 Vigílias), começando após o setup completo pré-pago.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = build_report(source)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(render(report), encoding="utf-8")
    print(REPORT_MD)


if __name__ == "__main__":
    main()
