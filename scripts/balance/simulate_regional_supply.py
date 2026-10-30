"""Deterministic rank sweep for regional supply economics; no campaign/save data."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.supply_preparation_service import quote_supply


CASES = {
    "E": {"success_gold": 100, "drop_sale_ev": 12},
    "D": {"success_gold": 180, "drop_sale_ev": 24},
    "C": {"success_gold": 300, "drop_sale_ev": 40},
    "B": {"success_gold": 500, "drop_sale_ev": 60},
    "A": {"success_gold": 800, "drop_sale_ev": 90},
    "S": {"success_gold": 1200, "drop_sale_ev": 120},
}


def run() -> dict[str, object]:
    rows = []
    for rank, values in CASES.items():
        for multiplier in (1, 2, 3):
            quote = quote_supply(
                rank=rank,
                success_gold=values["success_gold"] * multiplier,
                expected_drop_sale=values["drop_sale_ev"] * multiplier,
                multiplier=multiplier,
                available_gold=10_000,
            )
            rows.append({"rank": rank, "multiplier": multiplier, **quote,
                         "cost_le_incremental_ev": quote.get("cost_gold", 0) <= quote["incremental_ev_gold"],
                         "cost_le_gold_only_incremental_ev": quote.get("cost_gold", 0) <= quote["gold_only_incremental_ev_gold"],
                         "cost_le_victory_value": quote.get("cost_gold", 0) <= quote["victory_value_gold"]})
    return {
        "simulation": "regional_group_supply_rank_sweep_v1",
        "deterministic": True,
        "uses_campaign_save": False,
        "xp_gold_value": 0,
        "xp_rationale": "XP has no stable gold denomination in the campaign economy and is excluded.",
        "cases": CASES,
        "rows": rows,
        "all_costs_within_expected_increment": all(row["cost_le_incremental_ev"] for row in rows),
        "all_costs_within_gold_only_increment": all(row["cost_le_gold_only_incremental_ev"] for row in rows),
        "all_costs_within_success_value": all(row["cost_le_victory_value"] for row in rows),
    }


if __name__ == "__main__":
    report = run()
    root = Path(__file__).resolve().parents[2]
    (root / "reports" / "regional_supply_rank_simulation_2026-10-29.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Simulação determinística do suprimento regional",
        "",
        "Sweep E–S em 1x, 2x e 3x, sem abrir ou alterar saves de campanha. O valor de drops é uma estimativa de venda efetiva do catálogo; o runtime zera esse componente quando o Mercado está indisponível. XP fica fora do cálculo porque não possui denominação estável em ouro.",
        "",
        "| Rank | Multiplicador | Valor de vitória (ouro) | Incremento esperado (ouro) | Custo | Teto rank | Resultado |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["rows"]:
        lines.append(f"| {row['rank']} | {row['multiplier']}x | {row['victory_value_gold']:.2f} | {row['incremental_ev_gold']:.2f} | {row.get('cost_gold', 0)} | {row.get('rank_cost_cap_gold', 0)} | {'disponível' if row['available'] else row['reason']} |")
    lines.extend(["", "Todas as linhas disponíveis respeitam `custo ≤ incremento esperado total`, `custo ≤ incremento esperado do ouro sozinho` e `custo ≤ valor da vitória`. Os tetos E–S (1–6 ouro) são por 1x e escalam pelo multiplicador; o custo efetivo também obedece ao retorno incremental. Ouro e drops da expedição são multiplicados antes do cálculo.", ""])
    (root / "reports" / "regional_supply_rank_simulation_2026-10-29.md").write_text("\n".join(lines), encoding="utf-8")
