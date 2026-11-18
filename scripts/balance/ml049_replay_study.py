"""Independent ML049 study. No production writes; pure replay has no gameplay imports."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DECAY = 2 ** (-1 / 8)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance():
    paths = sorted(set(ROOT.glob("app/**/*.py")) | set(ROOT.glob("alembic/**/*.py"))
                   | {ROOT / "scripts/balance/simulate_regional_cpu_campaigns.py",
                      Path(__file__), ROOT / "docs/ml049_estudo_ranking.md"})
    return {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
            "sources": {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}}


def points(rows, seen_events=None):
    # Event identity outlives cycle/season boundaries; failures do not consume a win.
    if seen_events is None:
        seen_events = set()
    seen, families = set(), defaultdict(list)
    for r in rows:
        if r["family"] == "event":
            if not r["success"]:
                continue
            if r.get("event") is None:
                raise ValueError("Confirmed event victory requires an event ID")
            event_key = (r.get("seed"), r["guild"], r["event"])
            if event_key in seen_events:
                continue
            seen_events.add(event_key)
        identity = (r["guild"], r.get("event") if r["family"] == "event" else r["activity"], r["family"])
        if identity in seen:
            continue
        seen.add(identity)
        if r["success"] and r["family"] in ("contract", "dungeon", "boss", "event"):
            families[r["family"]].append(3 if r["family"] == "event" else "EDCBAS".index(r["rank"]) + 1)
    return sum(sum(v * w for v, w in zip(sorted(vals, reverse=True), (1, .5)))
               for vals in families.values())


def replay(ledger, snapshots):
    indexed = defaultdict(list)
    ledger_events = set()
    # Filter the complete ledger first, even when a resumed view omits old snapshots.
    for row in sorted(ledger, key=lambda r: (r["seed"], r["cycle"], str(r["guild"]), str(r["activity"]))):
        if row["family"] == "event" and row["success"]:
            if row.get("event") is None:
                raise ValueError("Confirmed event victory requires an event ID")
            event_key = row["seed"], row["guild"], row["event"]
            if event_key in ledger_events:
                continue
            ledger_events.add(event_key)
        indexed[row["seed"], row["cycle"], row["guild"]].append(row)
    states, previous, metrics, rankings, seen_events = {}, {}, {}, [], set()
    for (seed, cycle), rows in sorted(snapshots.items()):
        scores = {m: {} for m in ("current", "season16", "ewma8")}
        names = {r["guild"]: r["name"] for r in rows}
        for r in rows:
            key = seed, r["guild"]
            season, ewma = states.get(key, (0, 0))
            p = points(indexed[seed, cycle, r["guild"]], seen_events)
            season = (0 if (cycle - 1) % 16 == 0 else season) + p
            ewma = DECAY * ewma + (1 - DECAY) * p
            states[key] = season, ewma
            scores["current"][r["guild"]] = round(.5 * r["influence"] + .25 * r["reputation"]
                                                     + .25 * min(100, 10 * r["event_wins"]), 2)
            scores["season16"][r["guild"]] = season
            scores["ewma8"][r["guild"]] = round(ewma, 2)
        for model, values in scores.items():
            order = sorted(values, key=lambda g: (-values[g], names[g].casefold()))
            key = seed, model
            m = metrics.setdefault(key, {"tie_pair_cycles": 0, "leader_changes": 0, "top10_entries": 0,
                                          "leader_changes_outside_reset": 0, "top10_entries_outside_reset": 0})
            m["tie_pair_cycles"] += sum(n * (n - 1) // 2 for n in Counter(values.values()).values())
            old = previous.get(key)
            if old:
                change, entries = int(old[0] != order[0]), len(set(order[:10]) - set(old[:10]))
                m["leader_changes"] += change
                m["top10_entries"] += entries
                if (cycle - 1) % 16:
                    m["leader_changes_outside_reset"] += change
                    m["top10_entries_outside_reset"] += entries
            previous[key] = order
            rankings.append({"seed": seed, "cycle": cycle, "model": model,
                             "order": order, "scores": values})
    return [{"seed": s, "model": m, **v} for (s, m), v in metrics.items()], rankings


def synthetic():
    ledger, snapshots, axes = [], {}, defaultdict(lambda: [0, 0, 0])
    names = ["Alfa", "Bravo", "Cume", "Delta", "Eco", "Forte", "Giro", "Halo", "Iris", "Jade", "Kilo"]
    for t in range(1, 65):
        if t == 45:
            names.append("Nova")
        for g in names:
            actions = {"Alfa": [("C", 4), ("D", 3)], "Bravo": [("C", 4), ("D", 3)],
                       "Cume": ([("C", 6), ("D", 5), ("B", 4)] + ([("V", 3)] if t % 4 == 0 else [])) if t <= 20 else [],
                       "Delta": [("C", 1)] * 40, "Eco": [("C", 6), ("D", 4)] if t % 2 == 0 else [],
                       "Forte": [("C", 3), ("B", 2)] + ([("F", 6)] if t % 4 == 0 else []),
                       "Giro": [("C", 2), ("D", 2), ("D", 1)], "Halo": [("C", 1)],
                       "Iris": [("C", 2)] if t % 3 == 0 else [],
                       "Jade": [("C", 4)] + ([("V", 3)] if t % 4 == 0 else []),
                       "Kilo": [("D" if t % 2 else "B", 3)], "Nova": [("C", 5), ("D", 4)]}[g]
            for i, (kind, rank) in enumerate(actions):
                row = {"seed": 0, "cycle": t, "guild": g, "activity": f"{g}:{t}:{i}",
                       "event": t if kind == "V" else None, "family": {"C": "contract", "D": "dungeon", "B": "boss", "V": "event", "F": "contract"}[kind],
                       "rank": "EDCBAS"[rank - 1], "success": kind != "F"}
                ledger.append(row)
                a = axes[g]
                if kind == "V":
                    a[2] += 1
                elif kind == "F":
                    a[0], a[1] = min(100, a[0] + 1), max(0, a[1] - max(1, rank // 2))
                else:
                    a[0], a[1] = min(100, a[0] + rank), min(100, a[1] + rank)
                if g == "Delta" and i == 0:
                    ledger.extend([dict(row) for _ in range(5)])
        snapshots[0, t] = [{"guild": g, "name": g, "influence": axes[g][0], "reputation": axes[g][1], "event_wins": axes[g][2]} for g in names]
    assert len(ledger) == 3870
    assert len({r["activity"] for r in ledger}) == 3550
    assert points([r for r in ledger if r["guild"] == "Delta" and r["cycle"] == 51]) == 1.5
    metrics, ranks = replay(ledger, snapshots)
    expected = {"current": (833, 1, 1), "season16": (82, 2, 5), "ewma8": (47, 2, 2)}
    for model, target in expected.items():
        subset = [r for r in ranks if r["model"] == model and r["cycle"] >= 20]
        ties = sum(sum(n * (n - 1) // 2 for n in Counter(r["scores"].values()).values()) for r in subset[1:])
        leaders = sum(a["order"][0] != b["order"][0] for a, b in zip(subset, subset[1:]))
        entries = sum(len(set(b["order"][:10]) - set(a["order"][:10])) for a, b in zip(subset, subset[1:]))
        assert (ties, leaders, entries) == target, (model, ties, leaders, entries)
    assert abs(DECAY ** 8 - .5) < 1e-12
    event = {"guild": "X", "event": 1, "activity": 1, "family": "event", "success": True, "rank": "S"}
    assert points([event, {**event, "activity": 2}]) == 3
    spam = [r for r in ledger if r["guild"] == "Delta" and r["cycle"] == 51]
    assert points(spam) == points(spam + spam) == points(list(reversed(spam)))
    assert points([]) == points([{**spam[0], "success": False}]) == 0
    event_dedup_regression()
    return {"asserts": "passed", "records": len(ledger), "unique_actions": 3550, "metrics_21_64": expected}, ledger, ranks


def event_dedup_regression():
    base = {"seed": 1, "guild": "X", "event": 91, "family": "event", "rank": "C", "success": True}
    actions = [{**base, "cycle": t, "activity": str(t)} for t in (16, 17, 33, 40)]
    actions += [{**base, "cycle": 15, "activity": "participation", "success": False},
                {**base, "seed": 2, "cycle": 17, "activity": "other-seed"},
                {**base, "guild": "Y", "cycle": 17, "activity": "other-guild"}]
    ss = {(seed, t): [{"guild": g, "name": g, "influence": 0, "reputation": 0, "event_wins": 0}
                      for g in ("X", "Y")] for seed in (1, 2) for t in range(1, 41)}
    _, ranks = replay(actions, ss)
    _, reversed_ranks = replay(list(reversed(actions)), ss)
    assert ranks == reversed_ranks
    scores = {(r["seed"], r["cycle"], r["model"]): r["scores"] for r in ranks}
    assert scores[1, 16, "season16"]["X"] == 3
    assert scores[1, 17, "season16"]["X"] == scores[1, 33, "season16"]["X"] == 0
    assert scores[2, 17, "season16"]["X"] == scores[1, 17, "season16"]["Y"] == 3
    assert scores[1, 40, "ewma8"]["X"] == round(3 * (1 - DECAY) * DECAY ** 24, 2)
    retained = set()
    assert points([actions[0]], retained) == 3
    retained = {tuple(key) for key in json.loads(json.dumps(list(retained)))}
    assert points(actions[1:4], retained) == 0  # Resumed projection retains dedup state.
    _, resumed = replay(actions, {(1, 17): ss[1, 17]})
    assert next(r for r in resumed if r["model"] == "season16")["scores"]["X"] == 0
    return {"cross_cycle": "pass", "cross_season_16_17_33": "pass", "resume": "pass",
            "seed_and_guild_isolation": "pass", "failure_before_success": "pass",
            "resume_without_old_snapshot": "pass", "serialized_seen_state": "pass"}


def capture(seed, saves):
    from sqlalchemy import select
    from app.models.regional import RegionalGuildState, RegionalEvent, RegionalEventActivity
    from app.services import regional_cycle_service as svc
    from app.services import regional_event_service as ev
    from scripts.balance import simulate_regional_cpu_campaigns as harness
    ledger, plans, snapshots, initial, xp_calls = [], [], {}, {}, []
    original_plan, original_cycle = svc._cpu_plan_for_guild, svc._process_cycle
    original_xp, original_summary = svc._apply_cpu_xp, ev._resolve_rebellion_summary
    current_cycle = [0]

    def state(s):
        return {k: getattr(s, k) for k in ("influence", "reputation", "event_wins", "xp", "level")}

    def apply_xp(s, roster, gain):
        before = state(s)
        result = original_xp(s, roster, gain)
        xp_calls.append({"before": before, "after": state(s), "xp_party_awarded": gain})
        return result

    def plan_hook(db, campaign_id, cycle, region, s):
        before = state(s)
        xp_calls.clear()
        result = original_plan(db, campaign_id, cycle, region, s)
        plan = result[0]
        decisions, outcomes = json.loads(plan.decisions_json), json.loads(plan.outcomes_json)
        by_action = {x["action"]: x for x in outcomes}
        after, axes, xi = state(s), dict(before), iter(xp_calls)
        for d in decisions:
            o = by_action[d["action"]]
            a = dict(axes)
            family = d["offer_type"]
            if family != "portal":
                rank = "EDCBAS".index(d["rank"]) + 1
                axes["influence"] = min(100, axes["influence"] + (rank if o["success"] else 1))
                axes["reputation"] = min(100, axes["reputation"] + rank) if o["success"] else max(0, axes["reputation"] - max(1, rank // 2))
                if o["xp"] > 0:
                    x = next(xi)
                    axes["xp"], axes["level"] = x["after"]["xp"], x["after"]["level"]
            ledger.append({"seed": seed, "cycle": cycle.cycle_number + 1, "guild": s.id,
                           "name": s.name, "profile": s.profile, "region": s.region_code,
                           "activity": f"plan:{plan.id}:action:{d['action']}", "event": d.get("event_id"),
                           "family": family, "rank": d["rank"], "success": o["success"],
                           "before": a, "after": dict(axes), "gold_awarded": o["gold"] if family != "portal" else 0,
                           "xp_party_awarded": o["xp"] * len(d["mercenary_slots"]) if family != "portal" else 0,
                           "resolved_at": d.get("resolved_at_utc"), "plan": plan.id})
        assert axes == after, (seed, cycle.cycle_number, s.id, axes, after)
        plans.append({"seed": seed, "cycle": cycle.cycle_number + 1, "guild": s.id, "profile": s.profile,
                      "plan": plan.id, "before": before, "after": after,
                      "resources_before": json.loads(plan.resources_before_json),
                      "resources_after": json.loads(plan.resources_after_json),
                      "xp_earned": plan.xp_earned, "gold_earned": plan.gold_earned,
                      "hire_gold_spent": plan.hire_gold_spent})
        return result

    def summary_hook(db, event, payload):
        states = list(db.scalars(select(RegionalGuildState).where(RegionalGuildState.campaign_id == event.campaign_id)))
        before = {s.id: state(s) for s in states}
        result = original_summary(db, event, payload)
        for s in states:
            if s.event_wins > before[s.id]["event_wins"]:
                assert s.event_wins - before[s.id]["event_wins"] == 1
                ledger.append({"seed": seed, "cycle": current_cycle[0], "guild": s.id, "name": s.name,
                               "profile": s.profile, "region": s.region_code, "activity": f"victory:{event.id}:{s.id}",
                               "event": event.id, "family": "event", "rank": "C", "success": True,
                               "before": before[s.id], "after": state(s), "gold_awarded": 0, "xp_party_awarded": 0})
        return result

    def cycle_hook(db, campaign_id, cycle, world):
        current_cycle[0] = cycle.cycle_number + 1
        states = list(db.scalars(select(RegionalGuildState).where(RegionalGuildState.campaign_id == campaign_id)))
        for s in states:
            initial.setdefault(s.id, {"guild": s.id, "name": s.name, "profile": s.profile, **state(s)})
        result = original_cycle(db, campaign_id, cycle, world)
        snapshots[seed, current_cycle[0]] = [{"guild": s.id, "name": s.name, "profile": s.profile,
                                            "region": s.region_code, **state(s)} for s in states]
        print(f"seed={seed} completed={current_cycle[0]}/55", flush=True)
        return result

    harness.HORIZON = 55
    with ExitStack() as stack:
        for obj, name, fn in ((svc, "_cpu_plan_for_guild", plan_hook), (svc, "_process_cycle", cycle_hook),
                              (svc, "_apply_cpu_xp", apply_xp), (ev, "_resolve_rebellion_summary", summary_hook)):
            stack.enter_context(patch.object(obj, name, fn))
        result = harness.run_campaign(seed, saves)
    assert len(snapshots) == 55, len(snapshots)
    return ledger, plans, snapshots, initial, result


def observed(ledger, plans, snapshots, initials):
    report = []
    for seed, initial in initials.items():
        for guild, first in initial.items():
            series = [r for (s, t), rows in sorted(snapshots.items()) if s == seed for r in rows if r["guild"] == guild]
            actions = [r for r in ledger if r["seed"] == seed and r["guild"] == guild and r["family"] != "event"]
            ps = [r for r in plans if r["seed"] == seed and r["guild"] == guild]
            active = {r["cycle"] for r in actions}
            longest = run = 0
            for t in range(1, 56):
                run = 0 if t in active else run + 1
                longest = max(longest, run)
            row = {"seed": seed, "guild": guild, "name": first["name"], "profile": first["profile"],
                   "initial": first, "final": series[-1], "activity_cycles": len(active), "longest_no_action_streak": longest,
                   "actions": len(actions), "successes": sum(r["success"] for r in actions),
                   "families": dict(Counter(r["family"] for r in actions)),
                   "gross_xp_party": sum(r["xp_party_awarded"] for r in actions),
                   "plan_xp_earned_telemetry": sum(r["xp_earned"] for r in ps),
                   "gross_gold": sum(r["gold_earned"] for r in ps),
                   "hire_gold_spent": sum(r["hire_gold_spent"] for r in ps),
                   "resource_net": {k: ps[-1]["resources_after"].get(k, 0) - ps[0]["resources_before"].get(k, 0) for k in ("gold", "xp")} if ps else {}}
            row["saturation"] = {axis: {"first_cycle": next((i for i, r in enumerate(series, 1) if r[axis] >= cap), None),
                                         "cycles_at_cap": sum(r[axis] >= cap for r in series), "final": series[-1][axis]}
                                 for axis, cap in (("influence", 100), ("reputation", 100), ("event_wins", 10))}
            report.append(row)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument("--reanalyze", action="store_true", help="Pure replay of existing frozen ledger; no campaign imports")
    parser.add_argument("--output", default="reports/ml049_replay_2026-11-17")
    args = parser.parse_args()
    prefix = ROOT / args.output
    assert prefix.resolve().is_relative_to((ROOT / "reports").resolve())
    prefix.parent.mkdir(exist_ok=True)
    if args.reanalyze:
        frozen = Path(str(prefix) + "_ledger.json")
        output = Path(str(prefix) + "_results.json")
        report = json.loads(output.read_text(encoding="utf-8"))
        assert digest(frozen) == report["ledger_sha256"]
        data = json.loads(frozen.read_text(encoding="utf-8"))
        snapshots = {(r["seed"], r["cycle"]): r["guilds"] for r in data["snapshots"]}
        metrics, ranks = replay(data["actions"], snapshots)
        assert metrics == report["metrics"]
        assert json.loads(json.dumps(ranks)) == json.loads(Path(str(prefix) + "_rankings.json").read_text(encoding="utf-8"))
        initials = defaultdict(dict)
        for guild in report["guilds"]:
            initials[guild["seed"]][guild["guild"]] = guild["initial"]
        report["guilds"] = observed(data["actions"], data["plans"], snapshots, initials)
        report["analysis_revision"] = {"script_sha256": digest(Path(__file__)),
                                       "reason": "XP from outcomes; P2 event dedup retained across entire replay, including seasons. Original collection hashes unchanged.",
                                       "event_dedup_tests": event_dedup_regression()}
        assert digest(frozen) == report["ledger_sha256"]
        assert not any(k == "app" or k.startswith("app.") for k in sys.modules)
        write_json(output, report)
        print("Frozen hash, all metrics/rankings and pure import isolation: PASS")
        return
    syn, synledger, synranks = synthetic()
    write_json(Path(str(prefix) + "_synthetic.json"), {"validation": syn, "ledger": synledger, "rankings": synranks})
    print(json.dumps(syn), flush=True)
    if args.synthetic_only:
        return
    start = provenance()
    write_json(Path(str(prefix) + "_sources_start.json"), start)
    os.environ.update(APP_MODE="desktop", DATABASE_URL="sqlite:///:memory:", PYTHONDONTWRITEBYTECODE="1", PYTHON_DOTENV_DISABLED="1")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    # Avoid Windows WMI subprocesses; platform identity does not enter campaign RNG.
    import platform
    platform.uname = lambda: type("StudyUname", (), dict(system="Windows", node="ML049", release="study", version="study", machine="AMD64", processor="study"))()
    ledger, plans, snapshots, initials, results = [], [], {}, {}, []
    error = None
    try:
        with tempfile.TemporaryDirectory(prefix="ml049-", dir=prefix.parent) as tmp:
            os.environ["TEMP"] = os.environ["TMP"] = tmp
            tempfile.tempdir = tmp
            for seed in range(2026110301, 2026110304):
                rows, ps, ss, ii, result = capture(seed, Path(tmp) / "saves")
                ledger.extend(rows)
                plans.extend(ps)
                snapshots.update(ss)
                initials[seed] = ii
                results.append(result)
            from app.database.connection import configure_database
            configure_database("sqlite:///:memory:")
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
    finally:
        end = provenance()
        write_json(Path(str(prefix) + "_sources_end.json"), end)
    changes = [p for p, h in start["sources"].items() if end["sources"].get(p) != h]
    ledger.sort(key=lambda r: (r["seed"], r["cycle"], r["guild"], r["profile"], r["activity"], str(r.get("event")), r["family"], r["rank"], r["success"]))
    frozen = Path(str(prefix) + "_ledger.json")
    write_json(frozen, {"actions": ledger, "plans": plans, "snapshots": [{"seed": s, "cycle": t, "guilds": rows} for (s, t), rows in sorted(snapshots.items())]})
    frozen_hash = digest(frozen)
    reloaded = json.loads(frozen.read_text(encoding="utf-8"))
    metrics, ranks = replay(reloaded["actions"], {(r["seed"], r["cycle"]): r["guilds"] for r in reloaded["snapshots"]})
    assert digest(frozen) == frozen_hash
    write_json(Path(str(prefix) + "_rankings.json"), ranks)
    write_json(Path(str(prefix) + "_results.json"), {"error": error, "ledger_sha256": frozen_hash,
               "source_changes": changes, "sha_start": start["sha"], "sha_end": end["sha"],
               "campaigns_completed": len(results), "horizon": 55, "metrics": metrics,
               "guilds": observed(ledger, plans, snapshots, initials), "campaign_results": results,
               "synthetic": syn,
               "limits": ["Formula-only replay: no behavioral/economic counterfactual.",
                          "Player idle; CPU/player opportunity parity not established.",
                          "Cycle labels are completed zero-based service cycles plus one; 1..55.",
                          "I/R action deltas reconstructed from actual outcomes, asserted against live plan states; XP/level hooked live.",
                          "Resource balances/hiring observed at plan boundaries, not individual action boundaries.",
                          "Snapshots at process-cycle end, before next materialization/board refresh.",
                          "Synthetic absence/newcomer/spam are not real campaign behavioral evidence."]})
    print(json.dumps({"completed": len(results), "ledger_rows": len(ledger), "sha256": frozen_hash, "changed_sources": changes, "error": error}), flush=True)


if __name__ == "__main__":
    main()
