"""ML049 bounded controlled SQLite fixtures, not random campaigns or production rules."""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from itertools import combinations
import json
import os
from pathlib import Path
from random import Random
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.balance import ml049_replay_study as study

START = datetime(2026, 11, 17, tzinfo=timezone.utc)


class FixedSuccess(Random):
    def randint(self, a, b):
        return a


def setup_imports():
    os.environ.update(APP_MODE="desktop", DATABASE_URL="sqlite:///:memory:",
                      PYTHON_DOTENV_DISABLED="1", PYTHONDONTWRITEBYTECODE="1")
    sys.dont_write_bytecode = True
    import platform
    platform.uname = lambda: type("StudyUname", (), dict(system="Windows", node="ML049", release="study", version="study", machine="AMD64", processor="study"))()
    import app.models
    from app.database.connection import Base, create_database_engine
    from app.models import regional as m
    from app.models.campaign import CampaignMetadata
    from app.services import regional_cycle_service as svc, regional_event_service as events
    from sqlalchemy import select, func, text
    from sqlalchemy.orm import sessionmaker
    globals().update(m=m, CampaignMetadata=CampaignMetadata, svc=svc, events=events,
                     select=select, func=func, text=text, Base=Base,
                     create_database_engine=create_database_engine, sessionmaker=sessionmaker)


def campaign(db, label):
    c = CampaignMetadata(campaign_id=label, campaign_name=label, created_at_utc=START,
                         updated_at_utc=START, home_region="ML049 fixture", schema_version=8)
    db.add(c)
    db.flush()
    return c


def actor(db, c, name, region_code, *, team=True, slot=1):
    s = m.RegionalGuildState(campaign_id=c.campaign_id, name=name, region_code=region_code,
                            slot=slot, profile="new", archetype="contracts", level=1,
                            influence=0, reputation=0, event_wins=0, xp=0, power=10,
                            created_at_utc=START, updated_at_utc=START)
    db.add(s)
    db.flush()
    if team:
        db.add(m.RegionalCpuMercenary(campaign_id=c.campaign_id, guild_state_id=s.id, slot=1,
                                     name=name + " member", class_code="fixture", level=1,
                                     power=10, vitality=10, agility=10, intelligence=10, luck=10,
                                     armor=0, created_at_utc=START, updated_at_utc=START))
        for code in ("gold", "xp"):
            db.add(m.RegionalCpuResource(campaign_id=c.campaign_id, guild_state_id=s.id,
                                        resource_code=code, amount=0, capacity=1000000))
    db.flush()
    return s


def state(db, s):
    return {"guild": s.id, "name": s.name, "level": s.level, "xp": s.xp,
            "influence": s.influence, "reputation": s.reputation, "event_wins": s.event_wins,
            "active": s.active,
            "resources": {r.resource_code: r.amount for r in db.scalars(select(m.RegionalCpuResource).where(
                m.RegionalCpuResource.guild_state_id == s.id))},
            "roster": [{"id": r.id, "level": r.level, "slot": r.slot, "class": r.class_code,
                        "attributes": {k: getattr(r, k) for k in ("power", "vitality", "agility", "intelligence", "luck", "armor")},
                        "equipment": r.equipment_bonus_json} for r in db.scalars(select(m.RegionalCpuMercenary).where(
                m.RegionalCpuMercenary.guild_state_id == s.id))]}


def cycle(db, c, t):
    start = START + timedelta(seconds=(t - 1) * svc.CYCLE_SECONDS)
    row = m.RegionalCycle(campaign_id=c.campaign_id, cycle_number=t - 1,
                         starts_at_utc=start, ends_at_utc=start + timedelta(seconds=svc.CYCLE_SECONDS),
                         seed=f"controlled:{t}", rules_version="vigilia-v7")
    db.add(row)
    db.flush()
    return row


