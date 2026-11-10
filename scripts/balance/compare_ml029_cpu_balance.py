"""Paired live-service CPU simulation of ML-029 baseline and candidate power.

Uses the same 20 deterministic seed UUIDs and disposable cloned campaign save for
each treatment. No user save, live profile, installer, or production data is used.
"""

from __future__ import annotations

import json
import argparse
import sys
from collections import defaultdict
from datetime import timedelta
from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "balance"))

import simulate_regional_cpu_campaigns as simulator  # noqa: E402
from app.database.connection import SessionLocal, configure_database  # noqa: E402
from app.models.campaign import CampaignMetadata  # noqa: E402
from app.models.regional import (  # noqa: E402
    RegionalCpuCyclePlan,
    RegionalCycle,
    RegionalCycleRegion,
    RegionalEvent,
    RegionalGuildState,
    RegionalOffer,
)
from app.services.campaign_service import CampaignService  # noqa: E402
from app.services import regional_cycle_service  # noqa: E402
from app.services.mission_power_service import common_apprentice_reference_power  # noqa: E402


PHASES = (("early", 0, 20), ("mid", 20, 60), ("late", 60, simulator.HORIZON))
SCOPES = ("global", "home_region", "other_regions")


def _phase(cycle_number: int) -> str:
    return next(name for name, start, end in PHASES if start <= cycle_number < end)


def _is_opened(event: RegionalEvent) -> bool:
    return event.status not in {"not_triggered", "suppressed"}


def _event_scope_phase_metrics(summary: dict, home_region: str) -> dict[str, dict[str, int]]:
    metrics: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for region_code, region in summary.get("regional", {}).items():
        scope = "home_region" if region_code == home_region else "other_regions"
        for cycle_number in region.get("portal_cycles", []):
            phase = _phase(int(cycle_number))
            for bucket in ("global", scope):
                metrics[f"{bucket}|{phase}"]["opened_portals"] += 1
    for cycle in summary.get("rebellion_funnel_by_cycle", []):
        phase = _phase(int(cycle.get("cycle", 0)))
        for region_code in cycle.get("rebellion_opened_regions", []):
            scope = "home_region" if region_code == home_region else "other_regions"
            for bucket in ("global", scope):
                metrics[f"{bucket}|{phase}"]["opened_rebellions"] += 1
    return {key: dict(values) for key, values in metrics.items()}


