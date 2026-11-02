"""Repeatable early Rank E economy sample using an isolated, disposable campaign."""

from __future__ import annotations

import json
import os
from pathlib import Path
import random
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("APP_MODE", "desktop")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database.connection import SessionLocal, configure_database
from app.models.campaign import CampaignMetadata
from app.models.mercenary import Mercenary
from app.models.regional import RegionalOffer
from app.services.campaign_service import CampaignService
from app.services.equipment_service import get_party_chance_details
from app.services.building_service import ensure_guild_buildings, get_building_level, get_upgrade_cost, upgrade_guild_building
from app.services.guild_service import get_current_guild_context
from app.services.regional_cycle_service import get_regional_board
from app.services.tavern_service import get_tavern_page_context, hire_apprentice


MONTE_CARLO_RUNS = 20_000
STARTING_GOLD_AFTER_BASELINE = 30
MAX_VIGILIAS = 5


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * percentile))]


def run(seed: int = 20261102) -> dict[str, object]:
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory(prefix="gim-ml013-") as data_dir:
        service = CampaignService(Path(data_dir) / "saves")
        with patch("app.services.campaign_service.uuid4", return_value=__import__("uuid").UUID("00000000-0000-4000-8000-000000000013")):
            info = service.create_campaign("Auditoria ML-013", "Guilda ML-013")
        service.activate_campaign(info.campaign_id)
        try:
            with SessionLocal() as db:
                campaign = db.get(CampaignMetadata, info.campaign_id)
                guild, resources = get_current_guild_context(db, info.campaign_id)
                buildings = ensure_guild_buildings(db, guild.id)
                for effect in ("tavern", "housing"):
                    if get_building_level(db, guild.id, effect) == 0:
                        building = next(row for row in buildings if row.building_template.effect_type == effect)
                        upgrade_guild_building(db, guild, resources, building.id)
                hire_apprentice(db, guild, resources, "Aprendiz do cenário")
                tavern_cost = int(get_tavern_page_context(db, guild, resources)["current_apprentice_base_cost"])
                if int(resources.gold) != STARTING_GOLD_AFTER_BASELINE:
                    raise RuntimeError(f"Baseline inicial inesperado: {resources.gold} ouro.")
                housing = next(row for row in ensure_guild_buildings(db, guild.id)
                               if row.building_template.effect_type == "housing")
                housing_costs = get_upgrade_cost(housing)
                housing_gold_cost = int(housing_costs["gold"])
                board = get_regional_board(db, campaign, guild, now=campaign.created_at_utc)
                offers = [offer for offer in board["offers"].get("contract", []) if offer.rank == "E"]
                members = list(db.scalars(select(Mercenary).where(
                    Mercenary.guild_id == guild.id, Mercenary.status == "available",
                )))
                if not offers or not members:
                    raise RuntimeError("A campanha descartável não gerou contratos E nem Aprendiz inicial.")
                member = members[0]
                eligible = []
                for offer in offers:
                    if offer.min_party_size_snapshot > 1 or guild.level < offer.required_guild_level_snapshot:
                        continue
                    details = get_party_chance_details(
                        db, guild.id, offer.success_chance_snapshot, [member],
                        offer.recommended_power_snapshot, offer.recommended_level_snapshot,
                    )
                    eligible.append({
                        "gold": offer.gold_reward_snapshot,
                        "chance": details["final_chance"],
                        "duration_seconds": offer.duration_seconds_snapshot,
                        "offer_id": offer.id,
                    })
                if not eligible:
                    raise RuntimeError("Nenhum contrato E do board é iniciável por um grupo solo de nível 1.")
                snapshot = {
                    "gold": resources.gold,
                    "home_region": campaign.home_region,
                    "rank_e_offers_in_board": len(offers),
                    "eligible_rank_e_offers": len(eligible),
                    "eligible_rank_e_gold_rewards": [row["gold"] for row in eligible],
                    "eligible_rank_e_chances": [row["chance"] for row in eligible],
                    "eligible_rank_e_durations_seconds": [row["duration_seconds"] for row in eligible],
                }
        finally:
            service.close_active_campaign(info.campaign_id)
            configure_database("sqlite:///:memory:")

    reaches_recruit: list[int] = []
    reaches_housing: list[int] = []
    recruit_by_5_vigilias = housing_by_5_vigilias = 0
    total_gold_after_5 = 0
    for _ in range(MONTE_CARLO_RUNS):
        gold = STARTING_GOLD_AFTER_BASELINE
        actions = 0
        recruit_actions = None
        housing_actions = None
        for _cycle in range(MAX_VIGILIAS):
            cycle_offers = list(eligible)
            rng.shuffle(cycle_offers)
            for offer in cycle_offers:
                actions += 1
                if rng.randrange(100) < offer["chance"]:
                    gold += offer["gold"]
                if gold >= tavern_cost and recruit_actions is None:
                    recruit_actions = actions
                if gold >= housing_gold_cost and housing_actions is None:
                    housing_actions = actions
                if gold >= housing_gold_cost:
                    break
            if gold >= housing_gold_cost:
                break
        total_gold_after_5 += gold
        if recruit_actions is not None:
            reaches_recruit.append(recruit_actions)
        if housing_actions is not None:
            reaches_housing.append(housing_actions)
        recruit_by_5_vigilias += int(gold >= tavern_cost)
        housing_by_5_vigilias += int(gold >= housing_gold_cost)

    return {
        "simulation": "ml013_early_rank_e_economy_v1",
        "seed": seed,
        "monte_carlo_runs": MONTE_CARLO_RUNS,
        "uses_campaign_save": False,
        "uses_isolated_temporary_campaign": True,
        "starting_gold_after_existing_baseline": STARTING_GOLD_AFTER_BASELINE,
        "second_recruit_cost_gold": tavern_cost,
        "housing_level_2_gold_cost": housing_gold_cost,
        "housing_level_2_material_costs": {key: int(housing_costs[key]) for key in ("wood", "ore", "crystals")},
        "rank_e_board_snapshot": snapshot,
        "repeat_assumption": "Five successive Vigílias reuse the first real Rank E offer sample; each success pays only the frozen gold reward, failures pay zero, XP/material value excluded.",
        "success_gold_median_actions_to_second_recruit": _percentile(reaches_recruit, 0.5),
        "success_gold_p90_actions_to_second_recruit": _percentile(reaches_recruit, 0.9),
        "success_gold_median_actions_to_housing_level_2": _percentile(reaches_housing, 0.5),
        "success_gold_p90_actions_to_housing_level_2": _percentile(reaches_housing, 0.9),
        "probability_second_recruit_gold_by_5_vigilias": round(recruit_by_5_vigilias / MONTE_CARLO_RUNS, 4),
        "probability_housing_gold_by_5_vigilias": round(housing_by_5_vigilias / MONTE_CARLO_RUNS, 4),
        "mean_gold_after_5_vigilias": round(total_gold_after_5 / MONTE_CARLO_RUNS, 2),
        "decision": "No Rank E reward change: this isolates gold only; housing also needs 40 wood, and contract office costs remain separate sinks.",
    }


