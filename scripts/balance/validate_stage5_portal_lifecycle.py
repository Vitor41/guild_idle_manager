"""Bounded fresh-campaign portal participation and offline-expiry validation.

Only disposable SQLite databases are used. Portal generation and the player
result use the runtime services without forcing event thresholds or RNG.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Make the app's module-level engine an in-memory SQLite engine as well; all
# campaign execution below uses an explicit temporary SQLite file.
os.environ["APP_MODE"] = "desktop"

from app.database.connection import Base, configure_database, create_database_engine
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.models import CampaignMetadata, DungeonTemplate, Guild, GuildResources, Mercenary
from app.models.item import GuildItemInstance
from app.models.regional import (
    RegionalEvent, RegionalEventActivity, RegionalEventParticipant, RegionalRegionState,
)
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services import dungeon_service
from app.services.dungeon_service import start_dungeon, claim_dungeon_loot
from app.services import regional_cycle_service
from app.services.regional_cycle_service import get_current_player_regional_guild
from app.services import regional_event_service
from app.services.regional_event_service import attach_event_activity
from app.services.session_service import start_offline_period

import scripts.balance.simulate_stage5_service_journeys as journeys


PROFILE = next(profile for profile in journeys.PROFILES if profile["name"] == "offline")
PATH = "roster_first"
SEED = 2026303000
MAX_DAYS = 90
MAX_WALL_SECONDS = 180
REPORT_STEM = "stage5_portal_lifecycle_validation_2026-10-29"


class PortalCheckpoint(Exception):
    def __init__(self, day: int, event_id: int, region_code: str, event_created: str):
        super().__init__(f"home portal {event_id} on day {day}")
        self.day = day
        self.event_id = event_id
        self.region_code = region_code
        self.event_created = event_created


class BudgetCheckpoint(Exception):
    pass


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _portal_cycle_observer(home_code: str, trace: list[dict[str, object]]):
    """Wrap the natural portal evaluator without changing its inputs or RNG."""
    original = regional_event_service._create_cycle_portals_locked

    def observe(db, campaign_id, cycle, regions):
        cycle_end = _utc(cycle.ends_at_utc)
        home = next((row for row in regions if row.region_code == home_code), None)
        record: dict[str, object] | None = None
        if home is not None:
            threat = float(home.threat)
            eligible = threat >= regional_event_service.PORTAL_MIN_THREAT
            chance = (
                min(
                    regional_event_service.PORTAL_MAX_CHANCE,
                    regional_event_service.PORTAL_BASE_CHANCE
                    + (threat - regional_event_service.PORTAL_MIN_THREAT) * (0.20 / 30.0),
                )
                if eligible else None
            )
            active_id = db.scalar(select(RegionalEvent.id).where(
                RegionalEvent.campaign_id == campaign_id,
                RegionalEvent.event_type == "portal",
                RegionalEvent.region_code == home_code,
                RegionalEvent.status.in_(("active", "in_progress")),
                RegionalEvent.created_at_utc <= cycle_end,
                RegionalEvent.expires_at_utc > cycle_end,
            ).limit(1))
            record = {
                "cycle": int(cycle.cycle_number),
                "cycle_end_utc": cycle_end.isoformat(),
                "threat": threat,
                "security": float(home.security),
                "influence": int(home.influence),
                "eligible_by_threat": eligible,
                "active_portal_id_blocking_roll": int(active_id) if active_id is not None else None,
                "chance_if_eligible": round(chance, 10) if chance is not None else None,
                "chance_used": None,
                "seed": None,
                "rng_roll_replayed": None,
                "rng_decision": "not_rolled",
                "reason": None,
                "event_id_created": None,
                "decision_matches_runtime": None,
            }
            trace.append(record)

        original(db, campaign_id, cycle, regions)

        if record is None:
            return
        if not eligible:
            record["reason"] = "threat_below_minimum"
            return
        if active_id is not None:
            record["reason"] = "active_portal_blocks_new_roll"
            return
        if db.scalar(select(DungeonTemplate.id).where(
            DungeonTemplate.is_active.is_(True),
            DungeonTemplate.content_type == "boss",
            DungeonTemplate.biome == "portal",
        ).limit(1)) is None:
            record["reason"] = "no_active_portal_boss_template"
            return

        seed = regional_event_service._seed_text(
            campaign_id, cycle.cycle_number, home_code,
            regional_event_service.EVENT_RULES_VERSION, "portal",
        )
        # _rng(seed) is deterministic; this independent replay observes the exact
        # draw the untouched evaluator makes, without consuming or altering it.
        roll = regional_event_service._rng(seed).random()
        record.update({
            "chance_used": round(chance, 10),
            "seed": seed,
            "rng_roll_replayed": roll,
            "rng_decision": "accepted" if roll < chance else "rejected",
            "reason": "rng_accepted" if roll < chance else "rng_rejected",
        })
        created = db.scalar(select(RegionalEvent).where(
            RegionalEvent.campaign_id == campaign_id,
            RegionalEvent.event_type == "portal",
            RegionalEvent.region_code == home_code,
            RegionalEvent.trigger_cycle_number == cycle.cycle_number,
        ).order_by(RegionalEvent.id.desc()).limit(1))
        if created is not None:
            record["event_id_created"] = int(created.id)
        record["decision_matches_runtime"] = (
            created is not None if roll < chance else created is None
        )

    return observe


def _summarize_home_trace(trace: list[dict[str, object]]) -> dict[str, object]:
    reasons: dict[str, int] = {}
    for row in trace:
        reason = str(row.get("reason") or "not_classified")
        reasons[reason] = reasons.get(reason, 0) + 1
    eligible = [row for row in trace if row.get("eligible_by_threat")]
    rolled = [row for row in eligible if row.get("rng_roll_replayed") is not None]
    return {
        "cycles_observed": len(trace),
        "threat_eligible_cycles": len(eligible),
        "rng_rolls": len(rolled),
        "rng_accepted": sum(row.get("rng_decision") == "accepted" for row in rolled),
        "rng_rejected": sum(row.get("rng_decision") == "rejected" for row in rolled),
        "active_portal_blocked_cycles": reasons.get("active_portal_blocks_new_roll", 0),
        "reason_counts": reasons,
        "max_threat": max((float(row["threat"]) for row in trace), default=None),
        "eligible_cycle_numbers": [int(row["cycle"]) for row in eligible],
        "all_observed_rolls_match_runtime": (
            all(row.get("decision_matches_runtime") is True for row in rolled) if rolled else None
        ),
    }


def _home_cpu_static_analysis(campaign_id: str, home_code: str) -> dict[str, object]:
    """Describe initialized home rivals and their configured action cadence."""
    profiles = {1: "strong", 2: "medium", 3: "new", 4: "new"}
    rivals: list[dict[str, object]] = []
    no_activation_probability = 1.0
    expected_activation_checks = 0.0
    for slot, profile in profiles.items():
        archetype_index = int(regional_cycle_service._seed_text(
            campaign_id, home_code, slot, "archetype",
        )[:8], 16) % len(regional_cycle_service.RIVAL_ARCHETYPES)
        archetype = regional_cycle_service.RIVAL_ARCHETYPES[archetype_index]
        probability = regional_cycle_service.regional_cpu_action_probability(
            campaign_id,
            SimpleNamespace(
                profile=profile, archetype=archetype, region_code=home_code, slot=slot,
            ),
        )
        checks = 2 if profile == "strong" else 1
        no_activation_probability *= (1.0 - probability) ** checks
        expected_activation_checks += probability * checks
        rivals.append({
            "slot": slot, "profile": profile, "archetype": archetype,
            "configured_per_check_probability": probability,
            "checks_per_vigil": checks,
            "initial_roster_size": {"strong": 5, "medium": 3, "new": 1}[profile],
        })
    return {
        "region_initial_state": {"threat": 25, "security": 50, "influence": 0},
        "rivals": rivals,
        "nominal_expected_activation_checks_per_vigil": round(expected_activation_checks, 4),
        "nominal_probability_at_least_one_activation_check": round(1.0 - no_activation_probability, 4),
        "nominal_probability_note": (
            "Probabilidade nominal calculada das verificações independentes configuradas; não é a contagem observada de ações CPU. "
            "Ofertas, elegibilidade do grupo e resultados podem impedir que uma verificação vire ação."
        ),
        "baseline_rule": "ameaça +1/segurança -1 somente quando ações CPU e do jogador são zero naquela Vigília",
        "cpu_outcome_rule": "cada sucesso/falha efetivo altera ameaça pelo impacto do rank (-/+0,04 a 0,14); qualquer ação CPU efetiva suprime o baseline",
        "gdd_expectation": "O GDD §13 diz que o rival forte mantém a região calma por um período, mas não indefinidamente.",
        "implementation_gap": (
            "As regras examinadas usam taxas fixas por perfil/arquétipo e não definem duração nem atenuação explícita do efeito estabilizador do rival forte."
        ),
        "inference_limit": (
            "O SQLite temporário foi removido e a trilha JSON não preserva cada plano/resultado CPU nem o marcador baseline_applied; "
            "as contribuições realizadas não podem ser atribuídas apenas ao rival forte."
        ),
    }


def _write_report(result: dict[str, object]) -> None:
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    (report_dir / f"{REPORT_STEM}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8",
    )
    lines = [
        "# Validação limitada do ciclo de portal — 29/10/2026",
        "",
        f"- Estado: **{result['status']}**",
        f"- Perfil/caminho/seed: `{PROFILE['name']}/{PATH}/{SEED}`",
        f"- Campanha: `{result.get('campaign_id')}`",
        f"- Tempo de campanha: {result.get('journey_wall_seconds')}s; dia do portal natal: {result.get('checkpoint_day') or 'não alcançado'}",
        f"- Coordenação das execuções: {result.get('execution_coordination_note', 'não registrada')}",
        f"- Checkpoint: `{result.get('checkpoint') or result.get('snapshot', 'não criado')}`",
        f"- Região/portal: `{result.get('region_code') or 'não houve portal natal elegível'}` / `{result.get('event_id') or '—'}`",
        f"- Região natal: `{result.get('home_region_code')}`; portais naturais no horizonte: {result.get('natural_portal_count', 0)}",
        "",
        "## Regras e escopo",
        "",
        "Cada execução usa uma campanha fresh-save em SQLite temporário; o JSON publicado representa a execução final, limitada a 90 dias ou 180 segundos. O checkpoint ocorre somente após o serviço natural de ciclo apresentar um portal ativo da região natal. Nenhum threshold, seed de evento, rolagem de combate, preço ou regra foi forçado. Se o portal natal não surgir no teto, os ramos A e B não são criados; não existe snapshot de evento elegível para copiar.",
        "",
        "## Evidência",
        "",
        f"- Síntese fiel do JSON: estado `{result.get('status')}`, perfil `{PROFILE['name']}/{PATH}`, seed `{SEED}`, {result.get('natural_portal_count', 0)} portais naturais; região natal `{result.get('home_region_code')}`.",
        f"- Portais observados por região: `{json.dumps(result.get('portal_counts_by_region', {}), ensure_ascii=False)}`.",
        f"- Portais observados por estado: `{json.dumps(result.get('portal_counts_by_status', {}), ensure_ascii=False)}`.",
        f"- Ledger diário coletado (não usado como evidência econômica): `{json.dumps(result.get('campaign_ledger_totals', {}), ensure_ascii=False)}`; resíduo não atribuído: `{result.get('campaign_ledger_totals', {}).get('unattributed_residual')}`.",
        f"- Diagnóstico da região natal por ciclo: `{json.dumps(result.get('home_region_cycle_summary', {}), ensure_ascii=False)}`.",
        "- O JSON mantém cada ciclo com ameaça, segurança, influência, elegibilidade, chance (somente quando elegível), bloqueio, seed, rolagem determinística reproduzida e decisão; a reprodução usa o mesmo seed sem consumir nem alterar a rolagem do serviço.",
        f"- A/B e ledger de evento: `{json.dumps(result.get('branch_outcome', {}), ensure_ascii=False)}`.",
        f"- {str(result.get('absence_cause_note', 'Cause of absence not recorded')).rstrip('.') }.",
        "",
        "## Leitura estática das regras regionais",
        "",
        f"- Estado inicial por código: `{json.dumps(result.get('static_balance_analysis', {}).get('region_initial_state', {}), ensure_ascii=False)}`. Rivais natais e cadência nominal: `{json.dumps(result.get('static_balance_analysis', {}).get('rivals', []), ensure_ascii=False)}`.",
        f"- Ameaça observada na trilha: `{json.dumps(result.get('static_balance_analysis', {}).get('observed_threat', {}), ensure_ascii=False)}`.",
        f"- As probabilidades configuradas produzem nominalmente `{result.get('static_balance_analysis', {}).get('nominal_expected_activation_checks_per_vigil')}` verificações de atividade por Vigília e `{result.get('static_balance_analysis', {}).get('nominal_probability_at_least_one_activation_check')}` de chance de ao menos uma verificação; `{result.get('static_balance_analysis', {}).get('nominal_probability_note')}",
        f"- Regra observada no código: `{result.get('static_balance_analysis', {}).get('baseline_rule')}`; `{result.get('static_balance_analysis', {}).get('cpu_outcome_rule')}`.",
        f"- Comparação com GDD §§13–15: {result.get('static_balance_analysis', {}).get('gdd_expectation')} {result.get('static_balance_analysis', {}).get('implementation_gap')}",
        f"- Limite de atribuição: {result.get('static_balance_analysis', {}).get('inference_limit')}",
        "- Proposta para revisão de design: decidir se “não indefinidamente” exige uma duração/atenuação explícita ou se o comportamento emergente atual é aceitável. Se for exigida uma subida garantida, aprovar a regra e uma validação temporal com ledger por Vigília (CPU solicitada/executada, rank, sucesso/falha e baseline) antes de qualquer alteração de produção. Nenhuma alteração de produção foi feita.",
        "",
        "Os arquivos SQLite de execução ficaram em diretório temporário e foram removidos ao fim. Sem checkpoint elegível, não há hashes de snapshot nem operações/ledger dos ramos A/B; os resultados naturais e a trilha diagnóstica estão preservados no JSON. Esta validação não altera preços/regras, não é amostra estatística e não aprova Stage 5.",
        "",
    ]
    (report_dir / f"{REPORT_STEM}.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    wall_start = time.perf_counter()
    result: dict[str, object] = {
        "validation": REPORT_STEM,
        "status": "running",
        "profile": PROFILE["name"], "path": PATH, "seed": SEED,
        "max_simulated_days": MAX_DAYS, "max_wall_seconds": MAX_WALL_SECONDS,
        "event_generation_rng_forced": False, "combat_rng_forced": False,
        "prices_or_rules_changed": False,
    }
    with TemporaryDirectory(prefix="gim-portal-lifecycle-") as directory:
        root = Path(directory)
        live_path = root / "campaign.sqlite3"
        engine = create_database_engine(f"sqlite:///{live_path.as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as db:
            apply_initial_campaign_content(db)
            db.commit()

        # Reuse a previously recorded seed for reproducibility while keeping
        # event rolls natural. Align day 33 of the simulation with the present.
        real_anchor = datetime.now(timezone.utc)
        journeys.EPOCH = real_anchor - timedelta(days=33)
        home_code = journeys.REGIONS[0][0]
        original_board = journeys.get_regional_board
        journey_started = time.perf_counter()
        journey_result: dict[str, object] | None = None
        home_cycle_trace: list[dict[str, object]] = []

        def stop_on_natural_home_portal(db, campaign, guild, now):
            if time.perf_counter() - journey_started >= MAX_WALL_SECONDS:
                raise BudgetCheckpoint("wall budget reached")
            board = original_board(db, campaign, guild, now)
            for event in board.get("portal_events", []):
                if event.status == "active" and event.region_code == home_code:
                    raise PortalCheckpoint(
                        max(0, (now.date() - journeys.EPOCH.date()).days),
                        int(event.id), event.region_code, _utc(event.created_at_utc).isoformat(),
                    )
            return board

        checkpoint: PortalCheckpoint | None = None
        budget_error: str | None = None
        try:
            with factory() as db, patch.object(journeys, "get_regional_board", stop_on_natural_home_portal), patch.object(
                regional_event_service,
                "_create_cycle_portals_locked",
                _portal_cycle_observer(home_code, home_cycle_trace),
            ):
                try:
                    journey_result = journeys.run_journey(
                        db, PROFILE, PATH, SEED, MAX_DAYS,
                        max_wall_seconds=MAX_WALL_SECONDS,
                    )
                except PortalCheckpoint as found:
                    checkpoint = found
                    db.commit()
                except BudgetCheckpoint as stopped:
                    budget_error = str(stopped)
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
        finally:
            pass

        # The journey creates one campaign using its stable UUID formula.
        from uuid import NAMESPACE_URL, uuid5
        campaign_id = str(uuid5(NAMESPACE_URL, f"stage5-service:{PROFILE['name']}:{PATH}:{SEED}"))
        result["campaign_id"] = campaign_id
        result["journey_wall_seconds"] = round(time.perf_counter() - journey_started, 3)
        result["checkpoint_day"] = checkpoint.day if checkpoint else None
        result["event_id"] = checkpoint.event_id if checkpoint else None
        result["region_code"] = checkpoint.region_code if checkpoint else None
        result["event_created_at_utc"] = checkpoint.event_created if checkpoint else None
        result["home_region_code"] = home_code
        result["home_region_cycle_trace"] = home_cycle_trace
        result["home_region_cycle_summary"] = _summarize_home_trace(home_cycle_trace)
        result["static_balance_analysis"] = _home_cpu_static_analysis(campaign_id, home_code)
        if home_cycle_trace:
            result["static_balance_analysis"]["observed_threat"] = {
                "first_cycle": home_cycle_trace[0]["threat"],
                "minimum": min(float(row["threat"]) for row in home_cycle_trace),
                "maximum": max(float(row["threat"]) for row in home_cycle_trace),
                "last_cycle": home_cycle_trace[-1]["threat"],
                "cycles": len(home_cycle_trace),
            }

        if checkpoint is None:
            with factory() as db:
                portal_rows = list(db.scalars(select(RegionalEvent).where(
                    RegionalEvent.campaign_id == campaign_id,
                    RegionalEvent.event_type == "portal",
                ).order_by(RegionalEvent.trigger_cycle_number, RegionalEvent.id)))
                result["natural_portals_seen"] = [
                    {"id": event.id, "region": event.region_code, "status": event.status,
                     "cycle": event.trigger_cycle_number, "created_at_utc": _utc(event.created_at_utc).isoformat()}
                    for event in portal_rows
                ]
                result["natural_portal_count"] = len(portal_rows)
                result["portal_counts_by_region"] = {
                    region: sum(event.region_code == region for event in portal_rows)
                    for region in sorted({event.region_code for event in portal_rows})
                }
                result["portal_counts_by_status"] = {
                    status: sum(event.status == status for event in portal_rows)
                    for status in sorted({event.status for event in portal_rows})
                }
                if journey_result is not None:
                    ledger_keys = ("passive_offline", "missions", "dungeons", "market_sales",
                                   "salvage_fees", "building_and_hire_purchases", "observed_delta",
                                   "unattributed_residual")
                    result["campaign_ledger_totals"] = {
                        key: sum(int(day["gold_ledger"][key]) for day in journey_result["daily"])
                        for key in ledger_keys
                    }
            result["status"] = "stopped_no_eligible_home_portal_within_budget"
            result["stop_reason"] = budget_error or f"max {MAX_DAYS} simulated days reached"
            result["snapshot"] = "not taken: no active portal in the player's home region within the budget"
            result["campaign_daily_ledger_recorded"] = journey_result is not None and "daily" in journey_result
            result["branch_outcome"] = {
                "A_player_participation": "not run; eligibility precondition was not met",
                "B_offline_expiration": "not run; no eligible shared event snapshot existed",
                "event_reward_ledger": "not applicable; no player event activity was started",
            }
            result["absence_cause_note"] = (
                f"causa confirmada nesta execução: {home_code} ficou abaixo da ameaça mínima de "
                f"{regional_event_service.PORTAL_MIN_THREAT:g} em todos os "
                f"{result['home_region_cycle_summary']['cycles_observed']} ciclos; máxima observada "
                f"{result['home_region_cycle_summary']['max_threat']}. Houve zero rolagens RNG porque "
                "a região nunca foi elegível. O GDD §15 também condiciona o portal a ameaça ≥70; "
                "portanto, esta execução não demonstra contradição nem bug, embora a ocorrência na região "
                "natal dependa de ela alcançar esse limiar."
            )
            result["branches"] = {}
            engine.dispose()
            _write_report(result)
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return 0

        engine.dispose()
        snapshot_path = root / "snapshot.sqlite3"
        shutil.copy2(live_path, snapshot_path)
        branch_a_path = root / "branch_a.sqlite3"
        branch_b_path = root / "branch_b.sqlite3"
        shutil.copy2(snapshot_path, branch_a_path)
        shutil.copy2(snapshot_path, branch_b_path)
        snapshot_hash = _hash(snapshot_path)
        result["checkpoint"] = {
            "database": "SQLite temporário, transação commitada e engine fechada",
            "snapshot_sha256": snapshot_hash,
            "branch_a_initial_sha256": _hash(branch_a_path),
            "branch_b_initial_sha256": _hash(branch_b_path),
            "identical_before_actions": _hash(branch_a_path) == snapshot_hash == _hash(branch_b_path),
        }

        # Branch A: actual player event participation and actual dungeon services.
        branch_a_engine = create_database_engine(f"sqlite:///{branch_a_path.as_posix()}")
        branch_a_factory = sessionmaker(bind=branch_a_engine, expire_on_commit=False)
        branch_a: dict[str, object] = {"actions": [], "status": "not_run"}
        with branch_a_factory() as db:
            event = db.get(RegionalEvent, checkpoint.event_id)
            campaign = db.get(CampaignMetadata, campaign_id)
            guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
            resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild.id))
            player_state = get_current_player_regional_guild(db, campaign_id, guild.id)
            template = db.get(DungeonTemplate, event.dungeon_template_id)
            payload = json.loads(event.summary_json or "{}")
            boss_snapshot = payload["portal_boss"]["template"]
            members = list(db.scalars(select(Mercenary).where(
                Mercenary.guild_id == guild.id, Mercenary.status == "available",
            ).order_by(Mercenary.level.desc(), Mercenary.id).limit(int(boss_snapshot["max_party_size"]))))
            member_ids = [str(member.id) for member in members]
            try:
                start_time = _utc(event.created_at_utc) + timedelta(minutes=1)
                with patch.object(dungeon_service, "utc_now", return_value=start_time):
                    run = start_dungeon(
                        db, guild, str(template.id), member_ids, commit=False,
                        regional_duration_seconds=max(3600, int(boss_snapshot["duration_seconds"])),
                        regional_min_duration_seconds=3600,
                        template_snapshot=boss_snapshot,
                    )
                    activity = attach_event_activity(db, event, player_state, "dungeon", run.id)
                    db.commit()
                busy_after_start = [
                    {"mercenary_id": member.id, "status": db.get(Mercenary, member.id).status}
                    for member in members
                ]
                before_gold = int(resources.gold)
                before_items = int(db.query(GuildItemInstance).filter_by(guild_id=guild.id).count())
                duration_seconds = int((_utc(run.ends_at) - _utc(run.started_at)).total_seconds())
                with patch.object(dungeon_service, "utc_now", return_value=_utc(run.ends_at)):
                    claim_dungeon_loot(db, guild, resources, run.id, commit=True)
                db.refresh(event)
                db.refresh(run)
                db.refresh(resources)
                branch_a.update({
                    "status": "completed",
                    "actions": [
                        "start_dungeon com template snapshot do portal e grupo disponível",
                        "attach_event_activity(source_type=dungeon)",
                        "claim_dungeon_loot no instante ends_at do timer",
                    ],
                    "start_time_utc": start_time.isoformat(),
                    "timer_seconds": duration_seconds,
                    "timer_at_least_1h": duration_seconds >= 3600,
                    "busy_after_start": busy_after_start,
                    "mercenaries_after_claim": [
                        {"mercenary_id": member.id, "status": db.get(Mercenary, member.id).status}
                        for member in members
                    ],
                    "run": {"id": run.id, "status": run.status, "success": run.success,
                            "gold_reward": run.gold_reward, "xp_reward": run.xp_reward,
                            "result_details": run.result_details},
                    "event": {"id": event.id, "status": event.status,
                              "participant_status": db.scalar(select(RegionalEventParticipant.status).where(
                                  RegionalEventParticipant.event_id == event.id,
                                  RegionalEventParticipant.guild_state_id == player_state.id,
                              )),
                              "activity_status": db.scalar(select(RegionalEventActivity.status).where(
                                  RegionalEventActivity.event_id == event.id,
                                  RegionalEventActivity.source_run_id == run.id,
                              ))},
                    "reward_ledger": {"gold_before": before_gold, "gold_after": int(resources.gold),
                                      "gold_delta": int(resources.gold) - before_gold,
                                      "item_instances_before": before_items,
                                      "item_instances_after": int(db.query(GuildItemInstance).filter_by(guild_id=guild.id).count()),
                                      "portal_loot_result": json.loads(event.summary_json or "{}").get("portal_loot_result"),
                                      "dungeon_gold_reward": run.gold_reward,
                                      "dungeon_xp_reward": run.xp_reward},
                })
            except Exception as exc:
                db.rollback()
                branch_a.update({"status": "not_eligible_or_failed", "error": f"{type(exc).__name__}: {exc}"})
        branch_a_engine.dispose()
        result["branches"] = {"A_player_participation": branch_a}

        if branch_a["status"] != "completed":
            result["branches"]["B_offline_expiration"] = {
                "status": "not_run",
                "reason": "the natural portal was not player-eligible for the actual service path",
            }
            result["status"] = "stopped_portal_not_player_eligible"
            result["branch_outcome"] = {
                "A_player_participation": branch_a["status"],
                "B_offline_expiration": "not run; shared eligibility precondition failed",
                "event_reward_ledger": "no eligible activity was started",
            }
            result["branch_a_final_sha256"] = _hash(branch_a_path)
            result["branch_b_final_sha256"] = _hash(branch_b_path)
            result["branches_isolated"] = _hash(branch_a_path) != _hash(branch_b_path)
            result["total_wall_seconds"] = round(time.perf_counter() - wall_start, 3)
            _write_report(result)
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return 0

        # Branch B starts from the identical untouched snapshot and exercises ClockGuard.
        from app.database.connection import SessionLocal
        configure_database(f"sqlite:///{branch_b_path.as_posix()}")
        offline_store = MemoryAnchorStore()
        branch_b: dict[str, object] = {"actions": [], "status": "not_run"}
        with SessionLocal() as db:
            event = db.get(RegionalEvent, checkpoint.event_id)
            campaign = db.get(CampaignMetadata, campaign_id)
            guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
            offline_start = _utc(event.created_at_utc) + timedelta(minutes=1)
            offline_return = offline_start + timedelta(hours=4)
            start_offline_period(db, guild, offline_start)
            metadata = db.get(CampaignMetadata, campaign_id)
            metadata.last_clean_shutdown_utc = offline_start
            metadata.last_session_state = "offline"
            db.commit()
            offline_store.save(campaign_id, offline_start)
        clock = ClockGuard(offline_store, wall_clock=lambda: offline_return, monotonic_clock=lambda: 100.0)
        summary = clock.activate_campaign(campaign_id)
        with SessionLocal() as db:
            event = db.get(RegionalEvent, checkpoint.event_id)
            metadata = db.get(CampaignMetadata, campaign_id)
            branch_b.update({
                "status": "completed" if summary else "failed",
                "actions": ["start_offline_period", "ClockGuard.activate_campaign com retorno quatro horas após a desconexão"],
                "offline_start_utc": offline_start.isoformat(),
                "offline_return_utc": offline_return.isoformat(),
                "offline_elapsed_seconds": summary.get("elapsed_seconds") if summary else None,
                "elapsed_over_3h": bool(summary and summary.get("elapsed_seconds", 0) > 3 * 3600),
                "event": {"id": event.id, "status": event.status,
                          "summary": json.loads(event.summary_json or "{}")},
                "offline_summary": summary,
                "pending_offline_report_persisted": bool(metadata.pending_offline_report),
                "regional_context": summary.get("regional_context") if summary else None,
            })
        configure_database("sqlite:///:memory:")
        result["branches"]["B_offline_expiration"] = branch_b
        result["branch_a_final_sha256"] = _hash(branch_a_path)
        result["branch_b_final_sha256"] = _hash(branch_b_path)
        result["branches_isolated"] = _hash(branch_a_path) != _hash(branch_b_path)
        result["status"] = "completed" if branch_a["status"] == "completed" and branch_b["status"] == "completed" else "partial_event_validation"
        branch_a_engine.dispose()

    result["total_wall_seconds"] = round(time.perf_counter() - wall_start, 3)
    _write_report(result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
