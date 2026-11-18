"""Measure real CPU offer eligibility at ML-050 player-level band boundaries."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import sys
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

if platform.system() == "Windows":
    platform.machine = lambda: "AMD64"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database
from app.models.campaign import CampaignMetadata
from app.models.mercenary import MercenaryClass
from app.models.regional import (
    RegionalCpuCyclePlan,
    RegionalCpuMercenary,
    RegionalCycle,
    RegionalGuildState,
    RegionalOffer,
    RegionalWorldState,
)
from app.services.campaign_service import CampaignService
from app.services.guild_service import get_current_guild_context
from app.services import regional_cycle_service as regional


PLAYER_LEVELS = (14, 15, 24, 25, 29, 30, 49, 50)
CPU_GUILD_LEVELS = (1, 2, 3, 5)
OFFER_TYPES = ("contract", "dungeon", "boss")
CPU_EXAMPLES = {
    1: ("new", 1),
    2: ("medium", 1),
    3: ("medium", 3),
    5: ("strong", 5),
}


def _initial_cpu_examples(db, campaign_id: str) -> dict[int, RegionalGuildState]:
    states = list(db.scalars(select(RegionalGuildState).where(
        RegionalGuildState.campaign_id == campaign_id,
        RegionalGuildState.guild_id.is_(None),
        RegionalGuildState.active.is_(True),
    )))
    by_stage_profile = {
        (regional.regional_stage_for_region(state.region_code), state.profile): state
        for state in states
    }
    result = {}
    for level, (profile, stage) in CPU_EXAMPLES.items():
        state = by_stage_profile[(stage, profile)]
        if int(state.level) != level:
            raise ValueError(
                f"seeded profile {profile}, stage {stage} expected guild level {level}, got {state.level}"
            )
        result[level] = state.id
    return result


def _run_scenario(db, campaign, guild, world, state, player_level: int) -> dict[str, object]:
    savepoint = db.begin_nested()
    try:
        cpu_guild_level_before = int(state.level)
        cpu_profile = state.profile
        cpu_region = state.region_code
        active_roster_before = len(list(db.scalars(select(RegionalCpuMercenary.id).where(
            RegionalCpuMercenary.guild_state_id == state.id,
            RegionalCpuMercenary.active.is_(True),
        ))))
        guild.level = player_level
        for cpu_state in db.scalars(select(RegionalGuildState).where(
            RegionalGuildState.campaign_id == campaign.campaign_id,
            RegionalGuildState.guild_id.is_(None),
        )):
            cpu_state.active = cpu_state.id == state.id

        cycle = regional._materialize_cycle(db, campaign, guild, world, cycle_number=0)
        region_code = cpu_region
        cycle_start = regional._utc(cycle.starts_at_utc)
        first_pass_deadline = cycle_start + regional.timedelta(hours=1)
        considered = Counter()
        eligible = Counter()
        blocked = Counter()
        considered_public_ids: set[tuple[int, str, int]] = set()
        eligible_public_ids: set[tuple[int, str, int]] = set()
        blocked_public_ids: set[tuple[int, str, int]] = set()
        considered_internal_ids: set[tuple[int, int]] = set()
        eligible_internal_ids: set[tuple[int, int]] = set()
        real_party_choice = regional._cpu_offer_party

        def observe_real_party_choice(
            offer, cpu_state, roster, available_at, cycle_end, class_roles, **kwargs,
        ):
            choice = real_party_choice(
                offer, cpu_state, roster, available_at, cycle_end, class_roles, **kwargs,
            )
            first_pass = (
                cpu_state.id == state.id
                and bool(available_at)
                and all(
                    regional._utc(until) == first_pass_deadline
                    for until in available_at.values()
                )
            )
            if first_pass and getattr(offer, "internal_contract_candidate", False):
                pass
            elif first_pass and getattr(offer, "internal_contract", False):
                key = (cpu_state.id, int(offer.id))
                considered_internal_ids.add(key)
                if choice is not None:
                    eligible_internal_ids.add(key)
            elif first_pass and offer.offer_type in OFFER_TYPES:
                key = (cpu_state.id, offer.offer_type, int(offer.id))
                if key not in considered_public_ids:
                    considered_public_ids.add(key)
                    considered[offer.offer_type] += 1
                if cpu_state.level < offer.required_guild_level_snapshot and key not in blocked_public_ids:
                    blocked_public_ids.add(key)
                    blocked[offer.offer_type] += 1
                if choice is not None:
                    if key not in eligible_public_ids:
                        eligible_public_ids.add(key)
                        eligible[offer.offer_type] += 1
            return choice

        # This wrapper calls and returns the production planner helper unchanged;
        # it only records eligibility during the first planning pass.
        with patch.object(
            regional, "_cpu_offer_party", side_effect=observe_real_party_choice,
        ):
            regional._process_cycle(db, campaign.campaign_id, cycle, world)
        plan = db.scalar(select(RegionalCpuCyclePlan).where(
            RegionalCpuCyclePlan.cycle_id == cycle.id,
            RegionalCpuCyclePlan.guild_state_id == state.id,
        ))
        decisions = json.loads(plan.decisions_json or "[]") if plan is not None else []
        public_decisions = [
            row for row in decisions
            if isinstance(row, dict) and not row.get("internal_contract")
        ]
        starts = Counter(str(row.get("offer_type", "other")) for row in public_decisions)
        internal_actions = sum(
            isinstance(row, dict) and bool(row.get("internal_contract"))
            for row in decisions
        )
        roster = list(db.scalars(select(RegionalCpuMercenary).where(
            RegionalCpuMercenary.guild_state_id == state.id,
            RegionalCpuMercenary.active.is_(True),
        )))
        actions = int(plan.actions) if plan is not None else 0
        if actions:
            zero_reason = None
        elif not any(eligible.values()):
            if any(blocked.values()):
                zero_reason = "guild-level requirement blocked all offers that otherwise needed review"
            elif not any(considered.values()):
                zero_reason = "planner reviewed no offer (archetype filter or no active CPU roster)"
            else:
                zero_reason = "no offer passed real party, power, role, equipment, and finish-window checks"
        else:
            zero_reason = "eligible offers existed, but the planner started no action"
        return {
            "player_guild_level": player_level,
            "player_band": list(regional._contract_recommended_level_band(player_level)),
            "cpu_profile": cpu_profile,
            "cpu_region": region_code,
            "cpu_guild_level": cpu_guild_level_before,
            "cpu_guild_level_final": int(state.level),
            "cpu_archetype": state.archetype,
            "active_cpu_mercenaries_initial": int(active_roster_before),
            "active_cpu_mercenaries_final": len(roster),
            "planner_considered_offers": {kind: int(considered[kind]) for kind in OFFER_TYPES},
            "considered_offers": {kind: int(considered[kind]) for kind in OFFER_TYPES},
            "eligible_offers": {kind: int(eligible[kind]) for kind in OFFER_TYPES},
            "guild_level_blocked_offers": {kind: int(blocked[kind]) for kind in OFFER_TYPES},
            "internal_contract_candidates_considered": len(considered_internal_ids),
            "internal_contract_candidates_eligible": len(eligible_internal_ids),
            "internal_actions_started": int(internal_actions),
            "actions_started": actions,
            "public_actions_started": len(public_decisions),
            "actions_by_type": {kind: int(starts[kind]) for kind in OFFER_TYPES},
            "zero_action_reason": zero_reason,
            "cycle_seed": cycle.seed,
        }
    finally:
        savepoint.rollback()
        db.expunge_all()


def _markdown(rows: list[dict[str, object]]) -> str:
    lines = [
        "# ML-050 — elegibilidade CPU nos cortes de faixa após a contingência",
        "",
        "32 casos determinísticos em um único save sintético reutilizado. Cada cenário cria e processa uma Vigília "
        "com serviços reais e reverte a transação ao final. Só um rival CPU fica ativo em cada caso para não haver "
        "competição entre guildas pelo mesmo quadro. Nenhuma rotina de elegibilidade ou ação foi substituída.",
        "",
        "Os quatro estados CPU são exemplos semeados naturalmente: nova nível 1 na região de estágio 1; média nível 2 "
        "no estágio 1; média nível 3 no estágio 3; forte nível 5 no estágio 5. ‘Elegível’ chama o mesmo helper de "
        "seleção de equipe do planner e aplica duração, poderes, funções, equipamento e requisito de guilda. Ações "
        "elegíveis são contadas na primeira passagem do planner, antes de resultados/hiring mudarem o estado; ações "
        "são todos os inícios reais gravados no plano após resolver uma Vigília. As colunas de elegibilidade e início "
        "separam as ofertas públicas da contingência interna. O wrapper retorna o valor real do helper sem alterá-lo.",
        "",
        "| Guilda jogador | Faixa contrato | Perfil CPU | Região CPU | Nível guilda CPU antes → depois | Elenco ativo antes → depois | Contratos públicos elegíveis | Masmorras públicas elegíveis | Chefes públicos elegíveis | Contingências elegíveis | Ações internas iniciadas | Contratos públicos iniciados | Masmorras públicas iniciadas | Chefes públicos iniciados | Ações totais | Motivo quando 0 |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        band = row["player_band"]
        eligible = row["eligible_offers"]
        actions = row["actions_by_type"]
        reason = row["zero_action_reason"] or "—"
        lines.append(
            f"| {row['player_guild_level']} | {band[0]}–{band[1]} | {row['cpu_profile']} | "
            f"{row['cpu_region']} | {row['cpu_guild_level']} → {row['cpu_guild_level_final']} | "
            f"{row['active_cpu_mercenaries_initial']} → {row['active_cpu_mercenaries_final']} | "
            f"{eligible['contract']} | {eligible['dungeon']} | {eligible['boss']} | "
            f"{row['internal_contract_candidates_eligible']} | {row['internal_actions_started']} | "
            f"{actions['contract']} | {actions['dungeon']} | {actions['boss']} | {row['actions_started']} | {reason} |"
        )
    lines.extend([
        "",
        "Este ensaio mede permissões e atividade do planner em um ciclo por caso, não taxa de sucesso/recompensa nem "
        "progressão econômica de longo prazo. É evidência complementar à comparação pareada de 5 × 100 ciclos, "
        "que usa jogador nível 1 e por isso exercita apenas a faixa 1–10.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-prefix", type=Path,
        default=ROOT / "reports" / "ml050_cpu_band_eligibility_2026-11-17",
    )
    args = parser.parse_args()
    output_prefix = args.output_prefix if args.output_prefix.is_absolute() else ROOT / args.output_prefix
    if output_prefix.with_suffix(".json").exists() or output_prefix.with_suffix(".md").exists():
        parser.error(f"refusing to overwrite an existing assay report: {output_prefix}")

    with tempfile.TemporaryDirectory(
        prefix="ml050-band-eligibility-", dir=ROOT,
    ) as temp_dir:
        campaigns = CampaignService(Path(temp_dir) / "saves")
        info = campaigns.create_campaign("ML-050 band eligibility", "Synthetic CPU band test")
        campaigns.activate_campaign(info.campaign_id)
        rows: list[dict[str, object]] = []
        try:
            with SessionLocal() as db:
                campaign = db.get(CampaignMetadata, info.campaign_id)
                guild, _resources = get_current_guild_context(db, info.campaign_id)
                world = regional.ensure_campaign_world(db, campaign, guild)
                examples = _initial_cpu_examples(db, info.campaign_id)
                db.commit()
                for player_level in PLAYER_LEVELS:
                    for cpu_level in CPU_GUILD_LEVELS:
                        campaign = db.get(CampaignMetadata, info.campaign_id)
                        guild, _resources = get_current_guild_context(db, info.campaign_id)
                        world = db.get(RegionalWorldState, info.campaign_id)
                        state = db.get(RegionalGuildState, examples[cpu_level])
                        row = _run_scenario(db, campaign, guild, world, state, player_level)
                        if row["cpu_guild_level"] != cpu_level:
                            raise ValueError("rollback changed a seeded CPU guild level")
                        rows.append(row)
        finally:
            campaigns.close_active_campaign(info.campaign_id)
            configure_database("sqlite:///:memory:")
            gc.collect()

    payload = {
        "card": "ML-050",
        "scope": "32 deterministic one-cycle real-planner scenarios after ML-050 internal fallback; a single synthetic campaign DB is reused and every case is rolled back",
        "internal_fallback_enabled": True,
        "player_levels": list(PLAYER_LEVELS),
        "cpu_guild_levels": list(CPU_GUILD_LEVELS),
        "cpu_examples": {str(level): {"profile": profile, "stage": stage}
                         for level, (profile, stage) in CPU_EXAMPLES.items()},
        "rows": rows,
    }
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    output_prefix.with_suffix(".json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    output_prefix.with_suffix(".md").write_text(_markdown(rows), encoding="utf-8")
    print(f"JSON: {output_prefix.with_suffix('.json')}")
    print(f"Markdown: {output_prefix.with_suffix('.md')}")


if __name__ == "__main__":
    main()
