"""Run a bounded paired ML-038 CPU simulation from a disposable template DB."""

from __future__ import annotations

import argparse
import runpy
import sys
import tempfile
from pathlib import Path

from sqlalchemy import event


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True,
                        help="SQLite campaign test template located under .lot-e2-test-tmp")
    parser.add_argument("--limit", type=int, default=5,
                        help="number of paired deterministic seeds (maximum 5 for this check)")
    parser.add_argument("--label", required=True,
                        help="unique report suffix; refuses to overwrite existing reports")
    args = parser.parse_args()
    template = args.template_db.resolve()
    test_root = TEST_ROOT.resolve()
    if not template.is_relative_to(test_root) or not template.is_file():
        parser.error("--template-db must be an existing SQLite file under .lot-e2-test-tmp")
    if not 1 <= args.limit <= 5:
        parser.error("--limit must be from 1 to 5")

    output = ROOT / "reports"
    stem = f"lot_e2_ml029_cpu_paired_{args.label}"
    existing = [output / f"{stem}.{extension}" for extension in ("json", "md", "csv")]
    if any(path.exists() for path in existing):
        parser.error(f"report label already exists: {args.label}")

    sys.path.insert(0, str(ROOT))
    _install_disposable_sqlite_pragmas()
    mod = runpy.run_path(str(ROOT / "scripts/balance/compare_ml029_cpu_balance.py"),
                         run_name="ml038_paired")
    simulator = mod["simulator"]
    pairs: list[dict] = []
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix="ml038-cpu-paired-", dir=TEST_ROOT)
    working = Path(temporary.name)
    try:
        for index, seed in enumerate(simulator.SEEDS[:args.limit], start=1):
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
                f"XP {baseline['total_xp_awarded']}->{candidate['total_xp_awarded']}; "
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
