"""Run paired five-profile Market material-quota scenarios on disposable SQLite saves."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "balance" / "simulate_stage5_service_journeys.py"
REPORTS = ROOT / "reports"
CAPS: tuple[int | None, ...] = (10, 25, 50, 100, 250, None)
RESERVES = (30, 300)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-per-cell", type=int, default=1)
    parser.add_argument("--seed-start", type=int, default=2026103000)
    parser.add_argument("--max-days", type=int, default=365)
    parser.add_argument("--max-wall-seconds", type=float, default=600)
    parser.add_argument("--only", nargs="*", default=None,
                        help="Optional explicit scenario stems to resume/re-run.")
    args = parser.parse_args()

    os.environ["APP_MODE"] = "desktop"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    REPORTS.mkdir(exist_ok=True)
    batch_dir = REPORTS / "market_quota_sensitivity_logs_2026-10-29"
    batch_dir.mkdir(exist_ok=True)
    started = time.perf_counter()
    batches: list[dict[str, object]] = []
    for cap in CAPS:
        for reserve in RESERVES:
            cap_label = "unlimited" if cap is None else str(cap)
            stem = f"market_quota_base{cap_label}_reserve{reserve}_n{args.runs_per_cell}"
            if args.only and stem not in args.only:
                continue
            log_path = batch_dir / f"{stem}.txt"
            report_path = REPORTS / f"{stem}.json"
            command = [
                sys.executable, str(RUNNER),
                "--runs-per-cell", str(args.runs_per_cell),
                "--seed-start", str(args.seed_start),
                "--max-days", str(args.max_days),
                "--max-wall-seconds", str(args.max_wall_seconds),
                "--market-reserve-base", str(reserve),
                "--path", "commerce_early",
                "--output-stem", stem,
            ]
            command.append("--market-unlimited-materials" if cap is None else
                           "--market-base-units-per-24h")
            if cap is not None:
                command.append(str(cap))
            batch_started_utc = datetime.now(timezone.utc).isoformat()
            batch_started = time.perf_counter()
            with log_path.open("w", encoding="utf-8", newline="") as log:
                result = subprocess.run(
                    command, cwd=ROOT, env=os.environ.copy(),
                    stdout=log, stderr=subprocess.STDOUT, check=False,
                )
            elapsed = round(time.perf_counter() - batch_started, 3)
            entry: dict[str, object] = {
                "scenario": stem,
                "base_quota_market_1_units_per_24h": cap,
                "market_level_progression": "base + 5 * floor(market_level / 5); rolling 24h",
                "market_reserve_base_units_per_family": reserve,
                "profile_path_cells": 5,
                "runs_per_cell": args.runs_per_cell,
                "seed_start": args.seed_start,
                "max_days": args.max_days,
                "max_wall_seconds_per_journey": args.max_wall_seconds,
                "command": command,
                "started_at_utc": batch_started_utc,
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "elapsed_wall_seconds": elapsed,
                "exit_code": result.returncode,
                "log": str(log_path.relative_to(ROOT)).replace("\\", "/"),
                "log_sha256": sha256(log_path),
                "campaign_data": "temporary SQLite only; runner never opens user saves",
                "report_json": str(report_path.relative_to(ROOT)).replace("\\", "/"),
            }
            if report_path.is_file():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                entry["runner_elapsed_seconds"] = report.get("elapsed_seconds")
                entry["journey_errors"] = report.get("journey_errors")
                entry["journey_count"] = len(report.get("journeys", []))
                entry["report_json_sha256"] = sha256(report_path)
            batches.append(entry)
            manifest = {
                "report_id": "gim-market-quota-paired-sensitivity-20261029-v1",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "parameters": vars(args),
                "candidate_caps_market1_units_per_24h": list(CAPS),
                "candidate_sale_reserves_units_per_family": list(RESERVES),
                "cap_fraction_of_one_offline_worker_base_8h": {
                    str(cap): round(cap / 480 * 100, 2) for cap in CAPS if cap is not None
                },
                "batch_count": len(batches),
                "elapsed_wall_seconds": round(time.perf_counter() - started, 3),
                "batches": batches,
            }
            manifest_name = (
                "market_quota_intermediate25_sensitivity_2026-10-30.manifest.json"
                if args.only and all("base25_" in item for item in args.only) else
                "market_quota_sensitivity_2026-10-29.manifest.json"
            )
            manifest_path = REPORTS / manifest_name
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"finished {stem}: exit={result.returncode}, wall={elapsed}s", flush=True)
    final_manifest_name = (
        "market_quota_intermediate25_sensitivity_2026-10-30.manifest.json"
        if args.only and all("base25_" in item for item in args.only) else
        "market_quota_sensitivity_2026-10-29.manifest.json"
    )
    final_manifest_path = REPORTS / final_manifest_name
    print(f"manifest={final_manifest_path}; batches={len(batches)}", flush=True)
    return 0 if all(item["exit_code"] == 0 for item in batches) else 1


if __name__ == "__main__":
    raise SystemExit(main())
