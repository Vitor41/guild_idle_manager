"""Measure regional fresh-save catch-up in a disposable campaign database.

This is a workload benchmark, not a product acceptance threshold. Each run uses
CampaignService's SQLite save under TemporaryDirectory and never touches the
user's installed profile or real campaign saves.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from math import ceil
from statistics import median
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal, get_engine
from app.models.campaign import CampaignMetadata
from app.models.regional import RegionalCpuCyclePlan, RegionalCycle, RegionalEvent, RegionalOffer
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.services.regional_cycle_service import CYCLE_SECONDS, advance_regional_world


CAMPAIGN_ID = UUID("00000000-0000-4000-8000-000000000531")
BATCH_SIZES = (1, 10, 50, 100)
HORIZONS = tuple(sum(BATCH_SIZES[:index + 1]) for index in range(len(BATCH_SIZES)))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, ceil(percentile * len(ordered)) - 1)], 4)


def run_benchmark(seed_count: int = 5) -> dict[str, object]:
    snapshots: list[dict[str, object]] = []
    seed_count = max(1, int(seed_count))
    for seed_index in range(seed_count):
        campaign_id = UUID(int=CAMPAIGN_ID.int + seed_index)
        with TemporaryDirectory(prefix=f"gim-stage5-catchup-{seed_index}-") as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            with patch("app.services.campaign_service.uuid4", return_value=campaign_id):
                info = campaigns.create_campaign(f"Stage 5 catch-up benchmark {seed_index}", "Benchmark Guild")
            campaigns.activate_campaign(info.campaign_id)
            try:
                with SessionLocal() as db:
                    campaign = db.get(CampaignMetadata, info.campaign_id)
                    guild, _resources = get_current_guild_context(db, info.campaign_id)
                    if campaign is None or guild is None:
                        raise RuntimeError("Fresh temporary campaign was not initialized")
                    start = campaign.created_at_utc
                    previous_cycle = 0
                    for horizon in HORIZONS:
                        started = time.perf_counter()
                        advance_regional_world(
                            db, campaign, guild, start + timedelta(seconds=horizon * CYCLE_SECONDS),
                        )
                        elapsed = time.perf_counter() - started
                        db.commit()
                        completed = int(db.scalar(select(func.count(RegionalCycle.id)).where(
                            RegionalCycle.campaign_id == info.campaign_id,
                            RegionalCycle.status == "completed",
                        )) or 0)
                        offers = int(db.scalar(select(func.count(RegionalOffer.id)).where(
                            RegionalOffer.campaign_id == info.campaign_id,
                        )) or 0)
                        plans = list(db.scalars(select(RegionalCpuCyclePlan).where(
                            RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                        )))
                        events = int(db.scalar(select(func.count(RegionalEvent.id)).where(
                            RegionalEvent.campaign_id == info.campaign_id,
                        )) or 0)
                        row = {
                            "seed_index": seed_index,
                            "campaign_id": info.campaign_id,
                            "target_cycles": horizon,
                            "new_cycles_in_call": completed - previous_cycle,
                            "completed_cycles": completed,
                            "elapsed_seconds": round(elapsed, 4),
                            "seconds_per_new_cycle": round(elapsed / max(1, completed - previous_cycle), 4),
                            "regional_offers_materialized": offers,
                            "cpu_actions_total": sum(int(plan.actions) for plan in plans),
                            "cpu_plan_rows": len(plans),
                            "regional_event_rows": events,
                        }
                        snapshots.append(row)
                        previous_cycle = completed
                        print(
                            f"seed {seed_index + 1}/{seed_count} batch {row['new_cycles_in_call']} "
                            f"cycles: {elapsed:.3f}s ({row['seconds_per_new_cycle']:.4f}s/cycle)",
                            flush=True,
                        )
            finally:
                get_engine().dispose()
    grouped = {}
    for batch_size in BATCH_SIZES:
        rows = [row for row in snapshots if row["new_cycles_in_call"] == batch_size]
        seconds = [float(row["seconds_per_new_cycle"]) for row in rows]
        grouped[str(batch_size)] = {
            "samples": len(rows),
            "per_call_seconds_p50_p95_p99": {
                key: _percentile([float(row["elapsed_seconds"]) for row in rows], quantile)
                for key, quantile in (("p50", .50), ("p95", .95), ("p99", .99))
            },
            "seconds_per_cycle_p50_p95_p99": {
                key: _percentile(seconds, quantile)
                for key, quantile in (("p50", .50), ("p95", .95), ("p99", .99))
            },
            "seconds_per_cycle_median": round(median(seconds), 4) if seconds else None,
        }
    return {
        "report_id": "gim-stage5-regional-catchup-benchmark-20261030-v2",
        "scope": "fresh temporary SQLite campaigns; regional CPU and offer materialization only",
        "campaign_id_seed": str(CAMPAIGN_ID),
        "seed_count": seed_count,
        "cycle_seconds": CYCLE_SECONDS,
        "batch_sizes_cycles": list(BATCH_SIZES),
        "cumulative_horizons_cycles": list(HORIZONS),
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "checkpoints": snapshots,
        "summary_by_batch_cycles": grouped,
        "limitations": [
            "Percentiles describe this machine and this sample only; they are not an approved product SLA.",
            "Excludes UI, installed package, player activity, gathering, dungeon rewards, real saves, backup and restore.",
            "DB initialization and content seeding are excluded from timed calls.",
            "No product CPU or save-time budget or minimum hardware target has been approved.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "stage5_regional_catchup_benchmark_2026-10-30.json")
    parser.add_argument("--seeds", type=int, default=5)
    args = parser.parse_args()
    payload = run_benchmark(args.seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
