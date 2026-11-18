"""Controlled global TOP2 alternative. Preserve every prior ML049 artifact."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from itertools import combinations
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.balance import ml049_controlled_study as fixture
from scripts.balance import ml049_replay_study as study

POLICIES = ("current_xp_rate", "rank_optimal", "farm_multi", "farm_one")
MEASURES = ("total_points", "xp_awarded", "gold_awarded", "guild_level_gain", "actions", "team_seconds_used")
PREFIX = ROOT / "reports/ml049_top2_2026-11-17"


def top2_global(rows, seen_events=None, ranked_families=("contract", "dungeon", "boss")):
    if seen_events is None:
        seen_events = set()
    seen_actions, values = set(), []
    for row in rows:
        if not row["success"]:
            continue
        if row["family"] == "event":
            if row.get("event") is None:
                raise ValueError("Confirmed event victory requires event ID")
            identity = row.get("seed"), row["guild"], row["event"]
            if identity in seen_events:
                continue
            seen_events.add(identity)
            value = 3
        elif row["family"] in ranked_families:
            identity = row.get("seed"), row["guild"], row["activity"]
            if identity in seen_actions:
                continue
            seen_actions.add(identity)
            value = "EDCBAS".index(row["rank"]) + 1
        else:
            continue
        values.append(value)
    return sum(v * w for v, w in zip(sorted(values, reverse=True), (1, .5)))


def pure_tests():
    def action(i, family="contract", rank="E", **kw):
        return {"seed": 981, "cycle": 16, "guild": 1, "activity": i, "event": None,
                "family": family, "rank": rank, "success": True, **kw}

    families = ("contract", "dungeon", "boss")
    spam = [action(i, families[i % 3]) for i in range(1000)]
    assert top2_global([]) == 0
    assert top2_global(spam[:1]) == 1
    assert all(top2_global(spam[:n]) == 1.5 for n in (2, 3, 6, 10, 100, 1000))
    assert top2_global(spam) == top2_global(spam * 5) == top2_global(list(reversed(spam))) == 1.5
    extended = families + ("fixture_family_4", "fixture_family_5")
    varied = [action(i, extended[i % 5]) for i in range(1000)]
    assert top2_global(varied, ranked_families=extended) == 1.5
    assert top2_global([action(1, rank="A")]) == 5
    assert top2_global([action(1, rank="A")] + spam) == 5.5
    assert top2_global([action(1, success=False)]) == 0
    event = action("win", "event", event=771)
    retained = set()
    assert top2_global([event, {**event, "activity": "duplicate"}], retained) == 3
    retained = {tuple(k) for k in json.loads(json.dumps(list(retained)))}
    assert top2_global([{**event, "cycle": 17}, {**event, "cycle": 33}], retained) == 0
    assert top2_global([{**event, "seed": 982}], retained) == 3
    assert top2_global([{**event, "guild": 2}], retained) == 3
    retained = set()
    assert top2_global([{**event, "success": False}], retained) == 0
    assert top2_global([event], retained) == 3
    # An event excluded by better actions still cannot be recycled in a later cycle.
    retained = set()
    high = [action("S1", rank="S"), action("S2", "boss", "S")]
    assert top2_global(high + [event], retained) == top2_global(high) == 9
    assert top2_global([{**event, "cycle": 17}], retained) == 0
    assert top2_global([action("A", rank="A"), event]) == 6.5
    values = [action(str(i), rank=r) for i, r in enumerate("EDCBAS")]
    assert top2_global(values + [event]) == 8.5  # S + .5 A, event gives no marginal point.

    with localcontext() as ctx:
        ctx.prec = 28
        decay = Decimal(2) ** (-Decimal(1) / Decimal(8))
        quantum = Decimal("0.000001")
        trajectory, memory = [], Decimal(0)
        for t in range(1, 56):
            memory = decay * memory + (1 - decay) * Decimal(9)
            bound = Decimal(9) * (1 - decay ** t)
            assert abs(memory - bound) < Decimal("1e-24") and memory < 9
            if t in (1, 8, 16, 32, 55):
                trajectory.append({"cycle": t, "M_pre_quantization_12": str(memory.quantize(Decimal("1e-12"), rounding=ROUND_HALF_EVEN)),
                                   "Q_official_6": str(memory.quantize(quantum, rounding=ROUND_HALF_EVEN))})
        assert Decimal("1.0000005").quantize(quantum, rounding=ROUND_HALF_EVEN) == Decimal("1.000000")
        assert Decimal("1.0000015").quantize(quantum, rounding=ROUND_HALF_EVEN) == Decimal("1.000002")
        assert Decimal("0.0000004").quantize(quantum, rounding=ROUND_HALF_EVEN) == 0
        # Official ties can arise before the internal asymptote, even at six places.
        official_limit_cycle = next(t for t in range(1, 400) if (
            Decimal(9) * (1 - decay ** t)).quantize(quantum, rounding=ROUND_HALF_EVEN) == Decimal("9.000000"))

    def expected_e(n, p):
        p = Decimal(str(p))
        q = 1 - p
        return 1 - q ** n + Decimal(".5") * (1 - q ** n - n * p * q ** (n - 1))

    expected = [{"attempts": n, "expected_E_points_independent_p95": str(expected_e(n, ".95"))} for n in (1, 2, 6, 10)]
    assert all(Decimal(r["expected_E_points_independent_p95"]) <= Decimal("1.5") for r in expected)
    assert expected_e(2, ".95") == Decimal("1.44875")
    assert Decimal(5) * Decimal(".25") < expected_e(2, ".95")
    assert not any(k == "app" or k.startswith("app.") for k in sys.modules)
    return {"asserts": "passed", "E_volume_duplicate_order_new_family_ceiling": 1.5, "single_A": 5,
            "global_event_identity_cross_cycle_season_resume": "passed",
            "eligible_families": list(families), "extension_test_families": list(extended),
            "per_cycle_formal_upper_bound_two_S": 9, "ewma_upper_envelope_not_campaign_measurement": trajectory,
            "first_cycle_Q6_rounds_to_formal_limit_under_constant_P9": official_limit_cycle,
            "probability_sensitivity_not_live_sampling": {"independent_E_attempts": expected,
                "single_A_p95_expected": "4.75", "single_A_p25_expected": "1.25",
                "two_E_p95_expected": "1.44875", "assumption": "independent Bernoulli trials; no time, opportunity or failure-reward inference"},
            "scope": "pure invariants/envelopes, not evidence of natural late-game sustainability"}


def optimize(offers, policy):
    allowed = [o for o in offers if policy == "rank_optimal" or (o.rank == "E" and (policy != "farm_one" or o.offer_type == "contract"))]
    best, chosen = None, []
    for count in range(len(allowed) + 1):
        for subset in combinations(allowed, count):
            seconds = sum(o.duration_seconds_snapshot for o in subset)
            if seconds > 18000:
                continue
            points = top2_global([{"guild": 0, "activity": o.id, "family": o.offer_type,
                                   "event": None, "rank": o.rank, "success": True} for o in subset])
            key = (-points, seconds, -sum(o.xp_reward_snapshot for o in subset), tuple(o.id for o in subset))
            if best is None or key < best:
                best, chosen = key, list(subset)
    return {o.id for o in chosen}


def global_fixture(db, reference):
    svc, m = fixture.svc, fixture.m
    data = {}
    for policy in POLICIES:
        c = fixture.campaign(db, "ml049-global-" + policy)
        region = m.RegionalRegionState(campaign_id=c.campaign_id, region_code="arena", region_name="arena")
        db.add(region)
        s = fixture.actor(db, c, policy, "arena")
        initial = fixture.state(db, s)
        old_initial = reference["policies"][policy]["initial"]
        for key in ("level", "xp", "influence", "reputation", "event_wins", "resources"):
            assert initial[key] == old_initial[key]
        assert [{k: v for k, v in r.items() if k != "id"} for r in initial["roster"]] == [
            {k: v for k, v in r.items() if k != "id"} for r in old_initial["roster"]]
        rows_all, records = [], []
        for t in range(1, 5):
            cy = fixture.cycle(db, c, t)
            specs = [("contract", "E", 1800, 100, 20)] * 10 + [("dungeon", "E", 1800, 10, 2)] * 2 + [("boss", "E", 1800, 10, 2)] * 2 + [("contract", "A", 18000, 100, 5)]
            offers = [fixture.add_offer(db, c, cy, "arena", i + 1, *spec) for i, spec in enumerate(specs)]
            signature = [fixture.offer_signature(o) for o in offers]
            assert signature == [o["values"] for o in reference["policies"][policy]["records"][t - 1]["offers"]]
            selected = {o.id for o in offers} if policy == "current_xp_rate" else optimize(offers, policy)
            original_party = svc._cpu_offer_party

            def policy_party(offer, *args, **kwargs):
                return original_party(offer, *args, **kwargs) if offer.id in selected else None

            before = fixture.state(db, s)
            with patch.object(svc, "_cpu_offer_party", policy_party):
                plan = svc._cpu_plan_for_guild(db, c.campaign_id, cy, region, s)[0]
            rows = fixture.rows_from_plan(plan, 983, t, s)
            assert sum(r["duration"] for r in rows) <= 18000 and all(r["success"] for r in rows)
            rows_all.extend(rows)
            records.append({"cycle": t, "cycle_id": cy.id, "plan_id": plan.id,
                            "offers": [{"id": o.id, "values": fixture.offer_signature(o)} for o in offers],
                            "selected_ids": sorted(selected), "executed": rows, "points": top2_global(rows),
                            "before": before, "after": fixture.state(db, s)})
            db.commit()
        final = fixture.state(db, s)
        xp, gold = sum(r["xp"] for r in rows_all), sum(r["gold"] for r in rows_all)
        assert final["resources"] == {"gold": gold, "xp": xp}
        data[policy] = {"initial": initial, "final": final, "records": records,
                        "total_points": sum(r["points"] for r in records), "xp_awarded": xp, "gold_awarded": gold,
                        "guild_level_gain": final["level"] - initial["level"], "actions": len(rows_all),
                        "team_seconds_used": sum(r["duration"] for r in rows_all)}
    assert [data[p]["total_points"] for p in POLICIES] == [6, 20, 6, 6]
    assert [data[p]["xp_awarded"] for p in POLICIES] == [4000, 400, 800, 800]
    assert [data[p]["gold_awarded"] for p in POLICIES] == [800, 20, 160, 160]
    assert [data[p]["actions"] for p in POLICIES] == [40, 4, 8, 8]
    assert data["farm_multi"]["total_points"] == data["farm_one"]["total_points"]
    for p in ("current_xp_rate", "rank_optimal", "farm_one"):
        assert all(data[p][k] == reference["policies"][p][k] for k in MEASURES)
    return {"policies": data, "asserts": "paired teams/offers/time/rewards; reoptimized subsets; global E ceiling; real reward/level reconciliation passed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pure-only", action="store_true")
    args = parser.parse_args()
    pure = pure_tests()
    if args.pure_only:
        print(json.dumps(pure), flush=True)
        return
    protected = {p.name: study.digest(p) for p in sorted((ROOT / "reports").glob("ml049_*"))
                 if p.is_file() and not p.name.startswith("ml049_top2_")}
    ledger = ROOT / "reports/ml049_replay_2026-11-17_ledger.json"
    assert study.digest(ledger) == "dd2b05d0f2010cbaca4cb9a8539036b137ce87f9ee9b8e39bca4abf1d043d4c9"
    approved = json.loads((ROOT / "reports/ml049_controlled_2026-11-17_results.json").read_text(encoding="utf-8"))
    output = Path(str(PREFIX) + "_results.json")
    prior = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    start = study.provenance()
    start["fixture_script_sha256"] = study.digest(Path(fixture.__file__))
    start["top2_script_sha256"] = study.digest(Path(__file__))
    study.write_json(Path(str(PREFIX) + "_sources_start.json"), start)
    with tempfile.TemporaryDirectory(prefix="ml049_top2_", dir=ROOT / "reports") as tmp:
        os.environ["TEMP"] = os.environ["TMP"] = tmp
        tempfile.tempdir = tmp
        fixture.setup_imports()
        engine = fixture.create_database_engine("sqlite:///" + (Path(tmp) / "top2.sqlite").as_posix())
        try:
            fixture.Base.metadata.create_all(engine)
            with fixture.sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)() as db:
                with ExitStack() as stack:
                    stack.enter_context(patch.object(fixture.svc, "_rng", lambda *args: fixture.FixedSuccess(0)))
                    stack.enter_context(patch.object(fixture.svc, "_try_hire_cpu_mercenary", lambda *args: (None, 0)))
                    old = fixture.policy_fixture(db)
                    assert all(old["policies"][p][k] == approved["policy_response"]["policies"][p][k] for p in POLICIES for k in MEASURES)
                    new = global_fixture(db, old)
                db.commit()
                assert list(db.execute(fixture.text("PRAGMA foreign_key_check"))) == []
                assert db.scalar(fixture.text("PRAGMA integrity_check")) == "ok"
                sqlite = {"integrity_check": "ok", "foreign_key_check": "passed", "discarded": True,
                          "table_counts": {model.__tablename__: db.scalar(fixture.select(fixture.func.count()).select_from(model))
                                           for model in (fixture.CampaignMetadata, fixture.m.RegionalGuildState, fixture.m.RegionalCycle,
                                                         fixture.m.RegionalCpuCyclePlan, fixture.m.RegionalOffer)}}
        finally:
            engine.dispose()
    end = study.provenance()
    end["fixture_script_sha256"] = study.digest(Path(fixture.__file__))
    end["top2_script_sha256"] = study.digest(Path(__file__))
    study.write_json(Path(str(PREFIX) + "_sources_end.json"), end)
    assert all(study.digest(ROOT / "reports" / name) == h for name, h in protected.items())
    payload = {"pure": pure, "per_family_controlled": old, "global_top2_controlled": new, "sqlite": sqlite}
    same = prior is not None and prior.get("script_sha256") == end["top2_script_sha256"]
    if same:
        assert prior["scenarios"] == json.loads(json.dumps(payload))
    report = {"scenarios": payload, "script_sha256": end["top2_script_sha256"],
              "protected_prior_artifacts_sha256": protected, "prior_artifacts_unchanged": True,
              "reproduction_same_script_payload_equal": True if same else None,
              "sha_start": start["sha"], "sha_end": end["sha"],
              "source_changes": [p for p, h in start["sources"].items() if end["sources"].get(p) != h],
              "limits": ["controlled four-cycle policies; snapshot chance95 but actual RNG success forced100%",
                         "probability sensitivity is separate exact Bernoulli algebra, not observed natural gameplay",
                         "formal P<=9 and EWMA envelope do not prove sustainable late game",
                         "original real-campaign evidence remains only 3x55, with original formulas and rounding",
                         "no production/UI/sprite/reward/XP changes"]}
    study.write_json(output, report)
    print(json.dumps({"asserts": "passed", "prior_artifacts_unchanged": True, "reproduction": report["reproduction_same_script_payload_equal"],
                      "source_changes": report["source_changes"], "sqlite": sqlite,
                      "before": {p: {k: old["policies"][p][k] for k in MEASURES} for p in POLICIES},
                      "after": {p: {k: new["policies"][p][k] for k in MEASURES} for p in POLICIES}}), flush=True)


if __name__ == "__main__":
    main()
