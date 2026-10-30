"""Service-backed dynamic incidence audit for regional events.

This is a sensitivity scenario, not an estimate of an average fresh campaign:
each deterministic seed starts from a varied near-threshold regional map and
then lets the production CPU-cycle service change it. Trigger decisions,
deadlines and rebellion opportunities are persisted by the production event
service in isolated temporary campaign saves.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from unittest.mock import patch
from uuid import UUID, NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database
from app.models.campaign import CampaignMetadata
from app.models.regional import (
    RegionalCycle,
    RegionalCycleRegion,
    RegionalEventActivity,
    RegionalEvent,
    RegionalRegionState,
    RegionalWorldState,
)
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.services.regional_cycle_service import CYCLE_SECONDS, REGIONS, advance_regional_world
from app.services.regional_event_service import (
    PORTAL_MIN_THREAT,
    REBELLION_CHANCE,
    REBELLION_MAX_SECURITY,
    REBELLION_MIN_THREAT,
    evaluate_open_rebellion,
)
from scripts.balance.funded_progression_simulation import wilson_interval_95

REPORT_JSON = ROOT / "reports" / "regional_event_dynamic_2026-10-29.json"
REPORT_MD = ROOT / "reports" / "regional_event_dynamic_2026-10-29.md"
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
SEED_COUNT = 36
CYCLES = 20


def _campaign_id(seed: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"gim-regional-event-dynamic-v1:{seed}")


def _initial_map(seed: int) -> dict[str, tuple[float, float]]:
    """Vary each region around trigger boundaries; no region is held eligible."""
    rng = random.Random(f"gim-dynamic-initial-map-v1:{seed}")
    return {
        code: (round(rng.uniform(63.0, 97.0), 4), round(rng.uniform(10.0, 45.0), 4))
        for code, _name in REGIONS
    }


def _run_seed(root: Path, seed: int, cycles: int = CYCLES) -> dict[str, object]:
    campaign_id = _campaign_id(seed)
    campaigns = CampaignService(root / f"seed-{seed}")
    with patch("app.services.campaign_service.uuid4", return_value=campaign_id):
        info = campaigns.create_campaign(f"Dynamic incidence seed {seed}", f"Seed guild {seed}")
    campaigns.activate_campaign(info.campaign_id)
    with SessionLocal() as db:
        campaign = db.get(CampaignMetadata, info.campaign_id)
        campaign.created_at_utc = BASE_TIME
        campaign.updated_at_utc = BASE_TIME
        guild, _resources = get_current_guild_context(db, info.campaign_id)
        active = advance_regional_world(db, campaign, guild, BASE_TIME)
        initial = _initial_map(seed)
        regions = list(db.scalars(select(RegionalRegionState).where(
            RegionalRegionState.campaign_id == info.campaign_id,
        )))
        for region in regions:
            region.threat, region.security = initial[region.region_code]
            db.add(region)
        db.commit()

        for cycle_number in range(1, cycles + 1):
            now = BASE_TIME + timedelta(seconds=cycle_number * CYCLE_SECONDS)
            active = advance_regional_world(db, campaign, guild, now)
            evaluate_open_rebellion(db, campaign, active, guild.id, now)
            db.commit()

        rows = list(db.scalars(select(RegionalCycleRegion).join(
            RegionalCycle, RegionalCycle.id == RegionalCycleRegion.cycle_id,
        ).where(
            RegionalCycleRegion.campaign_id == info.campaign_id,
            RegionalCycle.cycle_number.between(0, cycles - 1),
        ).order_by(RegionalCycle.cycle_number, RegionalCycleRegion.region_code)))
        events = list(db.scalars(select(RegionalEvent).where(
            RegionalEvent.campaign_id == info.campaign_id,
        ).order_by(RegionalEvent.event_type, RegionalEvent.trigger_cycle_number, RegionalEvent.region_code)))
        portal_events = [event for event in events if event.event_type == "portal"]
        rebellion_rows = [event for event in events if event.event_type == "rebellion"]

        portal_eligible = [row for row in rows if row.threat_after >= PORTAL_MIN_THREAT]
        portal_rate = len(portal_events) / max(1, len(portal_eligible))
        rebellion_eligible_rows = [
            row for row in rebellion_rows
            if json.loads(row.summary_json or "{}").get("eligible") is True
        ]
        rebellion_candidates = [
            row for row in rebellion_eligible_rows
            if (
                json.loads(row.summary_json or "{}").get("generated_while_campaign_open") is True
                or json.loads(row.summary_json or "{}").get("suppressed_by_global_limit") is True
            )
        ]
        crossings = []
        portal_recovery_cycles = []
        rebellion_recovery_cycles = []
        for code, _name in REGIONS:
            trajectory = [row for row in rows if row.region_code == code]
            portal_runs = _episodes([row.threat_after >= PORTAL_MIN_THREAT for row in trajectory])
            rebellion_runs = _episodes([
                row.threat_after >= REBELLION_MIN_THREAT and row.security_after <= REBELLION_MAX_SECURITY
                for row in trajectory
            ])
            crossings.append({
                "region_code": code,
                "portal_eligible_cycles": sum(row.threat_after >= PORTAL_MIN_THREAT for row in trajectory),
                "portal_eligible_episodes": len(portal_runs),
                "rebellion_eligible_cycles": sum(
                    row.threat_after >= REBELLION_MIN_THREAT and row.security_after <= REBELLION_MAX_SECURITY
                    for row in trajectory
                ),
                "rebellion_eligible_episodes": len(rebellion_runs),
            })
            if portal_runs:
                portal_recovery_cycles.extend(end - start for start, end in portal_runs if end < len(trajectory))
            if rebellion_runs:
                rebellion_recovery_cycles.extend(end - start for start, end in rebellion_runs if end < len(trajectory))
        portal_activities = list(db.scalars(select(RegionalEventActivity).join(
            RegionalEvent, RegionalEvent.id == RegionalEventActivity.event_id,
        ).where(
            RegionalEvent.campaign_id == info.campaign_id,
            RegionalEvent.event_type == "portal",
            RegionalEventActivity.source_type == "cpu_portal",
        )))
        rebellion_activities = list(db.scalars(select(RegionalEventActivity).join(
            RegionalEvent, RegionalEvent.id == RegionalEventActivity.event_id,
        ).where(
            RegionalEvent.campaign_id == info.campaign_id,
            RegionalEvent.event_type == "rebellion",
            RegionalEventActivity.source_type == "cpu_cycle",
        )))
        return {
            "seed": seed,
            "campaign_id": str(campaign_id),
            "cycles": cycles,
            "initial_regional_state": {
                code: {"threat": values[0], "security": values[1]}
                for code, values in initial.items()
            },
            "cpu_actions": sum(row.cpu_actions for row in rows),
            "cpu_successes": sum(row.cpu_successes for row in rows),
            "cpu_failures": sum(row.cpu_failures for row in rows),
            "portal_region_cycle_opportunities": len(portal_eligible),
            "portal_events": len(portal_events),
            "portal_rate": portal_rate,
            "rebellion_region_cycle_opportunities": len(rebellion_eligible_rows),
            "rebellion_candidates": len(rebellion_candidates),
            "rebellion_selected": sum(
                json.loads(row.summary_json or "{}").get("generated_while_campaign_open") is True
                for row in rebellion_candidates
            ),
            "rebellion_suppressed": sum(
                json.loads(row.summary_json or "{}").get("suppressed_by_global_limit") is True
                for row in rebellion_candidates
            ),
            "rebellion_rate": len(rebellion_candidates) / max(1, len(rebellion_eligible_rows)),
            "eligible_region_cycle_count": sum(
                1 for row in rows if row.threat_after >= REBELLION_MIN_THREAT
                and row.security_after <= REBELLION_MAX_SECURITY
            ),
            "eligible_region_cycle_total": len(rows),
            "region_dynamics": crossings,
            "portal_recovery_episode_cycles": portal_recovery_cycles,
            "rebellion_recovery_episode_cycles": rebellion_recovery_cycles,
            "cpu_portal_participations": len(portal_activities),
            "cpu_rebellion_activity_records": len(rebellion_activities),
            "resolved_portal_events": sum(
                event.status == "resolved" for event in portal_events
            ),
            "expired_portal_events": sum(
                event.status == "expired" for event in portal_events
            ),
            "resolved_rebellion_events": sum(
                event.status == "resolved" for event in rebellion_rows
            ),
            "portal_expired_deadline_policy": all(
                json.loads(event.summary_json or "{}").get("deadline_policy") == "continues_offline"
                for event in portal_events
            ),
            "portal_event_examples": [
                {"region": event.region_code, "cycle": event.trigger_cycle_number,
                 "created_at": event.created_at_utc.isoformat(), "expires_at": event.expires_at_utc.isoformat()}
                for event in portal_events[:8]
            ],
        }


def _episodes(values: list[bool]) -> list[tuple[int, int]]:
    episodes: list[tuple[int, int]] = []
    start = None
    for index, eligible in enumerate(values + [False]):
        if eligible and start is None:
            start = index
        elif not eligible and start is not None:
            episodes.append((start, index))
            start = None
    return episodes


def _ci(successes: int, trials: int) -> dict[str, object]:
    return wilson_interval_95(successes, trials)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=SEED_COUNT)
    parser.add_argument("--cycles", type=int, default=CYCLES)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--report-suffix", default="")
    args = parser.parse_args()
    per_seed = []
    with tempfile.TemporaryDirectory(prefix="gim-dynamic-events-") as temp:
        temp_root = Path(temp)
        for seed in range(args.seed_start, args.seed_start + args.seeds):
            try:
                per_seed.append(_run_seed(temp_root, seed, args.cycles))
                print(f"Dynamic event seed {seed - args.seed_start + 1}/{args.seeds} complete", flush=True)
            finally:
                # Windows cannot remove a SQLite save while the active engine
                # still owns a pooled file handle.
                configure_database("sqlite:///:memory:")

    portal_n = sum(int(row["portal_region_cycle_opportunities"]) for row in per_seed)
    portal_events = sum(int(row["portal_events"]) for row in per_seed)
    rebellion_n = sum(int(row["rebellion_region_cycle_opportunities"]) for row in per_seed)
    rebellion_candidates = sum(int(row["rebellion_candidates"]) for row in per_seed)
    region_cycle_n = sum(int(row["eligible_region_cycle_total"]) for row in per_seed)
    eligible_n = sum(int(row["eligible_region_cycle_count"]) for row in per_seed)
    portal_recovery = [
        int(value) for row in per_seed for value in row["portal_recovery_episode_cycles"]
    ]
    rebellion_recovery = [
        int(value) for row in per_seed for value in row["rebellion_recovery_episode_cycles"]
    ]
    initial_maps = {
        json.dumps(row["initial_regional_state"], sort_keys=True)
        for row in per_seed
    }
    initial_threat_values = [
        float(value["threat"])
        for row in per_seed for value in row["initial_regional_state"].values()
    ]
    initial_security_values = [
        float(value["security"])
        for row in per_seed for value in row["initial_regional_state"].values()
    ]
    data = {
        "title": "Regional event dynamic-incidence service audit",
        "date": "2026-10-29",
        "scenario": "deterministic_near_threshold_sensitivity_with_production_cpu_cycles",
        "rules_version": "regional-events-v3",
        "seed_scheme": "UUIDv5(NAMESPACE_URL, gim-regional-event-dynamic-v1:<seed>)",
        "seeds": args.seeds,
        "seed_start": args.seed_start,
        "seed_end": args.seed_start + args.seeds - 1,
        "cycles_per_seed": args.cycles,
        "cycle_hours": CYCLE_SECONDS / 3600,
        "initial_state_policy": "Each seed uses an independent deterministic initial-map RNG (separate from production event and CPU seeds); five regions draw threat 63-97 and security 10-45. No region is pinned eligible. Production CPU plans and regional deltas evolve each state for the full horizon.",
        "unique_initial_maps": len(initial_maps),
        "initial_threat_range_observed": [min(initial_threat_values), max(initial_threat_values)],
        "initial_security_range_observed": [min(initial_security_values), max(initial_security_values)],
        "rebellion_chance": REBELLION_CHANCE,
        "portal_min_threat": PORTAL_MIN_THREAT,
        "rebellion_min_threat": REBELLION_MIN_THREAT,
        "rebellion_max_security": REBELLION_MAX_SECURITY,
        "portal_deadline_hours": 3,
        "portal_deadline_runs_offline": True,
        "cpu_actions": sum(int(row["cpu_actions"]) for row in per_seed),
        "cpu_successes": sum(int(row["cpu_successes"]) for row in per_seed),
        "cpu_failures": sum(int(row["cpu_failures"]) for row in per_seed),
        "cpu_portal_participations": sum(int(row["cpu_portal_participations"]) for row in per_seed),
        "cpu_rebellion_activity_records": sum(int(row["cpu_rebellion_activity_records"]) for row in per_seed),
        "resolved_portal_events": sum(int(row["resolved_portal_events"]) for row in per_seed),
        "expired_portal_events": sum(int(row["expired_portal_events"]) for row in per_seed),
        "resolved_rebellion_events": sum(int(row["resolved_rebellion_events"]) for row in per_seed),
        "portal": {
            "events": portal_events,
            "eligible_region_cycles": portal_n,
            "empirical_rate": round(portal_events / max(1, portal_n), 5),
            "wilson_95": _ci(portal_events, portal_n),
        },
        "rebellion": {
            "candidate_rolls": rebellion_candidates,
            "eligible_region_cycle_rolls": rebellion_n,
            "empirical_rate": round(rebellion_candidates / max(1, rebellion_n), 5),
            "wilson_95": _ci(rebellion_candidates, rebellion_n),
            "selected": sum(int(row["rebellion_selected"]) for row in per_seed),
            "suppressed_simultaneous_candidates": sum(int(row["rebellion_suppressed"]) for row in per_seed),
            "dynamic_eligible_region_cycle_fraction": round(eligible_n / max(1, region_cycle_n), 5),
            "all_region_cycles": region_cycle_n,
        },
        "recovery": {
            "portal_eligibility": {
                "completed_episodes": len(portal_recovery),
                "episode_length_cycles_mean": round(mean(portal_recovery), 3) if portal_recovery else None,
                "episode_length_cycles_max": max(portal_recovery, default=None),
            },
            "rebellion_eligibility": {
                "completed_episodes": len(rebellion_recovery),
                "episode_length_cycles_mean": round(mean(rebellion_recovery), 3) if rebellion_recovery else None,
                "episode_length_cycles_max": max(rebellion_recovery, default=None),
            },
            "note": "Episode duration ends when a real CPU-updated snapshot falls below the relevant threshold; episodes still open at the horizon are right-censored.",
        },
        "replay": {
            "production_catch_up": "advance_regional_world processes every missed cycle in order; event triggers use deterministic campaign/cycle/region seeds.",
            "prior_replay_audit": "docs/work2_regional_validation.md documents direct versus staged advancement with 49,765 canonical records.",
            "offline_portal_deadline": "The portal expiry timestamp is created_at + 3h and expire_due_events runs during catch-up; new entries after expiry are blocked.",
        },
        "limitations": [
            "This is a deliberately near-threshold sensitivity scenario, not the incidence rate of a typical fresh campaign.",
            "The initial regional states are scenario inputs; all measured post-start movement is produced by the production CPU cycle service.",
            "Rebellion checks occur once per simulated open cycle and obey the one-active-global-event cap; candidate rate is measured only for eligible rows actually rolled by the service.",
            "No player run decisions, player portal entries/rewards, or long-term economy sinks are simulated; CPU event participation is measured separately in the lifecycle supplement.",
            "Wilson intervals quantify binomial sampling uncertainty only; deterministic seed correlation and scenario selection are not represented by those intervals.",
        ],
        "per_seed": per_seed,
    }
    report_json = REPORT_JSON if not args.report_suffix else REPORT_JSON.with_name(
        REPORT_JSON.stem.replace("_2026-10-29", f"_{args.report_suffix}_2026-10-29") + REPORT_JSON.suffix
    )
    report_md = REPORT_MD if not args.report_suffix else REPORT_MD.with_name(
        REPORT_MD.stem.replace("_2026-10-29", f"_{args.report_suffix}_2026-10-29") + REPORT_MD.suffix
    )
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    portal_ci = data["portal"]["wilson_95"]
    rebellion_ci = data["rebellion"]["wilson_95"]
    md = [
        "# Regional event dynamic-incidence audit",
        "",
        f"Scenario: **{args.seeds} deterministic seeds ({args.seed_start}–{args.seed_start + args.seeds - 1}) × {args.cycles} six-hour cycles**, with {len(initial_maps)} unique initial regional maps. This is a near-threshold sensitivity scenario; it is not the average fresh-campaign incidence.",
        "",
        f"CPU plans applied: **{data['cpu_actions']:,}** actions ({data['cpu_successes']:,} successes, {data['cpu_failures']:,} failures). CPU portal entries: **{data['cpu_portal_participations']}**; CPU rebellion activity records: **{data['cpu_rebellion_activity_records']}**. Resolved portal/rebellion events: **{data['resolved_portal_events']} / {data['resolved_rebellion_events']}**; expired portals: **{data['expired_portal_events']}**. Region states evolved through the production regional cycle service.",
        "",
        "| Trigger | Events/candidates | Eligible region-cycles actually rolled | Rate | Wilson 95% |",
        "|---|---:|---:|---:|---:|",
        f"| Portal | {portal_events} | {portal_n} | {data['portal']['empirical_rate']:.2%} | {portal_ci['lower_percent']:.2f}%–{portal_ci['upper_percent']:.2f}% |",
        f"| Rebellion candidates | {rebellion_candidates} | {rebellion_n} | {data['rebellion']['empirical_rate']:.2%} | {rebellion_ci['lower_percent']:.2f}%–{rebellion_ci['upper_percent']:.2f}% |",
        "",
        f"Dynamic rebellion-eligible snapshots: **{eligible_n}/{region_cycle_n} ({data['rebellion']['dynamic_eligible_region_cycle_fraction']:.2%})**. Selected rebellions: {data['rebellion']['selected']}; simultaneous candidates suppressed by the global cap: {data['rebellion']['suppressed_simultaneous_candidates']}.",
        "",
        f"Portal eligibility recovery: **{len(portal_recovery)}** completed episodes, mean **{data['recovery']['portal_eligibility']['episode_length_cycles_mean']} cycles**, max **{data['recovery']['portal_eligibility']['episode_length_cycles_max']}**. Rebellion eligibility recovery: **{len(rebellion_recovery)}** completed episodes, mean **{data['recovery']['rebellion_eligibility']['episode_length_cycles_mean']} cycles**, max **{data['recovery']['rebellion_eligibility']['episode_length_cycles_max']}**. Right-censored episodes are excluded.",
        "",
        "## Reproducibility and policy",
        "",
        f"Campaign IDs use `{data['seed_scheme']}`. Initial maps use a separate deterministic RNG per seed; observed initial threat range is {data['initial_threat_range_observed']} and security range is {data['initial_security_range_observed']}. No region is pinned eligible. Production CPU plans update all regions for {args.cycles} cycles. Rebellion chance is **{REBELLION_CHANCE:.0%} per eligible region-cycle roll**; portal entry deadlines remain **3 hours** and continue offline.",
        "",
        "Catch-up processes missed cycles in order. The prior direct-versus-staged replay audit documented in `docs/work2_regional_validation.md` compared 49,765 canonical records. Portal expiry runs during each processed cycle; a portal born more than 3 hours before return expires before entry is offered. The service expiry case is covered in `tests/test_regional_event_service.py`.",
        "",
        "## Limitations",
        "",
    ] + [f"- {limitation}" for limitation in data["limitations"]] + [
        "",
        "Per-seed inputs, outcomes, event timestamps, and regional episode counts are in the adjacent JSON.",
    ]
    report_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({key: data[key] for key in ("seeds", "cycles_per_seed", "cpu_actions", "portal", "rebellion", "recovery")}, indent=2))


if __name__ == "__main__":
    main()
