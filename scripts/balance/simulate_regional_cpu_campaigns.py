"""Run deterministic 100-cycle CPU/event balance campaigns and write a compact report."""

from __future__ import annotations

import argparse
import json
import hashlib
import math
import shutil
import sqlite3
import tempfile
from collections import Counter, defaultdict
from contextlib import closing
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


def _clone_campaign_database(template_database: Path, campaign_database: Path, campaign_id: str) -> None:
    """Clone one fully seeded disposable save and re-key its campaign-owned rows."""
    shutil.copy2(template_database, campaign_database)
    with closing(sqlite3.connect(campaign_database)) as connection:
        template_id = connection.execute(
            "SELECT campaign_id FROM campaign_metadata LIMIT 1"
        ).fetchone()[0]
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        for table in tables:
            columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
            if "campaign_id" in columns:
                connection.execute(
                    f'UPDATE "{table}" SET campaign_id = ? WHERE campaign_id = ?',
                    (campaign_id, template_id),
                )
        home_regions = (
            "Vale da Fronteira", "Bosque de Âmbar", "Costa das Brumas",
            "Terras de Cinza", "Picos do Norte",
        )
        home_index = int.from_bytes(hashlib.sha256(campaign_id.encode("utf-8")).digest()[:4], "big") % len(home_regions)
        connection.execute(
            "UPDATE campaign_metadata SET home_region = ?, campaign_name = ? WHERE campaign_id = ?",
            (home_regions[home_index], f"CPU balance {campaign_id}", campaign_id),
        )
        connection.commit()


