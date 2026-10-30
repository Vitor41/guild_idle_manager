"""Measure bounded strong-rival calm candidates against a fresh 100-cycle CPU trace."""

from __future__ import annotations

import gc
import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import UUID
from unittest.mock import patch

from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database
from app.models.campaign import CampaignMetadata
from app.models.regional import RegionalCpuCyclePlan, RegionalCycle, RegionalCycleRegion, RegionalGuildState
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.services import regional_cycle_service
from app.services.regional_cycle_service import cpu_initial_profile_values


HORIZONS = (10, 50, 100)
CALM_CANDIDATES = ((2, 0.10), (2, 0.25), (4, 0.10), (4, 0.25), (4, 0.50), (6, 0.10), (6, 0.25), (6, 0.50))
PORTAL_THREAT = 70.0
REBELLION_THREAT = 85.0
REBELLION_SECURITY = 25.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _replay(rows_by_region: dict[str, list[dict[str, object]]], duration: int, impact: float):
    output: dict[str, dict[str, object]] = {}
    for region_code, rows in rows_by_region.items():
        security, threat = 50.0, 25.0
        trajectory = []
        first_portal = first_rebellion = None
        for cycle_index, row in enumerate(rows):
            actual_calm = row["calm"]
            raw_security_delta = float(row["security_after"]) - float(row["security_before"]) - float(actual_calm["security"])
            raw_threat_delta = float(row["threat_after"]) - float(row["threat_before"]) - float(actual_calm["threat"])
            calm_active = cycle_index < duration
            calm_security = impact if calm_active else 0.0
            calm_threat = -impact if calm_active else 0.0
            security = _clamp(security + raw_security_delta + calm_security)
            threat = _clamp(threat + raw_threat_delta + calm_threat)
            trajectory.append({"security": security, "threat": threat})
            if first_portal is None and threat >= PORTAL_THREAT:
                first_portal = cycle_index + 1
            if first_rebellion is None and threat >= REBELLION_THREAT and security <= REBELLION_SECURITY:
                first_rebellion = cycle_index + 1
        output[region_code] = {
            "trajectory": trajectory,
            "first_portal_eligible_vigilia": first_portal,
            "first_rebellion_eligible_vigilia": first_rebellion,
        }
    return output


def _summarize(replay: dict[str, dict[str, object]], rows_by_region, horizons=HORIZONS):
    result = {}
    region_count = max(1, len(replay))
    for horizon in horizons:
        states = [data["trajectory"][horizon - 1] for data in replay.values()]
        count_region_cycles = region_count * horizon
        active_calms = sum(
            1 for rows in rows_by_region.values() for row in rows[:horizon]
            if row["calm"]["active"]
        )
        applied_calms = sum(
            1 for rows in rows_by_region.values() for row in rows[:horizon]
            if row["calm"]["applied"]
        )
        active_action_cycles = sum(
            1 for rows in rows_by_region.values() for row in rows[:horizon]
            if row["cpu_actions"] + row["player_actions"] > 0
        )
        result[horizon] = {
            "mean_security": round(sum(row["security"] for row in states) / region_count, 4),
            "mean_threat": round(sum(row["threat"] for row in states) / region_count, 4),
            "active_calm_region_cycles": active_calms,
            "applied_calm_region_cycles": applied_calms,
            "active_calm_rate": round(active_calms / count_region_cycles, 4),
            "active_calm_application_rate": round(applied_calms / max(1, active_calms), 4),
            "cycles_with_actions": active_action_cycles,
            "cycles_with_actions_rate": round(active_action_cycles / count_region_cycles, 4),
            "portal_eligible_regions": sum(
                1 for data in replay.values()
                if data["first_portal_eligible_vigilia"] is not None
                and data["first_portal_eligible_vigilia"] <= horizon
            ),
            "rebellion_eligible_regions": sum(
                1 for data in replay.values()
                if data["first_rebellion_eligible_vigilia"] is not None
                and data["first_rebellion_eligible_vigilia"] <= horizon
            ),
        }
    result["first_event_eligibility"] = {
        "portal_by_region": {
            region: data["first_portal_eligible_vigilia"] for region, data in replay.items()
        },
        "rebellion_by_region": {
            region: data["first_rebellion_eligible_vigilia"] for region, data in replay.items()
        },
    }
    return result


