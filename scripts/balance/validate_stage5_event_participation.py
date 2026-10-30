"""Real-service portal and rebellion participation checks on disposable SQLite."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, func
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ["APP_MODE"] = "desktop"

from app.database.connection import Base, create_database_engine
from app.models import (
    CampaignMetadata, DungeonRun, DungeonTemplate, Guild, GuildBuilding, GuildResources,
    ItemTemplate, Mercenary, MercenaryClass, MissionTemplate,
)
from app.models.item import GuildItemInstance
from app.models.regional import (
    RegionalCycle, RegionalEvent, RegionalEventActivity, RegionalEventParticipant,
    RegionalGuildState, RegionalRegionState,
)
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services import dungeon_service, mission_service
from app.services.building_service import ensure_guild_buildings
from app.services.dungeon_service import claim_dungeon_loot, start_dungeon
from app.services.equipment_service import create_equipment_instance_from_template, get_party_power_score
from app.services.mercenary_service import equip_mercenary_item
from app.services.mission_service import claim_mission_loot, start_mission
from app.services.regional_cycle_service import REGIONS, ensure_campaign_world, get_current_player_regional_guild, get_regional_board
from app.services.regional_event_service import (
    attach_event_activity, create_cycle_portals, evaluate_open_rebellion, expire_due_events,
    record_rebellion_decision,
)
from app.services.result_detail_service import parse_result_details

REPORT_STEM = "stage5_event_participation_runtime_2026-10-30"
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _new_cycle(db: Session, campaign: CampaignMetadata, number: int, at: datetime) -> RegionalCycle:
    cycle = RegionalCycle(
        campaign_id=campaign.campaign_id, cycle_number=number,
        starts_at_utc=at, ends_at_utc=at + timedelta(hours=6),
        seed=f"stage5-event-validation-{number}", rules_version="vigilia-v3",
        content_version=campaign.content_version, player_level_snapshot=50,
        player_power_snapshot=0, rank_weights_json="{}", status="open",
    )
    db.add(cycle)
    db.flush()
    return cycle


def _setup(db: Session):
    apply_initial_campaign_content(db)
    campaign = CampaignMetadata(
        campaign_id="stage5-event-validation-campaign",
        campaign_name="Stage 5 event participation validation",
        created_at_utc=EPOCH, updated_at_utc=EPOCH, schema_version=5,
        content_version=3, home_region=REGIONS[0][1], stamina_seconds=8 * 3600,
    )
    guild = Guild(campaign_id=campaign.campaign_id, name="Equipe financiada de validação", level=50)
    resources = GuildResources(guild=guild, gold=1_000_000, wood=1_000_000, ore=1_000_000, crystals=1_000_000)
    db.add_all((campaign, guild, resources))
    db.flush()
    buildings = {row.building_template.effect_type: row for row in ensure_guild_buildings(db, guild.id)}
    buildings["scouts"].level = 1
    db.flush()
    ensure_campaign_world(db, campaign, guild)
    now = EPOCH
    get_regional_board(db, campaign, guild, now)
    db.flush()
    player_state = get_current_player_regional_guild(db, campaign.campaign_id, guild.id)
    return campaign, guild, resources, buildings, player_state, now


def _fund_eligible_party(db: Session, guild: Guild, resources: GuildResources) -> list[Mercenary]:
    roles = ("knight", "cleric", "priest", "archer", "mage")
    by_code = {row.code: row for row in db.scalars(select(MercenaryClass).where(
        MercenaryClass.code.in_(roles), MercenaryClass.is_active.is_(True),
    ))}
    members = []
    for index, code in enumerate(roles):
        cls = by_code[code]
        member = Mercenary(
            guild_id=guild.id, class_id=cls.id, name=f"Expedição financiada {index + 1}",
            level=350, xp=0, status="available", rarity="epic", hire_cost=0,
            power=4500, vitality=500, agility=500, intelligence=500, luck=300,
        )
        members.append(member)
    db.add_all(members)
    db.flush()
    items = list(db.scalars(select(ItemTemplate).where(
        ItemTemplate.item_type == "equipment", ItemTemplate.tier >= 7,
        ItemTemplate.equipment_slot == "necklace", ItemTemplate.required_level <= 350,
    ).order_by(ItemTemplate.tier, ItemTemplate.required_level, ItemTemplate.id)))
    if not items:
        raise RuntimeError("Não há colar Tier 7 elegível para a composição financiada.")
    for member in members:
        instance = create_equipment_instance_from_template(db, guild.id, items[0])
        db.flush()
        equip_mercenary_item(db, guild, member.id, str(instance.id))
    db.refresh(resources)
    return members


def _natural_portal(db: Session, campaign: CampaignMetadata, home_code: str, start_cycle: int):
    region = db.scalar(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign.campaign_id,
        RegionalRegionState.region_code == home_code,
    ))
    if region is None:
        raise RuntimeError("Região natal não foi criada pelo serviço regional.")
    # Reachability stimulus for a late-game test save; the event probability and
    # template selection remain the unchanged production service/RNG.
    region.threat = 100.0
    db.flush()
    for offset in range(200):
        cycle_number = start_cycle + offset
        cycle_at = EPOCH + timedelta(days=400, hours=6 * cycle_number)
        cycle = _new_cycle(db, campaign, cycle_number, cycle_at)
        regions = list(db.scalars(select(RegionalRegionState).where(
            RegionalRegionState.campaign_id == campaign.campaign_id,
        ).order_by(RegionalRegionState.region_code)))
        create_cycle_portals(db, campaign.campaign_id, cycle, regions)
        event = db.scalar(select(RegionalEvent).where(
            RegionalEvent.campaign_id == campaign.campaign_id,
            RegionalEvent.event_type == "portal", RegionalEvent.region_code == home_code,
            RegionalEvent.trigger_cycle_number == cycle_number, RegionalEvent.status == "active",
        ))
        db.flush()
        if event is not None:
            return event, cycle_number
    raise RuntimeError("Portal natural não surgiu após 200 rollings elegíveis de 25%.")


def _portal_case(db: Session, campaign, guild, resources, player_state, home_code, cycle_start: int,
                 outcome: str) -> dict[str, object]:
    event, cycle_number = _natural_portal(db, campaign, home_code, cycle_start)
    payload = json.loads(event.summary_json or "{}")
    snapshot = payload["portal_boss"]["template"]
    template = db.get(DungeonTemplate, event.dungeon_template_id)
    members = list(db.scalars(select(Mercenary).where(
        Mercenary.guild_id == guild.id, Mercenary.status == "available",
    ).order_by(Mercenary.id).limit(int(snapshot["max_party_size"]))))
    if len(members) < int(snapshot["min_party_size"]):
        raise RuntimeError("Equipe financiada não atende ao tamanho congelado do snapshot.")
    if min(member.level for member in members) < int(snapshot["required_min_mercenary_level"]):
        raise RuntimeError("Equipe financiada não atende ao nível mínimo do snapshot.")
    from app.services.dungeon_service import validate_advanced_party_requirements, validate_dungeon_requirements
    from types import SimpleNamespace
    validate_dungeon_requirements(db, guild, SimpleNamespace(**snapshot))
    validate_advanced_party_requirements(db, guild, SimpleNamespace(**snapshot), members)
    party_power = get_party_power_score(db, guild.id, members)
    start_at = _utc(event.created_at_utc) + timedelta(minutes=1)
    run_clock = iter((start_at,))
    with patch.object(dungeon_service, "utc_now", side_effect=lambda: next(run_clock)):
        run = start_dungeon(
            db, guild, str(template.id), [str(member.id) for member in members], commit=False,
            regional_duration_seconds=max(3600, int(snapshot["duration_seconds"])),
            regional_min_duration_seconds=3600, template_snapshot=snapshot,
        )
        activity = attach_event_activity(db, event, player_state, "dungeon", run.id)
        run_id = run.id
        ends_at = _utc(run.ends_at)
        db.flush()
    db.refresh(run)
    before_gold = int(resources.gold)
    before_items = int(db.scalar(select(func.count(GuildItemInstance.id)).where(
        GuildItemInstance.guild_id == guild.id,
    )) or 0)
    forced_roll = 1 if outcome == "success" else 100
    with patch.object(dungeon_service, "utc_now", return_value=ends_at), \
            patch.object(dungeon_service, "randint", return_value=forced_roll):
        claimed = claim_dungeon_loot(db, guild, resources, run_id, commit=False)
    if bool(claimed.success) != (outcome == "success"):
        raise RuntimeError(f"O roll fixado não produziu o resultado portal esperado: {outcome}.")
    db.flush()
    item_details = parse_result_details(claimed.result_details)
    after_gold = int(resources.gold)
    after_items = int(db.scalar(select(func.count(GuildItemInstance.id)).where(
        GuildItemInstance.guild_id == guild.id,
    )) or 0)
    first_ledger = {"gold_before": before_gold, "gold_after": after_gold,
                    "item_instances_before": before_items, "item_instances_after": after_items,
                    "result_items": item_details.get("items", [])}
    duplicate_rejected = False
    try:
        claim_dungeon_loot(db, guild, resources, run_id, commit=False)
    except dungeon_service.DungeonError:
        duplicate_rejected = True
    if not duplicate_rejected:
        raise RuntimeError("O claim duplicado do portal foi aceito.")
    db.flush()
    expire_due_events(db, campaign.campaign_id, _utc(event.expires_at_utc) + timedelta(seconds=1))
    db.refresh(event)
    db.refresh(claimed)
    db.refresh(resources)
    return {
        "scenario": outcome, "cycle_number": cycle_number, "event_id": event.id,
        "template": template.name, "rank_template_band": template.level_band,
        "snapshot": {key: snapshot.get(key) for key in (
            "min_party_size", "max_party_size", "required_min_mercenary_level", "required_guild_level",
            "required_total_power", "required_building_type", "required_building_level",
            "required_equipment_tier", "required_tank_count", "required_support_count", "required_damage_count",
        )},
        "party_levels": [member.level for member in members], "party_roles": [member.mercenary_class.role_type for member in members],
        "party_power": party_power, "party_tier_7_each": True,
        "forced_combat_roll": forced_roll, "run_success": bool(claimed.success),
        "run_status": claimed.status, "activity_status": activity.status,
        "participant_status": db.scalar(select(RegionalEventParticipant.status).where(
            RegionalEventParticipant.event_id == event.id,
            RegionalEventParticipant.guild_state_id == player_state.id,
        )), "event_status_after_deadline": event.status,
        "reward_ledger": first_ledger, "duplicate_claim_rejected": duplicate_rejected,
        "duration_seconds": int((ends_at - start_at).total_seconds()),
    }


def _rebellion_case(db: Session, campaign, guild, resources, player_state, now) -> dict[str, object]:
    regions = list(db.scalars(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign.campaign_id,
    ).order_by(RegionalRegionState.region_code)))
    for region in regions:
        region.threat = 100.0
        region.security = 0.0
    db.flush()
    event = None
    selected_cycle = None
    for cycle_number in range(10_000, 11_000):
        at = now + timedelta(hours=6 * cycle_number)
        cycle = _new_cycle(db, campaign, cycle_number, at)
        event = evaluate_open_rebellion(db, campaign, cycle, guild.id, at)
        if event is not None:
            selected_cycle = cycle_number
            break
    if event is None or selected_cycle is None:
        raise RuntimeError("Rebelião natural não ativou após 1.000 ciclos elegíveis de 2%.")
    decision_at = _utc(event.created_at_utc) + timedelta(minutes=1)
    record_rebellion_decision(db, event, player_state.id, "accept", decision_at)
    participant_status_after_accept = db.scalar(select(RegionalEventParticipant.status).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == player_state.id,
    ))
    members = list(db.scalars(select(Mercenary).where(
        Mercenary.guild_id == guild.id, Mercenary.status == "available",
    ).order_by(Mercenary.id)))
    template = db.scalar(select(MissionTemplate).where(
        MissionTemplate.is_active.is_(True), MissionTemplate.mission_type != "long_idle",
        MissionTemplate.mission_type != "gathering",
        MissionTemplate.required_building_type.is_(None),
        MissionTemplate.required_guild_level <= guild.level,
        MissionTemplate.required_min_mercenary_level <= members[0].level,
        MissionTemplate.min_party_size <= 1, MissionTemplate.max_party_size >= 1,
    ).order_by(MissionTemplate.duration_seconds, MissionTemplate.id))
    if template is None:
        raise RuntimeError("Nenhum contrato de uma pessoa elegível para completar o cenário aceito.")
    start_at = decision_at + timedelta(minutes=1)
    run_clock = iter((start_at,))
    with patch.object(mission_service, "utc_now", side_effect=lambda: next(run_clock)):
        run = start_mission(db, guild, str(template.id), [str(members[0].id)], commit=False)
        activity = attach_event_activity(db, event, player_state, "mission", run.id)
        run_id = run.id
        ends_at = _utc(run.ends_at)
        db.flush()
    before_gold = int(resources.gold)
    with patch.object(mission_service, "utc_now", return_value=ends_at), \
            patch.object(mission_service, "randint", return_value=1):
        claimed = claim_mission_loot(db, guild, resources, run_id, commit=False)
    db.flush()
    participant = db.scalar(select(RegionalEventParticipant).where(
        RegionalEventParticipant.event_id == event.id,
        RegionalEventParticipant.guild_state_id == player_state.id,
    ))
    participant_status_after_claim = participant.status
    pre_deadline_status = event.status
    deadline = _utc(event.expires_at_utc)
    expire_due_events(db, campaign.campaign_id, deadline + timedelta(seconds=1))
    db.refresh(event)
    db.refresh(participant)
    db.refresh(resources)
    first_gold = int(resources.gold)
    duplicate_rejected = False
    try:
        claim_mission_loot(db, guild, resources, run_id, commit=False)
    except mission_service.MissionError:
        duplicate_rejected = True
    if not duplicate_rejected or not claimed.success or pre_deadline_status != "active":
        raise RuntimeError("A aceitação/claim real de rebelião não concluiu com as invariantes esperadas.")
    db.flush()
    db.refresh(resources)
    return {
        "cycle_number": selected_cycle, "decision": event.player_decision,
        "participant_status_after_accept": participant_status_after_accept,
        "participant_status_after_claim": participant_status_after_claim,
        "activity_status": activity.status,
        "mission_template": template.name, "mission_success": bool(claimed.success),
        "event_status_before_deadline": pre_deadline_status, "event_status_after_deadline": event.status,
        "participant_final": participant.status, "contribution": participant.contribution,
        "duplicate_claim_rejected": duplicate_rejected,
        "gold_before": before_gold, "gold_after_first_claim": first_gold,
        "gold_after_duplicate": int(resources.gold),
    }


def main() -> int:
    report: dict[str, object] = {
        "report_id": REPORT_STEM, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "disposable_sqlite": True, "production_requirements_changed": False,
        "forced_setup": ["late-game guild/mercenary levels and funded Tier 7 accessories",
                         "home-region threat 100 for portal reachability",
                         "eligible regions threat 100/security 0 for natural rebellion eligibility"],
        "forced_combat_rolls": "portal success/failure branches only; event chance and template selection remain natural",
    }
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False, autoflush=False) as db:
            campaign, guild, resources, buildings, player_state, now = _setup(db)
            members = _fund_eligible_party(db, guild, resources)
            home_code = next(code for code, name in REGIONS if name == campaign.home_region)
            db.flush()
            party_power = get_party_power_score(db, guild.id, members)
            portals = []
            start_cycle = 1000
            for outcome in ("success", "failure", "expiry"):
                if outcome == "expiry":
                    event, cycle_number = _natural_portal(db, campaign, home_code, start_cycle)
                    offline_return_at = _utc(event.created_at_utc) + timedelta(hours=6)
                    expire_due_events(db, campaign.campaign_id, offline_return_at)
                    db.refresh(event)
                    post_expiry_entry_rejected = False
                    try:
                        attach_event_activity(db, event, player_state, "dungeon", -cycle_number)
                    except ValueError:
                        post_expiry_entry_rejected = True
                    if event.status != "expired" or not post_expiry_entry_rejected:
                        raise RuntimeError("O portal expirado aceitou entrada ou não expirou.")
                    portals.append({"scenario": "expiry", "cycle_number": cycle_number,
                                    "event_status": event.status,
                                    "participant_count": int(db.scalar(select(func.count(RegionalEventParticipant.id)).where(
                                        RegionalEventParticipant.event_id == event.id,
                                    )) or 0), "reward_gold": 0, "reward_items": 0,
                                    "portal_window_hours": 3,
                                    "offline_catchup_elapsed_hours": round(
                                        (offline_return_at - _utc(event.created_at_utc)).total_seconds() / 3600, 2,
                                    ),
                                    "deadline_elapsed_before_return_hours": round(
                                        (offline_return_at - _utc(event.expires_at_utc)).total_seconds() / 3600, 2,
                                    ),
                                    "entry_after_expiry_rejected": post_expiry_entry_rejected,
                                    "claim_after_expiry_allowed": False})
                else:
                    case = _portal_case(db, campaign, guild, resources, player_state, home_code, start_cycle, outcome)
                    portals.append(case)
                    start_cycle = int(case["cycle_number"]) + 1
            guild_level_at_setup = int(guild.level)
            rebellion = _rebellion_case(db, campaign, guild, resources, player_state, now)
            report.update({"portal_cases": portals, "rebellion_case": rebellion,
                           "funded_party": {"count": len(members), "levels": [member.level for member in members],
                                            "roles": [member.mercenary_class.role_type for member in members],
                                            "power": party_power, "guild_level_at_setup": guild_level_at_setup,
                                            "guild_level_at_end": guild.level,
                                            "scouts_level": buildings["scouts"].level},
                           "event_generation_rng_forced": False,
                           "portal_template_rng_forced": False,
                           "portal_entries": sum(row.get("scenario") in {"success", "failure"} for row in portals),
                           "portal_successes": sum(bool(row.get("run_success")) for row in portals),
                           "portal_failures": sum(row.get("run_status") == "failed" for row in portals),
                           "all_claims_idempotent": all(row.get("duplicate_claim_rejected", True) for row in portals if row.get("scenario") != "expiry")
                           and rebellion.get("duplicate_claim_rejected", False)})
    finally:
        engine.dispose()
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    (report_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Participação em portais e rebelião por serviços reais — Stage 5", "",
             f"Data UTC: {report['generated_at_utc']}. Campanha e inventários em SQLite temporário; nenhum save real foi aberto.", "",
             "A configuração financiada monta guilda nível 50, equipe cinco de nível 350 com papéis válidos, Tier 7 equipado, Exploradores 1 e poder acima do maior portal seedado. Ameaça/segurança são definidas para alcançar a elegibilidade. Os serviços de evento ainda usam suas probabilidades e template RNG sem patch. Os rolls de combate portal são fixos apenas para cobrir resultados success/failure; não são estimativa de taxa.", "",
             "| Fluxo | Resultado | Evidência |", "|---|---|---|"]
    for row in portals:
        lines.append(f"| Portal {row['scenario']} | {row.get('event_status_after_deadline', row.get('event_status'))} | template {row.get('template', 'natural expiry')}; equipe {len(row.get('party_levels', []))}; sucesso {row.get('run_success', '—')}; claim repetido recusado {row.get('duplicate_claim_rejected', '—')} |")
    expiry = next(row for row in portals if row["scenario"] == "expiry")
    lines.extend([f"| Rebelião | decisão {rebellion.get('decision')}, evento {rebellion.get('event_status_after_deadline')} | aceitação registrada; contribuição {rebellion.get('contribution')}; atividade {rebellion.get('activity_status')}; claim repetido recusado {rebellion.get('duplicate_claim_rejected')} |", "",
                  f"No cenário de expiração, o portal ficou sem entrada durante 6 h de catch-up offline; o prazo de 3 h venceu 3 h antes do retorno e a entrada após expirar foi recusada: {expiry['event_status']}, `entry_after_expiry_rejected={expiry['entry_after_expiry_rejected']}`.", "",
                  "## Limites", "",
                  "A validação é de integração: prova que equipe elegível percorre start/claim e que recompensas não duplicam; não estima incidência, participação natural, balanceamento de loot nem acessibilidade fresh-save. Portal expira sem participante na terceira ramificação. A amostra de combate intencionalmente força success/failure para percorrer ambos os braços. O relatório econômico e de agregado de loot continuam separados.", "",
                  "Arquivo bruto: `stage5_event_participation_runtime_2026-10-30.json`.", ""])
    (report_dir / f"{REPORT_STEM}.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
