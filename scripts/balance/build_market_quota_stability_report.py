"""Consolidate saved Market quota sensitivity and paired producer journeys."""
from __future__ import annotations

import json
import hashlib
import csv
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
CAPS: tuple[int | None, ...] = (10, 25, 50, 100, 250, None)
RESERVES = (30, 300)
DECISION_RESERVES = (30,)
PROFILES = ("ativo", "casual", "offline", "produtor", "combate")


def load(name: str) -> dict[str, object]:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def market_totals(journey: dict[str, object]) -> tuple[int, int]:
    sales = [event for day in journey["daily"] for event in day["market_and_salvage_events"]
             if event.get("type") == "market_sale"]
    return sum(int(sale.get("units", 0)) for sale in sales), sum(int(sale.get("gold", 0)) for sale in sales)


def source_gold(journey: dict[str, object]) -> dict[str, int]:
    totals = {key: 0 for key in ("passive_offline", "missions", "dungeons", "market_sales")}
    for day in journey["daily"]:
        for key in totals:
            totals[key] += int(day["gold_ledger"].get(key, 0))
    return totals


def range_text(values: list[int | float]) -> str:
    return f"{median(values):.0f} ({min(values):.0f}–{max(values):.0f})" if values else "—"


def reconcile_source_report(stem: str, source: dict[str, object]) -> None:
    """Make per-day JSON and ledger overflow agree with actual service results, then rebuild its Markdown."""
    ledger_lookup: dict[tuple[int, int], dict[str, int]] = {}
    pause_lookup: dict[tuple[int, int], int] = {}
    for journey in source["journeys"]:
        daily_sources = {int(day["day"]): {key: 0 for key in ("mission", "dungeon", "gathering", "salvage")}
                         for day in journey["daily"]}
        for action in journey["actions"]:
            kind = action.get("kind")
            family = "mission" if kind in ("contract", "mission") else "dungeon" if kind in ("dungeon", "portal") else None
            if family:
                daily_sources[int(action["day"])][family] += int(action.get("discarded", 0))
        for day in journey["daily"]:
            counts = daily_sources[int(day["day"])]
            counts["gathering"] = int(day.get("gathering_discarded", 0))
            counts["salvage"] = sum(
                int(event.get("discarded", 0)) for event in day.get("market_and_salvage_events", [])
                if event.get("type") == "salvage"
            )
            day["overflow_by_source"] = counts
            day["gathering_paused_worker_seconds"] = int(day.get("gathering_paused_seconds", 0))
            ledger_lookup[(int(journey["seed"]), int(day["day"]))] = counts
            pause_lookup[(int(journey["seed"]), int(day["day"]))] = int(day["gathering_paused_worker_seconds"])
        families = next(iter(daily_sources.values()))
        recomputed = {key: sum(row[key] for row in daily_sources.values()) for key in families}
        if recomputed != {key: int(journey["overflow"].get(key, 0)) for key in recomputed}:
            raise ValueError(f"JSON daily overflow does not reconcile to journey total: {stem} seed={journey['seed']}")

    json_path = REPORTS / f"{stem}.json"
    json_path.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger_path = REPORTS / f"{stem}.ledger.csv"
    if ledger_path.exists():
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0]) if rows else []
        for name in ("overflow_mission", "overflow_dungeon", "overflow_gathering", "overflow_salvage",
                     "gathering_paused_worker_seconds"):
            if name not in fieldnames:
                fieldnames.append(name)
        for row in rows:
            key = (int(row["seed"]), int(row["day"]))
            counts = ledger_lookup[key]
            row.update({f"overflow_{name}": counts[name] for name in ("mission", "dungeon", "gathering", "salvage")})
            day = next(day for journey in source["journeys"] if int(journey["seed"]) == key[0]
                       for day in journey["daily"] if int(day["day"]) == key[1])
            row["gathering_paused_worker_seconds"] = day["gathering_paused_worker_seconds"]
        with ledger_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reconciled_rows = list(csv.DictReader(handle))
        for row in reconciled_rows:
            key = (int(row["seed"]), int(row["day"]))
            counts = ledger_lookup[key]
            if any(int(row[f"overflow_{name}"]) != counts[name]
                   for name in ("mission", "dungeon", "gathering", "salvage")):
                raise ValueError(f"CSV overflow does not match JSON for {stem} seed/day={key}")
            if int(row["gathering_paused_worker_seconds"]) != pause_lookup[key]:
                raise ValueError(f"CSV gathering pause does not match JSON for {stem} seed/day={key}")

    lines = [
        f"# Fresh-save journey evidence — {stem}", "",
        f"report_id={source.get('report_id')} · N={source['runs_per_cell']}/cell · cap L1={source['market_base_units_per_24h']} · reserve harness={source['market_reserve_base']} · craft={source.get('craft_policy', 'none')} · disposable SQLite.", "",
        "Material quota: `25 + 5 * (market_level // 5)`; the row `cap L1` is the experiment's base at Market 1. Source/sink flows use live services; save snapshots are not used.", "",
        "| Perfil/caminho | Seed | Dias | Ouro final | Venda (un./ouro) | Overflow M/D/G/S (material units) | Pausa coleta (worker-h/pausados/total) | Pico pré-venda/capacidade | Portal entradas/drops | Crafts |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    evidence_rows = []
    for journey in source["journeys"]:
        units, market_gold = market_totals(journey)
        gross_gold = sum(source_gold(journey).values())
        share = round(100 * market_gold / gross_gold, 2) if gross_gold else 0
        paused_seconds = sum(int(day.get("gathering_paused_worker_seconds", 0)) for day in journey["daily"])
        pause_checkpoints = sum(int(day.get("gathering_paused_checkpoints", 0)) for day in journey["daily"])
        checkpoints = sum(int(day.get("gathering_checkpoints", 0)) for day in journey["daily"])
        capacity = journey.get("inventory_capacity_end", 0)
        if isinstance(capacity, list):
            capacity = capacity[0] if capacity else 0
        pre_sale_peak = journey.get("inventory_peak_before_market_sale", journey["inventory_peak"])
        portal_actions = [action for action in journey["actions"] if action.get("kind") == "portal"]
        portal_drops = sum(action.get("loot_item_template_id") is not None for action in portal_actions)
        overflow = journey["overflow"]
        rendered_row = (
            f"| {journey['profile']}/{journey['path']} | {journey['seed']} | {journey['days']} | {journey['ending_gold']} | "
            f"{units}/{market_gold} ({share}%) | {overflow['mission']}/{overflow['dungeon']}/{overflow['gathering']}/{overflow['salvage']} | "
            f"{paused_seconds/3600:.2f}/{pause_checkpoints}/{checkpoints} | {pre_sale_peak}/{capacity} | "
            f"{len(portal_actions)}/{portal_drops} | {journey.get('crafts_completed', 0)} |"
        )
        lines.append(rendered_row)
        evidence_rows.append(rendered_row)
    lines.extend(["", "M/D/G/S are material units actually rejected by capacity during mission/contract, dungeon/portal, gathering and salvage claims. They are lost loot, not gold or event counts. Pause is worker-time while capacity prevents collection; it is separate from discarded loot. Portal participation is attempted through real dungeon/claim services only when an active home-region portal and a legal party are naturally available in an online window. Rebellion has no player-participation policy in this sample.", ""])
    source_markdown = "\n".join(lines)
    if any(row not in source_markdown for row in evidence_rows):
        raise ValueError(f"Per-journey Markdown table does not match JSON: {stem}")
    (REPORTS / f"{stem}.md").write_text(source_markdown, encoding="utf-8")


def main() -> None:
    sensitivity = []
    source_reports: list[dict[str, object]] = []
    for cap in CAPS:
        label = "unlimited" if cap is None else str(cap)
        for reserve in RESERVES:
            stem = (
                f"market_quota_formula2_craftonce_base{label}_reserve30_n1"
                if label in {"25", "50"} and reserve == 30 else
                f"market_quota_base{label}_reserve{reserve}_n1"
            )
            report = load(f"{stem}.json")
            reconcile_source_report(stem, report)
            if report.get("journey_errors"):
                raise ValueError(f"N1 source has journey errors: {stem}")
            source_reports.append({"stem": stem, "report_id": report.get("report_id"), "journeys": len(report["journeys"])})
            for profile in PROFILES:
                journey = next(row for row in report["journeys"] if row["profile"] == profile)
                summary = report["cell_summaries"][f"{profile}/commerce_early"]
                units, market_gold = market_totals(journey)
                sources = source_gold(journey)
                gross = sum(sources.values())
                paused_family_days = sum(
                    bool(record.get("paused"))
                    for day in journey["daily"]
                    for record in day.get("gathering_by_family", {}).values()
                )
                sensitivity.append({
                    "profile": profile, "base_limit": cap, "reserve": reserve,
                    "days": journey["days"], "ending_gold": journey["ending_gold"],
                    "market_level_end": int(journey.get("market_level_end", 1)),
                    "crafts_completed": int(journey.get("crafts_completed", 0)),
                    "crafting_gold_cost": sum(int(event.get("gold_cost", 0)) for event in journey["events"]
                                               if event.get("type") == "craft"),
                    "net_gold_change": sum(int(day["gold_ledger"]["observed_delta"]) for day in journey["daily"]),
                    "market_gold": market_gold,
                    "market_share_percent": round(100 * market_gold / gross, 2) if gross else 0,
                    "materials_sold": units,
                    "ending_materials": journey["ending_materials"],
                    "closing_inventory_peak": journey["inventory_peak"],
                    "inventory_capacity_end": journey["inventory_capacity_end"],
                    "overflow_mission_dungeon_gathering_salvage": [
                        journey["overflow"][key] for key in ("mission", "dungeon", "gathering", "salvage")
                    ],
                    "gathering_produced": sum(int(day["gathering_produced"]) for day in journey["daily"]),
                    "gathering_stored": sum(int(day["gathering_stored"]) for day in journey["daily"]),
                    "gathering_discarded": sum(int(day["gathering_discarded"]) for day in journey["daily"]),
                    "gathering_final_checkpoint_paused_family_days": paused_family_days,
                    "gathering_pause_worker_hours": round(
                        sum(int(day.get("gathering_paused_seconds", 0)) for day in journey["daily"]) / 3600, 2,
                    ),
                    "gathering_pause_checkpoints": sum(
                        int(day.get("gathering_paused_checkpoints", 0)) for day in journey["daily"]
                    ),
                    "gathering_checkpoints": sum(
                        int(day.get("gathering_checkpoints", 0)) for day in journey["daily"]
                    ),
                    "level_milestone_days": journey["level_milestone_days"],
                    "same_blocked_upgrade_recoveries": journey["same_upgrade_blocked_then_bought"],
                    "gross_gold_by_source": sources,
                    "gold_drenos": {
                        "building_and_hiring": sum(int(day["gold_ledger"]["building_and_hire_purchases"])
                                                    for day in journey["daily"]),
                        "salvage_fees": sum(int(day["gold_ledger"]["salvage_fees"])
                                             for day in journey["daily"]),
                    "crafting_fees": sum(int(day["gold_ledger"].get("crafting_fees", 0))
                                          for day in journey["daily"]),
                    },
                    "n1_wilson_level50": summary["reached_rate_wilson_95"],
                })

    producer = []
    producer_rows: dict[tuple[int, int], list[dict[str, object]]] = {}
    for cap in (25, 35, 50):
        for reserve in DECISION_RESERVES:
            report = load(f"market_quota_formula2_craftonce_base{cap}_reserve{reserve}_n10.json")
            reconcile_source_report(f"market_quota_formula2_craftonce_base{cap}_reserve{reserve}_n10", report)
            if report.get("journey_errors"):
                raise ValueError(f"N10 source has journey errors: market_quota_formula2_craftonce_base{cap}_reserve{reserve}_n10")
            if len(report["journeys"]) != 10:
                raise ValueError(f"N10 source must contain ten journeys for cap {cap}")
            source_reports.append({
                "stem": f"market_quota_formula2_craftonce_base{cap}_reserve{reserve}_n10",
                "report_id": report.get("report_id"), "journeys": len(report["journeys"]),
            })
            rows = report["journeys"]
            producer_rows[(cap, reserve)] = rows
            cell_summary = report["cell_summaries"]["produtor/commerce_early"]
            milestone_medians = {
                level: range_text([row["level_milestone_days"][level] for row in rows
                                   if level in row["level_milestone_days"]])
                for level in ("10", "25", "50")
            }
            n = len(rows)
            units_gold = [market_totals(row) for row in rows]
            market_gold = [value[1] for value in units_gold]
            gross_sources = [sum(source_gold(row).values()) for row in rows]
            market_shares = [100 * market_gold[i] / gross_sources[i] if gross_sources[i] else 0
                             for i in range(n)]
            producer.append({
                "base_limit": cap, "reserve": reserve, "n": n,
                "seed_ids": [row["seed"] for row in rows],
                "reached_level_50": sum(bool(row["reached_level_50"]) for row in rows),
                "reached_level_50_wilson_95": cell_summary["reached_rate_wilson_95"],
                "ending_gold_median_range": range_text([row["ending_gold"] for row in rows]),
                "net_gold_change_median_range": range_text([
                    sum(int(day["gold_ledger"]["observed_delta"]) for day in row["daily"]) for row in rows
                ]),
                "market_gold_median_range": range_text(market_gold),
                "market_share_percent_median_range": range_text(market_shares),
                "materials_sold_median_range": range_text([value[0] for value in units_gold]),
                "overflow_totals_mission_dungeon_gathering_salvage": {
                    key: sum(int(row["overflow"][key]) for row in rows)
                    for key in ("mission", "dungeon", "gathering", "salvage")
                },
                "seeds_with_each_overflow": {
                    key: [row["seed"] for row in rows if int(row["overflow"][key]) > 0]
                    for key in ("mission", "dungeon", "gathering", "salvage")
                },
                "gathering_produced_median_range": range_text([
                    sum(int(day["gathering_produced"]) for day in row["daily"]) for row in rows
                ]),
                "gathering_discarded_total": sum(int(row["overflow"]["gathering"]) for row in rows),
                "gathering_pause_worker_hours_total": round(
                    sum(int(row["gathering_paused_seconds"]) for row in rows) / 3600, 2,
                ),
                "gathering_missed_cycle_equivalents": sum(
                    int(row["gathering_paused_seconds"]) // 60 for row in rows
                ),
                "gathering_pause_checkpoints_total": sum(
                    int(row["gathering_pause_checkpoints"]) for row in rows
                ),
                "gathering_checkpoints_total": sum(int(row["gathering_checkpoints"]) for row in rows),
                "pre_sale_inventory_peak_median_range": range_text([
                    row["inventory_peak_before_market_sale"] for row in rows
                ]),
                "post_sale_inventory_peak_median_range": range_text([row["inventory_peak"] for row in rows]),
                "capacity_end": rows[0]["inventory_capacity_end"],
                "milestone_days_median_range": milestone_medians,
                "portal_entries": sum(sum(action.get("kind") == "portal" for action in row["actions"])
                                       for row in rows),
                "portal_loot_equipment_drops": sum(sum(action.get("kind") == "portal"
                                                       and action.get("loot_item_template_id") is not None
                                                       for action in row["actions"]) for row in rows),
                "rebellion_player_participation": 0,
                "recovered_blocked_targets": sum(int(row["same_upgrade_blocked_then_bought"]) for row in rows),
                "blocked_targets_at_horizon": sum(int(row["blocked_upgrade_at_horizon_count"]) for row in rows),
                "crafts_completed": sum(int(row.get("crafts_completed", 0)) for row in rows),
                "crafting_gold_cost": sum(
                    int(event.get("gold_cost", 0)) for row in rows for event in row["events"]
                    if event.get("type") == "craft"
                ),
                "gross_gold_by_source": {
                    key: sum(source_gold(row)[key] for row in rows)
                    for key in ("passive_offline", "missions", "dungeons", "market_sales")
                },
                "gold_drenos": {
                    "building_and_hiring": sum(
                        sum(int(day["gold_ledger"]["building_and_hire_purchases"]) for day in row["daily"])
                        for row in rows
                    ),
                    "salvage_fees": sum(
                        sum(int(day["gold_ledger"]["salvage_fees"]) for day in row["daily"])
                        for row in rows
                    ),
                    "crafting_fees": sum(
                        sum(int(day["gold_ledger"].get("crafting_fees", 0)) for day in row["daily"])
                        for row in rows
                    ),
                },
                "unattributed_gold_residual": sum(
                    sum(int(day["gold_ledger"]["unattributed_residual"]) for day in row["daily"])
                    for row in rows
                ),
            })

    for (cap, _reserve), journeys in producer_rows.items():
        aggregate = next(row for row in producer if row["base_limit"] == cap)
        for kind in ("mission", "dungeon", "gathering", "salvage"):
            assert aggregate["overflow_totals_mission_dungeon_gathering_salvage"][kind] == sum(
                int(journey["overflow"][kind]) for journey in journeys
            )
        assert aggregate["portal_entries"] == sum(
            sum(action.get("kind") == "portal" for action in journey["actions"])
            for journey in journeys
        )
        assert aggregate["crafts_completed"] == sum(
            int(journey.get("crafts_completed", 0)) for journey in journeys
        )

    paired = []
    for reserve in DECISION_RESERVES:
        lower = {row["seed"]: row for row in producer_rows[(25, reserve)]}
        higher = {row["seed"]: row for row in producer_rows[(50, reserve)]}
        common = sorted(set(lower) & set(higher))
        def delta_series(value):
            differences = [value(lower[seed]) - value(higher[seed]) for seed in common]
            return {"median": median(differences), "min": min(differences), "max": max(differences),
                    "by_seed": {str(seed): delta for seed, delta in zip(common, differences)}}

        low_sales = {seed: market_totals(lower[seed]) for seed in common}
        high_sales = {seed: market_totals(higher[seed]) for seed in common}
        paired.append({
            "reserve": reserve, "paired_seed_count": len(common), "seeds": common,
            "ending_gold_25_minus_50": delta_series(lambda row: int(row["ending_gold"])),
            "market_gold_25_minus_50": delta_series(lambda row: market_totals(row)[1]),
            "materials_sold_25_minus_50": delta_series(lambda row: market_totals(row)[0]),
            "inventory_pre_sale_peak_25_minus_50": delta_series(
                lambda row: int(row["inventory_peak_before_market_sale"]),
            ),
            "gathering_pause_hours_25_minus_50": delta_series(
                lambda row: int(row["gathering_paused_seconds"]) / 3600,
            ),
            "overflow_25_minus_50": {
                kind: delta_series(lambda row, kind=kind: int(row["overflow"][kind]))
                for kind in ("mission", "dungeon", "gathering", "salvage")
            },
            "milestone_day_25_minus_50": {
                level: delta_series(lambda row, level=level: int(row["level_milestone_days"].get(level, 0)))
                for level in ("10", "25", "50")
            },
        })

    report = {
        "report_id": "gim-market-quota-operational-stability-20261030-v2",
        "source_reports": source_reports,
        "sensitivity_n1": sensitivity,
        "producer_paired_n10": producer,
        "paired_quota_deltas_n10": paired,
        "offline_worker_8h_baseline_units": 480,
        "quota_progression": "25 + 5 * (market_level // 5); L1-4=25, L5-9=30, L10-14=35, L100=125",
        "overflow_definition": "overflow values are material item units rejected by real service inventory-capacity claims, classified by source M/D/G/S; gathering pause time is a separate worker-seconds metric, not discarded loot.",
        "caps_as_fraction_of_one_worker_8h_at_market_1_percent": {
            str(cap): round(100 * cap / 480, 2) for cap in (10, 25, 35, 50, 100, 250)
        },
        "market_level_100_units_and_fraction": {
            str(cap): {"units_per_rolling_24h": cap + 5 * (100 // 5),
                       "percent_of_worker_8h": round(100 * (cap + 5 * (100 // 5)) / 480, 2)}
            for cap in (10, 25, 35, 50, 100, 250)
        },
        "interpretation": {
            "n1": "Descriptive pilot by profile and cap; Wilson intervals are very broad and do not estimate population outcomes.",
            "reserve": "The 30/300 material reserve is an explicit harness sale policy, not a game rule. It protects stock and changes throughput, sale income and capacity pressure; report it separately from quota effects.",
            "gathering_pause": "N1 historical runs expose final gathering checkpoint paused by family-day only. The new N10 runner reports paused worker-hours estimated by the live service and paused checkpoints; neither is interpreted as a whole-day pause.",
            "overflow_order": "M/D/G/S = mission/contract loot, dungeon/portal loot, gathering, salvage. Gathering paused time is distinct from overflow; paused seconds are converted to worker-hours across assignments.",
            "gate": "Market quota integration may close after service/UI regressions. Stage 5 and economy stability remain open pending natural event/rebellion participation coverage, crafting reachability, long-horizon gold criteria and user visual review of the isolated candidate build.",
        },
    }
    (REPORTS / "market_quota_stability_2026-10-30.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    lines = [
        "# Estabilidade operacional da cota do Mercado", "",
        "Sensibilidade descritiva N=1 dos cinco perfis em seis cotas e reservas 30/300, mais comparação N=10 do produtor entre bases25/35/50 com reserva30, política de crafting equivalente e seeds pareadas. Todos os saves são SQLite temporários.", "",
        "## Sensibilidade N=1 por perfil/cota/reserva", "",
        "| Perfil | Cota L1 | Reserva | Nível Mercado | Ouro líquido | Craft: quantidade/taxa | Venda: un./ouro/% fonte bruta | Materiais finais W/M/C | Pico estoque/cap. | Overflow M/D/G/S | Coleta produzida/descartada | Pausa: h-trabalhador / checkpoints pausados/total | Nível 10/25/50 (dia) |", "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in sensitivity:
        sales = f"{row['materials_sold']}/{row['market_gold']}/{row['market_share_percent']}%"
        craft = f"{row['crafts_completed']}/{row['crafting_gold_cost']}"
        stock = "/".join(str(row["ending_materials"].get(family, 0))
                         for family in ("wood", "ore", "leather"))
        capacity_value = row["inventory_capacity_end"]
        capacity = (capacity_value[0] if capacity_value else 0) if isinstance(capacity_value, list) else capacity_value
        milestones = "/".join(str(row["level_milestone_days"].get(level, "—")) for level in ("10", "25", "50"))
        pause = f"{row['gathering_pause_worker_hours']}/{row['gathering_pause_checkpoints']}/{row['gathering_checkpoints']}"
        lines.append(f"| {row['profile']} | {'sem limite' if row['base_limit'] is None else row['base_limit']} | {row['reserve']} | {row['market_level_end']} | {row['net_gold_change']} | {craft} | {sales} | {stock} | {row['closing_inventory_peak']}/{capacity} | {'/'.join(map(str, row['overflow_mission_dungeon_gathering_salvage']))} | {row['gathering_produced']}/{row['gathering_discarded']} | {pause} | {milestones} |")
    lines.extend(["", "Os casos N=1 mostram a forma dos fluxos, não diferenças populacionais. Estoque máximo histórico é o pico observado no fechamento diário após venda; o N10 instrumentado também guarda o pico antes da venda. Pausa mede segundos-trabalhador sem produção por capacidade cheia; não é descarte nem equivale a unidades fixas, pois os bônus por ciclo variam.", "", "## Produtor N=10: cotas 25, 35 e 50", "", "| Cota L1 | Reserva | Ouro final mediana (mín–máx) | Ouro Mercado mediana (mín–máx) | Parcela Mercado mediana (mín–máx) | Unidades vendidas mediana (mín–máx) | Overflow total M/D/G/S | Sementes com overflow M/D/G/S | Produção gathering mediana | Horas-trabalhador pausadas (total N=10) | Equivalentes de ciclo perdidos | Checkpoints pausados/total (N=10) | Pico antes/depois venda | Dias nível 10/25/50 (mediana [mín–máx]) | Nível 50 (IC95% Wilson) |", "|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---|---|"])
    for row in producer:
        overflow = row["overflow_totals_mission_dungeon_gathering_salvage"]
        loss_seeds = row["seeds_with_each_overflow"]
        milestones = "/".join(row["milestone_days_median_range"][level] for level in ("10", "25", "50"))
        ci = row["reached_level_50_wilson_95"]
        lines.append(f"| {row['base_limit']} | {row['reserve']} | {row['ending_gold_median_range']} | {row['market_gold_median_range']} | {row['market_share_percent_median_range']}% | {row['materials_sold_median_range']} | {overflow['mission']}/{overflow['dungeon']}/{overflow['gathering']}/{overflow['salvage']} | {len(loss_seeds['mission'])}/{len(loss_seeds['dungeon'])}/{len(loss_seeds['gathering'])}/{len(loss_seeds['salvage'])} | {row['gathering_produced_median_range']} | {row['gathering_pause_worker_hours_total']} | {row['gathering_missed_cycle_equivalents']} | {row['gathering_pause_checkpoints_total']}/{row['gathering_checkpoints_total']} | {row['pre_sale_inventory_peak_median_range']}/{row['post_sale_inventory_peak_median_range']} | {milestones} | {row['reached_level_50']}/10 ({ci['lower_percent']:.1f}–{ci['upper_percent']:.1f}%) |")
    lines.extend(["", "### Fontes, drenos e recuperação em N=10", "", "| Cota L1 | Reserva | Ouro offline | Missões/contratos | Masmorra/portal | Mercado | Construções/contratações | Desmontagem | Crafting | Crafts | Resíduo não atribuído | Alvos bloqueados depois comprados | Bloqueios no horizonte | Entradas portal/jogador | Drops portal |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in producer:
        sources = row["gross_gold_by_source"]
        drains = row["gold_drenos"]
        lines.append(f"| {row['base_limit']} | {row['reserve']} | {sources['passive_offline']} | {sources['missions']} | {sources['dungeons']} | {sources['market_sales']} | {drains['building_and_hiring']} | {drains['salvage_fees']} | {drains['crafting_fees']} | {row['crafts_completed']} | {row['unattributed_gold_residual']} | {row['recovered_blocked_targets']} | {row['blocked_targets_at_horizon']} | {row['portal_entries']} | {row['portal_loot_equipment_drops']} |")
    lines.extend(["", "### Diferença pareada: base25 menos base50", "", "Valores abaixo são medianas e intervalo mínimo–máximo por seed pareada; números negativos indicam resultado menor em base25.", "", "| Reserva | Ouro final | Ouro Mercado | Materiais vendidos | Overflow missão | Overflow masmorra | Overflow coleta | Overflow desmontagem | Pausa coleta (h-trabalhador) | Pico pré-venda | Dia nível 10 | Dia nível 25 | Dia nível 50 |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in paired:
        def fmt(key):
            item = row[key]
            return f"{item['median']:.1f} ({item['min']:.1f}–{item['max']:.1f})"
        def fmt_item(item):
            return f"{item['median']:.1f} ({item['min']:.1f}–{item['max']:.1f})"
        overflow = row["overflow_25_minus_50"]
        milestone = row["milestone_day_25_minus_50"]
        lines.append(f"| {row['reserve']} | {fmt('ending_gold_25_minus_50')} | {fmt('market_gold_25_minus_50')} | {fmt('materials_sold_25_minus_50')} | {fmt_item(overflow['mission'])} | {fmt_item(overflow['dungeon'])} | {fmt_item(overflow['gathering'])} | {fmt_item(overflow['salvage'])} | {fmt('gathering_pause_hours_25_minus_50')} | {fmt('inventory_pre_sale_peak_25_minus_50')} | {milestone['10']['median']:.1f} | {milestone['25']['median']:.1f} | {milestone['50']['median']:.1f} |")
    lines.extend(["", f"Regra versionada: `{report['quota_progression']}`. A base35 é somente o ponto intermediário experimental, não um novo marco da fórmula."])
    lines.extend(["", "### Leitura e limites", "", "M/D/G/S significa unidades de materiais descartadas por claims reais de missão/contrato, masmorra/portal, coleta e desmontagem, respectivamente, por falta de capacidade. São unidades de loot perdidas (não ouro nominal ou contagem de eventos); os valores vêm dos contadores de overflow dos serviços. Perda de loot continua sendo custo econômico. Pausa é registrada em segundos-trabalhador pelo serviço; convertida para horas-trabalhador, ela mede tempo de coleta que a regra de capacidade não reconhece, não equivale a unidades fixas pois o bônus por ciclo pode variar.", "", "A reserva 30/300 é uma política experimental do harness, não regra do jogador. Ela protege explicitamente materiais excedentes e, portanto, muda venda, ouro, estoque, gathering e capacidade. Nesta rodada usa-se a política representativa de reserva30; análises antigas com reserva300 permanecem separadas como sensibilidade do harness, não uma regra alternativa.", "", "O limite do Mercado 1 equivale a 2,08%, 5,21%, 10,42%, 20,83% ou 52,08% da produção base de 480 unidades de um trabalhador em 8h. A fórmula aprovada acrescenta 5 unidades em níveis múltiplos de cinco: base25 chega a 125 no nível100 (26,04% dessa referência); base50 chega a 150 (31,25%).", "", "O runner tenta participar de portal natal naturalmente ativo em janela online e registra início, claim e loot por serviços reais; uma ocorrência ausente permanece ausente, sem geração forçada. Os contadores distinguem entradas/loot do jogador dos eventos regionais apenas gerados ou expirados. Rebelião continua sem participação do jogador nesta política. A política experimental de crafting fabrica até um equipamento se receita e excedente protegido estiverem disponíveis; isso mede alcance condicional, não aprova uma regra obrigatória. Nenhuma destas amostras fecha estabilidade de longo prazo, softlock global ou gate Stage 5.", "", "## Critério operacional proposto para acompanhamento", "", "A cada perfil e horizonte (30/90/180 dias e nível50), publicar: fontes e drenos brutos/líquidos por tipo; participação do Mercado na renda; unidades por família e proporção da referência offline 8h; estoque final/pico pré-venda/capacidade; overflow M/D/G/S; horas-trabalhador pausadas e unidades descartadas; recuperação do mesmo bloqueio por compra; progressão de níveis 10/25/50; EV dos ciclos fechados de arbitragem. O produto ainda precisa definir faixa aceitável de ouro e inflação para um horizonte longo; sem isso, o indicador mede pressão e perdas, não uma nota binária de equilíbrio.", "", "## Reexecução", "", "```powershell", ".venv-desktop\\Scripts\\python.exe scripts\\balance\\build_market_quota_stability_report.py", "```", ""])
    markdown = "\n".join(lines)
    assert report["quota_progression"] in markdown
    assert "continuously by one fifth" not in markdown
    assert "nenhuma ação de participação/resolução pelo jogador é executada" not in markdown
    assert "total N=10" in markdown and "Pausa mede" in markdown
    for cap in (25, 35, 50):
        row = next(item for item in producer if item["base_limit"] == cap)
        overflow = row["overflow_totals_mission_dungeon_gathering_salvage"]
        assert f"| {cap} | {row['reserve']} | {row['ending_gold_median_range']} | {row['market_gold_median_range']} |" in markdown
        assert f"{overflow['mission']}/{overflow['dungeon']}/{overflow['gathering']}/{overflow['salvage']}" in markdown
        assert f"{row['portal_entries']} | {row['portal_loot_equipment_drops']} |" in markdown
    md_path = REPORTS / "market_quota_stability_2026-10-30.md"
    md_path.write_text(markdown, encoding="utf-8")
    json_path = REPORTS / "market_quota_stability_2026-10-30.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "report_id": report["report_id"],
        "inputs": [{**source, "sha256": hashlib.sha256((REPORTS / f"{source['stem']}.json").read_bytes()).hexdigest()}
                   for source in source_reports],
        "outputs": {name: hashlib.sha256((REPORTS / name).read_bytes()).hexdigest()
                    for name in (md_path.name, json_path.name)},
        "consistency_assertions": {
            "source_journey_errors": 0, "n10_journeys_per_quota": 10,
            "json_markdown_overflow_totals": True, "json_markdown_portal_totals": True,
            "json_csv_overflow_and_pause_by_seed_day": True, "per_journey_markdown_rows": True,
            "formula_and_examples_match": True, "portal_participation_description_consistent": True,
        },
    }
    (REPORTS / "market_quota_stability_2026-10-30.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print("reports/market_quota_stability_2026-10-30.md")


if __name__ == "__main__":
    main()