def _capture_run(
    seed: int,
    saves_root: Path,
    template_database: Path,
    *,
    candidate: bool,
    baseline_policy: str = "template",
) -> dict:
    eligible_contracts: set[tuple[int, int]] = set()
    original_party = regional_cycle_service._cpu_offer_party

    def capture_party(offer, state, roster, available_at, deadline, class_roles, **kwargs):
        choice = original_party(
            offer, state, roster, available_at, deadline, class_roles, **kwargs,
        )
        if choice is not None and offer.offer_type == "contract":
            start_at, party = choice
            if start_at + timedelta(seconds=max(1, offer.duration_seconds_snapshot)) <= deadline:
                eligible_contracts.add((state.id, offer.id))
        return choice

    previous_rank_multipliers = {
        "E": 0.700, "D": 0.735, "C": 0.770, "B": 0.840, "A": 0.945, "S": 1.085,
    }
    if baseline_policy == "previous_rank_table":
        def baseline_power(level, rank, max_party_size, *, fallback_power):
            multiplier = previous_rank_multipliers.get(str(rank).upper())
            if multiplier is None:
                return max(1, int(fallback_power or 1))
            return max(1, ceil(
                common_apprentice_reference_power(level) * multiplier * max(1, int(max_party_size or 1))
            ))
    elif baseline_policy == "template":
        baseline_power = lambda _level, _rank, _party, *, fallback_power: fallback_power
    else:
        raise ValueError(f"Unknown baseline policy: {baseline_policy}")
    with patch.object(regional_cycle_service, "_cpu_offer_party", side_effect=capture_party):
        if candidate:
            result = simulator.run_campaign(seed, saves_root, template_database)
        else:
            with patch.object(
                regional_cycle_service,
                "recommended_regional_contract_power",
                side_effect=baseline_power,
            ):
                result = simulator.run_campaign(seed, saves_root, template_database)

    campaign_id = result["campaign_id"]
    campaign_path = saves_root / f"{campaign_id}.db"
    configure_database(f"sqlite:///{campaign_path.as_posix()}")
    with SessionLocal() as db:
        campaign = db.get(CampaignMetadata, campaign_id)
        home_region = next(code for code, name in simulator.REGIONS if name == campaign.home_region)
        state_rows = list(db.scalars(select(RegionalGuildState).where(
            RegionalGuildState.campaign_id == campaign_id,
            RegionalGuildState.guild_id.is_(None),
            RegionalGuildState.active.is_(True),
        )))
        states = {state.id: state for state in state_rows}
        cycle_rows = list(db.scalars(select(RegionalCycle).where(
            RegionalCycle.campaign_id == campaign_id,
            RegionalCycle.cycle_number < simulator.HORIZON,
        )))
        cycles = {cycle.id: cycle.cycle_number for cycle in cycle_rows}
        plans = list(db.scalars(select(RegionalCpuCyclePlan).where(
            RegionalCpuCyclePlan.campaign_id == campaign_id,
        )))
        offer_rows = list(db.scalars(select(RegionalOffer).where(
            RegionalOffer.campaign_id == campaign_id,
        )))
        offers = {offer.id: offer for offer in offer_rows}
        region_snapshots = list(db.scalars(select(RegionalCycleRegion).where(
            RegionalCycleRegion.campaign_id == campaign_id,
            RegionalCycleRegion.cycle_id.in_(select(RegionalCycle.id).where(
                RegionalCycle.campaign_id == campaign_id,
                RegionalCycle.cycle_number < simulator.HORIZON,
            )),
        )))
        metric_buckets: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))

        def add(scope: str, phase: str, key: str, value: float = 1) -> None:
            metric_buckets[(scope, phase)][key] += value

        for state_id, offer_id in eligible_contracts:
            state = states.get(state_id)
            offer = offers.get(offer_id)
            if state is None or offer is None or offer.cycle_id not in cycles:
                continue
            phase = _phase(cycles[offer.cycle_id])
            add("global", phase, "eligible_contract_offer_cpu_pairs")
            add("home_region" if state.region_code == home_region else "other_regions",
                phase, "eligible_contract_offer_cpu_pairs")

        for plan in plans:
            cycle_number = cycles.get(plan.cycle_id)
            state = states.get(plan.guild_state_id)
            if cycle_number is None or state is None:
                continue
            phase = _phase(cycle_number)
            scopes = ("global", "home_region" if state.region_code == home_region else "other_regions")
            decisions = json.loads(plan.decisions_json or "[]")
            outcomes = json.loads(plan.outcomes_json or "[]")
            contract_decisions = [row for row in decisions if row.get("offer_type") == "contract"]
            contract_outcomes = [row for row in outcomes if row.get("offer_id") in {
                decision.get("offer_id") for decision in contract_decisions
            }]
            for scope in scopes:
                add(scope, phase, "cpu_plans")
                add(scope, phase, "contract_started", len(contract_decisions))
                add(scope, phase, "contract_successes", sum(bool(row.get("success")) for row in contract_outcomes))
                add(scope, phase, "contract_failures", sum(not bool(row.get("success")) for row in contract_outcomes))
                add(scope, phase, "contract_chance_sum", sum(
                    float(row.get("success_chance", 0)) for row in contract_decisions
                ))
                add(scope, phase, "contract_chance_samples", len(contract_decisions))
                add(scope, phase, "contract_gold_awarded", sum(int(row.get("gold", 0)) for row in contract_outcomes))
                add(scope, phase, "contract_xp_awarded", sum(int(row.get("xp", 0)) for row in contract_outcomes))
                add(scope, phase, "all_cpu_actions", int(plan.resolved_actions or 0))
                add(scope, phase, "all_cpu_successes", int(plan.successes or 0))
                add(scope, phase, "all_cpu_failures", int(plan.failures or 0))
                add(scope, phase, "cpu_hires", int(plan.hired_count or 0))
                add(scope, phase, "cpu_hire_gold_spent", int(plan.hire_gold_spent or 0))
                before = json.loads(plan.resources_before_json or "{}")
                after = json.loads(plan.resources_after_json or "{}")
                for resource_code in set(before) | set(after):
                    add(scope, phase, f"resource_net_{resource_code}",
                        float(after.get(resource_code, 0)) - float(before.get(resource_code, 0)))
                snapshot = json.loads(plan.roster_snapshot_json or "[]")
                add(scope, phase, "roster_level_sum", sum(int(row.get("level", 1)) for row in snapshot))
                add(scope, phase, "roster_members", len(snapshot))

        for row in region_snapshots:
            cycle_number = cycles.get(row.cycle_id)
            if cycle_number is None:
                continue
            phase = _phase(cycle_number)
            regional_scope = "home_region" if row.region_code == home_region else "other_regions"
            for scope in ("global", regional_scope):
                add(scope, phase, "threat_after_sum", float(row.threat_after))
                add(scope, phase, "security_after_sum", float(row.security_after))
                add(scope, phase, "regional_snapshot_count")
                add(scope, phase, "threat_85_cycles", float(row.threat_after >= 85))
                add(scope, phase, "security_25_cycles", float(row.security_after <= 25))
                add(scope, phase, "joint_rebellion_threshold_cycles",
                    float(row.threat_after >= 85 and row.security_after <= 25))

        final_state_by_scope: dict[str, list[RegionalGuildState]] = defaultdict(list)
        for state in state_rows:
            scope = "home_region" if state.region_code == home_region else "other_regions"
            final_state_by_scope[scope].append(state)
        for scope in SCOPES:
            if scope == "global":
                picked_states = state_rows
            else:
                picked_states = final_state_by_scope[scope]
            if picked_states:
                add(scope, "final", "cpu_guild_level_sum", sum(state.level for state in picked_states))
                add(scope, "final", "cpu_guild_state_count", len(picked_states))
                add(scope, "final", "cpu_roster_size_sum", sum(state.roster_size for state in picked_states))
                add(scope, "final", "cpu_guild_xp_sum", sum(state.xp for state in picked_states))

        events = list(db.scalars(select(RegionalEvent).where(
            RegionalEvent.campaign_id == campaign_id,
        )))
        rebellion_events = [event for event in events if event.event_type == "rebellion"]
        portal_events = [event for event in events if event.event_type == "portal"]
        portal_decisions = [decision for plan in plans for decision in json.loads(plan.decisions_json or "[]")
                            if decision.get("offer_type") == "portal"]
        portal_outcomes = [outcome for plan in plans for outcome in json.loads(plan.outcomes_json or "[]")
                           if outcome.get("offer_id") in {row.get("offer_id") for row in portal_decisions}]
        eligible_threshold_cycles = sum(
            row.threat_after >= 85 and row.security_after <= 25 for row in region_snapshots
        )
        opened_rebellions = sum(_is_opened(event) for event in rebellion_events)
        opened_portals = sum(_is_opened(event) for event in portal_events)
        event_metrics = {
            "opened_rebellions": opened_rebellions,
            "selected_rebellion_rolls": sum(
                bool(json.loads(event.summary_json or "{}").get("roll_selected"))
                for event in rebellion_events
            ),
            "eligible_region_cycles": eligible_threshold_cycles,
            "opened_portals": opened_portals,
            "portal_cpu_started": len(portal_decisions),
            "portal_cpu_successes": sum(bool(row.get("success")) for row in portal_outcomes),
            "portal_cpu_failures": sum(not bool(row.get("success")) for row in portal_outcomes),
        }
        captured = {
            "seed": seed,
            "campaign_id": campaign_id,
            "home_region": home_region,
            "summary": result,
            "buckets": {f"{scope}|{phase}": dict(values)
                        for (scope, phase), values in metric_buckets.items()},
            "event_metrics": event_metrics,
        }
    configure_database("sqlite:///:memory:")
    return captured