def run_campaign(seed: int, saves_root: Path, template_database: Path | None = None) -> dict:
    campaign_id = str(UUID(int=seed))
    campaigns = CampaignService(saves_root)
    if template_database is None:
        with patch("app.services.campaign_service.uuid4", return_value=UUID(campaign_id)):
            created = campaigns.create_campaign(f"CPU balance {seed}", f"Guilda {seed}")
    else:
        saves_root.mkdir(parents=True, exist_ok=True)
        target_database = saves_root / f"{campaign_id}.db"
        _clone_campaign_database(template_database, target_database, campaign_id)
        created = campaigns.inspect_campaign(campaign_id)
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
        cycle_records = {
            row.cycle_number: row
            for row in db.scalars(select(RegionalCycle).where(
                RegionalCycle.campaign_id == created.campaign_id,
                RegionalCycle.cycle_number < HORIZON,
            ))
        }
        rebellion_events_by_cycle = defaultdict(list)
        for event in events:
            if event.event_type == "rebellion":
                rebellion_events_by_cycle[event.trigger_cycle_number].append(event)
        regional_funnel = {code: {
            "pressure_target_cycles": 0,
            "eligible_region_cycles": 0,
            "cooldown_veto_region_cycles": 0,
            "single_roll_cap_veto_region_cycles": 0,
            "selected_rolls": 0,
            "rng_failures": 0,
            "rebellions_opened": 0,
        } for code, _name in REGIONS}
        rebellion_funnel_by_cycle = []
        last_selected_cycle_by_region: dict[str, int] = {}
        for cycle_number in range(HORIZON):
            snapshots = [row for row in regions if cycle_numbers.get(row.cycle_id) == cycle_number]
            pressure_regions = []
            eligible_regions = []
            for snapshot in snapshots:
                detail = json.loads(snapshot.summary_json or "{}").get("gradual_pressure", {})
                if detail.get("targeted"):
                    pressure_regions.append(snapshot.region_code)
                    regional_funnel[snapshot.region_code]["pressure_target_cycles"] += 1
                if snapshot.threat_after >= regional_event_service.REBELLION_MIN_THREAT \
                        and snapshot.security_after <= regional_event_service.REBELLION_MAX_SECURITY:
                    eligible_regions.append(snapshot.region_code)
                    regional_funnel[snapshot.region_code]["eligible_region_cycles"] += 1
            cycle_events = rebellion_events_by_cycle.get(cycle_number, [])
            event_summaries = [(event.region_code, json.loads(event.summary_json or "{}"))
                               for event in cycle_events]
            selected_regions = [code for code, summary in event_summaries if summary.get("roll_selected")]
            opened_regions = [event.region_code for event in cycle_events if _event_was_opened(event)]
            cycle_record = cycle_records.get(cycle_number)
            active_prior_event = any(
                event.trigger_cycle_number < cycle_number
                and event.expires_at_utc is not None
                and regional_cycle_service._utc(event.expires_at_utc)
                    > regional_cycle_service._utc(cycle_record.starts_at_utc)
                for event in events
                if event.event_type == "rebellion"
            )
            global_veto = bool(eligible_regions and not cycle_events and active_prior_event)
            cooldown_regions = []
            available_regions = []
            if eligible_regions and not global_veto:
                for code in eligible_regions:
                    last_roll = last_selected_cycle_by_region.get(code)
                    if last_roll is not None and cycle_number - last_roll <= \
                            regional_event_service.REBELLION_REGION_ROLL_COOLDOWN_CYCLES:
                        cooldown_regions.append(code)
                    else:
                        available_regions.append(code)
            selected_region = selected_regions[0] if selected_regions else None
            cap_veto_regions = [code for code in available_regions if code != selected_region]
            if selected_region is not None:
                regional_funnel[selected_region]["selected_rolls"] += 1
                if selected_region not in opened_regions:
                    regional_funnel[selected_region]["rng_failures"] += 1
                last_selected_cycle_by_region[selected_region] = cycle_number
            for code in cooldown_regions:
                regional_funnel[code]["cooldown_veto_region_cycles"] += 1
            for code in cap_veto_regions:
                regional_funnel[code]["single_roll_cap_veto_region_cycles"] += 1
            for code in opened_regions:
                regional_funnel[code]["rebellions_opened"] += 1
            rebellion_funnel_by_cycle.append({
                "cycle": cycle_number,
                "pressure_target_regions": sorted(pressure_regions),
                "threshold_eligible_regions": sorted(eligible_regions),
                "eligible_region_count": len(eligible_regions),
                "selected_roll_region": selected_region,
                "selected_roll_count": len(selected_regions),
                "rng_failure": bool(selected_region and selected_region not in opened_regions),
                "rebellion_opened_regions": sorted(opened_regions),
                "global_limit_veto": global_veto,
                "global_limit_veto_region_count": len(eligible_regions) if global_veto else 0,
                "cooldown_veto_regions": sorted(cooldown_regions),
                "single_roll_cap_veto_regions": sorted(cap_veto_regions),
            })
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
        cpu_scope_phase = {
            scope: {
                phase: {"actions": 0, "successes": 0, "failures": 0, "planned": 0,
                        "eligible": 0, "started": 0, "resolved": 0, "profiles": {}}
                for phase in ("early", "mid", "late")
            }
            for scope in ("home_region", "other_regions", "global")
        }
        for plan in plans:
            cycle_number = db.get(RegionalCycle, plan.cycle_id).cycle_number
            phase = "early" if cycle_number < 20 else ("mid" if cycle_number < 60 else "late")
            state = db.get(RegionalGuildState, plan.guild_state_id)
            scopes = ["global", "home_region" if state.region_code == home_code else "other_regions"]
            for scope in scopes:
                bucket = cpu_scope_phase[scope][phase]
                bucket["actions"] += plan.resolved_actions or 0
                bucket["successes"] += plan.successes
                bucket["failures"] += plan.failures
                bucket["planned"] += plan.planned_actions
                bucket["eligible"] += plan.eligible_actions
                bucket["started"] += plan.started_actions
                bucket["resolved"] += plan.resolved_actions or 0
                profile = bucket["profiles"].setdefault(
                    state.profile, {"actions": 0, "successes": 0, "failures": 0, "plans": 0},
                )
                profile["actions"] += plan.resolved_actions or 0
                profile["successes"] += plan.successes
                profile["failures"] += plan.failures
                profile["plans"] += 1
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
            "cpu_scope_phase": cpu_scope_phase,
            "home_region_cpu_actions_per_cycle": round(
                region_metrics[home_code]["actions"] / HORIZON, 2,
            ),
            "other_regions_cpu_actions_per_cycle": round(
                sum(value["actions"] for code, value in region_metrics.items() if code != home_code)
                / HORIZON, 2,
            ),
            "first_strong_hire_cycle": min(strong_hires) if strong_hires else None,
            "regional": region_metrics,
            "regional_pressure_counts_per_cycle": pressure_counts,
            "regional_pressure_longest_streaks": regional_pressure_streaks,
            "regional_rebellion_funnel": regional_funnel,
            "rebellion_funnel_by_cycle": rebellion_funnel_by_cycle,
            "old_v4_expected_actions_per_cycle_by_region": {
                code: round(old_baseline_by_region[code], 2) for code, _name in REGIONS
            },
            "final_security_min_max": [min(final_security), max(final_security)],
            "final_threat_min_max": [min(final_threat), max(final_threat)],
        }
    campaigns.close_active_campaign(created.campaign_id)
    return result


