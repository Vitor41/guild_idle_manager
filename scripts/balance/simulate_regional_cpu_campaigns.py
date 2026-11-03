"""Run deterministic 100-cycle CPU/event balance campaigns and write a compact report."""

from __future__ import annotations

import json
import math
import tempfile
from collections import Counter
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database
from app.models.campaign import CampaignMetadata
from app.models.regional import (
    RegionalCpuCyclePlan,
    RegionalCycle,
    RegionalCycleRegion,
    RegionalEvent,
    RegionalGuildState,
    RegionalRegionState,
)
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.services import regional_cycle_service
from app.services import regional_event_service
from app.services.regional_cycle_service import (
    CYCLE_SECONDS,
    REGIONS,
    advance_regional_world,
    get_regional_board,
    regional_cpu_action_probability,
)


ROOT = Path(__file__).resolve().parents[2]
SEEDS = tuple(range(2026110301, 2026110321))
HORIZON = 100


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _event_was_opened(event: RegionalEvent) -> bool:
    return event.status not in {"not_triggered", "suppressed"}


def run_campaign(seed: int, saves_root: Path) -> dict:
    campaign_id = str(UUID(int=seed))
    campaigns = CampaignService(saves_root)
    with patch("app.services.campaign_service.uuid4", return_value=UUID(campaign_id)):
        created = campaigns.create_campaign(f"CPU balance {seed}", f"Guilda {seed}")
    campaigns.activate_campaign(created.campaign_id)

    with SessionLocal() as db:
        campaign = db.get(CampaignMetadata, created.campaign_id)
        guild, _resources = get_current_guild_context(db, created.campaign_id)
        start = campaign.created_at_utc
        advance_regional_world(db, campaign, guild, start)
        get_regional_board(db, campaign, guild, start)
        active_max = 0
        rebellion_window_rolls = 0
        for cycle_index in range(1, HORIZON + 1):
            now = start + timedelta(seconds=cycle_index * CYCLE_SECONDS)
            advance_regional_world(db, campaign, guild, now)
            get_regional_board(db, campaign, guild, now)
            active_count = db.scalar(select(RegionalEvent.id).where(
                RegionalEvent.campaign_id == created.campaign_id,
                RegionalEvent.event_type == "rebellion",
                RegionalEvent.status.in_(("active", "in_progress")),
            ).limit(2))
            if active_count is not None:
                active_max = max(active_max, len(list(db.scalars(select(RegionalEvent.id).where(
                    RegionalEvent.campaign_id == created.campaign_id,
                    RegionalEvent.event_type == "rebellion",
                    RegionalEvent.status.in_(("active", "in_progress")),
                )))))

        events = list(db.scalars(select(RegionalEvent).where(
            RegionalEvent.campaign_id == created.campaign_id,
            RegionalEvent.trigger_cycle_number < HORIZON,
        )))
        opened = [event for event in events if _event_was_opened(event)]
        first_by_type = {}
        for event_type in ("portal", "rebellion"):
            matches = [event.trigger_cycle_number for event in opened if event.event_type == event_type]
            first_by_type[event_type] = min(matches) if matches else None
        opened_by_type = Counter(event.event_type for event in opened)

        selected_rolls = 0
        for event in events:
            if event.event_type == "rebellion":
                summary = json.loads(event.summary_json or "{}")
                selected_rolls += int(bool(summary.get("roll_selected")))
        rebellion_window_rolls = selected_rolls

        regions = list(db.scalars(select(RegionalCycleRegion).where(
            RegionalCycleRegion.campaign_id == created.campaign_id,
            RegionalCycleRegion.cycle_id.in_(select(RegionalCycle.id).where(
                RegionalCycle.campaign_id == created.campaign_id,
                RegionalCycle.cycle_number < HORIZON,
            )),
        )))
        cycle_numbers = {
            row.id: row.cycle_number
            for row in db.scalars(select(RegionalCycle).where(
                RegionalCycle.campaign_id == created.campaign_id,
                RegionalCycle.cycle_number < HORIZON,
            ))
        }
        region_metrics = {}
        pressure_counts = {
            "security_at_floor": [0] * HORIZON,
            "threat_at_least_85": [0] * HORIZON,
            "joint_rebellion_vulnerability": [0] * HORIZON,
        }
        regional_pressure_streaks = {}
        home_code = next(code for code, name in REGIONS if name == campaign.home_region)
        for code, _name in REGIONS:
            snapshots = [row for row in regions if row.region_code == code]
            actions = sum(row.cpu_actions for row in snapshots)
            portal_cycles = sorted(
                event.trigger_cycle_number for event in opened
                if event.event_type == "portal" and event.region_code == code
            )
            portal_gaps = [right - left for left, right in zip(portal_cycles, portal_cycles[1:])]
            ordered_snapshots = sorted(snapshots, key=lambda row: cycle_numbers.get(row.cycle_id, -1))
            pressure_states = {
                "security_at_floor": [
                    row.security_after <= regional_cycle_service.REGIONAL_ACTIVE_SECURITY_FLOOR
                    for row in ordered_snapshots
                ],
                "threat_at_least_85": [row.threat_after >= 85 for row in ordered_snapshots],
                "joint_rebellion_vulnerability": [
                    row.threat_after >= 85 and row.security_after <= 25 for row in ordered_snapshots
                ],
            }
            for key, states in pressure_states.items():
                for row, active in zip(ordered_snapshots, states):
                    if active:
                        cycle_number = cycle_numbers.get(row.cycle_id)
                        if cycle_number is not None:
                            pressure_counts[key][cycle_number] += 1
            regional_pressure_streaks[code] = {}
            for key, states in pressure_states.items():
                current_streak = longest_streak = 0
                for active in states:
                    current_streak = current_streak + 1 if active else 0
                    longest_streak = max(longest_streak, current_streak)
                regional_pressure_streaks[code][key] = longest_streak
            targeted_windows = sum(
                bool(json.loads(row.summary_json or "{}").get("gradual_pressure", {}).get("targeted"))
                for row in snapshots
            )
            region_state = db.scalar(select(RegionalRegionState).where(
                RegionalRegionState.campaign_id == created.campaign_id,
                RegionalRegionState.region_code == code,
            ))
            region_metrics[code] = {
                "actions": actions,
                "actions_per_cycle": round(actions / HORIZON, 2),
                "cycles_with_cpu_activity": sum(row.cpu_actions > 0 for row in snapshots),
                "minimum_actions_per_cycle": min((row.cpu_actions for row in snapshots), default=0),
                "security_floor_cycles": sum(
                    row.security_after <= regional_cycle_service.REGIONAL_ACTIVE_SECURITY_FLOOR
                    for row in snapshots
                ),
                "threat_cap_cycles": sum(row.threat_after >= 100 for row in snapshots),
                "pressure_target_cycles": targeted_windows,
                "final_security": round(region_state.security, 2),
                "final_threat": round(region_state.threat, 2),
                "portal_count": len(portal_cycles),
                "portal_cycles": portal_cycles,
                "portal_intervals_cycles": portal_gaps,
                "cpu_actions_by_cycle": [row.cpu_actions for row in ordered_snapshots],
                "rebellion_count": sum(
                    event.event_type == "rebellion" and event.region_code == code for event in opened
                ),
                "home_region": code == home_code,
            }
        plans = list(db.scalars(select(RegionalCpuCyclePlan).where(
            RegionalCpuCyclePlan.campaign_id == created.campaign_id,
        )))
        old_baseline_by_region = Counter()
        for state in db.scalars(select(RegionalGuildState).where(
            RegionalGuildState.campaign_id == created.campaign_id,
            RegionalGuildState.guild_id.is_(None),
            RegionalGuildState.active.is_(True),
        )):
            probability = regional_cpu_action_probability(
                created.campaign_id, state, "vigilia-v4",
            )
            old_baseline_by_region[state.region_code] += (
                1 + probability if state.profile == "strong" else 1
            )
        cpu_actions = sum(plan.resolved_actions or 0 for plan in plans)
        cpu_successes = sum(plan.successes for plan in plans)
        cpu_failures = sum(plan.failures for plan in plans)
        strong_hires = [
            db.get(RegionalCycle, plan.cycle_id).cycle_number
            for plan in plans
            if plan.hired_count and db.get(RegionalGuildState, plan.guild_state_id).profile == "strong"
        ]
        final_security = [value["final_security"] for value in region_metrics.values()]
        final_threat = [value["final_threat"] for value in region_metrics.values()]
        cycles_with_threshold_eligibility = 0
        for cycle_number in range(HORIZON):
            chosen = [event for event in events if event.event_type == "rebellion"
                      and event.trigger_cycle_number == cycle_number
                      and json.loads(event.summary_json or "{}").get("threshold_eligible")]
            if chosen:
                cycles_with_threshold_eligibility += 1
        result = {
            "seed": seed,
            "campaign_id": created.campaign_id,
            "home_region": home_code,
            "first_portal_cycle": first_by_type["portal"],
            "first_rebellion_cycle": first_by_type["rebellion"],
            "opened_portals": opened_by_type["portal"],
            "opened_rebellions": opened_by_type["rebellion"],
            "selected_rebellion_roll_windows": rebellion_window_rolls,
            "cycles_with_vulnerable_region": cycles_with_threshold_eligibility,
            "max_simultaneous_rebellions": active_max,
            "cpu_actions_total": cpu_actions,
            "cpu_actions_per_cycle_global": round(cpu_actions / HORIZON, 2),
            "cpu_successes": cpu_successes,
            "cpu_failures": cpu_failures,
            "cpu_success_rate": round(cpu_successes / max(1, cpu_successes + cpu_failures), 4),
            "first_strong_hire_cycle": min(strong_hires) if strong_hires else None,
            "regional": region_metrics,
            "regional_pressure_counts_per_cycle": pressure_counts,
            "regional_pressure_longest_streaks": regional_pressure_streaks,
            "old_v4_expected_actions_per_cycle_by_region": {
                code: round(old_baseline_by_region[code], 2) for code, _name in REGIONS
            },
            "final_security_min_max": [min(final_security), max(final_security)],
            "final_threat_min_max": [min(final_threat), max(final_threat)],
        }
    campaigns.close_active_campaign(created.campaign_id)
    return result


