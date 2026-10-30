"""Exercise closed Dock/Market, Craft/Market and Dock/Salvage/Market loops on disposable SQLite."""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev
from tempfile import TemporaryDirectory
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, create_database_engine
from app.models.campaign import CampaignMetadata
from app.models.crafting import CraftingRecipe
from app.models.dock import DockOffer, DockRotation, DockRotationMerchant, MerchantOfferTemplate, MerchantTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import GuildItemInstance, ItemTemplate
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services import market_service, salvage_service
from app.services.building_service import ensure_guild_buildings
from app.services.dock_service import buy_dock_offer
from app.services.economy_pricing_service import effective_dock_unit_price
from app.services.market_service import collect_market_sale, start_equipment_sale, start_material_sale
from app.services.salvage_service import collect_salvage, start_salvage
from app.services.crafting_service import craft_recipe, list_rotating_recipes
from scripts.balance.audit_economy_arbitrage import audit
from unittest.mock import patch

REPORT = "stage5_arbitrage_service_loops_2026-10-30"


def _ci95(values: list[float]) -> dict[str, float | int]:
    n = len(values)
    avg = mean(values) if values else 0.0
    half = 1.96 * stdev(values) / math.sqrt(n) if n > 1 else 0.0
    return {"mean": round(avg, 3), "ci95_low": round(avg - half, 3),
            "ci95_high": round(avg + half, 3), "n": n}


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _build_test_docks(db, guild, templates: list[ItemTemplate], stock: int, now: datetime) -> dict[int, DockOffer]:
    merchant = db.scalar(select(MerchantTemplate).where(MerchantTemplate.is_active.is_(True)).order_by(MerchantTemplate.id))
    if merchant is None:
        raise RuntimeError("Catálogo sem mercante ativo.")
    rotation = DockRotation(guild_id=guild.id, status="active", starts_at=now, ends_at=now + timedelta(days=2))
    db.add(rotation)
    db.flush()
    rotation_merchant = DockRotationMerchant(dock_rotation_id=rotation.id, merchant_template_id=merchant.id, slot=1)
    db.add(rotation_merchant)
    db.flush()
    offers: dict[int, DockOffer] = {}
    for template in templates:
        market_offers = list(db.scalars(select(MerchantOfferTemplate).where(
            MerchantOfferTemplate.is_active.is_(True),
            MerchantOfferTemplate.item_template_id == template.id,
        ).order_by(MerchantOfferTemplate.base_price, MerchantOfferTemplate.id)))
        if not market_offers:
            raise RuntimeError(f"Sem oferta catalogada nas Docas para {template.name}.")
        catalog = market_offers[0]
        offer = DockOffer(
            dock_rotation_merchant_id=rotation_merchant.id, item_template_id=template.id,
            unit_price=effective_dock_unit_price(catalog.base_price, template.base_sell_value),
            initial_stock=stock, remaining_stock=stock,
        )
        db.add(offer)
        db.flush()
        offers[template.id] = offer
    db.commit()
    return offers