def _align_rebellion_funnel_to_roll_cycles(results: list[dict]) -> list[dict]:
    """Align resolved region snapshots with the following cycle's rebellion check.

    A cycle's rebellion check runs when that cycle's board opens, after the previous
    cycle's snapshot has been materialized. Per-cycle evidence therefore keeps the
    event outcome at cycle N and takes pressure/eligibility from snapshot N-1.
    """
    for campaign in results:
        if campaign.get("funnel_alignment") == "snapshot N-1 to event check N":
            continue
        raw_cycles = campaign["rebellion_funnel_by_cycle"]
        regional = {code: Counter() for code, _name in REGIONS}
        aligned_cycles = []
        last_selected: dict[str, int] = {}
        opened_cycles = [
            cycle["cycle"] for cycle in raw_cycles if cycle["rebellion_opened_regions"]
        ]
        for cycle_number, event_evidence in enumerate(raw_cycles):
            snapshot = raw_cycles[cycle_number - 1] if cycle_number > 0 else None
            pressure_regions = set(snapshot["pressure_target_regions"] if snapshot else [])
            eligible_regions = set(snapshot["threshold_eligible_regions"] if snapshot else [])
            selected_region = event_evidence["selected_roll_region"]
            opened_regions = set(event_evidence["rebellion_opened_regions"])
            global_active = any(
                0 < (cycle_number - opened_cycle) * CYCLE_SECONDS
                < (regional_event_service.REBELLION_PRIORITY + regional_event_service.REBELLION_TTL).total_seconds()
                for opened_cycle in opened_cycles
            )
            global_veto = bool(eligible_regions and global_active)
            cooldown_regions = set()
            available_regions = set()
            if eligible_regions and not global_veto:
                for code in eligible_regions:
                    last = last_selected.get(code)
                    if last is not None and cycle_number - last <= \
                            regional_event_service.REBELLION_REGION_ROLL_COOLDOWN_CYCLES:
                        cooldown_regions.add(code)
                    else:
                        available_regions.add(code)
            cap_veto_regions = available_regions - ({selected_region} if selected_region else set())
            unclassified_regions = set()
            if selected_region is None and not global_veto and not cooldown_regions:
                # A still-eligible region without a roll or a recorded veto points to
                # missing event telemetry; keep it visible rather than mislabeling it.
                unclassified_regions = available_regions
                cap_veto_regions.clear()
            rng_failure = bool(selected_region and selected_region not in opened_regions)
            for code in pressure_regions:
                regional[code]["pressure_target_cycles"] += 1
            for code in eligible_regions:
                regional[code]["eligible_region_cycles"] += 1
            for code in cooldown_regions:
                regional[code]["cooldown_veto_region_cycles"] += 1
            for code in cap_veto_regions:
                regional[code]["single_roll_cap_veto_region_cycles"] += 1
            for code in unclassified_regions:
                regional[code]["unclassified_eligible_region_cycles"] += 1
            if global_veto:
                for code in eligible_regions:
                    regional[code]["global_limit_veto_region_cycles"] += 1
            if selected_region is not None:
                regional[selected_region]["selected_rolls"] += 1
                if rng_failure:
                    regional[selected_region]["rng_failures"] += 1
                last_selected[selected_region] = cycle_number
            for code in opened_regions:
                regional[code]["rebellions_opened"] += 1
            aligned_cycles.append({
                "cycle": cycle_number,
                "pressure_target_regions": sorted(pressure_regions),
                "threshold_eligible_regions": sorted(eligible_regions),
                "eligible_region_count": len(eligible_regions),
                "selected_roll_region": selected_region,
                "selected_roll_count": event_evidence["selected_roll_count"],
                "rng_failure": rng_failure,
                "rebellion_opened_regions": sorted(opened_regions),
                "global_limit_veto": global_veto,
                "global_limit_veto_region_count": len(eligible_regions) if global_veto else 0,
                "cooldown_veto_regions": sorted(cooldown_regions),
                "single_roll_cap_veto_regions": sorted(cap_veto_regions),
                "unclassified_eligible_regions": sorted(unclassified_regions),
            })
        campaign["rebellion_funnel_by_cycle"] = aligned_cycles
        campaign["funnel_alignment"] = "snapshot N-1 to event check N"
        campaign["regional_rebellion_funnel"] = {
            code: dict(values) for code, values in regional.items()
        }
    return results


