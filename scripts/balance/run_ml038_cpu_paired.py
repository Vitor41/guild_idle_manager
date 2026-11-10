"""Run a bounded paired ML-038 CPU simulation from a disposable template DB."""

from __future__ import annotations

import argparse
import csv
import json
import os
import runpy
import sqlite3
import sys
import tempfile
from pathlib import Path

from sqlalchemy import event


os.environ.setdefault("APP_MODE", "desktop")
ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / ".lot-e2-test-tmp"


def _install_disposable_sqlite_pragmas() -> None:
    """Avoid SQLite sidecar files for isolated clones only."""
    import app.database.connection as connection
    import app.services.campaign_service as campaign_service

    original_factory = connection.create_database_engine

    def create_isolated_engine(database_url: str):
        engine = original_factory(database_url)
        if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:///:memory:"):
            @event.listens_for(engine, "connect")
            def _configure_disposable_clone(dbapi_connection, _record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=OFF")
                cursor.execute("PRAGMA synchronous=OFF")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()

        return engine

    connection.create_database_engine = create_isolated_engine
    campaign_service.create_database_engine = create_isolated_engine


def _load_completed_pairs(json_path: Path, csv_path: Path, simulator) -> list[dict]:
    """Restore finished seed pairs so an interrupted bounded run can resume."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    expected = list(simulator.SEEDS)
    seeds = payload.get("calibration", {}).get("seeds", [])
    if not seeds or seeds != expected[:len(seeds)]:
        raise ValueError("resume report seeds do not match this simulator's deterministic seed prefix")
    totals = payload.get("totals", {})
    csv_rows: dict[tuple[int, str, str], dict[str, str]] = {}
    with csv_path.open("r", newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            csv_rows[(int(row["seed"]), row["scenario"], f"{row['scope']}|{row['phase']}")] = row

    restored = []
    for pair_summary in payload.get("paired_results", []):
        seed = int(pair_summary["seed"])
        pair = {}
        for scenario in ("baseline", "ml029_e2"):
            source = pair_summary[scenario]
            buckets = {}
            for scope_phase, metrics in totals.get(scenario, {}).items():
                row = csv_rows.get((seed, scenario, scope_phase))
                if row is None:
                    raise ValueError(f"resume CSV is missing seed {seed} {scenario} {scope_phase}")
                buckets[scope_phase] = {
                    key: float(row.get(key) or 0)
                    for key in metrics
                }
            pair[scenario] = {
                "seed": seed,
                "home_region": pair_summary["home_region"],
                "summary": source["summary"],
                "event_metrics": source["event_metrics"],
                "buckets": buckets,
            }
        restored.append(pair)
    if [pair["baseline"]["seed"] for pair in restored] != seeds:
        raise ValueError("resume JSON does not contain all completed paired seed records")
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True,
                        help="SQLite campaign test template located under .lot-e2-test-tmp")
    parser.add_argument("--limit", type=int, default=5,
                        help="number of paired deterministic seeds (maximum 5 for this check)")
    parser.add_argument("--label", required=True,
                        help="unique report suffix; refuses to overwrite existing reports")
    parser.add_argument("--resume-json", type=Path,
                        help="completed prior report JSON to resume; pair with --resume-csv")
    parser.add_argument("--resume-csv", type=Path,
                        help="CSV companion to --resume-json")
    parser.add_argument("--skip-seed", type=int, action="append", default=[],
                        help="exclude a deterministic seed that failed for a reason unrelated to the candidate")
    args = parser.parse_args()
    template = args.template_db.resolve()
    test_root = TEST_ROOT.resolve()
    if not template.is_relative_to(test_root) or not template.is_file():
        parser.error("--template-db must be an existing SQLite file under .lot-e2-test-tmp")
    try:
        with sqlite3.connect(f"file:{template.as_posix()}?mode=ro", uri=True) as db:
            existing_states = db.execute("SELECT COUNT(*) FROM regional_guild_state").fetchone()[0]
            existing_worlds = db.execute("SELECT COUNT(*) FROM regional_world_state").fetchone()[0]
    except sqlite3.Error as exc:
        parser.error(f"cannot inspect disposable template database: {exc}")
    if existing_states or existing_worlds:
        parser.error(
            "template database must be a pristine test campaign with no regional guild states or world"
        )
    if not 1 <= args.limit <= 5:
        parser.error("--limit must be from 1 to 5")
    if bool(args.resume_json) != bool(args.resume_csv):
        parser.error("--resume-json and --resume-csv must be supplied together")

    output = ROOT / "reports"
    stem = f"lot_e2_ml029_cpu_paired_{args.label}"
    existing = [output / f"{stem}.{extension}" for extension in ("json", "md", "csv")]
    resuming_same_output = (
        args.resume_json is not None
        and args.resume_csv is not None
        and args.resume_json.resolve() == existing[0].resolve()
        and args.resume_csv.resolve() == existing[2].resolve()
    )
    if any(path.exists() for path in existing) and not resuming_same_output:
        parser.error(f"report label already exists: {args.label}")

    sys.path.insert(0, str(ROOT))
    _install_disposable_sqlite_pragmas()
    mod = runpy.run_path(str(ROOT / "scripts/balance/compare_ml029_cpu_balance.py"),
                         run_name="ml038_paired")
    simulator = mod["simulator"]
    simulator.SEEDS = tuple(seed for seed in simulator.SEEDS if seed not in set(args.skip_seed))
    if not 1 <= args.limit <= len(simulator.SEEDS):
        parser.error("--limit exceeds the remaining deterministic seed pool")
    pairs: list[dict] = []
    if args.resume_json:
        try:
            pairs = _load_completed_pairs(args.resume_json.resolve(), args.resume_csv.resolve(), simulator)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            parser.error(f"cannot resume from paired report: {exc}")
        if len(pairs) >= args.limit:
            parser.error("resume report already contains the requested number of pairs")
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix="ml038-cpu-paired-", dir=TEST_ROOT)
    working = Path(temporary.name)
    try:
        remaining_seeds = simulator.SEEDS[len(pairs):args.limit]
        for index, seed in enumerate(remaining_seeds, start=len(pairs) + 1):
            pair = {}
            for scenario, candidate in (("baseline", False), ("ml029_e2", True)):
                print(f"[{index}/{args.limit}] seed={seed} scenario={scenario}", flush=True)
                pair[scenario] = mod["_capture_run"](
                    seed, working / scenario / "saves", template, candidate=candidate,
                )
            pairs.append(pair)
            baseline = pair["baseline"]["summary"]
            candidate = pair["ml029_e2"]["summary"]
            print(
                f"[{index}/{args.limit}] success {baseline['cpu_success_rate']:.1%}"
                f"->{candidate['cpu_success_rate']:.1%}; "
                f"XP {baseline['cpu_xp_net']}->{candidate['cpu_xp_net']}; "
                f"portals {baseline['opened_portals']}->{candidate['opened_portals']}; "
                f"rebellions {baseline['opened_rebellions']}->{candidate['opened_rebellions']}",
                flush=True,
            )
            mod["_write_outputs"](pairs, output, args.label)
    finally:
        mod["configure_database"]("sqlite:///:memory:")
        temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