def _run_sample(
    output_dir: Path,
    seeds: tuple[int, ...] = simulator.SEEDS,
    label: str = "2026-11-09-adjusted",
) -> list[dict]:
    paired: list[dict] = []
    with TemporaryDirectory(prefix="ml029-cpu-paired-", dir=ROOT) as temp_name:
        temp_dir = Path(temp_name)
        template_saves = temp_dir / "template"
        template_campaign = CampaignService(template_saves).create_campaign(
            "ML-029 pareado", "Guilda de calibração",
        )
        CampaignService(template_saves).activate_campaign(template_campaign.campaign_id)
        try:
            for index, seed in enumerate(seeds, start=1):
                seed_pair = {}
                for scenario_label, candidate in (("baseline", False), ("ml029_e2", True)):
                    run = _capture_run(
                        seed,
                        temp_dir / scenario_label / "saves",
                        Path(template_campaign.database_path),
                        candidate=candidate,
                    )
                    seed_pair[scenario_label] = run
                paired.append(seed_pair)
                baseline = seed_pair["baseline"]["summary"]
                candidate = seed_pair["ml029_e2"]["summary"]
                print(
                    f"[{index}/{len(seeds)}] seed={seed} "
                    f"CPU success {baseline['cpu_success_rate']:.1%}->{candidate['cpu_success_rate']:.1%}; "
                    f"rebellions {baseline['opened_rebellions']}->{candidate['opened_rebellions']}; "
                    f"portals {baseline['opened_portals']}->{candidate['opened_portals']}",
                    flush=True,
                )
                _write_outputs(paired, output_dir, label)
        finally:
            configure_database("sqlite:///:memory:")
    _write_outputs(paired, output_dir, label)
    return paired


