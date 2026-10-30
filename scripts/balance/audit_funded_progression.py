"""Refresh the funded purchase-path report on temporary SQLite."""
from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.balance.funded_progression_simulation import render_markdown, run_funded_simulation

JSON_PATH = ROOT / "reports" / "funded_upgrade_trajectories_2026-10-29.json"
MD_PATH = ROOT / "reports" / "funded_upgrade_trajectories_2026-10-29.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible funded 1–50 progression sensitivity for the five GDD profiles.")
    parser.add_argument("--runs-per-strategy", type=int, default=100,
                        help="number of independent seeds per profile (default: 100)")
    parser.add_argument("--seed-start", type=int, default=2026102900,
                        help="first seed of the first profile")
    parser.add_argument("--skip-economy-refresh", action="store_true",
                        help="do not refresh the companion fresh-save economy report")
    args = parser.parse_args()
    report = run_funded_simulation(runs_per_strategy=args.runs_per_strategy, seed_start=args.seed_start)
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(render_markdown(report), encoding="utf-8")
    main_json = ROOT / "reports" / "fresh_save_economy_audit_2026-10-29.json"
    if main_json.is_file() and not args.skip_economy_refresh:
        from scripts.balance.audit_fresh_save_economy import refresh_service_evidence_and_render

        refresh_service_evidence_and_render()
    print(f"JSON: {JSON_PATH}")
    print(f"Markdown: {MD_PATH}")
    for name, row in report["strategies"].items():
        print(json.dumps({
            "strategy": name,
            "n": row["trajectories"],
            "level_50_reached": row["level_50_reached"],
            "level_50_reached_wilson_95": row["level_50_reached_wilson_95"],
            "level_50_day_distribution": row["level_50_day_distribution"],
            "level_50_day_median_ci_95": row["level_50_day_median_ci_95"],
            "investment_target_completed_wilson_95": row["investment_target_completed_wilson_95"],
            "modeled_no_route_stall_14d": row["modeled_no_route_stall_14d"],
            "hard_economic_softlock_status": "not_measured",
            "modeled_milestones": row["modeled_milestones"],
            "capacity_pause_incidence_wilson_95": row["capacity_pause_incidence_wilson_95"],
            "materials_gathered_median_ci_95": row["materials_gathered_median_ci_95"],
            "materials_spent_median_ci_95": row["materials_spent_median_ci_95"],
            "ending_gold_distribution": row["ending_gold_distribution"],
            "ending_gold_median_ci_95": row["ending_gold_median_ci_95"],
            "late_game_last_14_day_net_gold_distribution": row["late_game_last_14_day_net_gold_distribution"],
            "late_game_net_14d_median_ci_95": row["late_game_net_14d_median_ci_95"],
            "purchases": row["purchases"],
            "dominant_activity": row["dominant_activity"],
            "dominant_activity_share_percent_p50": row["dominant_activity_share_percent_p50"],
            "final_material_balances_p50": row["final_material_balances_p50"],
            "final_inventory_capacity_p50": row["final_inventory_capacity_p50"],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