def add_offer(db, c, cy, region, slot, family, rank, duration, xp, gold):
    o = m.RegionalOffer(campaign_id=c.campaign_id, cycle_id=cy.id, cycle_number=cy.cycle_number,
                        region_code=region, slot=slot, offer_type=family, rank=rank,
                        name_snapshot=f"controlled {family} {slot}", description_snapshot="controlled fixture",
                        recommended_level_snapshot=1, recommended_power_snapshot=1,
                        duration_seconds_snapshot=duration, gold_reward_snapshot=gold,
                        xp_reward_snapshot=xp, success_chance_snapshot=95, created_at_utc=START)
    db.add(o)
    db.flush()
    return o


def rows_from_plan(plan, seed, t, s):
    outcomes = {r["action"]: r for r in json.loads(plan.outcomes_json)}
    return [{"seed": seed, "cycle": t, "guild": s.id, "name": s.name,
             "activity": f"plan:{plan.id}:action:{d['action']}", "event": d.get("event_id"),
             "family": d["offer_type"], "rank": d["rank"], "success": outcomes[d["action"]]["success"],
             "offer": d["offer_id"], "duration": d["duration_seconds"],
             "gold": outcomes[d["action"]]["gold"],
             "xp": outcomes[d["action"]]["xp"] * len(d["mercenary_slots"])}
            for d in json.loads(plan.decisions_json)]


def rebellion_fixture(db):
    c = campaign(db, "ml049-events")
    actors = [actor(db, c, name, "events", team=False, slot=i + 1)
              for i, name in enumerate(("LocalSuccess", "LocalFailure", "NoContribution"))]
    for s in actors:
        s.influence = s.reputation = 100
    records, ledger, snapshots = [], [], {}
    for t in range(1, 14):
        deadline = START + timedelta(hours=6 * t)
        event = m.RegionalEvent(campaign_id=c.campaign_id, event_type="rebellion", region_code="events",
                                trigger_cycle_number=t - 1, rules_version="vigilia-v7", seed=f"rebellion:{t}",
                                created_at_utc=deadline - timedelta(hours=5), expires_at_utc=deadline,
                                priority_ends_at_utc=deadline - timedelta(hours=4), player_decision="delegated_cpu")
        db.add(event)
        db.flush()
        for i, s in enumerate(actors):
            db.add(m.RegionalEventParticipant(event_id=event.id, guild_state_id=s.id, status="accepted"))
            successes, failures = ((1, 0) if i == 0 else (0, 2)) if t == 1 else ((3, 0) if i == 0 else (0, 1))
            if i < 2:
                db.add(m.RegionalEventActivity(event_id=event.id, guild_state_id=s.id,
                                              source_type="cpu_cycle", source_run_id=100 * t + i,
                                              status="resolved", successes=successes, failures=failures,
                                              contribution=successes + failures, resolved_at_utc=deadline))
        db.flush()
        before = {s.id: s.event_wins for s in actors}
        events.expire_due_events(db, c.campaign_id, deadline)
        db.commit()
        payload = json.loads(event.summary_json)
        for s in actors:
            if s.event_wins > before[s.id]:
                ledger.append({"seed": 910, "cycle": t, "guild": s.id, "activity": f"event:{event.id}:{s.id}",
                               "event": event.id, "family": "event", "rank": "C", "success": True})
        snapshots[910, t] = [state(db, s) for s in actors]
        stable = [s.event_wins for s in actors]
        # Public expiry/catch-up is repeated after reload, not the unguarded private resolver.
        db.expire_all()
        events.expire_due_events(db, c.campaign_id, deadline + timedelta(hours=24))
        db.commit()
        assert [s.event_wins for s in actors] == stable
        assert stable == ([0, 0, 0] if t == 1 else [t - 1, t - 1, 0])
        records.append({"event": event.id, "cycle": t, "global_result": payload["result"],
                        "activities": payload["activities"], "wins": stable, "repeat_expiry_unchanged": True,
                        "current_scores": [75 + .25 * min(100, s.event_wins * 10) for s in actors]})
    metrics, ranks = study.replay(ledger, snapshots)
    assert records[0]["global_result"] == "failure"
    assert records[1]["global_result"] == "success"
    assert [r["current_scores"][0] for r in records[-3:]] == [100, 100, 100]
    assert len(ledger) == 24  # 12 global wins x two contributing guilds, not activities.
    return {"records": records, "ledger": ledger, "rankings": ranks, "metrics": metrics,
            "asserts": "local success/global loss; local failure/global win; no contribution; 10-win cap; repeated expiry passed"}