def _write_outputs(
    paired: list[dict],
    output_dir: Path,
    label: str,
    *,
    baseline_description: str = "template recommended_power",
    title: str = "ML-029 E2 — simulação pareada de CPU",
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"lot_e2_ml029_cpu_paired_{label}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    csv_path = output_dir / f"{stem}.csv"
    serializable = []
    rows = []
    totals: dict[str, dict[str, dict[str, float]]] = {
        scenario: defaultdict(lambda: defaultdict(float)) for scenario in ("baseline", "ml029_e2")
    }
    for pair in paired:
        pair_summary = {"seed": pair["baseline"]["seed"], "home_region": pair["baseline"]["home_region"]}
        for scenario in ("baseline", "ml029_e2"):
            run = pair[scenario]
            summary = run["summary"]
            event_scope_phase = _event_scope_phase_metrics(summary, run["home_region"])
            phase_keys = [f"{scope}|{phase}" for scope in SCOPES
                          for phase in [name for name, _, _ in PHASES] + ["final"]]
            for scope_phase in phase_keys:
                bucket = run["buckets"].get(scope_phase, {})
                for metric, value in bucket.items():
                    totals[scenario][scope_phase][metric] += value
                scope, phase = scope_phase.split("|")
                row = {
                    "seed": run["seed"],
                    "scenario": scenario,
                    "home_region": run["home_region"],
                    "scope": scope,
                    "phase": phase,
                    **bucket,
                    "cpu_success_rate": summary["cpu_success_rate"],
                    "cpu_actions_per_cycle": summary["cpu_actions_per_cycle_global"],
                    "opened_portals": run["event_metrics"]["opened_portals"],
                    "opened_rebellions": run["event_metrics"]["opened_rebellions"],
                    "eligible_region_cycles": run["event_metrics"]["eligible_region_cycles"],
                    "portal_cpu_started": run["event_metrics"]["portal_cpu_started"],
                    **event_scope_phase.get(scope_phase, {}),
                }
                rows.append(row)
            pair_summary[scenario] = {
                "cpu_success_rate": summary["cpu_success_rate"],
                "cpu_actions_per_cycle_global": summary["cpu_actions_per_cycle_global"],
                "home_region_cpu_actions_per_cycle": summary["home_region_cpu_actions_per_cycle"],
                "other_regions_cpu_actions_per_cycle": summary["other_regions_cpu_actions_per_cycle"],
                "opened_portals": run["event_metrics"]["opened_portals"],
                "opened_rebellions": run["event_metrics"]["opened_rebellions"],
                "selected_rebellion_rolls": run["event_metrics"]["selected_rebellion_rolls"],
                "eligible_region_cycles": run["event_metrics"]["eligible_region_cycles"],
                "event_metrics": run["event_metrics"],
                "event_scope_phase": event_scope_phase,
                "summary": summary,
            }
        serializable.append(pair_summary)
    import csv

    fieldnames = sorted({key for row in rows for key in row})
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "calibration": {
            "method": "paired deterministic clones with identical campaign UUID seeds, live campaign services, and no player actions",
            "seeds": [pair["baseline"]["seed"] for pair in paired],
            "cycles_per_seed": simulator.HORIZON,
            "phase_cycles": {name: [start, end] for name, start, end in PHASES},
            "formula_scope": "same rank and party-size multipliers apply to CPU and player contract snapshots",
            "baseline_description": baseline_description,
        },
        "totals": {
            scenario: {key: dict(values) for key, values in by_scope_phase.items()}
            for scenario, by_scope_phase in totals.items()
        },
        "paired_results": serializable,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _render_markdown(payload, md_path, csv_path.name, json_path.name, title=title)
    print(f"JSON: {json_path}\nMarkdown: {md_path}\nCSV: {csv_path}")


def _render_markdown(
    payload: dict,
    md_path: Path,
    csv_name: str,
    json_name: str,
    *,
    title: str = "ML-029 E2 — simulação pareada de CPU",
) -> None:
    totals = payload["totals"]
    lines = [
        f"# {title}",
        "",
        f"Simulação dos serviços reais de campanha com {len(payload['paired_results'])} seeds determinísticas pareadas, 100 Vigílias de seis horas por tratamento e nenhuma ação do jogador. Cada seed clona o mesmo save descartável; baseline: {payload['calibration'].get('baseline_description', 'template recommended_power')}; candidato usa os mesmos tipos de contratos de combate. Não há acesso a saves do usuário.",
        "",
        "A fórmula nova reduz a chance de qualquer guilda CPU que aceite esses contratos; isso é intencionalmente medido sob regras iguais, sem exceção de dificuldade. Os contadores elegíveis contam pares guilda/oferta/seed-ciclo em que a escala real de grupo/nível/requisitos permite a execução dentro da Vigília; iniciados são decisões efetivamente registradas como `contract`.",
        "",
        f"- Seeds: `{payload['calibration']['seeds'][0]}–{payload['calibration']['seeds'][-1]}` ({len(payload['calibration']['seeds'])} pares); {payload['calibration']['cycles_per_seed']} ciclos por cenário; fases: início 0–19, meio 20–59 e final 60–99.",
        f"- CSV com linhas por seed/cenário/escopo/fase: [{csv_name}]({csv_name}); detalhe pareado por seed: [{json_name}]({json_name}).",
        "",
        "## CPU regional por fase",
        "",
        "| Escopo | Fase | Elegíveis B→E2 | Iniciados B→E2 | Sucesso/falha B→E2 | Chance média B→E2 | Ouro líquido B→E2 | XP líquido B→E2 | Contratações B→E2 | Nível médio do elenco B→E2 | Pressão (ameaça ≥85 / segurança ≤25) B→E2 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scope in SCOPES:
        for phase, _start, _end in PHASES:
            key = f"{scope}|{phase}"
            base = totals["baseline"].get(key, {})
            e2 = totals["ml029_e2"].get(key, {})
            def ratio(bucket, numerator, denominator):
                return bucket.get(numerator, 0) / max(1, bucket.get(denominator, 0))
            lines.append(
                f"| {scope} | {phase} | {int(base.get('eligible_contract_offer_cpu_pairs', 0))} → {int(e2.get('eligible_contract_offer_cpu_pairs', 0))} | "
                f"{int(base.get('contract_started', 0))} → {int(e2.get('contract_started', 0))} | "
                f"{int(base.get('contract_successes', 0))}/{int(base.get('contract_failures', 0))} → "
                f"{int(e2.get('contract_successes', 0))}/{int(e2.get('contract_failures', 0))} | "
                f"{ratio(base, 'contract_chance_sum', 'contract_chance_samples'):.1f}% → "
                f"{ratio(e2, 'contract_chance_sum', 'contract_chance_samples'):.1f}% | "
                f"{base.get('resource_net_gold', 0):.0f} → {e2.get('resource_net_gold', 0):.0f} | "
                f"{base.get('resource_net_xp', 0):.0f} → {e2.get('resource_net_xp', 0):.0f} | "
                f"{int(base.get('cpu_hires', 0))} → {int(e2.get('cpu_hires', 0))} | "
                f"{ratio(base, 'roster_level_sum', 'roster_members'):.2f} → "
                f"{ratio(e2, 'roster_level_sum', 'roster_members'):.2f} | "
                f"{int(base.get('threat_85_cycles', 0))}/{int(base.get('security_25_cycles', 0))} → "
                f"{int(e2.get('threat_85_cycles', 0))}/{int(e2.get('security_25_cycles', 0))} |"
            )
    lines.extend([
        "",
        "## Portais e rebeliões por fase e escopo",
        "",
        "| Escopo | Fase | Portais abertos B→E2 | Rebeliões abertas B→E2 |",
        "|---|---|---:|---:|",
    ])
    event_totals: dict[str, dict[str, dict[str, int]]] = {
        scenario: defaultdict(lambda: defaultdict(int)) for scenario in ("baseline", "ml029_e2")
    }
    for pair in payload["paired_results"]:
        for scenario in ("baseline", "ml029_e2"):
            for scope_phase, metrics in pair[scenario].get("event_scope_phase", {}).items():
                for key, value in metrics.items():
                    event_totals[scenario][scope_phase][key] += int(value)
    for scope in SCOPES:
        for phase, _start, _end in PHASES:
            key = f"{scope}|{phase}"
            base = event_totals["baseline"].get(key, {})
            e2 = event_totals["ml029_e2"].get(key, {})
            lines.append(
                f"| {scope} | {phase} | {base.get('opened_portals', 0)} → {e2.get('opened_portals', 0)} | "
                f"{base.get('opened_rebellions', 0)} → {e2.get('opened_rebellions', 0)} |"
            )
    lines.extend([
        "",
        "`home_region` é a região natal da guilda CPU; `other_regions` agrega as outras quatro regiões. `global` conta todas as cinco. Recursos líquidos vêm do before/after dos planos CPU e incluem custo de contratação e limites de capacidade; sucesso/fracasso e chance dizem respeito apenas a contratos efetivamente iniciados. A pressão regional conta estados pós-ciclo, não eventos independentes.",
        "",
        "## Eventos e progressão CPU",
        "",
        "| Indicador | Baseline | E2 | Δ E2 − baseline |",
        "|---|---:|---:|---:|",
    ])
    event_metric_keys = (
        ("CPU success rate", lambda run: run["summary"]["cpu_success_rate"]),
        ("Ações CPU/ciclo", lambda run: run["summary"]["cpu_actions_per_cycle_global"]),
        ("Rebeliões abertas", lambda run: run["event_metrics"]["opened_rebellions"]),
        ("Rolagens de rebelião", lambda run: run["event_metrics"]["selected_rebellion_rolls"]),
        ("Região-ciclos elegíveis para rebelião", lambda run: run["event_metrics"]["eligible_region_cycles"]),
        ("Portais abertos", lambda run: run["event_metrics"]["opened_portals"]),
        ("Entradas CPU em portal", lambda run: run["event_metrics"]["portal_cpu_started"]),
        ("Sucessos CPU em portal", lambda run: run["event_metrics"]["portal_cpu_successes"]),
    )
    pairs = payload["paired_results"]
    for label, getter in event_metric_keys:
        before = sum(getter(pair["baseline"]) for pair in pairs)
        after = sum(getter(pair["ml029_e2"]) for pair in pairs)
        if label == "CPU success rate":
            before = 100 * before / max(1, len(pairs))
            after = 100 * after / max(1, len(pairs))
            lines.append(f"| {label} (média) | {before:.1f}% | {after:.1f}% | {after-before:+.1f} p.p. |")
        elif label == "Ações CPU/ciclo":
            before /= max(1, len(pairs))
            after /= max(1, len(pairs))
            lines.append(f"| {label} (média por seed) | {before:.2f} | {after:.2f} | {after-before:+.2f} |")
        else:
            lines.append(f"| {label} (total em {len(pairs)} seeds) | {before:.0f} | {after:.0f} | {after-before:+.0f} |")
    for scope in ("global", "home_region", "other_regions"):
        base = totals["baseline"].get(f"{scope}|final", {})
        e2 = totals["ml029_e2"].get(f"{scope}|final", {})
        b_level = base.get("cpu_guild_level_sum", 0) / max(1, base.get("cpu_guild_state_count", 0))
        e_level = e2.get("cpu_guild_level_sum", 0) / max(1, e2.get("cpu_guild_state_count", 0))
        b_roster = base.get("cpu_roster_size_sum", 0) / max(1, base.get("cpu_guild_state_count", 0))
        e_roster = e2.get("cpu_roster_size_sum", 0) / max(1, e2.get("cpu_guild_state_count", 0))
        lines.append(f"| Nível médio final de guildas CPU ({scope}) | {b_level:.2f} | {e_level:.2f} | {e_level-b_level:+.2f} |")
        lines.append(f"| Roster médio final ({scope}) | {b_roster:.2f} | {e_roster:.2f} | {e_roster-b_roster:+.2f} |")
    lines.extend([
        "",
        "## Leitura de risco",
        "",
        "Os efeitos sobre sucesso, recursos, ameaça/segurança, portais e rebeliões são resultados pareados das mesmas seeds, mas as execuções divergem deterministicamente depois da primeira resolução cujo sucesso mudou. Portanto, os deltas mostram o efeito total de equilíbrio ao longo de 100 ciclos, não uma comparação controlada de uma única oferta. As regiões permanecem com a mesma fórmula de Rank e grupo para CPU e jogador; não há regra especial para preservar sucesso CPU.",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0,
                        help="run only the first N paired seeds as a smoke check")
    parser.add_argument("--label", default="2026-11-09-adjusted",
                        help="suffix for evidence artifacts")
    args = parser.parse_args()
    output_dir = ROOT / "reports"
    seeds = simulator.SEEDS[:args.limit] if args.limit else simulator.SEEDS
    if args.limit < 0:
        parser.error("--limit cannot be negative")
    _run_sample(output_dir, seeds, args.label)


if __name__ == "__main__":
    main()