def run_audit(n_salvage_roundtrips: int = 30, n_craft_roundtrips: int = 10) -> dict[str, object]:
    with TemporaryDirectory(prefix="gim-stage5-arbitrage-services-") as temp:
        engine = create_database_engine(f"sqlite:///{(Path(temp) / 'arbitrage.sqlite3').as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with factory() as db:
                apply_initial_campaign_content(db)
                now = datetime.now(timezone.utc)
                campaign = CampaignMetadata(
                    campaign_id="stage5-arbitrage-loops", campaign_name="Service arbitrage loop audit",
                    created_at_utc=now, updated_at_utc=now, schema_version=5,
                    content_version=3, home_region="North Forest",
                )
                guild = Guild(campaign_id=campaign.campaign_id, name="Arbitrage audit", level=100)
                resources = GuildResources(guild=guild, gold=50_000_000)
                db.add_all((campaign, guild, resources))
                db.flush()
                buildings = ensure_guild_buildings(db, guild.id)
                for building in buildings:
                    building.level = 100
                db.commit()

                math_audit = audit(db)
                candidate_rows = {row["recipe_id"]: row for row in math_audit["docks_to_crafting_to_market"]["rows"]}
                rotating, _rules = list_rotating_recipes(db, guild, 100, now)
                recipe = next((row for row in rotating if row.id in candidate_rows
                               and candidate_rows[row.id]["configured_net_gold"] > 0
                               and not candidate_rows[row.id]["materials_unavailable_from_docks_or_salvage"]), None)
                if recipe is None:
                    raise RuntimeError("A rotação atual não oferece uma receita candidata de margem configurada positiva.")
                candidates = candidate_rows[recipe.id]
                ingredient_templates = [material.item_template for material in recipe.materials]
                market_offers = _build_test_docks(db, guild, ingredient_templates, n_craft_roundtrips * 100,
                                                  datetime.now(timezone.utc))
                initial_gold = int(resources.gold)
                craft_loops = []
                for attempt in range(n_craft_roundtrips):
                    before = int(resources.gold)
                    # One extra unit of the first ingredient closes Dock→Market direct resale in the same cycle.
                    for index, material in enumerate(recipe.materials):
                        quantity = int(material.quantity) + int(index == 0)
                        buy_dock_offer(db, guild, resources, market_offers[material.item_template_id].id, quantity)
                    purchased_gold = before - int(resources.gold)
                    direct_material = recipe.materials[0].item_template
                    material_sale = start_material_sale(
                        db, guild, str(direct_material.id), "1",
                    )
                    with patch.object(market_service, "utc_now", return_value=_aware(material_sale.ends_at)):
                        collect_market_sale(db, guild, resources, material_sale.id)
                    material_revenue = int(material_sale.total_value)
                    gold_before_craft = int(resources.gold)
                    craft_recipe(db, guild, resources, str(recipe.id))
                    craft_spend = gold_before_craft - int(resources.gold)
                    item = db.scalar(select(GuildItemInstance).where(
                        GuildItemInstance.guild_id == guild.id,
                        GuildItemInstance.item_template_id == recipe.output_item_template_id,
                        GuildItemInstance.equipped_to_mercenary_id.is_(None),
                    ).order_by(GuildItemInstance.id.desc()))
                    if item is None:
                        raise RuntimeError("Craft service não deixou instância vendável.")
                    equipment_sale = start_equipment_sale(db, guild, str(item.id))
                    with patch.object(market_service, "utc_now", return_value=_aware(equipment_sale.ends_at)):
                        collect_market_sale(db, guild, resources, equipment_sale.id)
                    equipment_revenue = int(equipment_sale.total_value)
                    craft_loops.append({
                        "attempt": attempt + 1, "dock_purchase_gold": purchased_gold,
                        "direct_material_resale_gold": material_revenue,
                        "crafting_gold_fee": craft_spend, "crafted_equipment_sale_gold": equipment_revenue,
                        "net_gold": int(resources.gold) - before,
                    })

                equipment_offer_template = db.scalar(select(MerchantOfferTemplate).join(
                    ItemTemplate, ItemTemplate.id == MerchantOfferTemplate.item_template_id,
                ).where(
                    MerchantOfferTemplate.is_active.is_(True), ItemTemplate.item_type == "equipment",
                ).order_by(MerchantOfferTemplate.base_price, MerchantOfferTemplate.id))
                if equipment_offer_template is None:
                    raise RuntimeError("Sem equipamento ativo ofertado nas Docas.")
                equipment_template = db.get(ItemTemplate, equipment_offer_template.item_template_id)
                salvage_docks = _build_test_docks(db, guild, [equipment_template], n_salvage_roundtrips,
                                                  datetime.now(timezone.utc))
                salvage_nets = []
                salvage_yields = []
                for _ in range(n_salvage_roundtrips):
                    before = int(resources.gold)
                    buy_dock_offer(db, guild, resources, salvage_docks[equipment_template.id].id, 1)
                    item = db.scalar(select(GuildItemInstance).where(
                        GuildItemInstance.guild_id == guild.id,
                        GuildItemInstance.item_template_id == equipment_template.id,
                        GuildItemInstance.equipped_to_mercenary_id.is_(None),
                    ).order_by(GuildItemInstance.id.desc()))
                    job = start_salvage(db, guild, resources, "1", str(equipment_template.id), "1")
                    with patch.object(salvage_service, "utc_now", return_value=_aware(job.ends_at)):
                        collect_salvage(db, guild, str(job.id))
                    salvage_yields.append(int(job.result_quantity or 0))
                    sale = start_material_sale(db, guild, str(job.material_template_id), str(job.result_quantity))
                    with patch.object(market_service, "utc_now", return_value=_aware(sale.ends_at)):
                        collect_market_sale(db, guild, resources, sale.id)
                    salvage_nets.append(int(resources.gold) - before)
                final_gold = int(resources.gold)
                return {
                    "report_id": REPORT, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "database": "temporary SQLite; services commit within disposable database",
                    "closed_loop_contract": "actual buy_dock_offer → start/collect material Market sale → craft_recipe → start/collect equipment Market sale",
                    "craft_recipe": recipe.name, "craft_recipe_id": recipe.id,
                    "catalog_model_configured_margin_per_craft": candidates["configured_net_gold"],
                    "effective_craft_gold_cost": candidates["effective_craft_gold_cost"],
                    "craft_loops": craft_loops, "craft_loop_net_gold_ci95": _ci95([r["net_gold"] for r in craft_loops]),
                    "dock_salvage_contract": "actual buy_dock_offer → start_salvage → collect_salvage → start/collect material Market sale",
                    "salvage_equipment": equipment_template.name, "salvage_roundtrips": n_salvage_roundtrips,
                    "salvage_material_units": salvage_yields, "salvage_net_gold_ci95": _ci95([float(v) for v in salvage_nets]),
                    "salvage_positive_net_roundtrips": sum(v > 0 for v in salvage_nets),
                    "salvage_net_gold_min_max": [min(salvage_nets), max(salvage_nets)],
                    "initial_gold": initial_gold, "final_gold": final_gold,
                    "total_closed_loop_gold_delta": final_gold - initial_gold,
                    "positive_ev_seen_in_realized_runs": any(r["net_gold"] > 0 for r in craft_loops) or any(v > 0 for v in salvage_nets),
                    "formula_catalog_audit": {
                        "result": math_audit["result"],
                        "dock_to_market_positive_templates": math_audit["direct_dock_to_market"]["positive_ev_templates"],
                        "dock_salvage_market_positive_ev": math_audit["docks_to_salvage_to_market"]["positive_expected_ev_templates"],
                        "craft_market_positive_recipes_after_protection": math_audit["docks_to_crafting_to_market"]["positive_net_recipes"],
                        "craft_salvage_market_positive_ev": math_audit["crafted_equipment_to_salvage_to_market"]["positive_expected_ev_loops"],
                    },
                }
        finally:
            engine.dispose()


def main() -> int:
    report = run_audit()
    out = ROOT / "reports" / f"{REPORT}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Ciclos fechados de arbitragem pelos serviços", "",
             f"Campanha descartável · loops de crafting N={len(report['craft_loops'])}, loops de salvage N={report['salvage_roundtrips']}.", "",
             f"Crafting: {report['craft_recipe']} (configurado +{report['catalog_model_configured_margin_per_craft']} ouro; custo efetivo {report['effective_craft_gold_cost']}). Margem realizada total com compra, revenda de ingrediente, craft e venda de equipamento: {report['craft_loop_net_gold_ci95']['mean']:.1f} ouro/loop (IC95% {report['craft_loop_net_gold_ci95']['ci95_low']:.1f}–{report['craft_loop_net_gold_ci95']['ci95_high']:.1f}).",
             f"Desmontagem: {report['salvage_equipment']}; margem média Dock→salvage→Market {report['salvage_net_gold_ci95']['mean']:.1f} ouro (IC95% {report['salvage_net_gold_ci95']['ci95_low']:.1f}–{report['salvage_net_gold_ci95']['ci95_high']:.1f}), intervalo observado {report['salvage_net_gold_min_max'][0]}…{report['salvage_net_gold_min_max'][1]}.",
             f"Resultado realizado: delta de ouro conjunto {report['total_closed_loop_gold_delta']}; algum loop positivo na amostra: {report['positive_ev_seen_in_realized_runs']}. O caminho executou os serviços reais sobre ofertas sintéticas temporárias com preços derivados do catálogo; estoque/rotação natural e preço/EV de todo o catálogo continuam cobertos pela auditoria de catálogo adjacente.", ""]
    (ROOT / "reports" / f"{REPORT}.md").write_text("\n".join(lines), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