def late_fixture(db):
    c = campaign(db, "ml049-late")
    world = m.RegionalWorldState(campaign_id=c.campaign_id, rules_version="vigilia-v7")
    db.add(world)
    actors = {}
    for name in ("Active", "Paused", "Late", "LateTwin"):
        db.add(m.RegionalRegionState(campaign_id=c.campaign_id, region_code=name, region_name=name))
        if name not in ("Late", "LateTwin"):
            actors[name] = actor(db, c, name, name)
    db.flush()
    ledger, snapshots, records, paired = [], {}, [], []
    for t in range(1, 13):
        if t == 5:
            assert db.scalar(select(func.count()).select_from(m.RegionalGuildState).where(
                m.RegionalGuildState.campaign_id == c.campaign_id)) == 2
            for name in ("Late", "LateTwin"):
                actors[name] = actor(db, c, name, name)
            db.commit()
            assert all(state(db, actors[n])["xp"] == 0 and actors[n].level == 1 for n in ("Late", "LateTwin"))
        cy = cycle(db, c, t)
        actors["Paused"].active = t not in (7, 8, 9)
        offers = {}
        for name in ("Active", "Paused", "Late", "LateTwin"):
            offers[name] = add_offer(db, c, cy, name, 1, "contract", "C", 7200, 400, 20)
        db.flush()
        svc._process_cycle(db, c.campaign_id, cy, world)
        db.commit()
        count_before = db.scalar(select(func.count()).select_from(m.RegionalCpuCyclePlan).where(
            m.RegionalCpuCyclePlan.campaign_id == c.campaign_id))
        plans = list(db.scalars(select(m.RegionalCpuCyclePlan).where(m.RegionalCpuCyclePlan.cycle_id == cy.id)))
        for plan in plans:
            s = db.get(m.RegionalGuildState, plan.guild_state_id)
            ledger.extend(rows_from_plan(plan, 920, t, s))
        snapshots[920, t] = [state(db, s) for s in actors.values()]
        _, before_rank = study.replay(ledger, snapshots)
        before_state = [state(db, s) for s in actors.values()]
        db.expire_all()
        svc._process_cycle(db, c.campaign_id, cy, world)
        db.commit()
        count_after = db.scalar(select(func.count()).select_from(m.RegionalCpuCyclePlan).where(
            m.RegionalCpuCyclePlan.campaign_id == c.campaign_id))
        assert count_before == count_after and before_state == [state(db, s) for s in actors.values()]
        after_rows = [row for p in db.scalars(select(m.RegionalCpuCyclePlan).where(
            m.RegionalCpuCyclePlan.cycle_id == cy.id)) for row in rows_from_plan(p, 920, t, db.get(m.RegionalGuildState, p.guild_state_id))]
        _, duplicate_rank = study.replay(ledger + after_rows, snapshots)
        # Ordinary actions have stable per-cycle IDs, and cannot award points again.
        assert before_rank == duplicate_rank
        if t == 10:
            # Bounded catch-up retry at return: replay the paused interval plus return.
            batch = list(db.scalars(select(m.RegionalCycle).where(
                m.RegionalCycle.campaign_id == c.campaign_id,
                m.RegionalCycle.cycle_number.between(6, 9)).order_by(m.RegionalCycle.cycle_number)))
            assert len(batch) == 4
            for _ in range(2):
                db.expire_all()
                for old_cycle in batch:
                    svc._process_cycle(db, c.campaign_id, old_cycle, world)
                db.commit()
                assert before_state == [state(db, s) for s in actors.values()]
                assert count_before == db.scalar(select(func.count()).select_from(m.RegionalCpuCyclePlan).where(
                    m.RegionalCpuCyclePlan.campaign_id == c.campaign_id))
        if t >= 5:
            l, twin = (actors[n] for n in ("Late", "LateTwin"))
            assert (l.xp, l.level, l.influence, l.reputation) == (twin.xp, twin.level, twin.influence, twin.reputation)
            paired.append({"cycle": t, "guilds": [l.id, twin.id], "offers": [offers[n].id for n in ("Late", "LateTwin")],
                           "identical_offer_values": True, "identical_initial_teams": t == 5,
                           "identical_outcomes": True})
        records.append({"cycle": t, "cycle_id": cy.id, "states": before_state,
                        "plans": [{"id": p.id, "guild": p.guild_state_id, "actions": p.actions} for p in plans],
                        "repeat_cycle_no_new_plan_or_points": True,
                        "catchup_7_through_10_repeated_twice": t == 10})
    counts = Counter(r["name"] for r in ledger)
    assert counts == {"Active": 12, "Paused": 9, "Late": 8, "LateTwin": 8}, counts
    assert not any(r["name"].startswith("Late") and r["cycle"] < 5 for r in ledger)
    metrics, ranks = study.replay(ledger, snapshots)
    ewma = {r["cycle"]: r["scores"] for r in ranks if r["model"] == "ewma8"}
    pid = actors["Paused"].id
    assert ewma[9][pid] < ewma[6][pid] and ewma[10][pid] > ewma[9][pid]
    assert ewma[12][actors["Late"].id] < ewma[12][actors["Active"].id]
    return {"records": records, "paired_opportunities": paired, "ledger": ledger, "rankings": ranks,
            "metrics": metrics, "action_counts": dict(counts),
            "asserts": "late row absent until 5; zero retrocredit; paired twins; pause 7..9; return 10; repeated process-cycle and projection passed",
            "scope": "Real model/planner/process-cycle in disposable SQLite; controlled catch-up of already materialized cycles, not desktop offline session service."}


