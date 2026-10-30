"""Deterministic multi-seed audit of regional portal and rebellion triggers.

Uses the production seed derivation, RNG, thresholds, chance curve and event
window/global-limit policy. Service-level SQLite tests separately verify that
the implementation persists these decisions idempotently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.regional_cycle_service import REGIONS, _rng, _seed_text
from app.services.regional_event_service import (
    EVENT_RULES_VERSION,
    PORTAL_BASE_CHANCE,
    PORTAL_MAX_CHANCE,
    PORTAL_MIN_THREAT,
    PORTAL_TTL,
    REBELLION_CHANCE,
    REBELLION_MAX_SECURITY,
    REBELLION_MIN_THREAT,
    REBELLION_PRIORITY,
    REBELLION_TTL,
)
from scripts.balance.funded_progression_simulation import wilson_interval_95


REPORT_JSON = ROOT / "reports" / "regional_event_incidence_2026-10-29.json"
REPORT_MD = ROOT / "reports" / "regional_event_incidence_2026-10-29.md"
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
CYCLE_HOURS = 6
CYCLE_INTERVAL = timedelta(hours=CYCLE_HOURS)
HORIZONS = (100, 250, 500)
PORTAL_THREAT_PROFILES = {"threat_70": 70.0, "threat_85": 85.0, "threat_100": 100.0}


def portal_chance(threat: float) -> float:
    return min(PORTAL_MAX_CHANCE,
               PORTAL_BASE_CHANCE + (float(threat) - PORTAL_MIN_THREAT) * (0.20 / 30.0))


def portal_roll(campaign_id: str, cycle_number: int, region_code: str, threat: float) -> bool:
    if threat < PORTAL_MIN_THREAT:
        return False
    seed = _seed_text(campaign_id, cycle_number, region_code, EVENT_RULES_VERSION, "portal")
    return _rng(seed).random() < portal_chance(threat)


def rebellion_roll(campaign_id: str, cycle_number: int, region_code: str,
                   threat: float, security: float) -> bool:
    if threat < REBELLION_MIN_THREAT or security > REBELLION_MAX_SECURITY:
        return False
    seed = _seed_text(campaign_id, cycle_number, region_code, EVENT_RULES_VERSION, "rebellion")
    return _rng(seed).random() < REBELLION_CHANCE


def _empirical_distribution(values: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"n": 0, "mean": None, "median": None, "p2_5": None, "p97_5": None, "min": None, "max": None}
    return {
        "n": len(ordered),
        "mean": round(mean(ordered), 4),
        "median": median(ordered),
        "p2_5": ordered[int(0.025 * (len(ordered) - 1))],
        "p97_5": ordered[int(0.975 * (len(ordered) - 1))],
        "min": ordered[0],
        "max": ordered[-1],
    }


def _campaign_id(kind: str, profile: str, seed: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"gim-regional-event-incidence-v1:{kind}:{profile}:{seed}"))


def _portal_seed_run(*, profile: str, threat: float, seed: int, cycles: int) -> list[int]:
    campaign_id = _campaign_id("portal", profile, seed)
    return [
        sum(portal_roll(campaign_id, cycle_number, code, threat) for code, _name in REGIONS)
        for cycle_number in range(1, cycles + 1)
    ]


def _rebellion_seed_run(*, seed: int, cycles: int) -> dict[str, object]:
    campaign_id = _campaign_id("rebellion", "all_regions_eligible", seed)
    event_counts: list[int] = []
    roll_cycles: list[int] = []
    candidate_counts: list[int] = []
    blocked_cycles: list[int] = []
    suppressed_candidates = 0
    active_until: datetime | None = None
    max_active = 0
    for cycle_number in range(1, cycles + 1):
        now = BASE_TIME + CYCLE_INTERVAL * cycle_number
        if active_until is not None and now < active_until:
            event_counts.append(0)
            candidate_counts.append(0)
            blocked_cycles.append(1)
            continue
        blocked_cycles.append(0)
        roll_cycles.append(cycle_number)
        candidates = [
            code for code, _name in sorted(REGIONS)
            if rebellion_roll(campaign_id, cycle_number, code,
                              REBELLION_MIN_THREAT, REBELLION_MAX_SECURITY)
        ]
        candidate_counts.append(len(candidates))
        event_counts.append(1 if candidates else 0)
        if candidates:
            suppressed_candidates += len(candidates) - 1
            # The service picks the first region in stable region_code order.
            # No-response delegation starts after one hour, then grants 12h;
            # the 13h expiry is used by expire_due_events on the next cycle.
            active_until = now + REBELLION_PRIORITY + REBELLION_TTL
            max_active = max(max_active, 1)
    return {
        "event_counts_by_cycle": event_counts,
        "roll_cycles": roll_cycles,
        "candidate_counts_by_cycle": candidate_counts,
        "blocked_cycles_by_cycle": blocked_cycles,
        "suppressed_candidates": suppressed_candidates,
        "max_simultaneous_active_events": max_active,
    }


def run_regional_event_incidence(*, seeds: int = 100, seed_start: int = 2026102900,
                                 cycles: int = 500) -> dict[str, object]:
    if seeds <= 0 or cycles <= 0:
        raise ValueError("seeds and cycles must be positive")
    if PORTAL_TTL >= CYCLE_INTERVAL:
        raise ValueError("The portal incidence model requires the 3h portal window to fit within the 6h cycle")
    portal_runs = {name: [] for name in PORTAL_THREAT_PROFILES}
    rebellion_runs = []
    for run_index in range(seeds):
        seed = seed_start + run_index
        for profile, threat in PORTAL_THREAT_PROFILES.items():
            portal_runs[profile].append(_portal_seed_run(
                profile=profile, threat=threat, seed=seed, cycles=cycles,
            ))
        rebellion_runs.append(_rebellion_seed_run(seed=seed, cycles=cycles))

    portal_summary = {}
    for profile, run_rows in portal_runs.items():
        target_threat = PORTAL_THREAT_PROFILES[profile]
        chance = portal_chance(target_threat)
        portal_summary[profile] = {
            "threat": target_threat,
            "expected_chance_per_region_cycle_percent": round(chance * 100, 2),
            "horizons": {},
        }
        for horizon in HORIZONS:
            effective_horizon = min(horizon, cycles)
            clipped = [row[:effective_horizon] for row in run_rows]
            events = sum(sum(row) for row in clipped)
            trials = len(clipped) * effective_horizon * len(REGIONS)
            per_seed_counts = [sum(row) for row in clipped]
            hits = sum(count > 0 for count in per_seed_counts)
            portal_summary[profile]["horizons"][str(horizon)] = {
                "region_cycle_events": events,
                "eligible_region_cycles": trials,
                "event_rate_wilson_95": wilson_interval_95(events, trials),
                "campaigns_with_any_portal_wilson_95": wilson_interval_95(hits, len(clipped)),
                "events_per_campaign_distribution": _empirical_distribution(per_seed_counts),
            }

    rebellion_summary = {
        "eligible_regions": len(REGIONS),
        "threat": REBELLION_MIN_THREAT,
        "security": REBELLION_MAX_SECURITY,
        "expected_chance_per_eligible_region_cycle_percent": REBELLION_CHANCE * 100,
        "horizons": {},
    }
    for horizon in HORIZONS:
        effective_horizon = min(horizon, cycles)
        per_seed_events = [sum(row["event_counts_by_cycle"][:effective_horizon]) for row in rebellion_runs]
        events = sum(per_seed_events)
        world_cycles = len(rebellion_runs) * effective_horizon
        any_event = sum(count > 0 for count in per_seed_events)
        roll_counts = [sum(cycle <= effective_horizon for cycle in row["roll_cycles"]) for row in rebellion_runs]
        blocked_counts = [effective_horizon - count for count in roll_counts]
        # Each cycle in roll_cycles produces one trial for every eligible region.
        candidate_trials = sum(count * len(REGIONS) for count in roll_counts)
        candidates = sum(
            sum(row["candidate_counts_by_cycle"][:effective_horizon]) for row in rebellion_runs
        )
        suppressed = sum(
            sum(max(0, count - 1) for count in row["candidate_counts_by_cycle"][:effective_horizon])
            for row in rebellion_runs
        )
        rebellion_summary["horizons"][str(horizon)] = {
            "global_rebellion_events": events,
            "campaign_cycles": world_cycles,
            "event_per_campaign_cycle_wilson_95": wilson_interval_95(events, world_cycles),
            "campaigns_with_any_rebellion_wilson_95": wilson_interval_95(any_event, len(rebellion_runs)),
            "events_per_campaign_distribution": _empirical_distribution(per_seed_events),
            "roll_cycles_per_campaign_distribution": _empirical_distribution(roll_counts),
            "global_limit_blocked_cycles_per_campaign_distribution": _empirical_distribution(blocked_counts),
            "eligible_region_cycle_rolls": candidate_trials,
            "candidate_rolls": candidates,
            "candidate_rate_wilson_95": wilson_interval_95(candidates, candidate_trials),
            "suppressed_simultaneous_candidates": suppressed,
            "max_simultaneous_active_events": max(row["max_simultaneous_active_events"] for row in rebellion_runs),
        }

    return {
        "report_id": "gim-regional-event-incidence-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seeds": seeds,
        "seed_start": seed_start,
        "seed_end": seed_start + seeds - 1,
        "cycles_per_campaign": cycles,
        "cycle_hours": CYCLE_HOURS,
        "source": {
            "event_service_sha256": hashlib.sha256(
                (ROOT / "app" / "services" / "regional_event_service.py").read_bytes()
            ).hexdigest(),
            "cycle_rng_sha256": hashlib.sha256(
                (ROOT / "app" / "services" / "regional_cycle_service.py").read_bytes()
            ).hexdigest(),
            "simulator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "method": {
            "campaign_identity": "UUID5 from event type, profile and seed; the production _seed_text/_rng helpers derive the event rolls",
            "regions": "five GDD regions, all held at the stated trigger state for every cycle",
            "portals": "production chance formula and RNG seed; one roll per region/cycle; the 3h window is less than the 6h cycle, so prior portals expire before the next same-region roll",
            "rebellions": "production chance formula and RNG seed; stable region ordering; one campaign-global event; no-response expiry after 1h priority + 12h CPU window; active event suppresses subsequent roll cycles until expiry",
            "intervals": "Wilson score 95% intervals for binary event rates; empirical 2.5th–97.5th percentile range and median across deterministic campaign seeds for per-campaign counts",
            "service_verification": "Regional event service tests separately invoke SQLite services to check thresholds, expiry, deterministic replay, duplicate suppression and one-global-active behavior; this incidence runner reproduces their trigger-seed policy without materializing every database row",
            "scope_limit": "This isolates trigger incidence under permanently eligible regional conditions. It does not simulate changing regional pressure, CPU plans, player choices, event completion/rewards or full campaign distributions. Wilson intervals summarize the selected deterministic seed bank and do not guarantee future random outcomes.",
        },
        "portal_profiles": portal_summary,
        "rebellion": rebellion_summary,
        "design_comparison": {
            "portal_gdd": "5% at threat 70, growing linearly to 25% at threat 100; one active portal per region; 3h entry window",
            "rebellion_gdd": "2% per eligible region-cycle at threat >=85 and security <=25; one active rebellion globally",
            "expected_any_region_candidate_per_roll_cycle_with_five_eligible_regions_percent": round(
                (1 - (1 - REBELLION_CHANCE) ** len(REGIONS)) * 100, 2
            ),
            "rebellion_cycle_suppression": "The 13h rebellion lifecycle crosses two later 6h cycle checks. Those cycles do not roll while the single global event is active, reducing effective events per campaign-cycle below the five-region candidate probability.",
        },
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Incidência de portais e rebeliões",
        "",
        f"Execução `{report['report_id']}` · seeds {report['seed_start']}–{report['seed_end']} · {report['cycles_per_campaign']} ciclos de 6h por campanha.",
        "",
        "Modelo de trigger determinístico com as funções de seed/RNG e parâmetros atuais do serviço. Wilson 95% mede taxas sobre o banco de seeds fixo; o intervalo empírico de contagens descreve a dispersão entre campanhas observadas, não uma previsão completa do jogo.",
        "",
        "## Portais",
        "",
        "Cada perfil fixa as cinco regiões no mesmo nível de ameaça por 100, 250 ou 500 Vigílias. A janela ativa dura 3h, menor que o ciclo de 6h.",
        "",
        "| Ameaça | Chance GDD por região/Vigília | Horizonte | Eventos / região-ciclos (Wilson 95%) | Campanhas com ≥1 portal (Wilson 95%) | Eventos por campanha (mediana; p2,5–p97,5) |",
        "|---:|---:|---:|---|---|---|",
    ]
    for profile in PORTAL_THREAT_PROFILES:
        row = report["portal_profiles"][profile]
        for horizon, stats in row["horizons"].items():
            rate = stats["event_rate_wilson_95"]
            any_rate = stats["campaigns_with_any_portal_wilson_95"]
            dist = stats["events_per_campaign_distribution"]
            lines.append(
                f"| {row['threat']:g} | {row['expected_chance_per_region_cycle_percent']:.1f}% | {horizon} | "
                f"{stats['region_cycle_events']:,}/{stats['eligible_region_cycles']:,}; {rate['rate_percent']:.2f}% "
                f"({rate['lower_percent']:.2f}–{rate['upper_percent']:.2f}%) | "
                f"{any_rate['events']}/{any_rate['n']}; {any_rate['rate_percent']:.1f}% "
                f"({any_rate['lower_percent']:.1f}–{any_rate['upper_percent']:.1f}%) | "
                f"{dist['median']:g}; {dist['p2_5']:g}–{dist['p97_5']:g} |"
            )
    rebellion = report["rebellion"]
    lines.extend([
        "",
        "## Rebeliões",
        "",
        f"GDD: {rebellion['expected_chance_per_eligible_region_cycle_percent']:.1f}% por região/Vigília elegível; ameaça ≥85, segurança ≤25 e limite global de uma rebelião ativa. Sem limite global, cinco regiões dariam {report['design_comparison']['expected_any_region_candidate_per_roll_cycle_with_five_eligible_regions_percent']:.2f}% de chance de ao menos uma candidata em cada ciclo com rolagem. O prazo real de 13h suprime ciclos seguintes até expirar.",
        "",
        "| Horizonte | Rebeliões/ciclos de campanha (Wilson 95%) | Campanhas com ≥1 rebelião (Wilson 95%) | Eventos por campanha (mediana; p2,5–p97,5) | Ciclos rolados p50 | Ciclos bloqueados p50 | Candidatas/rolagens região-ciclo (Wilson 95%) | Candidatas simultâneas suprimidas | Máximo de eventos ativos |",
        "|---:|---|---|---|---:|---:|---|---:|---:|",
    ])
    for horizon, stats in rebellion["horizons"].items():
        rate = stats["event_per_campaign_cycle_wilson_95"]
        any_rate = stats["campaigns_with_any_rebellion_wilson_95"]
        candidate_rate = stats["candidate_rate_wilson_95"]
        event_dist = stats["events_per_campaign_distribution"]
        roll_dist = stats["roll_cycles_per_campaign_distribution"]
        blocked_dist = stats["global_limit_blocked_cycles_per_campaign_distribution"]
        lines.append(
            f"| {horizon} | {stats['global_rebellion_events']:,}/{stats['campaign_cycles']:,}; "
            f"{rate['rate_percent']:.2f}% ({rate['lower_percent']:.2f}–{rate['upper_percent']:.2f}%) | "
            f"{any_rate['events']}/{any_rate['n']}; {any_rate['rate_percent']:.1f}% "
            f"({any_rate['lower_percent']:.1f}–{any_rate['upper_percent']:.1f}%) | "
            f"{event_dist['median']:g}; {event_dist['p2_5']:g}–{event_dist['p97_5']:g} | "
            f"{roll_dist['median']:g} | {blocked_dist['median']:g} | "
            f"{candidate_rate['events']:,}/{candidate_rate['n']:,}; {candidate_rate['rate_percent']:.2f}% "
            f"({candidate_rate['lower_percent']:.2f}–{candidate_rate['upper_percent']:.2f}%) | "
            f"{stats['suppressed_simultaneous_candidates']:,} | {stats['max_simultaneous_active_events']} |"
        )
    lines.extend([
        "",
        "## Interpretação e limites",
        "",
        "Os portais devem acompanhar a chance GDD em cada região/Vigília elegível e não repetir antes de expirar a janela de 3h. Para rebeliões, a taxa candidata por região nas oportunidades efetivamente roladas deve acompanhar 2%; a taxa por Vigília de campanha é menor porque uma rebelião ativa globalmente bloqueia novas rolagens. Candidatas extras no mesmo ciclo são suprimidas pela ordem estável de região; o serviço tem teste de replay idêntico e de uma única rebelião ativa.",
        "",
        "Todas as regiões ficam artificialmente elegíveis durante todo o horizonte. A amostra não simula mudanças regionais por atividade CPU/jogador, escolhas de rebelião, conclusão de eventos, recompensas nem progressão completa. Os intervalos Wilson se aplicam aos seeds determinísticos selecionados, não são garantia de resultados futuros.",
        "",
        "Stage 5 permanece aberto: a rota financiada de nível 1–50 chega ao nível 50 nos cinco perfis, mas não demonstra financiamento de todos os upgrades, economia de endgame sem sink, hard softlock geral ou os marcos de equipamento/masmorra/evento. Nenhum sink foi inventado ou aplicado.",
        "",
        "Seeds, configuração, ledger agregado e hashes estão no JSON adjacente.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit deterministic portal and rebellion trigger incidence.")
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=2026102900)
    parser.add_argument("--cycles", type=int, default=500)
    args = parser.parse_args()
    report = run_regional_event_incidence(seeds=args.seeds, seed_start=args.seed_start, cycles=args.cycles)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {REPORT_JSON}")
    print(f"Markdown: {REPORT_MD}")
    print(json.dumps({
        "portal_rates": {profile: {horizon: row["event_rate_wilson_95"] for horizon, row in stats["horizons"].items()}
                         for profile, stats in report["portal_profiles"].items()},
        "rebellion": {horizon: {"event_per_campaign_cycle": row["event_per_campaign_cycle_wilson_95"],
                                "candidate_rate": row["candidate_rate_wilson_95"],
                                "suppressed": row["suppressed_simultaneous_candidates"],
                                "max_active": row["max_simultaneous_active_events"]}
                      for horizon, row in report["rebellion"]["horizons"].items()},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