def _no_action_stress(duration: int, impact: float, max_cycles: int = 100):
    security, threat = 50.0, 25.0
    first_portal = first_rebellion = None
    for resolved in range(1, max_cycles + 1):
        calm = impact if resolved <= duration else 0.0
        # The existing no-action baseline is applied once; calm is a separate
        # additive regional delta and never changes whether actions resolve.
        security = _clamp(security - 1.0 + calm)
        threat = _clamp(threat + 1.0 - calm)
        if first_portal is None and threat >= PORTAL_THREAT:
            first_portal = resolved
        if first_rebellion is None and threat >= REBELLION_THREAT and security <= REBELLION_SECURITY:
            first_rebellion = resolved
    return {
        "first_portal_eligible_vigilia": first_portal,
        "first_rebellion_eligible_vigilia": first_rebellion,
        "security_after_100": security,
        "threat_after_100": threat,
    }


def run_sensitivity() -> dict[str, object]:
    campaign_id = "00000000-0000-4000-8000-00000000cafe"
    with tempfile.TemporaryDirectory(prefix="gim-rival-calm-") as temp_dir:
        try:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            with patch("app.services.campaign_service.uuid4", return_value=UUID(campaign_id)):
                info = campaigns.create_campaign("Auditoria de calmaria", "Guilda descartável")
            campaigns.activate_campaign(info.campaign_id, mark_active=False)
            with SessionLocal() as db:
                campaign = db.get(CampaignMetadata, info.campaign_id)
                guild, _resources = get_current_guild_context(db, info.campaign_id)
                start = campaign.created_at_utc
                regional_cycle_service.advance_regional_world(
                    db, campaign, guild,
                    start + timedelta(seconds=100 * regional_cycle_service.CYCLE_SECONDS),
                )
                cycles = list(db.scalars(select(RegionalCycle).where(
                    RegionalCycle.campaign_id == info.campaign_id,
                    RegionalCycle.status == "completed",
                ).order_by(RegionalCycle.cycle_number)))
                states = list(db.scalars(select(RegionalGuildState).where(
                    RegionalGuildState.campaign_id == info.campaign_id,
                    RegionalGuildState.guild_id.is_(None),
                )))
                region_stage = {
                    code: regional_cycle_service.regional_stage_for_region(code)
                    for code, _name in regional_cycle_service.REGIONS
                }
                rows_by_region = {code: [] for code, _name in regional_cycle_service.REGIONS}
                for cycle in cycles:
                    snapshots = list(db.scalars(select(RegionalCycleRegion).where(
                        RegionalCycleRegion.cycle_id == cycle.id,
                    ).order_by(RegionalCycleRegion.region_code)))
                    for snapshot in snapshots:
                        summary = json.loads(snapshot.summary_json or "{}")
                        calm = summary.get("rival_calm", {
                            "active": False, "applied": False, "security": 0.0, "threat": 0.0,
                        })
                        rows_by_region[snapshot.region_code].append({
                            "cycle_number": cycle.cycle_number,
                            "security_before": snapshot.security_before,
                            "threat_before": snapshot.threat_before,
                            "security_after": snapshot.security_after,
                            "threat_after": snapshot.threat_after,
                            "calm": calm,
                            "cpu_actions": snapshot.cpu_actions,
                            "player_actions": int(summary.get("player_actions", 0)),
                            "baseline_applied": bool(summary.get("baseline", {}).get("applied", False)),
                        })

                no_calm = _replay(rows_by_region, 0, 0.0)
                candidates = {}
                for duration, impact in CALM_CANDIDATES:
                    key = f"{duration}v-x-{impact:.2f}"
                    replay = _replay(rows_by_region, duration, impact)
                    candidates[key] = {
                        "duration_cycles": duration,
                        "impact_per_cycle": impact,
                        "max_cumulative_delta_per_region": round(duration * impact, 4),
                        "horizons": _summarize(replay, rows_by_region),
                        "no_action_stress": _no_action_stress(duration, impact),
                    }
                selected = _replay(
                    rows_by_region,
                    regional_cycle_service.RIVAL_CALM_WINDOW_CYCLES,
                    regional_cycle_service.RIVAL_CALM_IMPACT_PER_CYCLE,
                )
                selected_horizons = _summarize(selected, rows_by_region)
                no_calm_horizons = _summarize(no_calm, rows_by_region)
                active_calm_cycles = sum(
                    row["calm"]["active"]
                    for rows in rows_by_region.values() for row in rows
                )
                applied_calm_cycles = sum(
                    row["calm"]["applied"]
                    for rows in rows_by_region.values() for row in rows
                )
                baseline_calm_cycles = sum(
                    row["calm"]["applied"] and row["baseline_applied"]
                    for rows in rows_by_region.values() for row in rows
                )
                baseline_cycles = sum(
                    row["baseline_applied"] for rows in rows_by_region.values() for row in rows
                )
                action_cycles = sum(
                    row["cpu_actions"] + row["player_actions"] > 0
                    for rows in rows_by_region.values() for row in rows
                )
                window_rows = [
                    row for rows in rows_by_region.values()
                    for row in rows[:regional_cycle_service.RIVAL_CALM_WINDOW_CYCLES]
                ]
                window_action_cycles = sum(
                    row["cpu_actions"] + row["player_actions"] > 0 for row in window_rows
                )
                window_cpu_actions = sum(row["cpu_actions"] for row in window_rows)
                strong_actions = strong_success_impact = strong_failure_impact = 0
                for plan in db.scalars(select(RegionalCpuCyclePlan).join(
                    RegionalGuildState, RegionalGuildState.id == RegionalCpuCyclePlan.guild_state_id,
                ).join(
                    RegionalCycle, RegionalCycle.id == RegionalCpuCyclePlan.cycle_id,
                ).where(
                    RegionalCpuCyclePlan.campaign_id == info.campaign_id,
                    RegionalCycle.cycle_number < regional_cycle_service.RIVAL_CALM_WINDOW_CYCLES,
                    RegionalGuildState.profile == "strong",
                )):
                    outcomes = json.loads(plan.outcomes_json or "[]")
                    strong_actions += len(outcomes)
                    for outcome in outcomes:
                        delta = regional_cycle_service.regional_outcome_impact(outcome["rank"])
                        if outcome["success"]:
                            strong_success_impact += delta
                        else:
                            strong_failure_impact += delta
                stage_profiles = {
                    stage: {
                        profile: cpu_initial_profile_values(profile, stage)
                        for profile in ("strong", "medium", "new")
                    }
                    for stage in (1, 5)
                }
                return {
                    "simulation": {
                        "campaign_id": campaign_id,
                        "cycles_per_region": min((len(rows) for rows in rows_by_region.values()), default=0),
                        "regions": len(rows_by_region),
                        "region_stages": region_stage,
                        "completed_cycles": len(cycles),
                        "cpu_guilds": len(states),
                        "seed_rule": "fixed campaign UUID + per-cycle deterministic seeds",
                    },
                    "selected_rule": {
                        "version": regional_cycle_service.VIGILIA_RULES_VERSION,
                        "duration_cycles": regional_cycle_service.RIVAL_CALM_WINDOW_CYCLES,
                        "impact_per_cycle": regional_cycle_service.RIVAL_CALM_IMPACT_PER_CYCLE,
                        "max_cumulative_delta_per_region": round(
                            regional_cycle_service.RIVAL_CALM_WINDOW_CYCLES
                            * regional_cycle_service.RIVAL_CALM_IMPACT_PER_CYCLE, 4,
                        ),
                        "active_region_cycles": int(active_calm_cycles),
                        "applied_region_cycles": int(applied_calm_cycles),
                        "active_rate_100_vigílias": round(active_calm_cycles / max(1, 100 * len(rows_by_region)), 4),
                        "application_rate_when_active": round(applied_calm_cycles / max(1, active_calm_cycles), 4),
                        "applied_with_baseline": int(baseline_calm_cycles),
                        "baseline_cycles": int(baseline_cycles),
                        "cpu_or_player_action_cycles": int(action_cycles),
                        "active_window_region_cycles": len(window_rows),
                        "active_window_action_cycles": int(window_action_cycles),
                        "active_window_action_rate": round(window_action_cycles / max(1, len(window_rows)), 4),
                        "active_window_cpu_actions": int(window_cpu_actions),
                        "strong_rival_actions_in_window": int(strong_actions),
                        "strong_rival_success_regional_impact": round(strong_success_impact, 4),
                        "strong_rival_failure_regional_impact": round(strong_failure_impact, 4),
                    },
                    "initial_profile_bands": stage_profiles,
                    "selected_horizons": selected_horizons,
                    "no_calm_horizons": no_calm_horizons,
                    "candidates": candidates,
                    "no_action_stress_control": _no_action_stress(0, 0.0),
                }
        finally:
            configure_database("sqlite:///:memory:")
            gc.collect()


