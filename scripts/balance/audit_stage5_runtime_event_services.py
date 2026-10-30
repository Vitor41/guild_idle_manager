"""Conditional event-service audit; not a natural fresh-save progression run."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, create_database_engine
from app.models.campaign import CampaignMetadata
from app.models.guild import Guild, GuildResources
from app.models.regional import RegionalEvent, RegionalRegionState
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_VERSION
from app.services.regional_cycle_service import CYCLE_SECONDS, REGIONS, advance_regional_world
from app.services.regional_event_service import (
    EVENT_RULES_VERSION, REBELLION_CHANCE, create_cycle_portals, evaluate_open_rebellion,
)
from scripts.balance.funded_progression_simulation import wilson_interval_95


def run_audit(*, cycles: int, seed_start: int) -> dict[str, object]:
    fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    campaign_id = str(uuid5(NAMESPACE_URL, f"stage5-runtime-events:{seed_start}"))
    with TemporaryDirectory(prefix="gim-stage5-runtime-events-") as temp_dir:
        engine = create_database_engine(f"sqlite:///{(Path(temp_dir) / 'events.sqlite3').as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with factory() as db:
                apply_initial_campaign_content(db)
                campaign = CampaignMetadata(
                    campaign_id=campaign_id, campaign_name="Stage 5 event service audit",
                    created_at_utc=fixed_time, updated_at_utc=fixed_time,
                    schema_version=5, content_version=PACK_VERSION,
                    home_region=REGIONS[0][1],
                )
                guild = Guild(campaign_id=campaign_id, name="Event service audit", level=1)
                db.add_all((campaign, guild))
                db.flush()
                db.add(GuildResources(guild_id=guild.id, gold=0))
                db.flush()
                advance_regional_world(db, campaign, guild, fixed_time)
                regions = list(db.scalars(select(RegionalRegionState).where(
                    RegionalRegionState.campaign_id == campaign_id,
                ).order_by(RegionalRegionState.region_code)))
                # Hold every region at one explicit, eligible snapshot to estimate
                # conditional service odds without claiming natural threshold timing.
                for region in regions:
                    region.threat = 85.0
                    region.security = 25.0
                db.flush()

                for offset in range(cycles):
                    cycle_end = fixed_time + timedelta(seconds=(offset + 1) * CYCLE_SECONDS)
                    cycle = SimpleNamespace(
                        cycle_number=offset,
                        starts_at_utc=cycle_end - timedelta(seconds=CYCLE_SECONDS),
                        ends_at_utc=cycle_end,
                    )
                    create_cycle_portals(db, campaign_id, cycle, regions)
                    evaluate_open_rebellion(db, campaign, cycle, guild.id, cycle_end)
                    db.commit()

                events = list(db.scalars(select(RegionalEvent).where(
                    RegionalEvent.campaign_id == campaign_id,
                )))
                portal_rows = [event for event in events if event.event_type == "portal"]
                rebellion_rows = [event for event in events if event.event_type == "rebellion"]
                rebellion_summaries = {
                    event.id: json.loads(event.summary_json or "{}") for event in rebellion_rows
                }
                rebellion_opportunities = [
                    event for event in rebellion_rows
                    if rebellion_summaries[event.id].get("eligible") is True
                ]
                rebellion_candidates = [
                    event for event in rebellion_opportunities
                    if rebellion_summaries[event.id].get("generated_while_campaign_open") is True
                    or rebellion_summaries[event.id].get("suppressed_by_global_limit") is True
                ]
                portal_opportunities = cycles * len(regions)
                blocks = []
                cumulative_portal_events = cumulative_rebellion_candidates = cumulative_rebellion_opportunities = 0
                for block_start in range(0, cycles, 100):
                    block_end = min(cycles, block_start + 100)
                    in_block_portals = [event for event in portal_rows
                                        if block_start <= event.trigger_cycle_number < block_end]
                    in_block_rebellions = [event for event in rebellion_rows
                                           if block_start <= event.trigger_cycle_number < block_end]
                    in_block_eligible = [event for event in in_block_rebellions
                                         if rebellion_summaries[event.id].get("eligible") is True]
                    in_block_candidates = [event for event in in_block_eligible
                                           if rebellion_summaries[event.id].get("generated_while_campaign_open") is True
                                           or rebellion_summaries[event.id].get("suppressed_by_global_limit") is True]
                    cumulative_portal_events += len(in_block_portals)
                    cumulative_rebellion_candidates += len(in_block_candidates)
                    cumulative_rebellion_opportunities += len(in_block_eligible)
                    portal_ci = wilson_interval_95(
                        cumulative_portal_events, block_end * len(regions),
                    )
                    rebellion_ci = wilson_interval_95(
                        cumulative_rebellion_candidates, cumulative_rebellion_opportunities,
                    )
                    blocks.append({
                        "cycle_start_inclusive": block_start,
                        "cycle_end_exclusive": block_end,
                        "portal_created_in_block": len(in_block_portals),
                        "portal_rate_cumulative": portal_ci,
                        "rebellion_eligible_opportunities_in_block": len(in_block_eligible),
                        "rebellion_candidates_in_block": len(in_block_candidates),
                        "rebellion_rate_cumulative": rebellion_ci,
                    })
                return {
                    "report_id": "gim-stage5-runtime-event-services-20261029-v1",
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "n_vigilias": cycles,
                    "cycle_seconds": CYCLE_SECONDS,
                    "campaign_seed_key": seed_start,
                    "cycle_number_start": 0,
                    "cycle_number_end_exclusive": cycles,
                    "regions_eligible_per_vigilia": len(regions),
                    "rules_version": EVENT_RULES_VERSION,
                    "conditional_snapshot": {"threat": 85.0, "security": 25.0},
                    "portal": {
                        "chance_per_region_cycle": 0.15,
                        "opportunities": portal_opportunities,
                        "events_created": len(portal_rows),
                        "rate_wilson_95": wilson_interval_95(len(portal_rows), portal_opportunities),
                        "expected_by_rule": 0.15 * portal_opportunities,
                    },
                    "rebellion": {
                        "chance_per_eligible_region_cycle": REBELLION_CHANCE,
                        "eligible_opportunities_rolled": len(rebellion_opportunities),
                        "candidates_including_global_suppression": len(rebellion_candidates),
                        "candidate_rate_wilson_95": wilson_interval_95(
                            len(rebellion_candidates), len(rebellion_opportunities),
                        ),
                        "events_activated": sum(
                            summary.get("generated_while_campaign_open") is True
                            for summary in rebellion_summaries.values()
                        ),
                        "candidates_suppressed_by_global_limit": sum(
                            summary.get("suppressed_by_global_limit") is True
                            for summary in rebellion_summaries.values()
                        ),
                    },
                    "cumulative_blocks": blocks,
                    "scope": "Serviços reais create_cycle_portals/evaluate_open_rebellion em campanha SQLite temporária. As cinco regiões ficam fixas em ameaça 85/segurança 25 para cada Vigília rolada. Tempo de elegibilidade, ações do jogador, mudança dos limiares, resultados de CPU e participação/recompensas de evento ficam fora desta auditoria condicional.",
                }
        finally:
            engine.dispose()


def render_markdown(report: dict[str, object]) -> str:
    portal = report["portal"]
    rebellion = report["rebellion"]
    p_ci = portal["rate_wilson_95"]
    r_ci = rebellion["candidate_rate_wilson_95"]
    return "\n".join([
        "# Auditoria condicional dos serviços de eventos Stage 5", "",
        f"Executada em {report['generated_at_utc']} · N={report['n_vigilias']} Vigílias · chave seed da campanha={report['campaign_seed_key']} · números de ciclo 0–{report['cycle_number_end_exclusive'] - 1}.", "",
        "Esta amostra executa os serviços reais de eventos em SQLite temporário. Todas as cinco regiões são mantidas artificialmente elegíveis em ameaça 85 e segurança 25. Os números estimam rolagens condicionais, não o tempo para atingir os limiares em campanha nova. A chave seed determina um UUID estável da campanha; o serviço de eventos deriva cada rolagem desse UUID, do número de ciclo, da região e da versão de regras.", "",
        "| Evento | Oportunidades efetivamente roladas | Resultado | IC95% Wilson | Regra-alvo |", "|---|---:|---:|---:|---:|",
        f"| Portal | {portal['opportunities']} região-Vigílias | {portal['events_created']} ({p_ci['rate_percent']:.2f}%) | {p_ci['lower_percent']:.2f}–{p_ci['upper_percent']:.2f}% | 15% por região-ciclo |",
        f"| Rebelião | {rebellion['eligible_opportunities_rolled']} região-Vigílias elegíveis sem rebelião global ativa | {rebellion['candidates_including_global_suppression']} candidatas ({r_ci['rate_percent']:.2f}%) | {r_ci['lower_percent']:.2f}–{r_ci['upper_percent']:.2f}% | {100*rebellion['chance_per_eligible_region_cycle']:.2f}% por região-ciclo |", "",
        f"Rebeliões ativadas: {rebellion['events_activated']}. Candidatas suprimidas pelo limite global: {rebellion['candidates_suppressed_by_global_limit']}. O denominador de rebelião exclui ciclos em que uma rebelião ativa impediu a rolagem, conforme o serviço.", "",
        "### Estabilidade por blocos cumulativos", "",
        "| Ciclos | Portais no bloco | Portais acumulados / oportunidades (IC95%) | Rebeliões elegíveis no bloco | Candidatas no bloco | Rebeliões acumuladas / oportunidades (IC95%) |", "|---:|---:|---:|---:|---:|---:|",
        *[f"| {block['cycle_start_inclusive']}–{block['cycle_end_exclusive'] - 1} | {block['portal_created_in_block']} | {block['portal_rate_cumulative']['events']}/{block['portal_rate_cumulative']['n']} ({block['portal_rate_cumulative']['rate_percent']:.2f}%; {block['portal_rate_cumulative']['lower_percent']:.2f}–{block['portal_rate_cumulative']['upper_percent']:.2f}%) | {block['rebellion_eligible_opportunities_in_block']} | {block['rebellion_candidates_in_block']} | {block['rebellion_rate_cumulative']['events']}/{block['rebellion_rate_cumulative']['n']} ({block['rebellion_rate_cumulative']['rate_percent']:.2f}%; {block['rebellion_rate_cumulative']['lower_percent']:.2f}–{block['rebellion_rate_cumulative']['upper_percent']:.2f}%) |" for block in report['cumulative_blocks']], "",
        "## Limites", "",
        report["scope"],
        "A amostra não inclui resolução de portal, participação/decisão de rebelião, recompensas, progressão de ameaça/segurança, nem campanha econômica. Reutilize como validação condicional de serviço, não como estimativa de incidência média e não como playthrough.", "",
        "## Reprodução", "", "```powershell",
        f".venv\\Scripts\\python.exe scripts\\balance\\audit_stage5_runtime_event_services.py --cycles {report['n_vigilias']} --seed-start {report['campaign_seed_key']}",
        "```", "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=1000)
    parser.add_argument("--seed-start", type=int, default=2026102900)
    parser.add_argument("--output-stem", default="stage5_runtime_event_services_2026-10-29")
    args = parser.parse_args()
    report = run_audit(cycles=max(1, args.cycles), seed_start=args.seed_start)
    (ROOT / "reports" / f"{args.output_stem}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    (ROOT / "reports" / f"{args.output_stem}.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: reports/{args.output_stem}.json")
    print(f"Markdown: reports/{args.output_stem}.md")


if __name__ == "__main__":
    main()