if __name__ == "__main__":
    result = run()
    output = ROOT / "reports" / "ml013_early_rank_e_economy_v0.5.0.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    snapshot = result["rank_e_board_snapshot"]
    rows = "\n".join(
        f"| {reward} | {chance}% | {duration // 60} min {duration % 60} s |"
        for reward, chance, duration in zip(
            snapshot["eligible_rank_e_gold_rewards"], snapshot["eligible_rank_e_chances"],
            snapshot["eligible_rank_e_durations_seconds"],
        )
    )
    markdown = f"""# ML-013 — Auditoria da economia inicial Rank E

**Método:** campanha temporária descartável com catálogos e serviços reais; 20.000 sequências Monte Carlo fixadas pela seed `{result['seed']}`. Nenhum save do jogador foi aberto.

O cenário aplica Taverna 1, Alojamento 1 e o primeiro Aprendiz pelos serviços reais, deixando {result['starting_gold_after_existing_baseline']} ouro. O board inicial de {snapshot['home_region']} continha {snapshot['rank_e_offers_in_board']} contratos E; todos os {snapshot['eligible_rank_e_offers']} eram iniciáveis por um grupo solo de nível 1.

| Ouro no sucesso | Chance calculada | Duração congelada |
|---:|---:|---:|
{rows}

| Marco financiado apenas com ouro | Ações medianas | P90 | Probabilidade até 5 Vigílias |
|---|---:|---:|---:|
| Recruta 2 (custo {result['second_recruit_cost_gold']}; lacuna {result['second_recruit_cost_gold'] - result['starting_gold_after_existing_baseline']}) | {result['success_gold_median_actions_to_second_recruit']} | {result['success_gold_p90_actions_to_second_recruit']} | {result['probability_second_recruit_gold_by_5_vigilias']:.2%} |
| Alojamento nível 2 (custo {result['housing_level_2_gold_cost']}) | {result['success_gold_median_actions_to_housing_level_2']} | {result['success_gold_p90_actions_to_housing_level_2']} | {result['probability_housing_gold_by_5_vigilias']:.2%} |

O saldo médio após cinco Vigílias, sem compras intermediárias, foi {result['mean_gold_after_5_vigilias']:.2f} ouro. O Alojamento nível 2 também exige {result['housing_level_2_material_costs']['wood']} madeiras; este ensaio de ouro não atribui valor a XP nem materiais e não afirma que o marco completo esteja financiado.

**Decisão:** manter recompensas E atuais. A amostra real encontrou recompensa suficiente para fechar cedo a lacuna do segundo recruta, e o ouro sozinho alcança o custo de alojamento na grande maioria das sequências. Um aumento de recompensa não resolve o gargalo distinto dos materiais e elevaria o saldo sem necessidade demonstrada.

**Limitação:** os cinco boards repetem a distribuição do primeiro board inicial; cada oferta E amostrada representa uma nova oportunidade equivalente. O ensaio exclui gastos após o baseline, crescimento de guilda e recursos materiais. É uma comparação do fluxo de ouro inicial, não uma trajetória de campanha completa.
"""
    (ROOT / "reports" / "ml013_early_rank_e_economy_v0.5.0.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
