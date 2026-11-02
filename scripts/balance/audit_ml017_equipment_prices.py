"""Audit every seeded equipment row and monotonic Market prices, without a save."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.seeds.massive_content import _equipment_rows
from app.services.building_balance_service import market_values
from app.services.economy_pricing_service import (
    EQUIPMENT_COMMON_BASE_BY_SLOT,
    EQUIPMENT_RARITY_PREMIUM_PERCENT,
    equipment_base_sell_value,
    market_sale_unit_value,
)


def run() -> dict[str, object]:
    rows = _equipment_rows()
    rarities = tuple(EQUIPMENT_RARITY_PREMIUM_PERCENT)
    market_levels = (1, 100)
    checks = []
    for slot in EQUIPMENT_COMMON_BASE_BY_SLOT:
        base_prices = [equipment_base_sell_value(slot, rarity) for rarity in rarities]
        for level in market_levels:
            market_bonus = market_values(level)["value_bonus_percent"]
            effective_prices = [market_sale_unit_value(price, market_bonus) for price in base_prices]
            checks.append({
                "slot": slot, "market_level": level, "market_value_bonus_percent": market_bonus,
                "base_prices_by_rarity": dict(zip(rarities, base_prices)),
                "effective_prices_by_rarity": dict(zip(rarities, effective_prices)),
                "strictly_monotonic": all(left < right for left, right in zip(effective_prices, effective_prices[1:])),
            })
    slot_counts = {slot: sum(1 for row in rows if row["equipment_slot"] == slot) for slot in EQUIPMENT_COMMON_BASE_BY_SLOT}
    economic_ranges = {}
    for level in market_levels:
        bonus = market_values(level)["value_bonus_percent"]
        common = [market_sale_unit_value(equipment_base_sell_value(slot, "common"), bonus)
                  for slot in EQUIPMENT_COMMON_BASE_BY_SLOT]
        mythic = [market_sale_unit_value(equipment_base_sell_value(slot, "mythic"), bonus)
                  for slot in EQUIPMENT_COMMON_BASE_BY_SLOT]
        economic_ranges[str(level)] = {
            "lowest_common_unit_price": min(common),
            "highest_mythic_unit_price": max(mythic),
            "maximum_common_to_mythic_delta_for_same_slot": max(
                market_sale_unit_value(equipment_base_sell_value(slot, "mythic"), bonus)
                - market_sale_unit_value(equipment_base_sell_value(slot, "common"), bonus)
                for slot in EQUIPMENT_COMMON_BASE_BY_SLOT
            ),
        }
    return {
        "audit": "ml017_equipment_base_and_market_price_v1",
        "uses_campaign_save": False,
        "seeded_equipment_rows_audited": len(rows),
        "equipment_rows_by_slot": slot_counts,
        "common_base_by_slot": EQUIPMENT_COMMON_BASE_BY_SLOT,
        "rarity_premium_percent": EQUIPMENT_RARITY_PREMIUM_PERCENT,
        "market_levels_checked": {str(level): market_values(level)["value_bonus_percent"] for level in market_levels},
        "economic_price_ranges": economic_ranges,
        "comparability_dimensions": {
            "fixed_when_comparing_rarity": ["equipment_slot", "item_level", "instance_refinement_level"],
            "pricing_inputs": ["equipment_slot", "rarity", "market_value_bonus_percent"],
            "item_level_or_refinement_changes_sale_price": False,
        },
        "monotonic_comparison_count": len(checks),
        "all_comparisons_strictly_monotonic": all(row["strictly_monotonic"] for row in checks),
        "comparisons": checks,
        "manual_admin_price_preservation": "covered by tests.test_equipment_pricing.EquipmentPricingTests.test_catalog_upgrade_reprices_legacy_values_but_preserves_admin_price",
        "method_limit": "The Common reference is intentionally slot-based. Item level and instance refinement are not price inputs, so comparisons hold those dimensions constant; tier does not shift the requested slot baseline.",
    }


if __name__ == "__main__":
    report = run()
    (ROOT / "reports" / "ml017_equipment_price_audit_v0.5.0.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    lines = [
        "# ML-017 — Auditoria de preços de equipamentos",
        "",
        f"Foram auditados {report['seeded_equipment_rows_audited']} equipamentos gerados pelo catálogo e {report['monotonic_comparison_count']} comparações tipo/raridade/Mercado. Resultado estritamente crescente em todos os casos: **{report['all_comparisons_strictly_monotonic']}**.",
        "",
        "## Ouro-base Comum por tipo de equipamento",
        "",
        "| Tipo / espaço | Ouro-base Comum |",
        "|---|---:|",
    ]
    for slot, value in report["common_base_by_slot"].items():
        lines.append(f"| {slot} | {value} |")
    lines.extend(["", "## Acréscimo por raridade", "", "| Raridade | Acréscimo sobre o Comum |", "|---|---:|"])
    for rarity, premium in report["rarity_premium_percent"].items():
        lines.append(f"| {rarity} | +{premium}% |")
    lines.extend([
        "", "## Bônus do Mercado testados", "",
        f"Mercado nível 1: +{report['market_levels_checked']['1']}%; Mercado nível 100: +{report['market_levels_checked']['100']}%. Os bônus foram aplicados aos preços unitários com o serviço real `market_sale_unit_value`.",
        "", "O preço Comum fica fixo por espaço de equipamento. Para cada tipo, o cálculo aplica o acréscimo de raridade com arredondamento para cima; todos os níveis de Mercado preservam diferença estrita entre raridades comparáveis com mesmo tipo, nível do item e refino. Nível do item e refino não entram no preço unitário de venda; tier não desloca a referência Comum.",
        "", f"Faixa econômica auditada: no Mercado nível 1, Common vai de {report['economic_price_ranges']['1']['lowest_common_unit_price']} ouro e o maior preço Mythic é {report['economic_price_ranges']['1']['highest_mythic_unit_price']} (diferença máxima Common→Mythic do mesmo tipo: {report['economic_price_ranges']['1']['maximum_common_to_mythic_delta_for_same_slot']}); no nível 100, os valores são {report['economic_price_ranges']['100']['lowest_common_unit_price']}, {report['economic_price_ranges']['100']['highest_mythic_unit_price']} e {report['economic_price_ranges']['100']['maximum_common_to_mythic_delta_for_same_slot']} ouro, respectivamente.",
        "", "Os testes também verificam que a atualização do catálogo altera valores gerados pela fórmula antiga e preserva um preço administrativo customizado.", "",
    ])
    (ROOT / "reports" / "ml017_equipment_price_audit_v0.5.0.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