def build_report(results: list[dict]) -> tuple[dict, str]:
    results = _align_rebellion_funnel_to_roll_cycles(results)
    campaign_summaries = []
    for row in results:
        selected_cycles = [cycle["cycle"] for cycle in row["rebellion_funnel_by_cycle"]
                           if cycle["selected_roll_count"]]
        opened_cycles = [cycle["cycle"] for cycle in row["rebellion_funnel_by_cycle"]
                         if cycle["rebellion_opened_regions"]]
        regional_funnel = row["regional_rebellion_funnel"]
        campaign_summaries.append({
            key: row[key] for key in (
                "seed", "home_region", "first_portal_cycle", "first_rebellion_cycle",
                "opened_portals", "opened_rebellions", "selected_rebellion_roll_windows",
                "cycles_with_vulnerable_region", "max_simultaneous_rebellions",
                "cpu_actions_total", "cpu_actions_per_cycle_global", "cpu_successes",
                "cpu_failures", "cpu_success_rate", "home_region_cpu_actions_per_cycle",
                "other_regions_cpu_actions_per_cycle", "final_security_min_max", "final_threat_min_max",
            )
        } | {
            "selected_roll_cycles": selected_cycles,
            "rebellion_opened_cycles": opened_cycles,
            "regional_rebellion_funnel": regional_funnel,
        })
    portal_cycles = [row["first_portal_cycle"] for row in results if row["first_portal_cycle"] is not None]
    rebellion_cycles = [row["first_rebellion_cycle"] for row in results
                        if row["first_rebellion_cycle"] is not None]
    profile_phase_summary = {}
    for scope in ("home_region", "other_regions", "global"):
        profile_phase_summary[scope] = {}
        for phase in ("early", "mid", "late"):
            profiles = {}
            profile_names = {
                profile
                for row in results
                for profile in row["cpu_scope_phase"][scope][phase]["profiles"]
            }
            for profile in sorted(profile_names):
                counts = {key: 0 for key in ("actions", "successes", "failures", "plans")}
                for row in results:
                    counts_for_profile = row["cpu_scope_phase"][scope][phase]["profiles"].get(profile, {})
                    for key in counts:
                        counts[key] += counts_for_profile.get(key, 0)
                profiles[profile] = {
                    **counts,
                    "actions_per_guild_plan": round(counts["actions"] / max(1, counts["plans"]), 3),
                    "success_rate": round(
                        counts["successes"] / max(1, counts["successes"] + counts["failures"]), 4,
                    ),
                }
            profile_phase_summary[scope][phase] = profiles
    funnel_totals = Counter()
    regional_funnel_totals = {code: Counter() for code, _name in REGIONS}
    cycle_funnel = []
    for cycle_number in range(HORIZON):
        cycle_summary = Counter()
        by_region = {code: Counter() for code, _name in REGIONS}
        for row in results:
            cycle = row["rebellion_funnel_by_cycle"][cycle_number]
            cycle_summary["campaigns_with_pressure"] += bool(cycle["pressure_target_regions"])
            cycle_summary["eligible_cycles"] += cycle["eligible_region_count"] > 0
            cycle_summary["eligible_region_cycles"] += cycle["eligible_region_count"]
            cycle_summary["selected_rolls"] += cycle["selected_roll_count"]
            cycle_summary["rng_failures"] += cycle["rng_failure"]
            cycle_summary["rebellions_opened"] += len(cycle["rebellion_opened_regions"])
            cycle_summary["global_limit_veto_cycles"] += cycle["global_limit_veto"]
            cycle_summary["global_limit_veto_region_cycles"] += cycle["global_limit_veto_region_count"]
            cycle_summary["cooldown_veto_region_cycles"] += len(cycle["cooldown_veto_regions"])
            cycle_summary["single_roll_cap_veto_region_cycles"] += len(cycle["single_roll_cap_veto_regions"])
            cycle_summary["unclassified_eligible_region_cycles"] += len(cycle["unclassified_eligible_regions"])
            pressure_set = set(cycle["pressure_target_regions"])
            eligible_set = set(cycle["threshold_eligible_regions"])
            opened_set = set(cycle["rebellion_opened_regions"])
            cooldown_set = set(cycle["cooldown_veto_regions"])
            roll_cap_set = set(cycle["single_roll_cap_veto_regions"])
            unclassified_set = set(cycle["unclassified_eligible_regions"])
            for code, _name in REGIONS:
                by_region[code]["pressure_target_campaigns"] += code in pressure_set
                by_region[code]["eligible_region_cycles"] += code in eligible_set
                by_region[code]["selected_rolls"] += cycle["selected_roll_region"] == code
                by_region[code]["cooldown_veto_region_cycles"] += code in cooldown_set
                by_region[code]["single_roll_cap_veto_region_cycles"] += code in roll_cap_set
                by_region[code]["unclassified_eligible_region_cycles"] += code in unclassified_set
                by_region[code]["global_limit_veto_region_cycles"] += (
                    cycle["global_limit_veto"] and code in eligible_set
                )
                by_region[code]["rng_failures"] += (
                    cycle["selected_roll_region"] == code and code not in opened_set
                )
                by_region[code]["rebellions_opened"] += code in opened_set
        for key, value in cycle_summary.items():
            funnel_totals[key] += value
        for code in by_region:
            regional_funnel_totals[code].update(by_region[code])
        cycle_funnel.append({
            "cycle": cycle_number,
            **dict(cycle_summary),
            "regions": {code: dict(by_region[code]) for code, _name in REGIONS},
        })
    selected_rolls_total = funnel_totals["selected_rolls"]
    rebellion_funnel_summary = {
        "campaigns": len(results),
        "cycles_per_campaign": HORIZON,
        "pressure_target_region_cycles": funnel_totals["campaigns_with_pressure"],
        "eligible_region_cycles": funnel_totals["eligible_region_cycles"],
        "cycles_with_at_least_one_eligible_region": funnel_totals["eligible_cycles"],
        "selected_rolls": selected_rolls_total,
        "rebellion_chance_per_selected_roll": regional_event_service.REBELLION_CHANCE,
        "expected_openings_at_configured_chance": round(
            selected_rolls_total * regional_event_service.REBELLION_CHANCE, 3,
        ),
        "observed_rng_failures": funnel_totals["rng_failures"],
        "rebellions_opened": funnel_totals["rebellions_opened"],
        "global_limit_veto_cycles": funnel_totals["global_limit_veto_cycles"],
        "global_limit_veto_region_cycles": funnel_totals["global_limit_veto_region_cycles"],
        "region_cooldown_veto_region_cycles": funnel_totals["cooldown_veto_region_cycles"],
        "one_roll_per_cycle_veto_region_cycles": funnel_totals["single_roll_cap_veto_region_cycles"],
        "unclassified_eligible_region_cycles": funnel_totals["unclassified_eligible_region_cycles"],
        "per_region": {code: dict(values) for code, values in regional_funnel_totals.items()},
        "by_cycle": cycle_funnel,
    }
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
        "home_vs_other_regions_cpu_actions_per_cycle": {
            scope: {
                "mean": round(sum(row[key] for row in results) / len(results), 2),
                "p50": _percentile([row[key] for row in results], 0.5),
                "p90": _percentile([row[key] for row in results], 0.9),
            }
            for scope, key in (
                ("home_region", "home_region_cpu_actions_per_cycle"),
                ("other_regions", "other_regions_cpu_actions_per_cycle"),
            )
        },
        "cpu_profile_phase_by_scope": profile_phase_summary,
        "rebellion_funnel": rebellion_funnel_summary,
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
        "campaign_results": campaign_summaries,
    }
    lines = [
        "# Regional CPU event balance — 20 campaigns",
        "",
        "Deterministic SQLite campaigns; 100 six-hour cycles each; player takes no actions. "
        "Events, timers, CPU plans, snapshots and region state use the live services.",
        "The funnel aligns pressure and threshold state from snapshot N−1 to the rebellion check when Vigília N opens; "
        "global-lock cycles are inferred from the active event deadline and the preceding snapshot.",
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
        f"- CPU actions per Vigília: guilda da região natal **{report['home_vs_other_regions_cpu_actions_per_cycle']['home_region']['mean']}**; "
        f"nas outras quatro regiões, juntas, **{report['home_vs_other_regions_cpu_actions_per_cycle']['other_regions']['mean']}**.",
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
    ]
    funnel = report["rebellion_funnel"]
    lines.extend([
        f"- Rebellion funnel across {funnel['campaigns']}×{funnel['cycles_per_campaign']} Vigílias: "
        f"{funnel['pressure_target_region_cycles']} pressure-target region-cycles; "
        f"{funnel['eligible_region_cycles']} eligible region-cycles in "
        f"{funnel['cycles_with_at_least_one_eligible_region']} campaign-cycles; "
        f"{funnel['selected_rolls']} selected rolls × {funnel['rebellion_chance_per_selected_roll']:.0%} "
        f"= {funnel['expected_openings_at_configured_chance']} expected openings; "
        f"{funnel['rebellions_opened']} observed, {funnel['observed_rng_failures']} RNG failures.",
        f"- Eligible region-cycles withheld by regional cooldown: {funnel['region_cooldown_veto_region_cycles']}; "
        f"by one-roll-per-cycle cap: {funnel['one_roll_per_cycle_veto_region_cycles']}; "
        f"by active global event limit: {funnel['global_limit_veto_region_cycles']} "
        f"across {funnel['global_limit_veto_cycles']} campaign-cycles; "
        f"unclassified: {funnel['unclassified_eligible_region_cycles']}.",
        "",
        "| Região | Ciclos-alvo | Região-ciclos elegíveis | Bloqueio cooldown | Bloqueio limite por ciclo | Rolagens | Rebeliões | Sem atribuição |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for code, name in REGIONS:
        values = funnel["per_region"][code]
        lines.append(
            f"| {name} (`{code}`) | {values['pressure_target_campaigns']} | "
            f"{values['eligible_region_cycles']} | {values['cooldown_veto_region_cycles']} | "
            f"{values['single_roll_cap_veto_region_cycles']} | {values['selected_rolls']} | "
            f"{values['rebellions_opened']} | {values.get('unclassified_eligible_region_cycles', 0)} |"
        )
    lines.extend([
        "",
        "| Vigília | Campanhas sob pressão | Campanhas com região elegível | Região-ciclos elegíveis | Rolagens selecionadas | RNG falhou | Bloqueio cooldown | Bloqueio global | Rebeliões | Sem atribuição |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for cycle in funnel["by_cycle"]:
        lines.append(
            f"| {cycle['cycle']} | {cycle['campaigns_with_pressure']} | "
            f"{cycle['eligible_cycles']} | {cycle['eligible_region_cycles']} | "
            f"{cycle['selected_rolls']} | {cycle['rng_failures']} | "
            f"{cycle['cooldown_veto_region_cycles']} | {cycle['global_limit_veto_region_cycles']} | "
            f"{cycle['rebellions_opened']} | {cycle['unclassified_eligible_region_cycles']} |"
        )
    lines.extend([
        "",
        "| Region | Mean CPU actions/cycle | 0.5.4 expected actions/cycle |",
        "|---|---:|---:|",
    ])
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pressure-window", type=int, default=regional_cycle_service.REGIONAL_PRESSURE_WINDOW_CYCLES)
    parser.add_argument("--output-prefix", default="reports/regional_cpu_incidence_2026-11-03")
    args = parser.parse_args()
    if args.pressure_window < 1:
        parser.error("--pressure-window must be positive")
    regional_cycle_service.REGIONAL_PRESSURE_WINDOW_CYCLES = args.pressure_window
    output_prefix = Path(args.output_prefix)
    if not output_prefix.is_absolute():
        output_prefix = ROOT / output_prefix
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="regional-cpu-balance-", dir=ROOT) as temp_dir:
        saves_root = Path(temp_dir) / "saves"
        template_saves = Path(temp_dir) / "template"
        template = CampaignService(template_saves).create_campaign("CPU balance template", "Guilda template")
        CampaignService(template_saves).activate_campaign(template.campaign_id)
        results = []
        try:
            for index, seed in enumerate(SEEDS, start=1):
                result = run_campaign(seed, saves_root, template.database_path)
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
    report["calibration"] = {
        "pressure_window_cycles": args.pressure_window,
        "seeds": list(SEEDS),
        "runner": "live campaign services with cloned, fully seeded disposable SQLite save per deterministic UUID seed",
    }
    json_path = output_prefix.with_suffix(".json")
    markdown_path = output_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown, encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "campaign_results"},
                     ensure_ascii=False, indent=2))
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")


if __name__ == "__main__":
    main()