def render_markdown(data: dict[str, object]) -> str:
    selected = data["selected_rule"]
    lines = [
        "# Sensibilidade da força regional e calmaria do rival forte",
        "",
        "Execução em save descartável SQLite. O trace base veio dos serviços regionais reais por 100 Vigílias em cinco regiões; as alternativas são replay determinístico dos mesmos deltas CPU/baseline, retirando a calmaria selecionada e aplicando cada duração/impacto. Nenhuma ação, recompensa ou snapshot histórico foi alterado.",
        "",
        "## Parâmetros escolhidos",
        "",
        f"- Versão: `{selected['version']}`.",
        f"- Calmaria: {selected['duration_cycles']} Vigílias ({selected['duration_cycles'] * 6}h), +{selected['impact_per_cycle']:.2f} segurança/−{selected['impact_per_cycle']:.2f} ameaça por Vigília, limitada a um deslocamento máximo de {selected['max_cumulative_delta_per_region']:.2f} ponto por região.",
        "- Diluído no horizonte, o deslocamento médio por região-ciclo é +0.10/−0.10 em 10 Vigílias, +0.02/−0.02 em 50 e +0.01/−0.01 em 100.",
        f"- Incidência no trace: aplicada em {selected['applied_region_cycles']} de 500 região-ciclos ({selected['active_rate_100_vigílias']:.1%}); {selected['application_rate_when_active']:.1%} dos ciclos em que a janela estava ativa. {selected['applied_with_baseline']} dessas aplicações coincidiram com baseline sem ação; {selected['cpu_or_player_action_cycles']} região-ciclos tiveram ações CPU/jogador.",
        f"- Nas 20 região-ciclos da janela: {selected['active_window_action_cycles']} tiveram ações CPU/jogador ({selected['active_window_action_rate']:.1%}); a CPU forte concluiu {selected['strong_rival_actions_in_window']} ações, com impacto regional agregado de +{selected['strong_rival_success_regional_impact']:.2f} segurança por sucessos e −{selected['strong_rival_failure_regional_impact']:.2f} por falhas. A calmaria máxima de 1.00 ponto fica separada e visível no ledger.",
        "- O bônus é aditivo depois dos resultados normais. Ele não cancela ações nem altera chance, recompensa ou resolução do jogador/CPU. O baseline continua aplicado uma única vez quando não há ações.",
        "",
        "## Bandas iniciais",
        "",
        "| Perfil | Nível da guilda estágio 1 → 5 | Nível dos mercenários 1 → 5 | Soma dos atributos-base 1 → 5 | Ouro 1 → 5 | Material 1 → 5 | Capacidade 1 → 5 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for profile in ("strong", "medium", "new"):
        low = data["initial_profile_bands"][1][profile]
        high = data["initial_profile_bands"][5][profile]
        lines.append(
            f"| {profile} | {low['guild_level']} → {high['guild_level']} | "
            f"{low['mercenary_level']} → {high['mercenary_level']} | "
            f"{sum(low['attributes'])} → {sum(high['attributes'])} | {low['gold']} → {high['gold']} | "
            f"{low['material']} → {high['material']} | {low['capacity']} → {high['capacity']} |"
        )
    lines += [
        "",
        "## Trajetória real com a regra escolhida e contrafactual sem calmaria",
        "",
        "| Horizonte | Segurança média com / sem | Ameaça média com / sem | Eventos elegíveis (portal / rebelião) com / sem |",
        "|---:|---:|---:|---:|",
    ]
    for horizon in HORIZONS:
        chosen = data["selected_horizons"][horizon]
        control = data["no_calm_horizons"][horizon]
        lines.append(
            f"| {horizon} Vigílias | {chosen['mean_security']:.2f} / {control['mean_security']:.2f} | "
            f"{chosen['mean_threat']:.2f} / {control['mean_threat']:.2f} | "
            f"{chosen['portal_eligible_regions']} / {control['portal_eligible_regions']} · "
            f"{chosen['rebellion_eligible_regions']} / {control['rebellion_eligible_regions']} |"
        )
    lines += [
        "",
        "## Comparação de candidatos",
        "",
        "| Janela | Impacto por Vigília | Máximo acumulado | Ameaça a 10 / 50 / 100 | Segurança a 10 / 50 / 100 | Portal elegível (stress sem ações) | Rebelião elegível (stress sem ações) |",
        "|---:|---:|---:|---|---|---:|---:|",
    ]
    for key, candidate in data["candidates"].items():
        horizons = candidate["horizons"]
        threat = " / ".join(f"{horizons[h]['mean_threat']:.2f}" for h in HORIZONS)
        security = " / ".join(f"{horizons[h]['mean_security']:.2f}" for h in HORIZONS)
        stress = candidate["no_action_stress"]
        lines.append(
            f"| {candidate['duration_cycles']} Vigílias | {candidate['impact_per_cycle']:.2f} | "
            f"{candidate['max_cumulative_delta_per_region']:.2f} | {threat} | {security} | "
            f"{stress['first_portal_eligible_vigilia']} | {stress['first_rebellion_eligible_vigilia']} |"
        )
    stress = data["no_action_stress_control"]
    lines += [
        "",
        "## Controle extremo sem ações",
        "",
        f"Sem calmaria, o baseline de +1 ameaça/−1 segurança torna portal elegível na {stress['first_portal_eligible_vigilia']}ª Vigília e rebelião na {stress['first_rebellion_eligible_vigilia']}ª. Todos os candidatos mantêm ambos os gatilhos finitos; nenhum bloqueia eventos indefinidamente. A calmaria só altera estado durante a janela declarada e nunca suprime a geração de evento.",
        "",
        "## Limites",
        "",
        "As linhas com CPU são replay contrafactual de um trace de uma campanha fixa, não amostra estatística. A calmaria é suficientemente pequena e curta para deixar a trajetória praticamente igual após a décima Vigília; o controle sem ações verifica o caso de pressão contínua mais severo. O roster é determinístico para UUID/versionamento, mas a simulação única não é inferência de balanceamento entre campanhas.",
        "",
        f"Execução: {data['simulation']['cycles_per_region']} ciclos resolvidos em cada uma das {data['simulation']['regions']} regiões; {data['simulation']['cpu_guilds']} rivais CPU; seed `{data['simulation']['campaign_id']}`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data = run_sensitivity()
    output = Path(__file__).resolve().parents[2] / "reports"
    output.mkdir(parents=True, exist_ok=True)
    stem = "regional_rival_stage_calm_sensitivity_2026-10-29"
    (output / f"{stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / f"{stem}.md").write_text(render_markdown(data), encoding="utf-8")
    print(render_markdown(data))


if __name__ == "__main__":
    main()