def offer_signature(o):
    return [o.offer_type, o.rank, o.duration_seconds_snapshot, o.xp_reward_snapshot,
            o.gold_reward_snapshot, o.success_chance_snapshot, o.min_party_size_snapshot,
            o.max_party_size_snapshot, o.required_guild_level_snapshot]


def best_subset(offers, policy):
    allowed = [o for o in offers if policy == "rank_optimal" or (o.rank == "E" and (policy != "farm_one" or o.offer_type == "contract"))]
    best, chosen = None, []
    for count in range(len(allowed) + 1):
        for subset in combinations(allowed, count):
            seconds = sum(o.duration_seconds_snapshot for o in subset)
            if seconds > 18000:
                continue
            rows = [{"guild": 0, "activity": o.id, "event": None, "family": o.offer_type, "rank": o.rank, "success": True} for o in subset]
            value = study.points(rows)
            key = (-value, seconds, -sum(o.xp_reward_snapshot for o in subset), tuple(o.id for o in subset))
            if best is None or key < best:
                best, chosen = key, list(subset)
    return {o.id for o in chosen}


def policy_fixture(db):
    policies = ("current_xp_rate", "rank_optimal", "farm_multi", "farm_one")
    data, signatures = {}, {}
    for policy in policies:
        c = campaign(db, "ml049-policy-" + policy)
        region = m.RegionalRegionState(campaign_id=c.campaign_id, region_code="arena", region_name="arena")
        db.add(region)
        s = actor(db, c, policy, "arena")
        initial = state(db, s)
        if data:
            other = data["current_xp_rate"]["initial"]
            assert {k: initial[k] for k in ("level", "xp", "influence", "reputation", "event_wins", "resources")} == {
                k: other[k] for k in ("level", "xp", "influence", "reputation", "event_wins", "resources")}
            assert [{k: v for k, v in member.items() if k != "id"} for member in initial["roster"]] == [
                {k: v for k, v in member.items() if k != "id"} for member in other["roster"]]
        ledger, records = [], []
        for t in range(1, 5):
            cy = cycle(db, c, t)
            specs = [("contract", "E", 1800, 100, 20)] * 10 + [("dungeon", "E", 1800, 10, 2)] * 2 + [("boss", "E", 1800, 10, 2)] * 2 + [("contract", "A", 18000, 100, 5)]
            offers = [add_offer(db, c, cy, "arena", i + 1, *spec) for i, spec in enumerate(specs)]
            sig = [offer_signature(o) for o in offers]
            signatures[policy, t] = sig
            if policy != "current_xp_rate":
                assert sig == signatures["current_xp_rate", t]
            selected = best_subset(offers, policy) if policy != "current_xp_rate" else {o.id for o in offers}
            original_party = svc._cpu_offer_party

            def policy_party(offer, *args, **kwargs):
                return original_party(offer, *args, **kwargs) if offer.id in selected else None

            before = state(db, s)
            # Selection is the only policy intervention. Feasibility, outcomes, rewards and XP use live code.
            with patch.object(svc, "_cpu_offer_party", policy_party):
                plan = svc._cpu_plan_for_guild(db, c.campaign_id, cy, region, s)[0]
            rows = rows_from_plan(plan, 930, t, s)
            assert sum(r["duration"] for r in rows) <= 18000
            assert all(r["success"] for r in rows)
            ledger.extend(rows)
            records.append({"cycle": t, "cycle_id": cy.id, "plan_id": plan.id, "offers": [{"id": o.id, "values": offer_signature(o)} for o in offers],
                            "selected_ids": sorted(selected), "executed": rows, "points": study.points(rows),
                            "before": before, "after": state(db, s)})
            db.commit()
        final = state(db, s)
        points = sum(r["points"] for r in records)
        awarded_xp, awarded_gold = sum(r["xp"] for r in ledger), sum(r["gold"] for r in ledger)
        assert final["resources"] == {"gold": awarded_gold, "xp": awarded_xp}
        data[policy] = {"initial": initial, "final": final, "records": records,
                        "total_points": points, "xp_awarded": awarded_xp, "gold_awarded": awarded_gold,
                        "guild_level_gain": final["level"] - initial["level"],
                        "actions": len(ledger), "team_seconds_used": sum(r["duration"] for r in ledger),
                        "opportunity_signature_sha256": study.hashlib.sha256(json.dumps(sig).encode()).hexdigest()}
    assert len({v["opportunity_signature_sha256"] for v in data.values()}) == 1
    assert [data[p]["total_points"] for p in policies] == [6, 20, 18, 6]
    assert [data[p]["xp_awarded"] for p in policies] == [4000, 400, 960, 800]
    assert [data[p]["gold_awarded"] for p in policies] == [800, 20, 192, 160]
    assert data["farm_multi"]["total_points"] == 3 * data["farm_one"]["total_points"]
    assert data["rank_optimal"]["guild_level_gain"] < data["current_xp_rate"]["guild_level_gain"]
    return {"policies": data,
            "interventions": ["same 15 offer values per arm/cycle", "one identical initial member; no hires", "5h after 1h CPU priority", "forced successful resolution for every feasible action", "4 cycles; fixed offer access regardless of progression", "rank policies optimize deterministic points, then least time, then XP", "no production policy changes"],
            "asserts": "same offers/team/time/rewards; real planner feasibility; different choices; reconciled XP/gold/levels; multi-family exploit passed",
            "causal_scope": "Within this deterministic fixture only: policy action-set choice changes observed rewards/progression; no inference to natural success risk, world events, longer campaigns or player behavior."}


