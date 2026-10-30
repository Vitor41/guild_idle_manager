"""Reproducible Stage 5 fresh-save funding audit.

Run from the repository root with:
    $env:APP_MODE = "desktop"
    .venv-desktop\\Scripts\\python.exe scripts\\balance\\audit_fresh_save_economy.py

The audit creates one disposable, temporary SQLite campaign and never opens the
user's save directory. It reports startup affordability and separately samples
regional boards with varied campaign seeds. It does not implement new balance
rules or recurring sinks.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from uuid import uuid5, NAMESPACE_URL

os.environ["APP_MODE"] = "desktop"

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, configure_database, get_engine, SessionLocal, create_database_engine
from app.models.building import GuildBuilding
from app.models.campaign import CampaignMetadata
from app.models.guild import Guild, GuildResources
from app.models.mercenary import Mercenary
from app.models.tavern import GuildTavernState
from app.seeds.campaign_content import apply_initial_campaign_content
from app.seeds.massive_content import PACK_VERSION
from app.services.building_service import (
    BuildingError,
    ensure_guild_buildings,
    get_upgrade_cost,
    upgrade_guild_building,
)
from app.services.campaign_service import CampaignService
from app.services.mercenary_service import dismiss_mercenary
from app.services.tavern_service import (
    generate_apprentice_preview,
    get_or_create_tavern_config,
    hire_apprentice,
)
from scripts.balance.simulate_guild_progression_profiles import (
    PROFILES,
    Profile,
    REGIONS,
    _build_profile_catalog,
    _create_abstract_roster,
    _profile_investment_policy,
    _simulate_regional_progression,
    _sample_real_home_board,
)

REPORT_JSON = ROOT / "reports" / "fresh_save_economy_audit_2026-10-29.json"
REPORT_MD = ROOT / "reports" / "fresh_save_economy_audit_2026-10-29.md"
BOARD_CHECKPOINTS = (1, 10, 20, 30, 40, 50)
BOARD_SEEDS_PER_CELL = 25
POLICY_TRAJECTORIES_PER_PROFILE = 50
STRESS_TRAJECTORIES_PER_PROFILE = 10
ECONOMIC_CONCLUSION_REASON = (
    "A separate funded trajectory now purchases a stated roster/building progression, resumes seeded regional earnings "
    "when cash is insufficient, collects materials under the current capacity and offline limits, and reports balances. "
    "It covers the five GDD profiles with 100 seeds each and Wilson/bootstrap intervals, under unapproved login, roster, and purchase-priority assumptions; "
    "it omits RNG recruitment, item drops/sales, and wider optional sinks. Its no-softlock result is narrowly defined "
    "as a 14-day no-route stall in the finite purchase path; whole-game hard economic softlock remains not measured. "
    "The model reports positive late-game "
    "surplus after its finite purchase plan, so it does not establish GDD-wide solvency, dominant activity across all "
    "content, or absence of infinite economy. Stage 5 remains open."
)
PROGRESSION_BOARD_POOL_SIZE = 10


def _dist(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "min": 0, "p50": 0, "mean": 0, "max": 0}
    return {
        "n": len(ordered),
        "min": round(ordered[0], 2),
        "p50": round(ordered[(len(ordered) - 1) // 2], 2),
        "mean": round(mean(ordered), 2),
        "max": round(ordered[-1], 2),
    }


def affordability(balance: dict[str, int], cost: dict[str, int]) -> dict[str, object]:
    resources = ("gold", "wood", "ore", "crystals")
    shortfalls = {key: max(0, int(cost.get(key, 0)) - int(balance.get(key, 0))) for key in resources}
    return {"affordable": not any(shortfalls.values()), "shortfalls": shortfalls,
            "balance_after_if_paid": {key: int(balance.get(key, 0)) - int(cost.get(key, 0)) for key in resources}}


def _funded_followup_summary() -> dict[str, object] | None:
    path = ROOT / "reports" / "funded_upgrade_trajectories_2026-10-29.json"
    if not path.is_file():
        return None
    funded = json.loads(path.read_text(encoding="utf-8"))
    return {
        "report_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "report_id": funded.get("report_id"),
        "source": funded.get("source"),
        "runs_per_strategy": funded.get("runs_per_strategy"),
        "strategies": funded.get("strategies"),
        "stage5_economy_accepted": False,
        "remaining_design_choices": funded.get("rules", {}).get("design_choices_left_open", []),
    }


def _fresh_save_service_smoke() -> dict[str, object]:
    """Create and exercise a real new campaign in a disposable SQLite folder."""
    with TemporaryDirectory(prefix="gim-stage5-economy-") as temp_dir:
        saves_dir = Path(temp_dir) / "saves"
        info = CampaignService(saves_dir).create_campaign("Estudo econômico", "Guilda temporária")
        engine = create_database_engine(f"sqlite:///{info.database_path.as_posix()}")
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with factory() as db:
                guild = db.scalar(select(Guild).where(Guild.campaign_id == info.campaign_id))
                resources = db.scalar(select(GuildResources).where(GuildResources.guild_id == guild.id))
                assert guild is not None and resources is not None
                buildings = ensure_guild_buildings(db, guild.id)
                by_type = {row.building_template.effect_type: row for row in buildings}
                start = {"gold": resources.gold, "wood": resources.wood, "ore": resources.ore, "crystals": resources.crystals}
                first_actions = []
                for building_type in ("tavern", "housing"):
                    building = by_type[building_type]
                    cost = get_upgrade_cost(building)
                    upgrade_guild_building(db, guild, resources, building.id)
                    first_actions.append({"action": f"upgrade_{building_type}_to_1", "cost": cost,
                                          "balance": {"gold": resources.gold, "wood": resources.wood, "ore": resources.ore}})
                config = get_or_create_tavern_config(db)
                hire_apprentice(db, guild, resources, "Aprendiz de estudo",
                                generate_apprentice_preview(config, tavern_level=1))
                first_actions.append({"action": "hire_first_apprentice", "cost": 50,
                                      "balance": {"gold": resources.gold, "wood": resources.wood, "ore": resources.ore}})
                office = by_type["contract_office"]
                office_cost = get_upgrade_cost(office)
                office_affordability = affordability(
                    {"gold": resources.gold, "wood": resources.wood, "ore": resources.ore,
                     "crystals": resources.crystals}, office_cost)
                try:
                    upgrade_guild_building(db, guild, resources, office.id)
                    office_action = {"affordable_after_minimum_start": True, "cost": office_cost}
                except BuildingError:
                    office_action = {"affordable_after_minimum_start": False, "cost": office_cost,
                                     "shortfalls": office_affordability["shortfalls"]}
                first_mercenary = db.scalar(select(Mercenary).where(Mercenary.guild_id == guild.id))
                dismissal_refund = dismiss_mercenary(db, guild, resources, first_mercenary.id)
                return {
                    "save_path_was_temporary": str(info.database_path).startswith(temp_dir),
                    "starting_balance": start,
                    "actions": first_actions,
                    "balance_after_minimum_start": {"gold": resources.gold, "wood": resources.wood, "ore": resources.ore},
                    "contract_office_level_1": office_action,
                    "dismiss_first_apprentice_refund": dismissal_refund,
                    "balance_after_dismissal": {"gold": resources.gold, "wood": resources.wood, "ore": resources.ore},
                    "first_hire_net_gold_cost_if_dismissed_immediately": 50 - dismissal_refund,
                    "two_person_group_upgrade_costs": _incremental_two_person_costs(db, by_type),
                    "fresh_campaign_created_by_campaign_service": True,
                    "campaign_id_redacted": True,
                    "service_affordability_check_agreed_with_balance_check": office_affordability["affordable"] is False,
                }
        finally:
            engine.dispose()


def _incremental_two_person_costs(db, buildings: dict[str, GuildBuilding]) -> dict[str, object]:
    housing = buildings["housing"]
    office = buildings["contract_office"]
    # Read each next-level quote through the same service used by the UI. The
    # temporary level changes are not committed and this disposable save is
    # deleted as soon as the audit finishes.
    housing_second = get_upgrade_cost(housing)
    office_next = get_upgrade_cost(office)
    tavern_state = db.scalar(select(GuildTavernState).order_by(GuildTavernState.id).limit(1))
    second_hire = int(tavern_state.current_apprentice_hire_cost) if tavern_state else 53
    no_income_steps = []
    projected = {"gold": 30, "wood": 0, "ore": 0, "crystals": 0}
    for label, cost in (
        ("second_apprentice", {"gold": second_hire, "wood": 0, "ore": 0, "crystals": 0}),
        ("housing_level_2", housing_second),
        ("contract_office_level_1", office_next),
    ):
        result = affordability(projected, cost)
        projected = result["balance_after_if_paid"]
        no_income_steps.append({"milestone": label, "cost": cost, "affordable_at_that_balance": result["affordable"],
                               "shortfalls_at_that_balance": result["shortfalls"], "projected_balance_if_paid": projected})
    return {
        "second_apprentice_cost_from_seeded_tavern_config": second_hire,
        "housing_level_2_cost": housing_second,
        "contract_office_level_1_cost": office_next,
        "combined_gold_after_first_apprentice": second_hire + housing_second["gold"] + office_next["gold"],
        "combined_materials_after_first_apprentice": {
            "wood": housing_second["wood"] + office_next["wood"],
            "ore": housing_second["ore"] + office_next["ore"],
            "crystals": housing_second["crystals"] + office_next["crystals"],
        },
        "projected_balance_without_intervening_income_after_expansion": {
            "gold": 30 - second_hire - housing_second["gold"] - office_next["gold"],
            "wood": -(housing_second["wood"] + office_next["wood"]),
            "ore": -(housing_second["ore"] + office_next["ore"]),
            "crystals": -(housing_second["crystals"] + office_next["crystals"]),
        },
        "milestone_ledger_without_intervening_income": no_income_steps,
        "note": "The second hire plus housing and Office gates are a candidate path, not a mandatory policy; solo progress remains a separate possible strategy.",
    }


def _board_seed_survey(db, sample_index_base: int = 0) -> dict[str, object]:
    """Survey service-materialized boards across deterministic campaign seeds."""
    cells: dict[str, object] = {}
    for profile_index, profile in enumerate(PROFILES):
        profile_rows = {}
        catalog = _build_profile_catalog(db, profile)
        for level in BOARD_CHECKPOINTS:
            eligible_counts: list[float] = []
            weighted_gold: list[float] = []
            success_chances: list[float] = []
            for sample in range(BOARD_SEEDS_PER_CELL):
                sample_index = sample_index_base + sample
                campaign_id = str(uuid5(NAMESPACE_URL, f"stage5-board-survey:{profile.name}:{level}:{sample_index}"))
                campaign = CampaignMetadata(campaign_id=campaign_id, campaign_name="Board survey",
                                            schema_version=5, content_version=PACK_VERSION,
                                            home_region=REGIONS[0][1])
                guild = Guild(campaign_id=campaign_id, name=f"{profile.name}-{level}", level=level)
                db.add_all((campaign, guild))
                db.flush()
                roster_size = profile.slots * profile.party_size + profile.gathering_workers
                _create_abstract_roster(db, guild, profile)
                board, _, _ = _sample_real_home_board(db, campaign, guild, sample_index)
                contracts = [offer for offer in board if offer["offer_type"] == "contract"
                             and int(offer["min_party_size"]) <= min(profile.party_size, int(offer["max_party_size"]))
                             and int(offer["required_guild_level"]) <= level
                             and int(offer["required_min_mercenary_level"]) <= level]
                eligible_counts.append(float(len(contracts)))
                if contracts:
                    weighted_gold.append(mean(float(row["gold_reward"]) * float(row["success_chance_percent"]) / 100 for row in contracts))
                    success_chances.extend(float(row["success_chance_percent"]) for row in contracts)
                db.rollback()
            profile_rows[str(level)] = {
                "distinct_deterministic_campaign_seeds": BOARD_SEEDS_PER_CELL,
                "eligible_contracts_per_10_contract_board": _dist(eligible_counts),
                "mean_success_weighted_gold_per_eligible_contract": _dist(weighted_gold),
                "snapshot_success_chance_percent": _dist(success_chances),
            }
        cells[profile.name] = profile_rows
    return {
        "sampling_policy": "25 deterministic campaign ids per profile and checkpoint level; each board is materialized by regional_cycle_service using a distinct campaign seed and then rolled back from the in-memory study database.",
        "checkpoints": list(BOARD_CHECKPOINTS),
        "seeds_per_profile_checkpoint": BOARD_SEEDS_PER_CELL,
        "boards_sampled": len(PROFILES) * len(BOARD_CHECKPOINTS) * BOARD_SEEDS_PER_CELL,
        "profiles": cells,
        "limitations": "This measures board-content variation at six checkpoints, not a 1–50 cash-affordability trajectory; no strategy or spend schedule is inferred.",
    }


def _candidate_policy_runs(db) -> dict[str, object]:
    """Run a low-investment 1–50 path and a half-reward gold stress case."""
    profiles = {}
    for profile_index, original in enumerate(PROFILES):
        mode = "contract_priority" if original.name == "combate" else "mission"
        candidate = Profile(original.name, mode, original.online_hours_per_day, 1, 1, 0, "selectable")
        catalog = _build_profile_catalog(db, candidate)
        seed = 30_000_000 + profile_index * 100_000
        candidate_run = _simulate_regional_progression(
            db, candidate, catalog, seed,
            sample_runs=POLICY_TRAJECTORIES_PER_PROFILE, max_days=365,
            vary_board_seeds=True, starting_gold=100, setup_gold_override=70,
            board_seed_pool_size=PROGRESSION_BOARD_POOL_SIZE,
        )
        stress_run = _simulate_regional_progression(
            db, candidate, catalog, seed + 50_000,
            sample_runs=STRESS_TRAJECTORIES_PER_PROFILE, max_days=365,
            vary_board_seeds=True, starting_gold=100, setup_gold_override=70,
            gold_reward_multiplier=0.5,
            board_seed_pool_size=PROGRESSION_BOARD_POOL_SIZE,
        )
        profiles[original.name] = {
            "policy": _candidate_policy_description(original.name),
            "solo_no_spend_varied_boards": _candidate_run_summary(candidate_run),
            "half_mission_gold_stress_varied_boards": _candidate_run_summary(stress_run),
        }
    return {
        "trajectories_per_profile": POLICY_TRAJECTORIES_PER_PROFILE,
        "stress_trajectories_per_profile": STRESS_TRAJECTORIES_PER_PROFILE,
        "scenarios_per_profile": 2,
        "board_seeds_vary_per_trajectory": True,
        "distinct_board_seed_pools_per_profile": PROGRESSION_BOARD_POOL_SIZE,
        "seed_start": 30_000_000,
        "initial_service_path_cost_gold": 70,
        "initial_balance_after_start_gold": 30,
        "profiles": profiles,
        "limitations": [
            "The candidate sensitivity uses 50 trajectories per profile across 10 distinct deterministic board pools (five outcome seeds per board slot). The stress sensitivity uses 10 trajectories per profile and has wider bounds; neither satisfies the GDD 1,000-trajectory gate.",
            "A single mission party of one common synthetic Apprentice is held through level 50; roster RNG, equipment and recruitment stats do not affect success chance.",
            "No construction, material drops, market sales, gathering worker, Docks, supplies, crafting, refinement or mandatory recurring cost is executed in these trajectories.",
            "The producer profile is mission-first in this 1–50 control; the report separately quantifies a candidate gathering expansion threshold but cannot validate producer cashflow without simulating loot/material decisions.",
            "The stress halves mission gold only; it is a sensitivity, not an approved balance change. XP, board rules, success chances and offline passive gold are held fixed.",
        ],
    }


def _candidate_policy_description(profile_name: str) -> dict[str, object]:
    common = "Begin with the service-verified Tavern 1, Housing 1 and one Apprentice; retain the 30 gold reserve. Do not buy an upgrade unless its cost and a 100-gold reserve can be funded; buy only when it unlocks the next selected action. No recurring spending."
    by_profile = {
        "ativo": "One solo team; use all four six-hour boards within 12 online hours. Add a second solo team only after the cash/material threshold; not purchased in this run.",
        "casual": "One solo team; distribute two online hours across the day. Keep all upgrades deferred until the threshold; not purchased in this run.",
        "offline": "One solo offer before each eligible absence and use the current return-online windows; passive gold is credited by the existing eight-hour formula. Portal three-hour deadlines continue during catch-up.",
        "produtor": "Mission-first solo control until the expansion threshold, then candidate option is Housing 2 plus a second Apprentice, assign one worker to gather 40 wood before upgrade and retain a mission team. The trajectory portion does not execute that expansion or material loop.",
        "combate": "One solo team; prioritize contracts as the combat profile does today. Defer gear/buildings until the reserve rule and next-action gate; no equipment/power-specific success modifier is modeled.",
    }
    return {"common_reserve_rule": common, "profile_policy": by_profile[profile_name]}


def _candidate_run_summary(result: dict[str, object]) -> dict[str, object]:
    trajectories = result.get("trajectory_samples", [])
    checkpoint_balances = {}
    for level in (10, 20, 30, 40, 50):
        values = [float(row["cash_balance_at_level_checkpoints"][str(level)]) for row in trajectories
                  if row["cash_balance_at_level_checkpoints"].get(str(level)) is not None]
        checkpoint_balances[str(level)] = _dist(values)
    deficits = sum(any(float(balance) < 0 for balance in row["cash_balance_at_level_checkpoints"].values()
                       if balance is not None) for row in trajectories)
    reached = sum(bool(row["reached_level_50"]) for row in trajectories)
    actions = sum(int(row["actions"]) for row in trajectories)
    successes = sum(int(row["successes"]) for row in trajectories)
    return {
        "trajectories": len(trajectories),
        "level_50_reached": reached,
        "level_50_not_reached": len(trajectories) - reached,
        "level_50_reached_percent": round(100 * reached / max(1, len(trajectories)), 1),
        "level_50_wilson_95_ci_percent": result["level_50_reached_wilson_95_ci_percent"],
        "level_50_days_p10_p50_p90": result["level_50_days"],
        "action_success_rate_percent": round(100 * successes / max(1, actions), 2),
        "trajectories_with_negative_checkpoint_balance": deficits,
        "cash_balance_at_checkpoint_distribution": checkpoint_balances,
        "gross_gold_to_level_50_p10_p50_p90": result["gross_gold"],
        "cash_balance_at_level_50_p10_p50_p90": result["net_gold_after_profile_setup"],
        "board_fixture_version": "per-trajectory-campaign-seed-v1",
    }


def _legacy_progression_summary() -> dict[str, object]:
    path = ROOT / "reports" / "guild_progression_profiles_1_50.json"
    raw = path.read_bytes()
    report = json.loads(raw)
    rows = report["regional_board_progression"]
    summaries = {}
    for name, row in rows.items():
        trajectories = row.get("trajectory_samples", [])
        if trajectories:
            actions = sum(int(item.get("actions", 0)) for item in trajectories)
            successes = sum(int(item.get("successes", 0)) for item in trajectories)
            reached = sum(bool(item.get("reached_level_50")) for item in trajectories)
            n = len(trajectories)
        else:
            actions = successes = reached = 0
            n = int(row.get("trajectories", 0))
        summaries[name] = {
            "trajectories": n,
            "reached_level_50": reached,
            "modeled_level_50_non_reach": max(0, n - reached),
            "modeled_action_success_rate_percent": round(100 * successes / actions, 2) if actions else None,
            "level_50_days_p10_p50_p90": row.get("level_50_days"),
            "setup_gold": row.get("profile_setup_costs", {}).get("total_setup_gold"),
            "setup_materials": row.get("profile_setup_costs", {}).get("building_materials"),
            "net_gold_p50_after_prepay": row.get("net_gold_after_profile_setup", {}).get("p50"),
        }
    return {
        "source": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "run_id": report.get("report_run_id"),
        "board_fixture": report.get("regional_board_fixture_version"),
        "board_fixture_policy": "The prior 1,000-trajectory model reuses one materialized board per level/cycle per profile; outcome seeds vary, board content does not vary between trajectories.",
        "profiles": summaries,
    }


def _render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Auditoria de financiamento de save novo — Stage 5",
        "",
        f"**Data:** {report['generated_at_local']}  ",
        f"**Branch/HEAD:** `{report['source']['git_head']}`  ",
        f"**Script SHA-256:** `{report['source']['script_sha256']}`  ",
        "**Uso:** estudo reproduzível; não altera regras de economia nem salva dados no perfil do jogador.",
        "",
        "## Save novo e primeiros marcos (serviços reais, SQLite temporário)",
        "",
        "O save criado pelo CampaignService começa com 100 ouro e zero de madeira, minério e cristais. O serviço de construção aplicou Taverna 1 (10 ouro) e Alojamento 1 (10 ouro); o serviço da Taverna contratou o primeiro Aprendiz (50 ouro). O saldo real após a sequência ficou em **30 ouro**. A tentativa de Office de Contratos 1 não é financiável nesse saldo; sua cotação atual é **180 ouro, 20 madeira e 20 minério**. A validação ocorreu numa pasta temporária descartável.",
        "",
        "| Ação inicial | Débito de ouro | Saldo após ação |",
        "|---|---:|---:|",
    ]
    for action in report["isolated_sqlite_service_smoke"]["actions"]:
        lines.append(f"| {action['action']} | {action['cost'] if isinstance(action['cost'], int) else action['cost']['gold']} | {action['balance']['gold']} |")
    lines.extend(["", f"Demitir imediatamente esse primeiro Aprendiz devolve {report['isolated_sqlite_service_smoke']['dismiss_first_apprentice_refund']} ouro; o custo líquido irrecuperável do hire inicial é {report['isolated_sqlite_service_smoke']['first_hire_net_gold_cost_if_dismissed_immediately']} ouro. O saldo do save descartável após a demissão foi {report['isolated_sqlite_service_smoke']['balance_after_dismissal']['gold']} ouro."])
    lines.extend(["", "### Abrir grupo de duas pessoas", "",
                  "| Item da opção gradual | Ouro | Madeira | Minério |", "|---|---:|---:|---:|"])
    next_group = report["isolated_sqlite_service_smoke"]["two_person_group_upgrade_costs"]
    for label, cost_key in (("Segundo Aprendiz", None), ("Alojamento nível 2", "housing_level_2_cost"), ("Office nível 1", "contract_office_level_1_cost")):
        if cost_key is None:
            lines.append(f"| {label} | {next_group['second_apprentice_cost_from_seeded_tavern_config']} | 0 | 0 |")
        else:
            cost = next_group[cost_key]
            lines.append(f"| {label} | {cost['gold']} | {cost['wood']} | {cost['ore']} |")
    lines.extend(["", "Na coluna de saldo, valores negativos são o saldo contrafactual se se tentasse pagar sem receitas no meio; o serviço bloqueia o primeiro item que não couber. Ganhos de missões/coleta poderiam financiar uma expansão posterior, mas esta auditoria não escolhe quando gastar.",
                  "", "| Marcos sem receitas intermediárias | Saldo de ouro no início | Custo ouro / madeira / minério | Acessível? | Saldo projetado após tentativa |",
                  "|---|---:|---|---|---|"])
    for step in next_group["milestone_ledger_without_intervening_income"]:
        cost, projected = step["cost"], step["projected_balance_if_paid"]
        lines.append(f"| {step['milestone']} | {projected['gold'] + cost['gold']} | {cost['gold']} / {cost['wood']} / {cost['ore']} | {'sim' if step['affordable_at_that_balance'] else 'não'} | {projected['gold']} / {projected['wood']} / {projected['ore']} |")
    lines.extend(["", "O caminho gradual pode começar com um Aprendiz e uma equipe solo; expansão e seu momento não são regra única confirmada.",
                  "", "## Opção de elenco simultâneo completo", "",
                  "Os custos abaixo replicam o setup do simulador atual: contratar todas as vagas concorrentes, subir Alojamento e Office até liberar a composição do perfil e pagar uma vez cada construção necessária. Essa opção foi calculada a partir dos templates e fórmulas atuais. Não é recomendação de design nem sequência obrigatória.",
                  "", "| Perfil | Roster simultâneo | Setup total (ouro) | Falta sobre 100 ouro | Materiais exigidos (madeira/minério/cristal) |",
                  "|---|---:|---:|---:|---|"])
    for name, profile in report["profile_setup_scenarios"].items():
        mats = profile["building_materials"]
        lines.append(f"| {name} | {profile['roster_size']} | {profile['total_setup_gold']:,} | {profile['gold_shortfall_from_fresh_save']:,} | {mats['wood']:,} / {mats['ore']:,} / {mats['crystals']:,} |")
    lines.extend(["", "Todos os perfis desse setup estão sem financiamento no instante zero; também faltam todos os materiais listados. A projeção regional anterior não tem falha por essa razão porque desconta setup pré-pago e não simula saldos durante a jornada.",
                  "", "## Amostra de boards com seeds variadas", "",
                  f"Foram materializados {report['varied_board_seed_survey']['boards_sampled']} boards (25 seeds por perfil × nível nos níveis 1, 10, 20, 30, 40 e 50) pelo serviço regional. A tabela completa por nível está no JSON. Essa amostra varia conteúdo do board e mede contratos elegíveis e ouro ponderado pela chance de sucesso; ela não simula compras, ganhos de materiais, saldos ou escolhas de gasto.",
                  "", "| Perfil | Nível | Contratos elegíveis p50 (min–max) | Ouro médio ponderado p50 (min–max) | Chance snapshot média p50 (%) |",
                  "|---|---:|---:|---:|---:|"])
    for name, levels in report["varied_board_seed_survey"]["profiles"].items():
        for level, cell in levels.items():
            eligible = cell["eligible_contracts_per_10_contract_board"]
            gold = cell["mean_success_weighted_gold_per_eligible_contract"]
            chance = cell["snapshot_success_chance_percent"]
            lines.append(f"| {name} | {level} | {eligible['p50']} ({eligible['min']}–{eligible['max']}) | {gold['p50']} ({gold['min']}–{gold['max']}) | {chance['mean']} |")
    lines.extend(["", "## O que os dados atuais mostram", "",
                  "| Perfil | Trajetórias antigas que chegaram ao nível 50 | Taxa de sucesso de ações (modelo) | Setup descontado no nível 50 (ouro p50) |",
                  "|---|---:|---:|---:|"])
    for name, row in report["prior_progression_model"]["profiles"].items():
        lines.append(f"| {name} | {row['reached_level_50']}/{row['trajectories']} | {row['modeled_action_success_rate_percent']}% | {row['net_gold_p50_after_prepay']:,} |")
    lines.extend(["", "A taxa de sucesso e a chegada ao nível 50 vêm do modelo anterior, com board fixo, roster/poder sintético, sem financiamento, e saldo líquido calculado só após descontar o setup.",
                  "", "## Políticas candidatas 1–50 e stress de caixa", "",
                  "Cada trajetória parte do save novo, paga Taverna 1 + Alojamento 1 + um Aprendiz (70 ouro) e começa com 30 ouro. O controle otimista anterior conserva roster simultâneo pré-pago; aqui o candidato é uma única equipe solo, nenhum gasto recorrente e expansão somente quando o custo e reserva de 100 ouro couberem. Combate mantém prioridade de contratos. Offline usa a cadência atual. O produtor tem um marco candidato para expandir após caixa e coleta, mas essa expansão não entra no progresso 1–50 porque a matriz de loot/material ainda não está conectada ao simulador.",
                  "", "| Perfil | Caso | N | Nível 50 | IC Wilson 95% | Dias p10/p50/p90 | Sucesso ação | Saldo no nível 50 p10/p50/p90 | Trajetórias com checkpoint negativo |",
                  "|---|---|---:|---:|---|---|---:|---|---:|"])
    for name, scenarios in report["candidate_policy_runs"]["profiles"].items():
        for scenario_name, label in (("solo_no_spend_varied_boards", "Candidata"),
                                      ("half_mission_gold_stress_varied_boards", "Stress: 50% ouro de missão")):
            row = scenarios[scenario_name]
            days = row["level_50_days_p10_p50_p90"]
            cash = row["cash_balance_at_level_50_p10_p50_p90"]
            lines.append(f"| {name} | {label} | {row['trajectories']} | {row['level_50_reached']}/{row['trajectories']} | {row['level_50_wilson_95_ci_percent'][0]}–{row['level_50_wilson_95_ci_percent'][1]}% | {days['p10']}/{days['p50']}/{days['p90']} | {row['action_success_rate_percent']}% | {cash['p10']:,}/{cash['p50']:,}/{cash['p90']:,} | {row['trajectories_with_negative_checkpoint_balance']} |")
    lines.extend(["", "### Caixa por marco (mínimo/p50/máximo, em ouro)", "",
                  "| Perfil | Caso | Nível 10 | Nível 20 | Nível 30 | Nível 40 | Nível 50 |",
                  "|---|---|---:|---:|---:|---:|---:|"])
    for name, scenarios in report["candidate_policy_runs"]["profiles"].items():
        for scenario_name, label in (("solo_no_spend_varied_boards", "Candidata"),
                                      ("half_mission_gold_stress_varied_boards", "Stress 50% ouro de missão")):
            row = scenarios[scenario_name]
            values = []
            for level in (10, 20, 30, 40, 50):
                d = row["cash_balance_at_checkpoint_distribution"][str(level)]
                values.append(f"{d['min']:,.0f}/{d['p50']:,.0f}/{d['max']:,.0f}")
            lines.append(f"| {name} | {label} | " + " | ".join(values) + " |")
    lines.extend(["", "O saldo é calculado após apenas o investimento inicial; não há desembolso por construção/expansão nos caminhos. Portanto, checkpoint negativo mede déficit operacional sob essas regras de gasto, não acessibilidade de qualquer expansão. O stress reduz somente pagamento de ouro das missões à metade e preserva XP, chance e ouro passivo offline. O caso candidato tem N=50 por perfil em dez pools de board (cinco sementes de resultado por board) e permanece uma sensibilidade; o stress tem N=10 por perfil.",
                  "", "Regras candidatas de expansão: manter 100 ouro de reserva; não subir prédio sem liberar a ação escolhida. Para uma segunda equipe solo ou o perfil produtor com gatherer, o pacote é Alojamento 2 (200 ouro, 40 madeira) + segundo Aprendiz (53 ouro), disparado quando houver 253 ouro e 100 de reserva, além de 40 madeira. A coleta atual gera a 1 unidade/min; 40 madeira exigem cerca de 40 minutos em espaço livre. Isso não inclui gastos opcionais nem material vendido. Uma party de duas pessoas acrescenta Office 1 (180 ouro, 20 madeira e 20 minério).",
                  "", "## Dados e políticas ainda necessários para afirmar solvência", "",
                  "1. Política de contratação: full roster upfront, expansão conforme ouro/material, ou roster mínimo; quantidade de equipes simultâneas ao longo dos níveis.",
                  "2. Agenda de gastos: sequência/níveis de Alojamento e Office, e critérios para Mercado, Armazém, Docas, refino/crafting; horizonte de saldo mínimo aceitável.",
                  "3. Política do produtor: quantas horas de coleta, família atribuída, retirada/pausa por limite, quando e quanto vender no Mercado.",
                  "4. Política de uso de materiais e itens: guardar, vender, consumir em construções ou gastar em suprimento; o GDD só fixa +5pp e diz que custo deve ser simulado.",
                  "5. Política de atividade por Vigília para perfis online/offline, dado que os boards avançam a cada 6h, horas de presença não mapeiam sozinhas em quais ciclos e ofertas são escolhidos.",
                  "6. Variância de recrutamento/equipe: a simulação econômica escolhe rosters sintéticos e não aplica os atributos RNG reais às chances de vitória.",
                  "", "O candidato mostra um caminho solo com caixa não negativa porque não compra upgrades: isso prova uma rota candidata sem compra obrigatória, mas não aprova equilíbrio, metas, formação ou produção. O stress de ouro de missão também não testa softlock de expansão nem a dependência de materiais. Ainda é necessário ligar ganhos, drops e vendas reais à expansão e validar produtor com coleta/mercado. Não implementei dreno recorrente.",
                  "", "## Regras de eventos usadas como contexto", "",
                  "- Rebelião: chance inicial confirmada de 2% por Vigília elegível após ameaça ≥85 e segurança ≤25; o limite global de uma rebelião ativa reduz a ocorrência efetiva quando a janela de 12h mantém o slot ocupado.",
                  "- Portal: prazo de 3h corre durante catch-up offline; portal não iniciado expira e não paga recompensa. A auditoria de caixa não credita ganhos de portal.",
                  "- Ouro passivo segue a fórmula atual e teto de 8h; não há materiais de madeira/minério no offline. Nenhuma dessas regras substitui uma política econômica de gastos.",
                  "", "## Stage 5", "",
                  "**Evidenciado:** saldo de save novo e primeiro setup executados por serviços reais em SQLite descartável; opções de setup completo recalculadas; 750 boards variados; caminho candidato anterior; e auditoria complementar financiada com 100 trajetórias por perfil GDD, IC Wilson para taxas, bootstrap para medianas, compras com cotações dos serviços, coleta limitada por capacidade, renda regional/passiva e ledger diário em [relatório de trajetórias financiadas](funded_upgrade_trajectories_2026-10-29.md). Os cinco perfis chegaram ao nível 50 e concluíram o plano finito em 100/100 trajetórias (IC95% Wilson 96,3%–100%).",
                  "**Pendente:** as prioridades e metas de roster usadas no complemento são hipóteses, não regras aprovadas. Não houve stall sem rota de 14 dias em 100 seeds por perfil (limite superior Wilson 3,7%), mas hard softlock econômico do jogo continua não mensurado: as rotas de missão, loot/venda e expansão real estão incompletas. O produtor pausou a coleta por Armazém cheio em 100/100 trajetórias. Equipamento, primeira masmorra e primeiro evento não são modelados. O saldo voltou a crescer após as compras previstas; sem um ralo recorrente aprovado, o critério ‘sem economia infinita’ não foi demonstrado. Também faltam execução desktop e estudo de eventos raros com amostra dimensionada para o limite de risco desejado. Stage 5 permanece aberto.",
                  "", "## Reproduzir", "",
                  "```powershell", "$env:APP_MODE = 'desktop'", ".venv\\Scripts\\python.exe scripts\\balance\\audit_fresh_save_economy.py", "```", "",
                  f"Fonte regional anterior: `{report['prior_progression_model']['source']}` SHA-256 `{report['prior_progression_model']['sha256']}`.",
                  f"Catálogo ativo: `{report['source']['catalog_version']}`. Seeds variados: `{BOARD_SEEDS_PER_CELL}` por célula."])
    return "\n".join(lines) + "\n"


def run() -> dict[str, object]:
    configure_database("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    with SessionLocal() as db:
        apply_initial_campaign_content(db)
        db.commit()
        legacy = _legacy_progression_summary()
        setup_scenarios = {}
        for profile in PROFILES:
            catalog = _build_profile_catalog(db, profile)
            setup = _profile_investment_policy(db, profile, catalog)
            setup_scenarios[profile.name] = {
                "roster_size": setup["roster_size"],
                "total_setup_gold": setup["total_setup_gold"],
                "gold_shortfall_from_fresh_save": max(0, int(setup["total_setup_gold"]) - 100),
                "building_gold": setup["building_gold"],
                "hire_gold": setup["hire_gold"],
                "building_materials": setup["building_materials"],
                "building_costs": setup["building_costs"],
                "hire_costs": setup["hire_costs"],
            }
        board_survey = _board_seed_survey(db)
        candidate_runs = _candidate_policy_runs(db)
    source_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    script_bytes = Path(__file__).read_bytes()
    report = {
        "report_id": "gim-fresh-save-economy-20261029",
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "git_head": source_head,
            "worktree_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()),
            "script_sha256": hashlib.sha256(script_bytes).hexdigest(),
            "simulator_sha256": hashlib.sha256((ROOT / "scripts/balance/simulate_guild_progression_profiles.py").read_bytes()).hexdigest(),
            "catalog_version": PACK_VERSION,
        },
        "policy_decisions": {
            "rebellion_chance_per_eligible_vigil": 0.02,
            "rebellion_eligibility": {"threat_min": 85, "security_max": 25},
            "portal_deadline_advances_offline": True,
            "portal_start_deadline_hours": 3,
            "offline_passive_gold_cap_hours": 8,
        },
        "isolated_sqlite_service_smoke": _fresh_save_service_smoke(),
        "profile_setup_scenarios": setup_scenarios,
        "varied_board_seed_survey": board_survey,
        "candidate_policy_runs": candidate_runs,
        "prior_progression_model": legacy,
        "economic_conclusion": {
            "unique_1_50_financing_baseline_defensible": False,
            "full_simultaneous_setup_profiles_unaffordable_at_fresh_save": len(setup_scenarios),
            "gradual_one_apprentice_start_financed_by_actual_services": True,
            "gradual_path_economic_softlock_rate": None,
            "reason": ECONOMIC_CONCLUSION_REASON,
            "stage5_economy_accepted": False,
        },
        "funded_purchase_trajectory_follow_up": _funded_followup_summary(),
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    print(f"Reports saved: {REPORT_JSON} and {REPORT_MD}")
    print(f"Isolated starting balance: {report['isolated_sqlite_service_smoke']['starting_balance']}")
    print(f"Varied regional boards: {board_survey['boards_sampled']}")
    print(f"Candidate economy trajectories: {len(PROFILES) * (POLICY_TRAJECTORIES_PER_PROFILE + STRESS_TRAJECTORIES_PER_PROFILE)}")
    return report


def refresh_service_evidence_and_render() -> dict[str, object]:
    """Refresh the quick SQLite evidence and render saved deterministic runs."""
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    report["generated_at_local"] = datetime.now().astimezone().isoformat(timespec="seconds")
    report["source"]["git_head"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    report["source"]["worktree_dirty"] = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip())
    report["source"]["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["source"]["simulator_sha256"] = hashlib.sha256(
        (ROOT / "scripts/balance/simulate_guild_progression_profiles.py").read_bytes()
    ).hexdigest()
    report["economic_conclusion"]["reason"] = ECONOMIC_CONCLUSION_REASON
    report["funded_purchase_trajectory_follow_up"] = _funded_followup_summary()
    report["isolated_sqlite_service_smoke"] = _fresh_save_service_smoke()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    print(f"Service evidence refreshed; reports saved: {REPORT_JSON} and {REPORT_MD}")
    return report


if __name__ == "__main__":
    if "--refresh-report" in sys.argv:
        refresh_service_evidence_and_render()
    else:
        run()
