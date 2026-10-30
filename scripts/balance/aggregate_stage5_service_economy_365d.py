"""Combine the five N=5 full-horizon service journey profile reports."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from statistics import median
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports"
STEM = "stage5_service_economy_365d_n5_2026-10-30"
DATE = "2026-10-30"
PROFILES = ("ativo", "casual", "offline", "produtor", "combate")
SOURCE_KEYS = ("passive_offline", "missions", "dungeons", "market_sales")
DRAIN_KEYS = ("building_and_hire_purchases", "salvage_fees", "crafting_fees")


def _housing_level(journey: dict) -> int:
    return max((int(str(row.get("item", "housing_0")).split("_")[-1])
                for row in journey.get("purchases", [])
                if str(row.get("item", "")).startswith("housing_")), default=0)


def aggregate() -> dict:
    reports = []
    for profile in PROFILES:
        path = REPORT_DIR / f"stage5_service_economy_365d_n5_{profile}_{DATE}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if len(data.get("journeys", [])) != 5:
            raise RuntimeError(f"{profile}: expected 5 final journeys, found {len(data.get('journeys', []))}.")
        if data.get("journey_errors"):
            raise RuntimeError(f"{profile}: has service journey errors.")
        if any(row.get("days") != 365 or row.get("stop_reason") != "full_horizon"
               or row.get("budget_exhausted") for row in data["journeys"]):
            raise RuntimeError(f"{profile}: at least one journey did not complete the 365-day horizon.")
        nonzero = [(row["seed"], day.get("day"), int(day["gold_ledger"].get("unattributed_residual", 0)))
                   for row in data["journeys"] for day in row.get("daily", [])
                   if int(day.get("gold_ledger", {}).get("unattributed_residual", 0)) != 0]
        if nonzero:
            raise RuntimeError(f"{profile}: per-day gold ledger residuals are nonzero: {nonzero[:10]}.")
        for row in data["journeys"]:
            identities = [(action.get("kind"), action.get("id")) for action in row.get("actions", [])
                          if action.get("id") is not None]
            if len(identities) != len(set(identities)):
                raise RuntimeError(f"{profile} seed {row['seed']}: duplicated action IDs in final journey.")
        reports.append(data)

    journeys = [row for report in reports for row in report["journeys"]]
    cell_summaries = {key: value for report in reports for key, value in report["cell_summaries"].items()}
    errors = [error for report in reports for error in report.get("journey_errors", [])]
    ledger_totals = {}
    portal_eligibility = {}
    service_rejections_by_profile = {}
    gold_ledger_reconciliation_by_journey = []
    for profile in PROFILES:
        rows = [row for row in journeys if row["profile"] == profile]
        totals = {key: 0 for key in (*SOURCE_KEYS, *DRAIN_KEYS, "observed_delta", "unattributed_residual")}
        for row in rows:
            journey_residual = 0
            nonzero_days = []
            for day in row["daily"]:
                for key in totals:
                    totals[key] += int(day["gold_ledger"].get(key, 0))
                day_residual = int(day["gold_ledger"].get("unattributed_residual", 0))
                journey_residual += day_residual
                if day_residual:
                    nonzero_days.append(int(day["day"]))
            gold_ledger_reconciliation_by_journey.append({
                "profile": profile, "seed": int(row["seed"]), "days": int(row["days"]),
                "nonzero_residual_days": nonzero_days, "unattributed_residual_total": journey_residual,
            })
        ledger_totals[profile] = totals
        diagnostics = [entry for row in rows for entry in row.get("portal_eligibility_diagnostics", [])]
        blocked = Counter(entry.get("reason", "unspecified") for entry in diagnostics
                          if entry.get("status") == "blocked")
        portal_eligibility[profile] = {
            "checks_by_status": dict(Counter(entry.get("status", "unknown") for entry in diagnostics)),
            "blocked_reasons": dict(blocked), "diagnostic_events": len(diagnostics),
            "player_portal_entries": sum(action.get("kind") == "portal"
                                          for row in rows for action in row.get("actions", [])),
        }
        rejections = [(int(row["seed"]), entry) for row in rows
                      for entry in row.get("service_rejections", [])]
        reasons = Counter((str(entry.get("service", "unknown")), str(entry.get("reason", "unspecified")))
                          for _seed, entry in rejections)
        service_rejections_by_profile[profile] = {
            "count": len(rejections),
            "by_reason": [
                {"service": service, "reason": reason, "count": count}
                for (service, reason), count in sorted(reasons.items())
            ],
            "by_seed": {
                str(seed): sum(entry_seed == seed for entry_seed, _entry in rejections)
                for seed in sorted({entry_seed for entry_seed, _entry in rejections})
            },
        }

    combined = {
        "report_id": "gim-stage5-service-economy-365d-n5-20261030-v1",
        "generated_at_utc": max(report["generated_at_utc"] for report in reports),
        "profiles": list(PROFILES), "runs_per_profile": 5, "paths": ["roster_first"],
        "horizon_days": 365, "full_horizon": True,
        "max_wall_seconds_per_journey": max(float(report["max_wall_seconds"]) for report in reports),
        "max_wall_seconds_by_profile": {report["profiles"][0]["name"]: float(report["max_wall_seconds"])
                                        for report in reports},
        "market_reserve_base": 30,
        "craft_policy": "first_surplus_equipment_once", "market_material_quota_per_24h_at_level_1": 25,
        "disposable_databases": True, "real_user_saves_opened": False,
        "source_reports": [f"stage5_service_economy_365d_n5_{p}_{DATE}.json" for p in PROFILES],
        "all_25_journeys_valid": len(journeys) == 25 and not errors,
        "journey_merge_policy": "each seed is represented once; corrected seeds replace the complete prior row and ledger",
        "journey_errors": errors, "journeys": journeys, "cell_summaries": cell_summaries,
        "gold_ledger_totals_by_profile": ledger_totals,
        "gold_ledger_reconciliation_by_journey": gold_ledger_reconciliation_by_journey,
        "service_rejections_by_profile": service_rejections_by_profile,
        "portal_eligibility_by_profile": portal_eligibility,
        "limitations": [
            "N=5 per profile is exploratory; reported intervals describe this sample and do not establish rare-event rates, useful P95, whole-game stability, or absence of a permanent softlock.",
            "Daily actions use an explicit roster-first simulator policy, a fixed material reserve of 30 units per family, and at most one optional affordable craft; these are harness choices.",
            "Rebellion invite acceptance is exercised in a separate service integration audit. This journey policy does not accept rebellions; it records natural opportunities and activations.",
            "Portal entry and claims use real services only when a fresh-save party meets the frozen event snapshot during an online window. Funded late-game success/failure/expiry is reported separately.",
            "An organic fresh-save journey reaching housing level 100 would be required to claim access to 20 slots. The separate funded route injects the quoted funds into a disposable save and calls the upgrade service 50 times.",
        ],
    }
    (REPORT_DIR / f"{STEM}.json").write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ledger_path = REPORT_DIR / f"{STEM}.ledger.csv"
    sources = [REPORT_DIR / f"stage5_service_economy_365d_n5_{p}_{DATE}.ledger.csv" for p in PROFILES]
    with ledger_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = None
        for source in sources:
            with source.open("r", encoding="utf-8-sig", newline="") as input_file:
                reader = csv.DictReader(input_file)
                if writer is None:
                    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
                    writer.writeheader()
                writer.writerows(reader)

    lines = ["# Economia Stage 5 por serviços reais — horizonte 365d, N=5 por perfil", "",
             "Cinco seeds independentes por perfil; uma política `roster_first`; execução até 365 dias com serviços reais em campanhas SQLite temporárias. Saldo final, loot, compras, salvamento, vendas, conquistas, eventos e sinks entram quando ocorrem.", "",
             "| Perfil | N | Guilda 50 | Alvos planejados completos | Guilda final | Craft(s) | Masmorras tentadas/vencidas | Entradas portal | Portal criado/fechado | Rebeliões ativadas/oportunidades | Bloqueado→comprado | Bloqueios finais | Maior housing | Regional cycles s (p50; faixa) | Ouro final p50 (IC95% descritivo) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for profile in PROFILES:
        rows = [row for row in journeys if row["profile"] == profile]
        summary = cell_summaries[f"{profile}/roster_first"]
        portal_actions = sum(action.get("kind") == "portal" for row in rows for action in row.get("actions", []))
        portal_created = sum(int(row["regional_event_opportunities"]["portal_created"]) for row in rows)
        portal_closed = sum(int(row["regional_event_opportunities"]["portal_resolved"]) for row in rows)
        rebellions = sum(int(row["regional_event_opportunities"]["rebellion_activated"]) for row in rows)
        opportunities = sum(int(row["regional_event_opportunities"]["rebellion_eligible_region_cycles"]) for row in rows)
        complete = sum(bool(row["planned_upgrade_targets_complete"]) for row in rows)
        reached = sum(bool(row["reached_level_50"]) for row in rows)
        crafts = sum(int(row.get("crafts_completed", 0)) for row in rows)
        highest_housing = max((_housing_level(row) for row in rows), default=0)
        regional_seconds = [float(row.get("stage_seconds", {}).get("regional_cycles", 0)) for row in rows]
        ending = summary["ending_gold_p50_ci95"]
        lines.append(f"| {profile} | {len(rows)} | {reached}/5 | {complete}/5 | {min(row['guild_level'] for row in rows)}–{max(row['guild_level'] for row in rows)} | {crafts} | {summary['dungeons']['attempts']}/{summary['dungeons']['wins']} | {portal_actions} | {portal_created}/{portal_closed} | {rebellions}/{opportunities} | {summary['same_upgrade_blocked_then_bought_total']} | {summary['blocked_targets_at_horizon_total']} | {highest_housing} | {median(regional_seconds):.1f}; {min(regional_seconds):.1f}–{max(regional_seconds):.1f} | {ending['median']:.0f} ({ending['lower_95']:.0f}–{ending['upper_95']:.0f}) |")

    lines.extend(["", "## Ouro: fontes e drenos registrados", "",
                  "Totais somados nas cinco campanhas do perfil; residual zero reconcilia as alterações de ouro contabilizadas com o delta diário. Valores agregados não significam renda média por dia nem aprovação de faixa econômica.",
                  "", "| Perfil | Passivo offline | Missões/contratos | Masmorras/portais | Market | Compras edifício/contratação | Taxas salvage | Craft | Delta observado | Resíduo |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for profile in PROFILES:
        t = ledger_totals[profile]
        lines.append(f"| {profile} | {t['passive_offline']} | {t['missions']} | {t['dungeons']} | {t['market_sales']} | {t['building_and_hire_purchases']} | {t['salvage_fees']} | {t['crafting_fees']} | {t['observed_delta']} | {t['unattributed_residual']} |")

    lines.extend(["", "## Reconciliação por seed", "",
                  "Validação seed a seed e dia a dia; a agregação é bloqueada se qualquer valor de resíduo for diferente de zero.",
                  "", "| Perfil | Seed | Dias | Dias com resíduo | Resíduo total |", "|---|---:|---:|---:|---:|"])
    for item in gold_ledger_reconciliation_by_journey:
        lines.append(f"| {item['profile']} | {item['seed']} | {item['days']} | {len(item['nonzero_residual_days'])} | {item['unattributed_residual_total']} |")

    lines.extend(["", "## Recusas e rejeições opcionais", "",
                  "A contagem inclui o motivo literal e a seed. Falhas do serviço são isoladas em savepoint; pré-checks atualizados podem bloquear uma ação antes da chamada. O agregador exige resíduo diário zero em cada uma das 25 trajetórias.",
                  "", "| Perfil | Registros | Motivos (etapa: mensagem × contagem) |", "|---|---:|---|"])
    for profile in PROFILES:
        summary = service_rejections_by_profile[profile]
        reasons = "; ".join(
            f"{item['service']}: {item['reason']} × {item['count']}"
            for item in summary["by_reason"]
        ) or "—"
        lines.append(f"| {profile} | {summary['count']} | {reasons} |")

    lines.extend(["", "## Entrada natural em portais", "",
                  "O runner registra gates do snapshot por portal ativo que foi avaliado; isso explica ausência de entrada. A bateria financiada separada testa sucesso/falha e claim idempotente sem inferir acessibilidade fresh-save.",
                  "", "| Perfil | Eventos diagnosticados | Elegíveis | Bloqueados e motivo mais frequente | Entradas reais |", "|---|---:|---:|---|---:|"])
    for profile in PROFILES:
        diag = portal_eligibility[profile]
        reasons = diag["blocked_reasons"]
        reason = max(reasons, key=reasons.get) if reasons else "—"
        status = diag["checks_by_status"]
        lines.append(f"| {profile} | {diag['diagnostic_events']} | {status.get('eligible', 0)} | {sum(reasons.values())}; {reason} | {diag['player_portal_entries']} |")

    recoveries = []
    for row in journeys:
        for item, detail in row.get("blocked_upgrades", {}).items():
            if detail.get("recovered_day") is not None:
                recoveries.append((int(detail.get("day", 0)), int(detail["recovered_day"]), row["profile"], row["seed"], item, detail))
    if recoveries:
        day, recovered_day, profile, seed, item, detail = min(recoveries, key=lambda record: (record[0], record[1], record[4]))
        lines.extend(["", "## Exemplo bloqueado e recuperado", "",
                      f"Na primeira ocorrência observada, **{item}** no perfil {profile}, seed {seed}, bloqueou no dia {day} por falta de {detail['gold_shortfall']} ouro, guilda {detail['guild_level_shortfall']} níveis abaixo do requisito e materiais `{detail['material_shortfalls']}`. A mesma melhoria foi comprada no dia {recovered_day}. Esta é recuperação observada dentro da política, não prova de que todos os bloqueios do jogo sejam temporários."])
    housing_reach = [f"{p}: nível {max((_housing_level(r) for r in journeys if r['profile'] == p), default=0)}"
                     for p in PROFILES]
    lines.extend(["", "## Alojamento nível 100 e as 20 vagas", "",
                  "Housing max alcançado nas cinco jornadas de cada perfil: " + "; ".join(housing_reach) + ". Se nenhum chegar a 100, as 20 vagas permanecem conteúdo tardio; a rota financiada via 50 chamadas do serviço está demonstrada separadamente.",
                  "", "N=5 não sustenta uma estimativa de P95; por isso este relatório não apresenta P95. O IC da mediana de ouro e os intervalos Wilson são descrições exploratórias da amostra. Os cinco arquivos individuais preservam checkpoints e evidência por perfil; o CSV adjacente reúne todos os ledgers diários.",
                  "", "Nenhum save real foi aberto. Veja também [participação real em eventos](stage5_event_participation_runtime_2026-10-30.md), [loot regional de chefes](stage5_regional_boss_loot_runtime_2026-10-30.md), [arbitragem por serviços reais](stage5_arbitrage_service_loops_2026-10-30.md), [rota financiada do Alojamento](stage5_buildings_51_100_2026-10-30.md) e [orçamento regional de catch-up](stage5_catchup_operational_budget_2026-10-30.md).", ""])
    (REPORT_DIR / f"{STEM}.md").write_text("\n".join(lines), encoding="utf-8")
    return combined


if __name__ == "__main__":
    data = aggregate()
    print(f"aggregated {len(data['journeys'])} journeys; errors={len(data['journey_errors'])}")