def main():
    prefix = ROOT / "reports/ml049_controlled_2026-11-17"
    output = Path(str(prefix) + "_results.json")
    prior = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    frozen = ROOT / "reports/ml049_replay_2026-11-17_ledger.json"
    original_hash = study.digest(frozen)
    assert original_hash == "dd2b05d0f2010cbaca4cb9a8539036b137ce87f9ee9b8e39bca4abf1d043d4c9"
    start = study.provenance()
    start["controlled_script"] = study.digest(Path(__file__))
    study.write_json(Path(str(prefix) + "_sources_start.json"), start)
    with tempfile.TemporaryDirectory(prefix="ml049_controlled_", dir=ROOT / "reports") as tmp:
        os.environ["TEMP"] = os.environ["TMP"] = tmp
        tempfile.tempdir = tmp
        setup_imports()
        engine = create_database_engine("sqlite:///" + (Path(tmp) / "controlled.sqlite").as_posix())
        try:
            Base.metadata.create_all(engine)
            with sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)() as db:
                with ExitStack() as stack:
                    stack.enter_context(patch.object(svc, "_rng", lambda *args: FixedSuccess(0)))
                    stack.enter_context(patch.object(svc, "_try_hire_cpu_mercenary", lambda *args: (None, 0)))
                    stack.enter_context(patch.object(events, "create_cycle_portals", lambda *args: None))
                    report = {"event_dedup": study.event_dedup_regression(),
                              "rebellions": rebellion_fixture(db), "late_pause_return": late_fixture(db),
                              "policy_response": policy_fixture(db)}
                db.commit()
                assert list(db.execute(text("PRAGMA foreign_key_check"))) == []
                assert db.scalar(text("PRAGMA integrity_check")) == "ok"
                report["sqlite"] = {"foreign_key_check": "passed", "integrity_check": "ok", "discarded": True,
                                    "schema": "real SQLAlchemy model metadata; minimal fixtures, not full migrated/seeded product campaign",
                                    "table_counts": {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in (CampaignMetadata, m.RegionalGuildState, m.RegionalCycle, m.RegionalCpuCyclePlan, m.RegionalOffer, m.RegionalEvent, m.RegionalEventActivity)}}
        finally:
            engine.dispose()
    end = study.provenance()
    end["controlled_script"] = study.digest(Path(__file__))
    study.write_json(Path(str(prefix) + "_sources_end.json"), end)
    assert study.digest(frozen) == original_hash
    report["original_ledger_sha256_preserved"] = original_hash
    report["source_changes"] = [p for p, h in start["sources"].items() if end["sources"].get(p) != h]
    report["sha_start"], report["sha_end"] = start["sha"], end["sha"]
    report["controlled_script_sha256"] = end["controlled_script"]
    # Prior schema revisions may add evidence fields; compare like-for-like current schema.
    same_schema = prior is not None and prior.get("controlled_script_sha256") == report["controlled_script_sha256"]
    if same_schema:
        serialized = json.loads(json.dumps(report))
        for key in ("event_dedup", "rebellions", "late_pause_return", "policy_response", "sqlite"):
            assert prior[key] == serialized[key], key
    report["reproduction"] = {"prior_same_script_compared": same_schema,
                              "scenario_payload_identical": True if same_schema else None}
    study.write_json(output, report)
    print(json.dumps({"asserts": "passed", "source_changes": report["source_changes"], "sqlite": report["sqlite"],
                      "policy_metrics": {p: {k: v[k] for k in ("total_points", "xp_awarded", "gold_awarded", "guild_level_gain", "actions")} for p, v in report["policy_response"]["policies"].items()}}), flush=True)


if __name__ == "__main__":
    main()