def build_report(results: list[dict]) -> tuple[dict, str]:
    portal_cycles = [row["first_portal_cycle"] for row in results if row["first_portal_cycle"] is not None]
    rebellion_cycles = [row["first_rebellion_cycle"] for row in results
                        if row["first_rebellion_cycle"] is not None]
    report = {
        "campaigns": len(results),
        "cycles_per_campaign": HORIZON,
        "rules": {
            "rebellion_chance": 0.02,
            "rebellion_region_cooldown_cycles": 5,
            "portal_region_cooldown_cycles": regional_event_service.PORTAL_REGION_COOLDOWN_CYCLES,
            "one_rebellion_roll_region_per_cycle_max": 1,
            "one_pressure_target_per_cycle": True,
            "pressure_target_window_cycles": regional_cycle_service.REGIONAL_PRESSURE_WINDOW_CYCLES,
            "regional_pressure_target_threat": [
                regional_cycle_service.REGIONAL_GRADUAL_PRESSURE_MIN,
                regional_cycle_service.REGIONAL_GRADUAL_PRESSURE_MAX,
            ],
            "regional_pressure_target_security_loss": [
                regional_cycle_service.REGIONAL_GRADUAL_SECURITY_PRESSURE_MIN,
                regional_cycle_service.REGIONAL_GRADUAL_SECURITY_PRESSURE_MAX,
            ],
            "rebellion_threat_maintenance": regional_cycle_service.REGIONAL_GRADUAL_MAINTENANCE_PRESSURE,
            "threat_pressure_soft_cap": regional_cycle_service.REGIONAL_GRADUAL_THREAT_SOFT_CAP,
            "off_window_threat_recovery_threshold": regional_cycle_service.REGIONAL_GRADUAL_RECOVERY_THRESHOLD,
            "off_window_threat_recovery": regional_cycle_service.REGIONAL_GRADUAL_RECOVERY_PRESSURE,
            "off_window_security_recovery": regional_cycle_service.REGIONAL_GRADUAL_SECURITY_RECOVERY,
            "off_window_security_recovery_ceiling": regional_cycle_service.REGIONAL_GRADUAL_SECURITY_RECOVERY_CEILING,
            "active_pressure_target_security_floor": regional_cycle_service.REGIONAL_ACTIVE_SECURITY_FLOOR,
            "cpu_action_throughput": "available offers, mercenary roster availability, durations, and 1h player priority",
        },
        "first_portal_cycles": portal_cycles,
        "first_rebellion_cycles": rebellion_cycles,
        "campaigns_with_portal": len(portal_cycles),
        "campaigns_without_portal": len(results) - len(portal_cycles),
        "campaigns_with_rebellion": len(rebellion_cycles),
        "mean_selected_rebellion_roll_windows": round(
            sum(row["selected_rebellion_roll_windows"] for row in results) / len(results), 2,
        ),
        "mean_cycles_with_vulnerable_region": round(
            sum(row["cycles_with_vulnerable_region"] for row in results) / len(results), 2,
        ),
        "simultaneous_regional_pressure": {
            key: {
                "p50_regions_per_cycle": _percentile(
                    [count for row in results for count in row["regional_pressure_counts_per_cycle"][key]], 0.5,
                ),
                "p90_regions_per_cycle": _percentile(
                    [count for row in results for count in row["regional_pressure_counts_per_cycle"][key]], 0.9,
                ),
                "maximum_regions_per_cycle": max(
                    count for row in results for count in row["regional_pressure_counts_per_cycle"][key]
                ),
                "cycles_with_two_or_more_regions": sum(
                    count >= 2 for row in results for count in row["regional_pressure_counts_per_cycle"][key]
                ),
            }
            for key in (
                "security_at_floor",
                "threat_at_least_85",
                "joint_rebellion_vulnerability",
            )
        },
        "total_opened_portals": sum(row["opened_portals"] for row in results),
        "total_opened_rebellions": sum(row["opened_rebellions"] for row in results),
        "mean_cpu_success_rate": round(sum(row["cpu_success_rate"] for row in results) / len(results), 4),
        "maximum_simultaneous_rebellions": max(
            row["max_simultaneous_rebellions"] for row in results
        ),
        "mean_cpu_actions_per_cycle_global": round(
            sum(row["cpu_actions_per_cycle_global"] for row in results) / len(results), 2,
        ),
        "security_final_min_max": [
            min(row["final_security_min_max"][0] for row in results),
            max(row["final_security_min_max"][1] for row in results),
        ],
        "threat_final_min_max": [
            min(row["final_threat_min_max"][0] for row in results),
            max(row["final_threat_min_max"][1] for row in results),
        ],
        "actions_per_region_mean": {
            code: round(sum(row["regional"][code]["actions_per_cycle"] for row in results)
                        / len(results), 2)
            for code, _name in REGIONS
        },
        "cpu_actions_per_region_cycle": {
            code: {
                "p50": _percentile(
                    [count for row in results for count in row["regional"][code]["cpu_actions_by_cycle"]], 0.5,
                ),
                "p90": _percentile(
                    [count for row in results for count in row["regional"][code]["cpu_actions_by_cycle"]], 0.9,
                ),
                "maximum": max(
                    count for row in results for count in row["regional"][code]["cpu_actions_by_cycle"]
                ),
            }
            for code, _name in REGIONS
        },
        "per_region": {
            code: {
                "campaigns_without_portal": sum(
                    row["regional"][code]["portal_count"] == 0 for row in results
                ),
                "mean_portals_per_campaign": round(
                    sum(row["regional"][code]["portal_count"] for row in results) / len(results), 2,
                ),
                "median_portals_per_campaign": _percentile(
                    [row["regional"][code]["portal_count"] for row in results], 0.5,
                ),
                "p90_portals_per_campaign": _percentile(
                    [row["regional"][code]["portal_count"] for row in results], 0.9,
                ),
                "median_portal_interval_cycles": _percentile(
                    [gap for row in results for gap in row["regional"][code]["portal_intervals_cycles"]], 0.5,
                ),
                "p90_portal_interval_cycles": _percentile(
                    [gap for row in results for gap in row["regional"][code]["portal_intervals_cycles"]], 0.9,
                ),
                "mean_portal_interval_cycles": round(
                    sum(gap for row in results for gap in row["regional"][code]["portal_intervals_cycles"])
                    / max(1, sum(len(row["regional"][code]["portal_intervals_cycles"])
                                 for row in results)), 2,
                ),
                "mean_security_floor_cycles": round(
                    sum(row["regional"][code]["security_floor_cycles"] for row in results) / len(results), 2,
                ),
                "mean_threat_cap_cycles": round(
                    sum(row["regional"][code]["threat_cap_cycles"] for row in results) / len(results), 2,
                ),
                "mean_pressure_target_cycles": round(
                    sum(row["regional"][code]["pressure_target_cycles"] for row in results) / len(results), 2,
                ),
                "mean_max_consecutive_security_floor_cycles": round(
                    sum(row["regional_pressure_longest_streaks"][code]["security_at_floor"]
                        for row in results) / len(results), 2,
                ),
                "max_consecutive_security_floor_cycles": max(
                    row["regional_pressure_longest_streaks"][code]["security_at_floor"] for row in results
                ),
                "mean_max_consecutive_threat_85_cycles": round(
                    sum(row["regional_pressure_longest_streaks"][code]["threat_at_least_85"]
                        for row in results) / len(results), 2,
                ),
                "max_consecutive_threat_85_cycles": max(
                    row["regional_pressure_longest_streaks"][code]["threat_at_least_85"] for row in results
                ),
                "mean_max_consecutive_joint_vulnerability_cycles": round(
                    sum(row["regional_pressure_longest_streaks"][code]["joint_rebellion_vulnerability"]
                        for row in results) / len(results), 2,
                ),
                "max_consecutive_joint_vulnerability_cycles": max(
                    row["regional_pressure_longest_streaks"][code]["joint_rebellion_vulnerability"]
                    for row in results
                ),
            }
            for code, _name in REGIONS
        },
        "minimum_region_cycles_with_cpu_activity": min(
            value["cycles_with_cpu_activity"]
            for row in results for value in row["regional"].values()
        ),
        "campaign_results": results,
    }
    lines = [
        "# Regional CPU event balance — 20 campaigns",
        "",
        "Deterministic SQLite campaigns; 100 six-hour cycles each; player takes no actions. "
        "Events, timers, CPU plans, snapshots and region state use the live services.",
        "",
        f"- Campaigns with at least one portal: **{report['campaigns_with_portal']}/{len(results)}**; "
        f"without portal: **{report['campaigns_without_portal']}**; "
        f"opened portals: **{report['total_opened_portals']}**; first portal cycles: `{portal_cycles}`.",
        f"- Campaigns with at least one rebellion: **{report['campaigns_with_rebellion']}/{len(results)}**; "
        f"opened rebellions: **{report['total_opened_rebellions']}**; first rebellion cycles: `{rebellion_cycles}`; "
        f"mean selected rolls: **{report['mean_selected_rebellion_roll_windows']}**; "
        f"mean cycles with a vulnerable region: **{report['mean_cycles_with_vulnerable_region']}**.",
        f"- Maximum simultaneous active global rebellions: **{report['maximum_simultaneous_rebellions']}**.",
        f"- Mean CPU success rate: **{report['mean_cpu_success_rate']:.1%}**.",
        f"- Mean CPU actions per global Vigília: **{report['mean_cpu_actions_per_cycle_global']}** "
        "with throughput set by eligible offers, available mercenaries, activity durations, and 1h player priority.",
        f"- Minimum regional Vigílias with at least one CPU action: "
        f"**{report['minimum_region_cycles_with_cpu_activity']}/{HORIZON}**.",
        f"- Final security range across all regions/campaigns: **{report['security_final_min_max'][0]}–"
        f"{report['security_final_min_max'][1]}**; threat range: **{report['threat_final_min_max'][0]}–"
        f"{report['threat_final_min_max'][1]}**.",
        "- Concurrent regional pressure per cycle (p50/p90/max regions): "
        + "; ".join(
            f"{key}: {value['p50_regions_per_cycle']}/{value['p90_regions_per_cycle']}/"
            f"{value['maximum_regions_per_cycle']}"
            for key, value in report["simultaneous_regional_pressure"].items()
        ) + ".",
        "",
        "| Region | Mean CPU actions/cycle | 0.5.4 expected actions/cycle |",
        "|---|---:|---:|",
    ]
    for code, name in REGIONS:
        old_mean = round(sum(row["old_v4_expected_actions_per_cycle_by_region"][code]
                             for row in results) / len(results), 2)
        lines.append(f"| {name} (`{code}`) | {report['actions_per_region_mean'][code]} | {old_mean} |")
    lines.extend([
        "",
        "| Região | Campanhas sem portal | Portais/campanha mediana (p90) | Intervalo portal mediano (p90) | Janelas pressão | Ciclos piso 20 | Ameaça 100 | Ações CPU/ciclo (p50/p90/máx.) | Seq. piso (média/máx.) | Seq. ameaça ≥85 (média/máx.) | Seq. vulnerável (média/máx.) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for code, name in REGIONS:
        values = report["per_region"][code]
        cpu_actions = report["cpu_actions_per_region_cycle"][code]
        lines.append(
            f"| {name} (`{code}`) | {values['campaigns_without_portal']} | "
            f"{values['median_portals_per_campaign']} ({values['p90_portals_per_campaign']}) | "
            f"{values['median_portal_interval_cycles']} ({values['p90_portal_interval_cycles']}) | "
            f"{values['mean_pressure_target_cycles']} | "
            f"{values['mean_security_floor_cycles']} | {values['mean_threat_cap_cycles']} | "
            f"{cpu_actions['p50']}/{cpu_actions['p90']}/{cpu_actions['maximum']} | "
            f"{values['mean_max_consecutive_security_floor_cycles']}/{values['max_consecutive_security_floor_cycles']} | "
            f"{values['mean_max_consecutive_threat_85_cycles']}/{values['max_consecutive_threat_85_cycles']} | "
            f"{values['mean_max_consecutive_joint_vulnerability_cycles']}/"
            f"{values['max_consecutive_joint_vulnerability_cycles']} |"
        )
    lines.extend([
        "",
        "| Seed | Portal(s) | Rebelião(ões) | 1º portal | 1ª rebelião | Ações CPU/ciclo | Sucesso CPU | Seg. final min–max | Ameaça final min–max |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in results:
        lines.append(
            f"| {row['seed']} | {row['opened_portals']} | {row['opened_rebellions']} | "
            f"{row['first_portal_cycle'] if row['first_portal_cycle'] is not None else '—'} | "
            f"{row['first_rebellion_cycle'] if row['first_rebellion_cycle'] is not None else '—'} | "
            f"{row['cpu_actions_per_cycle_global']} | {row['cpu_success_rate']:.1%} | {row['final_security_min_max'][0]}–"
            f"{row['final_security_min_max'][1]} | {row['final_threat_min_max'][0]}–"
            f"{row['final_threat_min_max'][1]} |"
        )
    lines.extend([
        "",
        f"Each {regional_cycle_service.REGIONAL_PRESSURE_WINDOW_CYCLES}-cycle pressure window targets one region; "
        "off-window threat and security recovery limits "
        "overlapping crises. The cooldown permits at most one hidden regional rebellion roll per eligible "
        "cycle. CPU action scheduling continues in all five regions.",
        "",
    ])
    return report, "\n".join(lines)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="regional-cpu-balance-") as temp_dir:
        saves_root = Path(temp_dir) / "saves"
        results = []
        try:
            for index, seed in enumerate(SEEDS, start=1):
                result = run_campaign(seed, saves_root)
                results.append(result)
                print(
                    f"[{index}/{len(SEEDS)}] seed={seed} portals={result['opened_portals']} "
                    f"rebellions={result['opened_rebellions']} "
                    f"security={result['final_security_min_max']} threat={result['final_threat_min_max']}",
                    flush=True,
                )
        finally:
            configure_database("sqlite:///:memory:")
    report, markdown = build_report(results)
    json_path = ROOT / "reports" / "regional_cpu_incidence_2026-11-03.json"
    markdown_path = ROOT / "reports" / "regional_cpu_incidence_2026-11-03.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown, encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "campaign_results"},
                     ensure_ascii=False, indent=2))
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")


if __name__ == "__main__":
    main()
