"""Paired funded-path simulation with real mission drops and inventory sources."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.balance.compare_funded_path_strategies import PATHS
from scripts.balance.funded_progression_simulation import (
    STRATEGIES, bootstrap_median_ci_95, run_funded_simulation, wilson_interval_95,
)


def _purchase_day(row: dict[str, object], item: str) -> int | None:
    return next((int(purchase["day"]) for purchase in row["purchases"]
                 if purchase["item"] == item), None)


def _trajectory_recovery(row: dict[str, object]) -> dict[str, object]:
    purchases = row["purchases"]
    first_block_by_item: dict[str, dict[str, object]] = {}
    for day in row["daily_ledger"]:
        req = day.get("next_purchase_requirements")
        if not req or not (int(req["gold_shortfall"])
                           or int(req["guild_level_shortfall"])
                           or any(int(v) for v in req["material_shortfalls"].values())):
            continue
        first_block_by_item.setdefault(str(req["item"]), {"day": int(day["day"]), "requirements": req})
    out = []
    for item, block in first_block_by_item.items():
        purchased = next((purchase for purchase in purchases
                          if purchase["item"] == item and int(purchase["day"]) > int(block["day"])), None)
        if purchased is None:
            continue
        start, end = int(block["day"]), int(purchased["day"])
        interval = [d for d in row["daily_ledger"] if start <= int(d["day"]) <= end]
        out.append({
            "item": item, "blocked_day": start, "purchased_day": end,
            "days_until_purchase": end - start,
            "block_snapshot": block["requirements"],
            "interval_actions": {
                "contract_gold": sum(int(d["contract_gold"]) for d in interval),
                "offline_gold": sum(int(d["offline_gold"]) for d in interval),
                "mission_material_units_stored": sum(int(d["mission_material_drop_stored_today"]) for d in interval),
                "gathered": {family: sum(int(d["materials_gathered"].get(family, 0)) for d in interval)
                             for family in ("wood", "ore", "leather")},
            },
            "interpretation": "A mesma compra foi bloqueada e depois concluída; ações no intervalo são coocorrências, não atribuição causal.",
        })
    return {"recovered_blocked_purchases": out,
            "unrecovered_blocked_items": sorted(set(first_block_by_item) - {r["item"] for r in out})}


def _profile_summary(rows: list[dict[str, object]], strategy: dict[str, object], *, seed: int) -> dict[str, object]:
    n = len(rows)
    completed = [r for r in rows if r["target_plan_complete"]]
    level50 = [r for r in rows if r["level_50_day"] is not None]
    first_gears = [int(r["first_gear_drop_day"]) for r in rows if r["first_gear_drop_day"] is not None]
    gate_days = [int(r["first_dungeon_gate_open_day"]) for r in rows if r["first_dungeon_gate_open_day"] is not None]
    offer_days = [int(r["first_dungeon_board_offer_day"]) for r in rows if r["first_dungeon_board_offer_day"] is not None]
    all_recoveries = [_trajectory_recovery(r) for r in rows]
    drop_rolls = sum(int(r["material_drop_roll_count"]) for r in rows)
    drop_awards = sum(int(r["material_drop_award_count"]) for r in rows)
    return {
        "n": n,
        "level_50_reached": len(level50), "level_50_rate_wilson_95": wilson_interval_95(len(level50), n),
        "level_50_day_p50": median([float(r["level_50_day"]) for r in level50]) if level50 else None,
        "plan_complete_including_scouts_1": len(completed),
        "plan_complete_rate_wilson_95": wilson_interval_95(len(completed), n),
        "first_realized_equipment_drop_day": {"n": len(first_gears), "p50": median(first_gears) if first_gears else None},
        "first_scouts_1_dungeon_gate_open_day": {"n": len(gate_days), "p50": median(gate_days) if gate_days else None},
        "first_eligible_dungeon_board_offer_day": {"n": len(offer_days), "p50": median(offer_days) if offer_days else None},
        "dungeon_execution": "Não simulado; os campos medem apenas gate aberto e oferta de board elegível, sem run ou recompensa.",
        "mission_material_drop_rolls_conditional_on_successful_missions": drop_rolls,
        "mission_material_drop_awards": drop_awards,
        "mission_material_award_rate_per_roll_wilson_95": wilson_interval_95(drop_awards, drop_rolls),
        "mission_material_units_stored": sum(int(r["material_drop_stored_total"]) for r in rows),
        "mission_material_units_discarded_by_capacity": sum(int(r["material_drop_discarded_total"]) for r in rows),
        "material_sources_realized": {
            family: {
                "gathered": sum(sum(int(d["materials_gathered"].get(family, 0)) for d in r["daily_ledger"]) for r in rows),
                "spent_on_buildings": sum(sum(int(d["materials_spent"].get(family, 0)) for d in r["daily_ledger"]) for r in rows),
                "ending_p50": median([int(r["balances_at_end"]["materials"].get(family, 0)) for r in rows]) if rows else 0,
            } for family in ("wood", "ore", "leather", "crystals")
        },
        "special_crystals_earned_total_not_building_material": sum(
            sum(int(d["special_crystals_earned"]) for d in r["daily_ledger"]) for r in rows),
        "inventory_peak_used_p50": median([
            max((int(d["inventory_peak_used"]) for d in r["daily_ledger"]), default=0) for r in rows
        ]) if rows else 0,
        "inventory_capacity_p50": median([int(r["balances_at_end"]["inventory_capacity"]) for r in rows]) if rows else 0,
        "blocked_upgrade_recovery": {
            "same_item_blocked_then_purchased": sum(len(x["recovered_blocked_purchases"]) for x in all_recoveries),
            "trajectory_count_with_unrecovered_block": sum(bool(x["unrecovered_blocked_items"]) for x in all_recoveries),
            "samples": all_recoveries,
        },
        "realized_first_gear_by_seed": {str(r["seed"]): r["first_gear_drop_day"] for r in rows},
        "first_dungeon_gate_by_seed": {str(r["seed"]): r["first_dungeon_gate_open_day"] for r in rows},
    }


def build_report(*, runs_per_profile: int, seed_start: int, max_days: int,
                 path_reports: dict[str, dict[str, object]]) -> dict[str, object]:
    profiles = {}
    for profile_index, strategy in enumerate(STRATEGIES):
        name = str(strategy["name"])
        variants = {}
        for path, report in path_reports.items():
            rows = [r for r in report["raw_trajectories"] if r["strategy"] == name]
            variants[path] = _profile_summary(rows, strategy, seed=seed_start + profile_index * 100_000)
        path_rows = {
            path: {str(r["seed"]): r for r in report["raw_trajectories"] if r["strategy"] == name}
            for path, report in path_reports.items()
        }
        shared = sorted(set(path_rows["roster_first"]) & set(path_rows["office_after_minimum_party"]))
        paired = {}
        for metric in ("level_50_day", "first_gear_drop_day", "first_dungeon_gate_open_day",
                       "first_dungeon_board_offer_day"):
            deltas = []
            for seed_key in shared:
                a = path_rows["roster_first"][seed_key].get(metric)
                b = path_rows["office_after_minimum_party"][seed_key].get(metric)
                if a is not None and b is not None:
                    deltas.append(float(b) - float(a))
            paired[metric + "_alternative_minus_roster_first"] = {
                "n_both_observed": len(deltas),
                "median_days": median(deltas) if deltas else None,
                "median_ci_95": bootstrap_median_ci_95(
                    deltas, seed=seed_start + profile_index * 100_000 + len(paired) + 77,
                ),
            }
        variants["paired_sample"] = {"n": runs_per_profile, "seed_first": seed_start + profile_index * 100_000,
                                      "seed_last": seed_start + profile_index * 100_000 + runs_per_profile - 1,
                                      "same_seed_across_paths": shared == sorted(path_rows["roster_first"]),
                                      "paired_deltas_alternative_minus_roster_first": paired}
        profiles[name] = variants
    return {
        "report_id": "gim-stage5-integrated-funded-paths-20261029-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs_per_profile_path": runs_per_profile,
        "seed_start": seed_start,
        "max_days": max_days,
        "paths": PATHS,
        "profile_results": profiles,
        "interpretation": {
            "scope": "Trajetória financiada de compras do nível 1 ao 50; snapshots atuais dos boards natais seedados; escolha/sucesso/recompensas de missão e RNG de drops condicionais via _cycle_outcome; limite real de inventário e aliases de materiais; gathering-base; gate Exploradores 1 e oportunidade de board elegível.",
            "mission_resolution": "A escolha e o sucesso de missão usam a política do simulador _cycle_outcome sobre snapshots materializados de board, não mission_service.start/resolve_mission. O modelo aplica a chance de sucesso do snapshot e os bônus selecionados de recompensa do Office e XP do Training; omite bônus de sucesso/drop de profissão e habilidades, uso de equipamento e efeitos transacionais de persistência/coleta.",
            "mercenary_level_assumption": "A elegibilidade de nível de mercenários em missões e masmorras lê os valores reais de Mercenary.level do melhor grupo legal abstrato. O elenco sintético é sincronizado de forma otimista ao nível da guilda uma vez por dia simulado por _sync_abstract_roster; XP individual, RNG de nível ao recrutar e progressão de classe não são modelados. Os dias de gate/oferta dependem dessa aproximação, não de mercenários com progressão independente.",
            "gathering_assumption": "Gathering usa o ciclo-base do serviço de 60 segundos, uma unidade por ciclo, templates seedados reais, limite de inventário e sincronização dos materiais. Trabalhadores sintéticos não têm profissão; portanto, o extra_chance por profissão compatível é 0% e o RNG determinístico por ciclo não acrescenta unidade. O modelo não executa checkpoints de advance_assignment, seeds de assignment nem transações completas de pausa/retomada; representa gathering-base sem bônus de profissão.",
            "drop_rates": "Catalog chances are rolled only after successful mission actions; reported conditional catalog rates and realized attempts/awards are distinct.",
            "blocker_recovery": "Only the same purchase observed blocked then later purchased is counted. Other actions in that interval are correlation, not causal recovery attribution.",
            "dungeon": "Gate and eligible board offer only; dungeon run, completion, and reward tables remain out of model.",
            "regional_events": "Portal and rebellion progression/rewards remain unmodeled; no event day is estimated. Confirmed design assumptions: rebellion 2% per eligible Vigília; portal's 3h TTL runs during offline catch-up.",
            "hard_softlock": "Not proven globally. This is a more connected finite policy path; market sales, salvage, dungeon rewards, player choices, regional event rewards, recruitment RNG, and optional-building paths are excluded.",
            "sample_limits": f"N={runs_per_profile} seeds pareadas por perfil e caminho. Os intervalos são publicados; a exclusão de eventos raros permanece fraca neste N. É evidência analítica, não aceite de Stage 5.",
        },
        "source_reports": {path: report["source"] for path, report in path_reports.items()},
    }


def enrich_report(report: dict[str, object]) -> dict[str, object]:
    """Add compact same-purchase blocker summaries from retained trajectory samples."""
    report["interpretation"]["sample_limits"] = (
        f"N={report['runs_per_profile_path']} seeds pareadas por perfil e caminho. "
        "Os intervalos são publicados; a exclusão de eventos raros permanece fraca neste N. "
        "É evidência analítica, não aceite de Stage 5."
    )
    for profile_index, variants in enumerate(report["profile_results"].values()):
        for path_index, path in enumerate(("roster_first", "office_after_minimum_party")):
            recovery = variants[path]["blocked_upgrade_recovery"]
            recovery["unrecovered_trajectory_rate_wilson_95"] = wilson_interval_95(
                int(recovery["trajectory_count_with_unrecovered_block"]), int(variants[path]["n"]),
            )
            grouped: dict[str, list[dict[str, object]]] = {}
            for sample in recovery["samples"]:
                for item in sample["recovered_blocked_purchases"]:
                    grouped.setdefault(str(item["item"]), []).append(item)
            by_item = {}
            for item, entries in sorted(grouped.items()):
                blocked = [entry["block_snapshot"] for entry in entries]
                intervals = [entry["interval_actions"] for entry in entries]
                base_seed = int(report["seed_start"]) + profile_index * 100_000 + path_index * 17
                by_item[item] = {
                    "recovered_count": len(entries),
                    "days_until_purchase_p50": median([int(entry["days_until_purchase"]) for entry in entries]),
                    "initial_gold_shortfall_p50": median([int(entry["gold_shortfall"]) for entry in blocked]),
                    "initial_material_shortfall_p50": {
                        family: median([int(entry["material_shortfalls"].get(family, 0)) for entry in blocked])
                        for family in ("wood", "ore", "crystals")
                    },
                    "interval_cooccurrence_totals": {
                        "contract_gold": sum(int(entry["contract_gold"]) for entry in intervals),
                        "offline_gold": sum(int(entry["offline_gold"]) for entry in intervals),
                        "mission_material_units_stored": sum(int(entry["mission_material_units_stored"]) for entry in intervals),
                        "gathered": {family: sum(int(entry["gathered"][family]) for entry in intervals)
                                     for family in ("wood", "ore", "leather")},
                    },
                    "days_until_purchase_median_ci_95": bootstrap_median_ci_95(
                        [float(entry["days_until_purchase"]) for entry in entries], seed=base_seed + len(by_item)),
                }
            recovery["by_item"] = by_item
    return report


def render_markdown(report: dict[str, object]) -> str:
    def rate_text(successes: int, interval: dict[str, object]) -> str:
        return (f"{successes}/{interval['n']} ({interval['rate_percent']:.0f}%; IC95% "
                f"{interval['lower_percent']:.0f}–{interval['upper_percent']:.0f}%)")

    lines = [
        "# Simulação integrada de trajetórias financiadas — Stage 5", "",
        f"Executada em {report['generated_at_utc']} · N={report['runs_per_profile_path']} seeds pareadas por perfil/estratégia · seeds {report['seed_start']}–{report['seed_start'] + 400_000 + report['runs_per_profile_path'] - 1} · horizonte até {report['max_days']} dias.", "",
        "Usa boards regionais materializados pelo serviço atual, mas política de missão/sucesso e saque implementada pelo simulador _cycle_outcome. Materiais entram no inventário pelo limite e pelos aliases reais do serviço. Compara roster-first com Office após o grupo mínimo e inclui Exploradores 1 para observar gate e oferta de masmorra.", "",
        "## Resultados por perfil e caminho", "",
        "| Perfil | Caminho | Nível 50 | Dia p50 | Plano + Exploradores 1 | Primeiro equipamento drop p50 | Gate dungeon Scouts 1 p50 | Oferta elegível p50 | Rolls de material / prêmios | Guardados / descartados | Pico estoque / capacidade |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for profile, rows in report["profile_results"].items():
        for path in ("roster_first", "office_after_minimum_party"):
            row = rows[path]
            first_gear = row["first_realized_equipment_drop_day"]["p50"]
            gate = row["first_scouts_1_dungeon_gate_open_day"]["p50"]
            offer = row["first_eligible_dungeon_board_offer_day"]["p50"]
            gear_n = row["first_realized_equipment_drop_day"]["n"]
            gate_n = row["first_scouts_1_dungeon_gate_open_day"]["n"]
            offer_n = row["first_eligible_dungeon_board_offer_day"]["n"]
            level50 = rate_text(row["level_50_reached"], row["level_50_rate_wilson_95"])
            complete = rate_text(row["plan_complete_including_scouts_1"], row["plan_complete_rate_wilson_95"])
            lines.append(f"| {profile} | {path} | {level50} | {row['level_50_day_p50'] if row['level_50_day_p50'] is not None else '—'} | {complete} | {first_gear if first_gear is not None else '—'} (n={gear_n}) | {gate if gate is not None else '—'} (n={gate_n}) | {offer if offer is not None else '—'} (n={offer_n}) | {row['mission_material_drop_rolls_conditional_on_successful_missions']} / {row['mission_material_drop_awards']} | {row['mission_material_units_stored']} / {row['mission_material_units_discarded_by_capacity']} | {row['inventory_peak_used_p50']} / {row['inventory_capacity_p50']} |")
    lines.extend(["", "### Diferenças pareadas (Office após grupo mínimo − roster-first)", "", "| Perfil | Nível 50, dias (IC95%) | Gate Scouts 1, dias (IC95%) | Oferta elegível, dias (IC95%) |", "|---|---:|---:|---:|"])
    for profile, rows in report["profile_results"].items():
        paired = rows["paired_sample"]["paired_deltas_alternative_minus_roster_first"]
        def delta(metric: str) -> str:
            row = paired[metric]
            ci = row["median_ci_95"]
            return "—" if row["median_days"] is None else f"{row['median_days']:+.1f} ({ci['lower_95']:+.1f}–{ci['upper_95']:+.1f}; n={row['n_both_observed']})"
        lines.append(f"| {profile} | {delta('level_50_day_alternative_minus_roster_first')} | {delta('first_dungeon_gate_open_day_alternative_minus_roster_first')} | {delta('first_dungeon_board_offer_day_alternative_minus_roster_first')} |")
    lines.extend(["", "## Materiais e recuperação de bloqueios", "", "Os roll counts abaixo acontecem somente após uma missão bem-sucedida e medem tentativas do catálogo; não equivalem à chance acumulada por dia. Itens descartados excederam a capacidade compartilhada. A métrica de recuperação exige que a mesma compra apareça bloqueada e depois seja comprada; ações registradas no intervalo são coocorrências, sem atribuição causal.", ""])
    for profile, rows in report["profile_results"].items():
        for path in ("roster_first", "office_after_minimum_party"):
            row = rows[path]
            mats = row["material_sources_realized"]
            top_block = sorted(row["blocked_upgrade_recovery"].get("by_item", {}).items(),
                               key=lambda pair: pair[1]["recovered_count"], reverse=True)[:2]
            top_text = ", ".join(f"{item}: {data['recovered_count']} compras, atraso p50 {data['days_until_purchase_p50']}d"
                                  for item, data in top_block) or "sem compra bloqueada depois recuperada"
            recovery = row["blocked_upgrade_recovery"]
            unresolved_ci = recovery["unrecovered_trajectory_rate_wilson_95"]
            lines.append(f"- **{profile}/{path}:** madeira gather {mats['wood']['gathered']}, gasto {mats['wood']['spent_on_buildings']}; minério gather {mats['ore']['gathered']}, gasto {mats['ore']['spent_on_buildings']}; cristais de prédio gasto {mats['crystals']['spent_on_buildings']}, saldo p50 {mats['crystals']['ending_p50']}; especiais offline {row['special_crystals_earned_total_not_building_material']}; mesmas compras bloqueadas e depois concluídas {recovery['same_item_blocked_then_purchased']}; trajetórias com bloqueio não resolvido {recovery['trajectory_count_with_unrecovered_block']}/{row['n']} (limite superior Wilson {unresolved_ci['upper_percent']:.1f}%); bloqueios mais comuns: {top_text}.")
    success_low = wilson_interval_95(report["runs_per_profile_path"], report["runs_per_profile_path"])["lower_percent"]
    zero_event_upper = wilson_interval_95(0, report["runs_per_profile_path"])["upper_percent"]
    lines.extend(["", "## Limites e hipóteses do modelo", "", "As chances do catálogo são sorteadas apenas após uma ação bem-sucedida; chance condicional e tentativas/prêmios observados ficam separadas.", report["interpretation"]["mission_resolution"], report["interpretation"]["mercenary_level_assumption"], report["interpretation"]["gathering_assumption"], "Somente gate e oferta elegível de masmorra são medidos; não há execução, conclusão ou loot de masmorra.", "Portais/rebeliões e suas recompensas não entram na trajetória; nenhum dia de evento é estimado. Regras confirmadas: rebelião 2% por Vigília elegível; prazo do portal de 3h corre durante catch-up offline.", "A evidência cobre uma rota financiada finita; venda, desmontagem, recompensas de masmorra, escolhas do jogador, eventos regionais, RNG real de contratação e rotas de melhorias opcionais continuam fora. Hard softlock global não está provado.", f"N={report['runs_per_profile_path']} seeds pareadas por perfil e caminho. Mesmo {report['runs_per_profile_path']}/{report['runs_per_profile_path']} sucessos deixa limite inferior Wilson de {success_low:.1f}%; zero bloqueios persistentes deixa limite superior de {zero_event_upper:.1f}%. É evidência analítica, não aceite de Stage 5.", "", "## Reprodução", "", "```powershell", f".venv\\Scripts\\python.exe scripts\\balance\\simulate_integrated_stage5_paths.py --runs-per-profile {report['runs_per_profile_path']} --seed-start {report['seed_start']} --max-days {report['max_days']}", "```", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-per-profile", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=2026102900)
    parser.add_argument("--max-days", type=int, default=365)
    args = parser.parse_args()
    path_reports = {}
    partial_paths = []
    for path in ("roster_first", "office_after_minimum_party"):
        print(f"Running integrated funded path {path}...", flush=True)
        path_reports[path] = run_funded_simulation(
            runs_per_strategy=args.runs_per_profile, seed_start=args.seed_start,
            max_days=args.max_days, path_variant=path,
            integrate_item_sources=True, include_scouts_objective=True,
        )
        checkpoint = ROOT / "reports" / f"integrated_funded_stage5_{path}.partial.json"
        checkpoint.write_text(json.dumps(path_reports[path], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        partial_paths.append(checkpoint)
        print(f"Checkpoint: {checkpoint}", flush=True)
    report = enrich_report(build_report(runs_per_profile=args.runs_per_profile, seed_start=args.seed_start,
                                        max_days=args.max_days,
                                        path_reports=path_reports))
    stem = ROOT / "reports" / "integrated_funded_stage5_2026-10-29"
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    for checkpoint in partial_paths:
        checkpoint.unlink(missing_ok=True)
    print(f"JSON: {stem.with_suffix('.json')}")
    print(f"Markdown: {stem.with_suffix('.md')}")


if __name__ == "__main__":
    main()
