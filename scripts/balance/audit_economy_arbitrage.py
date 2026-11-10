"""Reproducibly scan seeded Dock/Market/salvage/crafting loops for positive EV."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, create_database_engine
from app.models.dock import MerchantOfferTemplate
from app.models.crafting import CraftingRecipe, CraftingRecipeMaterial
from app.models.item import ItemTemplate
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services.building_balance_service import market_values
from app.services.economy_pricing_service import (
    effective_crafting_gold_cost, effective_dock_unit_price,
    effective_equipment_dock_unit_price, market_sale_unit_value,
)
from app.services.crafting_service import _effective_recipe_gold_cost
from app.services.salvage_service import SALVAGE_SLOT_RULES, _select_salvage_material


def audit(db: Session) -> dict[str, object]:
    maximum_bonus = market_values(100)["value_bonus_percent"]
    offers = list(db.scalars(select(MerchantOfferTemplate).options(
        joinedload(MerchantOfferTemplate.item_template),
    ).where(MerchantOfferTemplate.is_active.is_(True))))
    def effective_offer_price(offer: MerchantOfferTemplate) -> int:
        item = offer.item_template
        if item.item_type == "equipment":
            material = _select_salvage_material(db, item)
            return effective_equipment_dock_unit_price(
                offer.base_price, item.base_sell_value, material.base_sell_value,
            )
        return effective_dock_unit_price(offer.base_price, item.base_sell_value)

    direct_rows = []
    for offer in offers:
        item = offer.item_template
        price = effective_offer_price(offer)
        resale = market_sale_unit_value(item.base_sell_value, maximum_bonus)
        direct_rows.append({
            "offer_id": offer.id, "item": item.name, "item_type": item.item_type,
            "item_level": int(item.item_level), "level_band": item.level_band, "rarity": item.rarity,
            "configured_price": int(offer.base_price), "effective_dock_price": price,
            "legacy_effective_dock_price": effective_dock_unit_price(offer.base_price, item.base_sell_value),
            "max_market_resale": resale, "net_gold_per_unit": resale - price,
            "stock_range": [int(offer.min_stock), int(offer.max_stock)],
            "dock_level_required": int(offer.min_dock_level),
        })

    equipment = list(db.scalars(select(ItemTemplate).where(
        ItemTemplate.is_active.is_(True), ItemTemplate.item_type == "equipment",
    ).order_by(ItemTemplate.id)))
    equipment_dock_prices: dict[int, int] = {}
    legacy_equipment_dock_prices: dict[int, int] = {}
    for offer in offers:
        item = offer.item_template
        if item.item_type != "equipment":
            continue
        price = effective_offer_price(offer)
        equipment_dock_prices[item.id] = min(price, equipment_dock_prices.get(item.id, price))
        legacy_price = effective_dock_unit_price(offer.base_price, item.base_sell_value)
        legacy_equipment_dock_prices[item.id] = min(
            legacy_price, legacy_equipment_dock_prices.get(item.id, legacy_price),
        )
    salvage_rows = []
    for item in equipment:
        if item.id not in equipment_dock_prices:
            continue
        material = _select_salvage_material(db, item)
        dock_cost = equipment_dock_prices[item.id]
        per_item_payout = market_sale_unit_value(material.base_sell_value, maximum_bonus)
        outcomes = [
            {"yield": units, "payout": units * per_item_payout,
             "net_gold": units * per_item_payout - dock_cost - 50}
            for units in (1, 2, 3)
        ]
        legacy_outcomes = [
            {"yield": units, "net_gold": units * per_item_payout - legacy_equipment_dock_prices[item.id] - 50}
            for units in (1, 2, 3)
        ]
        salvage_rows.append({
            "equipment": item.name, "equipment_rarity": item.rarity,
            "equipment_level_band": item.level_band, "equipment_tier": int(item.tier),
            "equipment_item_level": int(item.item_level),
            "equipment_dock_cost": dock_cost, "material": material.name,
            "material_tier": int(material.tier), "material_item_level": int(material.item_level),
            "material_family": material.material_family,
            "material_unit_market_value": per_item_payout,
            "salvage_fee_minimum": 50,
            "legacy_equipment_dock_cost": legacy_equipment_dock_prices[item.id],
            "legacy_expected_net_gold": sum(row["net_gold"] for row in legacy_outcomes) / 3,
            "legacy_best_rng_net_gold": max(row["net_gold"] for row in legacy_outcomes),
            "expected_net_gold": sum(row["net_gold"] for row in outcomes) / 3,
            "rng_outcomes": outcomes,
        })

    cheapest_dock_material: dict[int, int] = {}
    for offer in offers:
        if offer.item_template.item_type != "material":
            continue
        item_id = int(offer.item_template_id)
        price = effective_dock_unit_price(offer.base_price, offer.item_template.base_sell_value)
        cheapest_dock_material[item_id] = min(price, cheapest_dock_material.get(item_id, price))
    cheapest_material_acquisition: dict[int, tuple[float, str]] = {
        item_id: (float(price), "Docas") for item_id, price in cheapest_dock_material.items()
    }
    legacy_material_acquisition = dict(cheapest_material_acquisition)
    for item in equipment:
        if item.id not in equipment_dock_prices:
            continue
        material = _select_salvage_material(db, item)
        expected_cost = (equipment_dock_prices[item.id] + 50) / 2
        previous = cheapest_material_acquisition.get(material.id)
        if previous is None or expected_cost < previous[0]:
            cheapest_material_acquisition[material.id] = (expected_cost, f"desmontagem de {item.name}")
        legacy_cost = (legacy_equipment_dock_prices[item.id] + 50) / 2
        legacy_previous = legacy_material_acquisition.get(material.id)
        if legacy_previous is None or legacy_cost < legacy_previous[0]:
            legacy_material_acquisition[material.id] = (legacy_cost, f"desmontagem de {item.name}")
    recipes = list(db.scalars(select(CraftingRecipe).options(
        joinedload(CraftingRecipe.output_item_template),
        selectinload(CraftingRecipe.materials).joinedload(CraftingRecipeMaterial.item_template),
    ).where(CraftingRecipe.is_active.is_(True))))
    crafting_rows = []
    crafted_equipment_salvage_rows = []
    for recipe in recipes:
        unavailable = [material for material in recipe.materials
                       if int(material.item_template_id) not in cheapest_material_acquisition]
        material_acquisition = [{
            "material": material.item_template.name,
            "quantity": int(material.quantity),
            "unit_cost_expected": cheapest_material_acquisition.get(
                int(material.item_template_id), (0, "indisponível")
            )[0],
            "source": cheapest_material_acquisition.get(
                int(material.item_template_id), (0, "indisponível")
            )[1],
        } for material in recipe.materials]
        inputs_gold = sum(
            cheapest_material_acquisition[int(material.item_template_id)][0] * int(material.quantity)
            for material in recipe.materials if int(material.item_template_id) in cheapest_material_acquisition
        )
        legacy_inputs_gold = sum(
            legacy_material_acquisition[int(material.item_template_id)][0] * int(material.quantity)
            for material in recipe.materials if int(material.item_template_id) in legacy_material_acquisition
        )
        output = recipe.output_item_template
        sale_gold = market_sale_unit_value(output.base_sell_value, maximum_bonus) * int(recipe.output_quantity)
        effective_gold_cost = _effective_recipe_gold_cost(db, recipe, docks_level=100)
        legacy_gold_cost = effective_crafting_gold_cost(
            recipe.gold_cost, output.base_sell_value, recipe.output_quantity, legacy_inputs_gold,
        )
        crafting_rows.append({
            "recipe_id": recipe.id, "recipe": recipe.name,
            "output": output.name, "output_item_level": int(output.item_level),
            "output_level_band": output.level_band, "output_rarity": output.rarity,
            "output_quantity": int(recipe.output_quantity),
            "output_base_sell_value": int(output.base_sell_value),
            "market_sale_total": sale_gold, "dock_material_cost": inputs_gold,
            "configured_craft_gold_cost": int(recipe.gold_cost),
            "effective_craft_gold_cost": effective_gold_cost,
            "configured_net_gold": sale_gold - inputs_gold - int(recipe.gold_cost),
            "net_gold": sale_gold - inputs_gold - effective_gold_cost,
            "legacy_dock_material_cost": legacy_inputs_gold,
            "legacy_effective_craft_gold_cost": legacy_gold_cost,
            "legacy_net_gold": sale_gold - legacy_inputs_gold - legacy_gold_cost,
            "material_acquisition": material_acquisition,
            "materials_unavailable_from_docks_or_salvage": [material.item_template.name for material in unavailable],
            "required_blacksmith_level": int(recipe.required_blacksmith_level),
        })
        if output.item_type == "equipment" and not unavailable:
            salvage_material = _select_salvage_material(db, output)
            material_unit_sale = market_sale_unit_value(salvage_material.base_sell_value, maximum_bonus)
            outcomes = []
            legacy_total_yields = {0: 1}
            for _ in range(int(recipe.output_quantity)):
                next_yields: dict[int, int] = {}
                for current_yield, frequency in legacy_total_yields.items():
                    for salvage_yield in (1, 2, 3):
                        next_yields[current_yield + salvage_yield] = (
                            next_yields.get(current_yield + salvage_yield, 0) + frequency
                        )
                legacy_total_yields = next_yields
            legacy_salvage_nets = [
                total_yield * material_unit_sale - legacy_inputs_gold - legacy_gold_cost
                - 50 * int(recipe.output_quantity)
                for total_yield in legacy_total_yields
            ]
            legacy_expected_net = sum(
                total_yield * material_unit_sale - legacy_inputs_gold - legacy_gold_cost
                - 50 * int(recipe.output_quantity)
                for total_yield, frequency in legacy_total_yields.items()
            ) / (3 ** int(recipe.output_quantity))
            # Each crafted item rolls an exact 1/2/3 salvage yield. Convolve
            # the finite outcomes instead of treating a multi-output recipe
            # as a single expected-value item.
            total_yields = {0: 1}
            for _ in range(int(recipe.output_quantity)):
                next_yields: dict[int, int] = {}
                for current_yield, frequency in total_yields.items():
                    for salvage_yield in (1, 2, 3):
                        next_yields[current_yield + salvage_yield] = (
                            next_yields.get(current_yield + salvage_yield, 0) + frequency
                        )
                total_yields = next_yields
            for total_yield, frequency in sorted(total_yields.items()):
                payout = total_yield * material_unit_sale
                net_gold = payout - inputs_gold - effective_gold_cost - 50 * int(recipe.output_quantity)
                outcomes.append({
                    "total_material_yield": total_yield,
                    "frequency": frequency,
                    "probability": frequency / (3 ** int(recipe.output_quantity)),
                    "market_payout": payout,
                    "net_gold": net_gold,
                })
            expected_net = sum(row["net_gold"] * row["probability"] for row in outcomes)
            crafted_equipment_salvage_rows.append({
                "recipe_id": recipe.id,
                "recipe": recipe.name,
                "crafted_equipment": output.name,
                "output_quantity": int(recipe.output_quantity),
                "salvaged_material": salvage_material.name,
                "material_unit_market_value": material_unit_sale,
                "expected_input_material_cost": inputs_gold,
                "effective_craft_gold_cost": effective_gold_cost,
                "salvage_fee_total": 50 * int(recipe.output_quantity),
                "expected_net_gold": expected_net,
                "best_rng_net_gold": max((row["net_gold"] for row in outcomes), default=0),
                "legacy_expected_net_gold": legacy_expected_net,
                "legacy_best_rng_net_gold": max(legacy_salvage_nets, default=0),
                "rng_outcomes": outcomes,
            })

    direct_profits = [row["net_gold_per_unit"] for row in direct_rows]
    expected = [row["expected_net_gold"] for row in salvage_rows]
    max_outcomes = [max(row["net_gold"] for row in item["rng_outcomes"]) for item in salvage_rows]
    craft_profits = [row["net_gold"] for row in crafting_rows if not row["materials_unavailable_from_docks_or_salvage"]]
    crafted_salvage_ev = [row["expected_net_gold"] for row in crafted_equipment_salvage_rows]
    crafted_salvage_best = [row["best_rng_net_gold"] for row in crafted_equipment_salvage_rows]
    equipment_offer_rows = [row for row in direct_rows if row["item_type"] == "equipment"]

    def stage_examples(rows: list[dict[str, object]], level_key: str, increase_key: str) -> list[dict[str, object]]:
        ordered = sorted(rows, key=lambda row: (int(row[level_key]), str(row.get("item", row.get("output", "")))))
        if not ordered:
            return []
        indexes = {"early": 0, "mid": (len(ordered) - 1) // 2, "late": len(ordered) - 1}
        selected = [(label, ordered[index]) for label, index in indexes.items()]
        extreme = max(rows, key=lambda row: int(row[increase_key]))
        selected.append(("extreme", extreme))
        return [{"stage": stage, **row} for stage, row in selected]

    for row in equipment_offer_rows:
        row["price_increase"] = int(row["effective_dock_price"]) - int(row["legacy_effective_dock_price"])
    for row in crafting_rows:
        row["craft_price_increase"] = int(row["effective_craft_gold_cost"]) - int(row["legacy_effective_craft_gold_cost"])
    price_comparison_examples = {
        "docks_equipment": stage_examples(equipment_offer_rows, "item_level", "price_increase"),
        "crafting": stage_examples(
            [row for row in crafting_rows if not row["materials_unavailable_from_docks_or_salvage"]],
            "output_item_level", "craft_price_increase",
        ),
    }
    rarity_breakdown: dict[str, dict[str, int]] = {}
    level_band_breakdown: dict[str, dict[str, int]] = {}
    for row in salvage_rows:
        for key, label in (("equipment_rarity", str(row["equipment_rarity"])),
                            ("equipment_level_band", str(row["equipment_level_band"]))):
            breakdown = rarity_breakdown if key == "equipment_rarity" else level_band_breakdown
            bucket = breakdown.setdefault(label, {"offers": 0, "positive_expected_ev": 0,
                                                    "positive_best_rng": 0, "best_rng_net_gold": -10**18})
            bucket["offers"] += 1
            bucket["positive_expected_ev"] += int(row["expected_net_gold"] > 0)
            best_rng = max(outcome["net_gold"] for outcome in row["rng_outcomes"])
            bucket["positive_best_rng"] += int(best_rng > 0)
            bucket["best_rng_net_gold"] = max(bucket["best_rng_net_gold"], best_rng)
    recipe_chain_edges = [{
        "from_recipe": upstream.name, "output": upstream.output_item_template.name,
        "to_recipe": downstream.name,
    } for upstream in recipes for downstream in recipes
        if upstream.id != downstream.id and any(
            int(material.item_template_id) == int(upstream.output_item_template_id)
            for material in downstream.materials
        )]
    recipe_chain_edges.extend({
        "from_recipe": recipe.name, "output": recipe.output_item_template.name,
        "to_recipe": "same recipe (self-loop)",
    } for recipe in recipes if any(
        int(material.item_template_id) == int(recipe.output_item_template_id)
        for material in recipe.materials
    ))
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "operational_definition": (
            "Economia sem arbitragem significa que nenhum ciclo fechado de conversão de ouro e bens "+
            "financiado por Docas/Market/desmontagem/crafting tem valor esperado positivo. Renda "+
            "legítima de tarefas, contratos, eventos e recompensas pode acumular sem teto de saldo."
        ),
        "scope": {
            "catalog": "Todos os MerchantOfferTemplate ativos e todos os ItemTemplate de equipamento seedados.",
            "dock_randomness": "Peso, presença do mercante e estoque min–max variam acesso/volume, não preço unitário; todos os preços de template foram verificados.",
            "market": f"Nível máximo 100; bônus de venda {maximum_bonus}%; preço unitário arredondado para baixo.",
            "progression_coverage": "Resultados detalhados por raridade e faixa de nível dos equipamentos ativos nas ofertas das Docas; avaliação no Market 100, limite superior de venda disponível em qualquer estágio.",
            "salvage_randomness": "Exaustão dos três resultados 1/2/3, equiprováveis por equipamento; expectativa usa a média exata.",
            "crafting": "Todas as receitas ativas; insumos são cobertos pelo menor custo esperado entre Docas e equipamentos comprados nas Docas, desmontados (custo mínimo 50g, rendimento esperado exato 2), mais o custo de ouro; saídas são vendidas no Market 100.",
            "recipe_chains": f"Grafo dirigido completo saída→insumo entre receitas seedadas; arestas encontradas: {len(recipe_chain_edges)}.",
            "salvage_assumptions": "Blacksmith 1+; custo mínimo de 50 ouro/unidade; Market 100; sem perda por capacidade, portanto cenário mais favorável à arbitragem.",
            "salvage_slot_fees": {str(slot): int(rule["unit_cost"]) for slot, rule in SALVAGE_SLOT_RULES.items()},
            "excluded": ["Fontes externas de criação de riqueza, como tarefas/contratos/recompensas", "Custos temporais e limites de vaga: reduzem apenas volume, não melhoram EV"],
        },
        "direct_dock_to_market": {
            "templates_scanned": len(direct_rows),
            "positive_ev_templates": sum(row["net_gold_per_unit"] > 0 for row in direct_rows),
            "best_net_gold_per_unit": max(direct_profits, default=0),
            "rows": direct_rows,
        },
        "docks_to_salvage_to_market": {
            "equipment_templates_scanned": len(salvage_rows),
            "positive_expected_ev_templates": sum(value > 0 for value in expected),
            "positive_best_rng_outcomes": sum(value > 0 for value in max_outcomes),
            "best_expected_net_gold": max(expected, default=0),
            "best_single_rng_outcome_net_gold": max(max_outcomes, default=0),
            "by_equipment_rarity": rarity_breakdown,
            "by_equipment_level_band": level_band_breakdown,
            "rows": salvage_rows,
        },
        "docks_to_crafting_to_market": {
            "active_recipes_scanned": len(crafting_rows),
            "recipes_with_all_materials_acquirable_from_docks_or_salvage": len(craft_profits),
            "positive_configured_net_recipes": sum(row["configured_net_gold"] > 0 for row in crafting_rows
                                                    if not row["materials_unavailable_from_docks_or_salvage"]),
            "positive_net_recipes": sum(value > 0 for value in craft_profits),
            "best_net_gold": max(craft_profits, default=0),
            "rows": crafting_rows,
            "output_used_as_recipe_input_edges": recipe_chain_edges,
            "unmodeled_recipe_chain_edges": len(recipe_chain_edges),
        },
        "crafted_equipment_to_salvage_to_market": {
            "closed_loops_scanned": len(crafted_equipment_salvage_rows),
            "positive_expected_ev_loops": sum(value > 0 for value in crafted_salvage_ev),
            "positive_best_rng_outcome_loops": sum(row["best_rng_net_gold"] > 0 for row in crafted_equipment_salvage_rows),
            "best_expected_net_gold": max(crafted_salvage_ev, default=0),
            "rows": crafted_equipment_salvage_rows,
        },
        "before_after_route_counts": {
            "direct_docks_market": {
                "legacy_positive_offers": sum(row["max_market_resale"] > row["legacy_effective_dock_price"] for row in direct_rows),
                "current_positive_offers": sum(row["net_gold_per_unit"] > 0 for row in direct_rows),
            },
            "docks_salvage_market": {
                "legacy_positive_expected": sum(row["legacy_expected_net_gold"] > 0 for row in salvage_rows),
                "legacy_positive_rng": sum(row["legacy_best_rng_net_gold"] > 0 for row in salvage_rows),
                "current_positive_expected": sum(row["expected_net_gold"] > 0 for row in salvage_rows),
                "current_positive_rng": sum(max(outcome["net_gold"] for outcome in row["rng_outcomes"]) > 0 for row in salvage_rows),
            },
            "docks_crafting_market": {
                "legacy_positive_expected": sum(row["legacy_net_gold"] > 0 for row in crafting_rows if not row["materials_unavailable_from_docks_or_salvage"]),
                "current_positive_expected": sum(row["net_gold"] > 0 for row in crafting_rows if not row["materials_unavailable_from_docks_or_salvage"]),
            },
            "crafting_salvage_market": {
                "legacy_positive_expected": sum(row["legacy_expected_net_gold"] > 0 for row in crafted_equipment_salvage_rows),
                "legacy_positive_rng": sum(row["legacy_best_rng_net_gold"] > 0 for row in crafted_equipment_salvage_rows),
                "current_positive_expected": sum(row["expected_net_gold"] > 0 for row in crafted_equipment_salvage_rows),
                "current_positive_rng": sum(row["best_rng_net_gold"] > 0 for row in crafted_equipment_salvage_rows),
            },
        },
        "price_comparison_examples": price_comparison_examples,
        "result": "PASS" if max(direct_profits, default=0) <= 0 and max(expected, default=0) <= 0 and max(max_outcomes, default=0) <= 0 and max(craft_profits, default=0) <= 0 and max(crafted_salvage_ev, default=0) <= 0 and max(crafted_salvage_best, default=0) <= 0 and not recipe_chain_edges else "FAIL",
    }


def render_markdown(data: dict[str, object]) -> str:
    direct, salvage = data["direct_dock_to_market"], data["docks_to_salvage_to_market"]
    crafting = data["docks_to_crafting_to_market"]
    lines = [
        "# Auditoria de arbitragem econômica — Stage 5", "",
        f"Gerada em {data['generated_at_utc']} · resultado **{data['result']}**.", "",
        data["operational_definition"], "",
        "## Cobertura", "",
        f"- Compra direta Docas → Market: {direct['templates_scanned']} ofertas seedadas; {direct['positive_ev_templates']} com margem positiva; melhor margem {direct['best_net_gold_per_unit']} ouro/unidade.",
        f"- Docas → desmontagem → Market: {salvage['equipment_templates_scanned']} equipamentos; {salvage['positive_expected_ev_templates']} com EV positivo; {salvage['positive_best_rng_outcomes']} têm algum resultado RNG positivo.",
        f"- Melhor EV da desmontagem: {salvage['best_expected_net_gold']:.2f} ouro; melhor resultado único: {salvage['best_single_rng_outcome_net_gold']} ouro.", "",
        "## Comparação antes e depois", "",
        "| Ciclo | Antes: rotas lucrativas | Depois: rotas lucrativas | Métrica |",
        "|---|---:|---:|---|",
        f"| Docas → Market | {data['before_after_route_counts']['direct_docks_market']['legacy_positive_offers']} | {data['before_after_route_counts']['direct_docks_market']['current_positive_offers']} | Ofertas |",
        f"| Docas → desmontagem → Market | {data['before_after_route_counts']['docks_salvage_market']['legacy_positive_expected']} | {data['before_after_route_counts']['docks_salvage_market']['current_positive_expected']} | EV positivo |",
        f"| Docas → desmontagem → Market | {data['before_after_route_counts']['docks_salvage_market']['legacy_positive_rng']} | {data['before_after_route_counts']['docks_salvage_market']['current_positive_rng']} | Algum resultado RNG lucrativo |",
        f"| Docas → crafting → Market | {data['before_after_route_counts']['docks_crafting_market']['legacy_positive_expected']} | {data['before_after_route_counts']['docks_crafting_market']['current_positive_expected']} | Receitas com EV positivo |",
        f"| Crafting → desmontagem → Market | {data['before_after_route_counts']['crafting_salvage_market']['legacy_positive_expected']} | {data['before_after_route_counts']['crafting_salvage_market']['current_positive_expected']} | EV positivo |",
        f"| Crafting → desmontagem → Market | {data['before_after_route_counts']['crafting_salvage_market']['legacy_positive_rng']} | {data['before_after_route_counts']['crafting_salvage_market']['current_positive_rng']} | Algum resultado RNG lucrativo |", "",
        "Preços de equipamentos nas Docas, antes/depois:", "",
        "| Estágio | Equipamento | Nv. item | Raridade | Antes | Depois | Aumento |",
        "|---|---|---:|---|---:|---:|---:|",
        *[f"| {row['stage']} | {row['item']} | {row['item_level']} | {row['rarity']} | {row['legacy_effective_dock_price']} | {row['effective_dock_price']} | {row['price_increase']} |"
          for row in data['price_comparison_examples']['docks_equipment']], "",
        "Custos de crafting, antes/depois:", "",
        "| Estágio | Receita | Saída | Nv. item | Raridade | Antes | Depois | Aumento |",
        "|---|---|---|---:|---|---:|---:|---:|",
        *[f"| {row['stage']} | {row['recipe']} | {row['output']} | {row['output_item_level']} | {row['output_rarity']} | {row['legacy_effective_craft_gold_cost']} | {row['effective_craft_gold_cost']} | {row['craft_price_increase']} |"
          for row in data['price_comparison_examples']['crafting']], "",
        "Resumo da desmontagem por raridade e faixa de progressão (cada linha contabiliza ofertas únicas de equipamento):", "",
        "| Raridade | Ofertas | EV positivo | RNG positivo | Melhor resultado RNG |",
        "|---|---:|---:|---:|---:|",
        *[f"| {rarity} | {values['offers']} | {values['positive_expected_ev']} | {values['positive_best_rng']} | {values['best_rng_net_gold']} ouro |"
          for rarity, values in sorted(salvage['by_equipment_rarity'].items())],
        "", "| Faixa de nível | Ofertas | EV positivo | RNG positivo | Melhor resultado RNG |",
        "|---|---:|---:|---:|---:|",
        *[f"| {band} | {values['offers']} | {values['positive_expected_ev']} | {values['positive_best_rng']} | {values['best_rng_net_gold']} ouro |"
          for band, values in sorted(salvage['by_equipment_level_band'].items())], "",
        "Taxas de desmontagem por slot preservadas: " + ", ".join(
            f"slot {slot}: {fee} ouro" for slot, fee in sorted(data['scope']['salvage_slot_fees'].items(), key=lambda row: int(row[0]))
        ) + ".", "",
        "Exemplos de preço Docas antes/depois por oferta (estágio, raridade e extremo): ver `price_comparison_examples` no JSON adjacente.", "",
        f"- Docas→Crafting→Market: {crafting['active_recipes_scanned']} receitas ativas; {crafting['recipes_with_all_materials_acquirable_from_docks_or_salvage']} abastecíveis por compra direta ou material recuperado por desmontagem; {crafting['positive_configured_net_recipes']} tinham margem positiva antes da proteção; após incluir o menor custo entre compra direta e material recuperado por desmontagem, {crafting['positive_net_recipes']} ficam positivas. Melhor margem: {crafting['best_net_gold']} ouro/receita.",
        f"- Arestas saída→insumo entre receitas (possível crafting encadeado): {crafting['unmodeled_recipe_chain_edges']}. O grafo seedado não contém uma saída de receita usada como ingrediente.", "",
        f"- Crafting→desmontagem→Market: {data['crafted_equipment_to_salvage_to_market']['closed_loops_scanned']} ciclos fechados com equipamento produzido; {data['crafted_equipment_to_salvage_to_market']['positive_expected_ev_loops']} com EV positivo e {data['crafted_equipment_to_salvage_to_market']['positive_best_rng_outcome_loops']} com algum resultado RNG positivo. Melhor EV: {data['crafted_equipment_to_salvage_to_market']['best_expected_net_gold']:.2f} ouro/ciclo.", "",
        "A busca usa o catálogo seedado real, bônus máximo do Market 100 e preços unitários reais. Sorteio de mercante, pesos e estoque limitam disponibilidade; como toda oferta é percorrida, não escondem um preço melhor. A desmontagem exaure exatamente os resultados 1, 2 e 3, e a expectativa usa a média dos três. Para o custo mínimo de salvage usa-se Blacksmith 1 (50 ouro) e rendimento esperado 2 por equipamento, sem penalidade de capacidade. Esse valor médio cobre o custo de longo prazo do insumo RNG; o relatório também testa a revenda direta de cada resultado isolado. Para receitas, cada ingrediente usa o menor custo esperado entre preço Dock acessível e equipamento comprado nas Docas e desmontado para o material requerido. Receitas sem fonte nessas rotas são listadas como inalcançáveis neste subgrafo.", "",
        "Variações de estoque, slots, timers e rotações aumentam ou reduzem throughput, mas não convertem uma margem negativa por unidade em EV positivo. Renda de sistemas que criam ouro ou itens fora desses ciclos é renda legítima e não implica arbitragem; o saldo de ouro não precisa de teto.", "",
        "## Reproduzir", "", "```powershell",
        ".venv-desktop\\Scripts\\python.exe scripts\\balance\\audit_economy_arbitrage.py", "```", "",
        "Receitas sem insumos recebem piso de ouro igual à revenda máxima mais 1 mesmo sem Docas. O JSON adjacente contém cada preço configurado/efetivo, estoque, requisito, material compatível e os três resultados de desmontagem por equipamento.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    with TemporaryDirectory(prefix="gim_economy_arbitrage_") as temp_dir:
        engine = create_database_engine(f"sqlite:///{Path(temp_dir) / 'audit.sqlite3'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with factory() as db:
            apply_initial_campaign_content(db)
            result = audit(db)
        engine.dispose()
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    stem = reports / "economy_arbitrage_bug012_2026-11-10"
    stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(result), encoding="utf-8")
    print(f"{result['result']}: {result['direct_dock_to_market']['templates_scanned']} dock offers; "
          f"{result['docks_to_salvage_to_market']['equipment_templates_scanned']} salvage equipment templates")
    print(stem.with_suffix(".md"))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
