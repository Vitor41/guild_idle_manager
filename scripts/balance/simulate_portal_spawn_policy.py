"""Bounded deterministic incidence study for the current regional portal policy."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time
from types import SimpleNamespace

from app.services.portal_spawn_rules import (
    CURRENT_PORTAL_SPAWN_RULES_VERSION,
    get_portal_spawn_rules,
)
from app.services.regional_cycle_service import REGIONS, VIGILIA_RULES_VERSION, _rng, _seed_text


SEED_COUNT = 64
SIMULATION_DAYS = 180
STAGES = (1, 15, 30, 50)
SCOUT_BONUSES_PP = (0, 5)
PLAYER_PRESENCE_HOURS_UTC = ((20, 22),)
SOURCE_PATHS = (
    "app/services/portal_spawn_rules.py",
    "app/services/regional_event_service.py",
    "app/services/regional_cycle_service.py",
    "app/seeds/massive_content.py",
    "app/services/dungeon_service.py",
    "scripts/balance/simulate_portal_spawn_policy.py",
)


def _has_presence(start_hour: float, end_hour: float) -> bool:
    first_day = int(start_hour // 24)
    last_day = int((end_hour - 1e-9) // 24)
    for day in range(first_day, last_day + 1):
        for start, end in PLAYER_PRESENCE_HOURS_UTC:
            if max(start_hour, day * 24 + start) < min(end_hour, day * 24 + end):
                return True
    return False


def stage_content_pool_sizes() -> dict[int, int]:
    """Seed a disposable in-memory catalog and call the production pool filter."""
    from app.database.connection import Base, SessionLocal, configure_database, get_engine
    from app.seeds.campaign_content import apply_initial_campaign_content
    from app.services.regional_event_service import _versioned_portal_boss_pool

    configure_database("sqlite:///:memory:")
    Base.metadata.create_all(bind=get_engine())
    sizes: dict[int, int] = {}
    with SessionLocal() as db:
        apply_initial_campaign_content(db)
        for stage in STAGES:
            synthetic_cycle = SimpleNamespace(
                rules_version=VIGILIA_RULES_VERSION,
                player_level_snapshot=stage,
            )
            pool, _stage_eligible = _versioned_portal_boss_pool(db, synthetic_cycle)
            sizes[stage] = len(pool)
    configure_database("sqlite:///:memory:")
    return sizes


def _source_metadata() -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[2]
    hashes = {
        source: hashlib.sha256((repository_root / source).read_bytes()).hexdigest()
        for source in SOURCE_PATHS
    }
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_status = subprocess.run(
        ["git", "status", "--porcelain", "--", *SOURCE_PATHS],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "git_revision": revision,
        "selected_source_status": source_status or "clean",
        "sha256": hashes,
    }


def simulate_case(stage: int, scout_bonus_pp: int, stage_eligible_boss_count: int) -> dict[str, object]:
    rules = get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION)
    cycle_count = SIMULATION_DAYS * 4
    total_opportunities = 0
    chance_counts: Counter[int] = Counter()
    blocked_cycles: Counter[str] = Counter()
    regional_spawns: Counter[str] = Counter()
    home_region_spawns = 0
    other_region_spawns = 0
    spawn_cycles: dict[tuple[int, int], int] = defaultdict(int)
    spawn_intervals_days: list[float] = []
    first_spawn_days: list[float] = []
    no_portal_at_days = Counter({30: 0, 90: 0, SIMULATION_DAYS: 0})
    missed_entry_windows = 0
    all_spawn_count = 0
    wall_start = time.perf_counter()
    max_stack_seen = 0

    for seed_id in range(SEED_COUNT):
        campaign_id = f"ml054-sim-{seed_id:04d}-stage-{stage}-scouts-{scout_bonus_pp}"
        for region_index, (region_code, _region_name) in enumerate(REGIONS):
            failure_stacks = 0
            cooldown_until_hour: float | None = None
            entry_window_until_hour: float | None = None
            last_spawn_hour: float | None = None
            spawned_this_region: list[float] = []

            for cycle_number in range(1, cycle_count + 1):
                cycle_end_hour = cycle_number * 6.0
                if entry_window_until_hour is not None and cycle_end_hour < entry_window_until_hour:
                    blocked_cycles["active_portal"] += 1
                    continue
                if cooldown_until_hour is not None and cycle_end_hour < cooldown_until_hour:
                    blocked_cycles["cooldown"] += 1
                    continue
                if stage_eligible_boss_count <= 0:
                    blocked_cycles["content_unavailable"] += 1
                    continue

                _base_chance_pp, _scout_component, chance_pp = rules.chance_percentages(
                    failure_stacks,
                    scout_bonus_pp,
                )
                total_opportunities += 1
                chance_counts[chance_pp] += 1
                portal_seed = _seed_text(
                    campaign_id,
                    cycle_number,
                    region_code,
                    rules.version,
                    "portal",
                )
                if _rng(portal_seed, "chance").random() * 100.0 >= chance_pp:
                    failure_stacks = min(rules.max_stack(), failure_stacks + 1)
                    max_stack_seen = max(max_stack_seen, failure_stacks)
                    continue

                spawn_hour = cycle_end_hour
                all_spawn_count += 1
                regional_spawns[region_code] += 1
                if region_index == 0:
                    home_region_spawns += 1
                else:
                    other_region_spawns += 1
                spawn_cycles[(seed_id, cycle_number)] += 1
                spawned_this_region.append(spawn_hour)
                if last_spawn_hour is not None:
                    spawn_intervals_days.append((spawn_hour - last_spawn_hour) / 24.0)
                else:
                    first_spawn_days.append(spawn_hour / 24.0)
                if not _has_presence(spawn_hour, spawn_hour + rules.entry_window_hours):
                    missed_entry_windows += 1
                last_spawn_hour = spawn_hour
                entry_window_until_hour = spawn_hour + rules.entry_window_hours
                cooldown_until_hour = spawn_hour + rules.cooldown_hours
                failure_stacks = 0

            for checkpoint_day in (30, 90, SIMULATION_DAYS):
                if not any(hour <= checkpoint_day * 24 for hour in spawned_this_region):
                    no_portal_at_days[checkpoint_day] += 1
            if not spawned_this_region:
                first_spawn_days.append(float(SIMULATION_DAYS))

    simultaneous_cycles = [count for count in spawn_cycles.values() if count > 1]
    seed_region_runs = SEED_COUNT * len(REGIONS)
    potential_cycle_closures = seed_region_runs * cycle_count
    for reason in ("active_portal", "cooldown", "content_unavailable"):
        blocked_cycles.setdefault(reason, 0)
    if total_opportunities + sum(blocked_cycles.values()) != potential_cycle_closures:
        raise AssertionError("Every cycle closure must be either blocked before RNG or rolled once.")
    return {
        "stage_level": stage,
        "explorer_bonus_pp": scout_bonus_pp,
        "seed_count": SEED_COUNT,
        "region_count": len(REGIONS),
        "stage_eligible_boss_count_from_seeded_catalog": stage_eligible_boss_count,
        "simulation_days": SIMULATION_DAYS,
        "regional_runs": seed_region_runs,
        "eligible_rolls": total_opportunities,
        "eligible_rolls_per_region_run": round(total_opportunities / seed_region_runs, 3),
        "chance_distribution_percent": {
            str(chance): round(count * 100 / total_opportunities, 2)
            for chance, count in sorted(chance_counts.items())
        },
        "chance_roll_counts": dict(sorted(chance_counts.items())),
        "portal_spawns": all_spawn_count,
        "portals_per_region_run_180d": round(all_spawn_count / seed_region_runs, 3),
        "portals_per_region_run_30d": round(all_spawn_count / seed_region_runs / 6, 3),
        "first_portal_days_median": round(statistics.median(first_spawn_days), 2) if first_spawn_days else None,
        "between_portal_days_median": round(statistics.median(spawn_intervals_days), 2) if spawn_intervals_days else None,
        "between_portal_days_p90": round(sorted(spawn_intervals_days)[int(0.9 * (len(spawn_intervals_days) - 1))], 2) if spawn_intervals_days else None,
        "no_portal_by_day_percent": {
            str(day): round(count * 100 / seed_region_runs, 2)
            for day, count in sorted(no_portal_at_days.items())
        },
        "regional_spawn_counts": dict(sorted(regional_spawns.items())),
        "home_region_spawn_share_percent": round(home_region_spawns * 100 / all_spawn_count, 2) if all_spawn_count else 0,
        "other_regions_spawn_share_percent": round(other_region_spawns * 100 / all_spawn_count, 2) if all_spawn_count else 0,
        "cycles_with_simultaneous_regions": len(simultaneous_cycles),
        "simultaneous_share_of_portal_cycles_percent": round(
            len(simultaneous_cycles) * 100 / len(spawn_cycles), 2,
        ) if spawn_cycles else 0,
        "maximum_regions_spawning_same_cycle": max(spawn_cycles.values(), default=0),
        "entry_windows_without_player_presence": missed_entry_windows,
        "entry_windows_without_presence_percent": round(
            missed_entry_windows * 100 / all_spawn_count, 2,
        ) if all_spawn_count else 0,
        "maximum_failure_stack_observed": max_stack_seen,
        "blocked_cycle_reasons_without_rng": dict(sorted(blocked_cycles.items())),
        "potential_cycle_closures": potential_cycle_closures,
        "wall_seconds": round(time.perf_counter() - wall_start, 3),
        "scope_note": (
            "The stage-eligible boss/loot count is read from a disposable seed using the production "
            "_versioned_portal_boss_pool helper. The simulation models portal generation and entry windows only, "
            "not CPU participation, combat, or rewards."
        ),
        "absence_assumption": "Player is available daily from 20:00 to 22:00 UTC; the 12h entry window continues offline.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="reports/ml054_portal_spawn_policy_2026-11-24.json",
        help="Path for the generated JSON report.",
    )
    args = parser.parse_args()
    start = time.perf_counter()
    content_pool_sizes = stage_content_pool_sizes()
    sources = _source_metadata()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output.with_suffix(".checkpoint.json")
    cases: list[dict[str, object]] = []
    for stage in STAGES:
        for scout_bonus in SCOUT_BONUSES_PP:
            cases.append(simulate_case(stage, scout_bonus, content_pool_sizes[stage]))
            checkpoint_path.write_text(json.dumps({
                "source": sources,
                "policy_version": CURRENT_PORTAL_SPAWN_RULES_VERSION,
                "seed_count": SEED_COUNT,
                "simulation_days": SIMULATION_DAYS,
                "stage_content_pool_sizes": content_pool_sizes,
                "completed_cases": len(cases),
                "cases": cases,
            }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy_version": CURRENT_PORTAL_SPAWN_RULES_VERSION,
        "source": sources,
        "deterministic_seeds": {
            "campaign_id_format": "ml054-sim-{seed_id:04d}-stage-{stage}-scouts-{bonus}",
            "seed_ids": [0, SEED_COUNT - 1],
            "roll_seed": "sha256(campaign_id:cycle_number:region_code:policy_version:portal), then sha256(seed:chance)",
        },
        "horizon": {"days": SIMULATION_DAYS, "cycles_per_day": 4, "cycle_hours": 6},
        "seeded_catalog_stage_eligible_boss_counts": content_pool_sizes,
        "parameters": {
            "base_chance_pp": get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION).base_chance_pp,
            "failure_increment_pp": get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION).failure_increment_pp,
            "base_chance_cap_pp": get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION).base_chance_cap_pp,
            "explorer_bonus_cap_pp": get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION).explorer_bonus_cap_pp,
            "cooldown_hours": get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION).cooldown_hours,
            "entry_window_hours": get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION).entry_window_hours,
            "max_failure_stacks": get_portal_spawn_rules(CURRENT_PORTAL_SPAWN_RULES_VERSION).max_stack(),
        },
        "cases": cases,
    }
    result["total_wall_seconds"] = round(time.perf_counter() - start, 3)
    result["checkpoint_path"] = str(checkpoint_path)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = [
        "# ML-054 portal spawn policy simulation",
        "",
        f"Policy: `{result['policy_version']}`. Generated: {result['generated_at_utc']}.",
        "",
        f"Runs: {SEED_COUNT} deterministic seeds × {len(REGIONS)} regions × {SIMULATION_DAYS} days × {len(STAGES)} stage levels × {len(SCOUT_BONUSES_PP)} Explorer bonus cases.",
        "",
        "## Results",
        "",
        "| Stage | Eligible bosses | Explorer bonus | Rolls / region / 180d | Portals / region / 180d | Median first portal (days, censored at 180) | Median interval (days) | No portal by 30 / 90 / 180d | Simultaneous portal cycles | Entry window missed* |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in result["cases"]:
        no_portal = case["no_portal_by_day_percent"]
        markdown.append(
            f"| {case['stage_level']} | {case['stage_eligible_boss_count_from_seeded_catalog']} | {case['explorer_bonus_pp']} pp | {case['eligible_rolls_per_region_run']} | "
            f"{case['portals_per_region_run_180d']} | {case['first_portal_days_median']} | "
            f"{case['between_portal_days_median']} | {no_portal['30']}% / {no_portal['90']}% / {no_portal['180']}% | "
            f"{case['simultaneous_share_of_portal_cycles_percent']}% (max {case['maximum_regions_spawning_same_cycle']}) | "
            f"{case['entry_windows_without_presence_percent']}%"
        )
    markdown.extend([
        "",
        "## Chance and regional distribution",
        "",
        "Each chance-distribution value is the share of eligible rolls at that effective chance.",
        "",
        "| Stage | Eligible bosses | Explorer bonus | Effective chance distribution | Home-region share | Other-region share | Blocked cycles (no RNG) |",
        "|---:|---:|---:|---|---:|---:|---|",
    ])
    for case in result["cases"]:
        distribution = ", ".join(
            f"{chance}%: {share}%" for chance, share in case["chance_distribution_percent"].items()
        )
        markdown.append(
            f"| {case['stage_level']} | {case['stage_eligible_boss_count_from_seeded_catalog']} | {case['explorer_bonus_pp']} pp | {distribution} | "
            f"{case['home_region_spawn_share_percent']}% | {case['other_regions_spawn_share_percent']}% | "
            f"{case['blocked_cycle_reasons_without_rng']}"
        )
    markdown.extend([
        "",
        "*The missed-window estimate assumes player availability only from 20:00–22:00 UTC daily. Portal generation continues offline and the approved 12-hour entry deadline continues offline. This is a narrow availability scenario, not an estimate of the player's actual schedule.",
        "",
        f"The service helper found {content_pool_sizes} active boss/loot candidate counts by player level in a disposable catalog seeded from committed content. Region 1 ({REGIONS[0][1]}) is labeled home, and the remaining four as other regions for reporting only. Every blocked cycle is counted before RNG; no-content stages never roll or accumulate failures. Null-marker legacy cycles are excluded from this new-policy simulation and covered separately by regression tests. The study does not model CPU participation, combat, rewards, rebellion rules, or real user behavior.",
        "",
        f"Parameters: base {result['parameters']['base_chance_pp']}%, +{result['parameters']['failure_increment_pp']} pp per eligible failure, base cap {result['parameters']['base_chance_cap_pp']}%, Explorers cap +{result['parameters']['explorer_bonus_cap_pp']} pp, {result['parameters']['cooldown_hours']}h cooldown, {result['parameters']['entry_window_hours']}h entry window. Total runtime: {result['total_wall_seconds']}s.",
        "",
        f"Source revision: `{sources['git_revision']}`. Selected source worktree: `{sources['selected_source_status']}`. SHA-256 values are in the JSON. The checkpoint file preserves completed case aggregates.",
        "",
    ])
    markdown_path = output.with_suffix(".md")
    markdown_path.write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps({"json": str(output), "markdown": str(markdown_path), "total_wall_seconds": result["total_wall_seconds"], "cases": len(result["cases"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
