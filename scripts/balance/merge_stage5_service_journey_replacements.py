"""Replace incomplete or ledger-invalid journey seeds with validated reruns."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.balance.simulate_stage5_service_journeys import summarize


def _residuals(journey: dict) -> tuple[int, list[dict]]:
    bad = [day for day in journey.get("daily", [])
           if int(day.get("gold_ledger", {}).get("unattributed_residual", 0)) != 0]
    return sum(int(day.get("gold_ledger", {}).get("unattributed_residual", 0))
               for day in journey.get("daily", [])), bad


def _atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def merge(profile: str, base_json: Path, replacement_jsons: list[Path]) -> dict:
    base = json.loads(base_json.read_text(encoding="utf-8"))
    if len(base.get("journeys", [])) != 5:
        raise RuntimeError(f"{profile}: expected five base journey rows.")
    if any(row.get("profile") != profile for row in base["journeys"]):
        raise RuntimeError(f"{profile}: base report contains a different profile.")

    replacements = {}
    replacement_caps = []
    for replacement_path in replacement_jsons:
        source = json.loads(replacement_path.read_text(encoding="utf-8"))
        if source.get("journey_errors"):
            raise RuntimeError(f"{replacement_path.name}: replacement contains journey errors.")
        replacement_caps.append(float(source.get("max_wall_seconds", 0)))
        for row in source.get("journeys", []):
            seed = int(row["seed"])
            if row.get("profile") != profile or row.get("path") != "roster_first":
                raise RuntimeError(f"{replacement_path.name}: wrong profile/path for seed {seed}.")
            if seed in replacements:
                raise RuntimeError(f"Replacement seed {seed} appears more than once.")
            residual, bad_days = _residuals(row)
            if (row.get("days") != 365 or row.get("stop_reason") != "full_horizon"
                    or row.get("budget_exhausted") or bad_days or residual):
                raise RuntimeError(f"Replacement seed {seed} is not valid through day 365 or has ledger residuals.")
            replacements[seed] = (row, replacement_path.name)

    old_rows = {int(row["seed"]): row for row in base["journeys"]}
    if len(old_rows) != len(base["journeys"]):
        raise RuntimeError(f"{profile}: base report contains duplicate seeds.")
    if not replacements or not set(replacements).issubset(old_rows):
        raise RuntimeError("Replacement seeds must match rows in the base report.")
    correction_records = []
    merged = []
    for row in base["journeys"]:
        seed = int(row["seed"])
        if seed not in replacements:
            merged.append(row)
            continue
        corrected, source_name = replacements[seed]
        old_residual, old_bad_days = _residuals(row)
        correction_records.append({
            "seed": seed,
            "source_report": source_name,
            "previous_days": int(row.get("days", 0)),
            "previous_stop_reason": row.get("stop_reason"),
            "previous_ledger_residual_total": old_residual,
            "previous_nonzero_ledger_days": [int(day["day"]) for day in old_bad_days],
            "replacement_days": 365,
            "replacement_stop_reason": "full_horizon",
            "replacement_ledger_residual_total": 0,
        })
        merged.append(corrected)
    merged.sort(key=lambda row: int(row["seed"]))
    if len(merged) != 5 or len({int(row["seed"]) for row in merged}) != 5:
        raise RuntimeError(f"{profile}: replacement merge must leave exactly five unique seeds.")

    if any(row.get("days") != 365 or row.get("stop_reason") != "full_horizon"
           or row.get("budget_exhausted") or _residuals(row)[1]
           for row in merged):
        raise RuntimeError(f"{profile}: merged five-seed report fails full-horizon/per-seed ledger checks.")

    backup_md = base_json.with_suffix(".md")
    backup_csv = base_json.with_suffix(".ledger.csv")
    for path in (base_json, backup_md, backup_csv):
        if path.exists():
            backup = path.with_name(path.stem + ".pre_replacement" + path.suffix)
            if not backup.exists():
                shutil.copy2(path, backup)

    base["journeys"] = merged
    base["journey_merge_policy"] = "replace the complete seed row and its daily ledger; never append old and rerun actions"
    base["cell_summaries"] = {
        f"{profile}/roster_first": summarize(merged, int(base["seed_start"])),
    }
    base["max_wall_seconds"] = max([float(base.get("max_wall_seconds", 0)), *replacement_caps])
    base["elapsed_seconds"] = round(float(base.get("elapsed_seconds", 0))
                                     + sum(float(json.loads(p.read_text(encoding="utf-8")).get("elapsed_seconds", 0))
                                           for p in replacement_jsons), 2)
    base["generated_at_utc"] = max(
        [base.get("generated_at_utc", ""), *(json.loads(p.read_text(encoding="utf-8")).get("generated_at_utc", "")
                                               for p in replacement_jsons)]
    )
    base["seed_replacements"] = [
        *[record for record in base.get("seed_replacements", [])
          if int(record.get("seed", -1)) not in replacements],
        *correction_records,
    ]
    rejection_rows = [(int(row["seed"]), entry) for row in merged
                      for entry in row.get("service_rejections", [])]
    rejection_counts = Counter((str(entry.get("service", "unknown")),
                                str(entry.get("reason", "unspecified")))
                               for _seed, entry in rejection_rows)
    base["service_rejection_count"] = len(rejection_rows)
    base["service_rejection_reasons"] = [
        {"service": service, "reason": reason, "count": count}
        for (service, reason), count in sorted(rejection_counts.items())
    ]

    ledger_path = base_json.with_suffix(".ledger.csv")
    fields = None
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
        old_ledger = list(csv.DictReader(handle))
        fields = list(old_ledger[0]) if old_ledger else None
    replacement_ledger = []
    for replacement_path in replacement_jsons:
        csv_path = replacement_path.with_suffix(".ledger.csv")
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if fields is None:
                fields = list(reader.fieldnames or [])
            replacement_ledger.extend(row for row in reader if int(row["seed"]) in replacements)
    corrected_seeds = set(replacements)
    replacement_ledger_counts = Counter(int(row["seed"]) for row in replacement_ledger)
    if any(replacement_ledger_counts[seed] != 365 for seed in corrected_seeds):
        raise RuntimeError("Replacement ledgers must contain exactly 365 rows per corrected seed.")
    for seed in corrected_seeds:
        days = {int(row["day"]) for row in replacement_ledger if int(row["seed"]) == seed}
        if days != set(range(1, 366)):
            raise RuntimeError(f"Replacement ledger for seed {seed} does not contain exactly D1–D365.")
    retained = [row for row in old_ledger if int(row["seed"]) not in corrected_seeds]
    ledger_temp = ledger_path.with_name(ledger_path.name + ".tmp")
    with ledger_temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(retained)
        writer.writerows(replacement_ledger)
    ledger_temp.replace(ledger_path)
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
        final_ledger = list(csv.DictReader(handle))
    final_counts = Counter(int(row["seed"]) for row in final_ledger)
    if set(final_counts) != {int(row["seed"]) for row in merged} or any(
            final_counts[int(row["seed"])] != 365 for row in merged):
        raise RuntimeError(f"{profile}: final ledger must contain one 365-day stream per seed.")
    if any(len({int(row["day"]) for row in final_ledger if int(row["seed"]) == seed}) != 365
           for seed in final_counts):
        raise RuntimeError(f"{profile}: final ledger contains duplicate or missing seed/day entries.")
    _atomic_json(base_json, base)

    totals = Counter()
    for row in merged:
        for daily in row["daily"]:
            for key, value in daily["gold_ledger"].items():
                totals[key] += int(value)
    correction_table = "\n".join(
        f"| {row['seed']} | {row['days']} | {row['stop_reason']} | {row['elapsed_seconds']:.1f} | "
        f"{_residuals(row)[0]} | {len(row.get('service_rejections', []))} |"
        for row in merged
    )
    reasons = "\n".join(
        f"| {service} | {reason} | {count} |"
        for (service, reason), count in sorted(rejection_counts.items())
    ) or "| — | Nenhuma rejeição registrada | 0 |"
    rejection_details = []
    for seed, entry in rejection_rows:
        precheck = entry.get("precheck", {})
        actual = entry.get("actual_can_pay") or {}
        actual_materials = actual.get("available_materials", {})
        actual_required = actual.get("required", {})
        available_materials = precheck.get("available_materials", {})
        required_materials = precheck.get("required_materials", {})
        material_summary = ", ".join(
            f"{name}: {available_materials.get(name, '—')} disponível / {required_materials.get(name, 0)} exigido"
            for name in ("wood", "ore", "crystals")
        )
        actual_material_summary = ", ".join(
            f"{name}: {actual_materials.get(name, '—')} disponível / {actual_required.get(name, 0)} exigido"
            for name in ("wood", "ore", "crystals")
        )
        rejection_details.append(
            f"| {seed} | D{entry.get('day', '—')} | {entry.get('attempt', '—')} | "
            f"{'serviço chamado' if entry.get('service_called', True) else 'pré-check; sem chamada'} | "
            f"{entry.get('target_item', entry.get('target', '—'))} | "
            f"{precheck.get('available_gold', '—')} / {precheck.get('required_gold', '—')} | "
            f"{material_summary} | {actual.get('available_gold', '—')} / {actual_required.get('gold', '—')} | "
            f"{actual_material_summary} | {entry.get('reason', '—')} |"
        )
    rejection_details_md = "\n".join(rejection_details) or "| — | — | — | — | — | — | — | — | Nenhuma |"
    corrections = "\n".join(
        f"- Seed {r['seed']}: antes {r['previous_days']} dias / `{r['previous_stop_reason']}` / "
        f"resíduo {r['previous_ledger_residual_total']}; reexecutada até D365, resíduo 0 "
        f"(evidência {r['source_report']})."
        for r in correction_records
    )
    text = [
        f"# Economia Stage 5 — perfil {profile}, 365d, N=5", "",
        "Cinco seeds completos com serviços reais em SQLite descartável e política `roster_first`. "
        "Este arquivo agrega as trajetórias válidas; a tabela abaixo valida cada seed separadamente.", "",
        "| Seed | Dias | Encerramento | Segundos | Resíduo diário somado | Rejeições de serviço |",
        "|---:|---:|---|---:|---:|---:|", correction_table, "",
        f"**Ouro:** passivo {totals['passive_offline']}; missões {totals['missions']}; masmorras {totals['dungeons']}; "
        f"Market {totals['market_sales']}; compras {totals['building_and_hire_purchases']}; "
        f"salvage {totals['salvage_fees']}; crafting {totals['crafting_fees']}; "
        f"delta {totals['observed_delta']}; resíduo agregado {totals['unattributed_residual']}. "
        "O agregador também exige resíduo zero em cada dia de cada seed.", "",
        "## Recusas e rejeições opcionais", "",
        "| Etapa | Motivo | Contagem |", "|---|---|---:|", reasons, "",
        "### Estado das tentativas recusadas", "",
        "Valores de ouro: disponível / exigido. Materiais são apresentados nessa mesma ordem para a cotação do simulador "
        "e para a validação real do serviço. `pré-check; sem chamada` significa que o orçamento atualizado bloqueou a ação "
        "antes de invocar o serviço; `serviço chamado` identifica uma recusa retornada pelo próprio serviço.", "",
        "| Seed | Dia | Tentativa | Camada | Alvo | Ouro pré-checagem | Materiais pré-checagem | Ouro em `can_pay` | Materiais em `can_pay` | Motivo |",
        "|---:|---:|---|---|---|---:|---|---:|---|---|", rejection_details_md, "",
        "## Seeds substituídos", "", corrections or "Nenhum.", "",
        "O JSON mantém todos os campos de contexto e as entradas literais em `service_rejections`. "
        "N=5 é uma amostra exploratória; não sustenta alegação de P95 ou estabilidade global.", "",
        f"Artefatos: [{base_json.name}]({base_json.name}), [{ledger_path.name}]({ledger_path.name}). "
        "O agregado dos cinco perfis é [stage5_service_economy_365d_n5_2026-10-30.md]"
        "(stage5_service_economy_365d_n5_2026-10-30.md).", "",
    ]
    base_json.with_suffix(".md").write_text("\n".join(text), encoding="utf-8")
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=("ativo", "casual", "offline", "produtor", "combate"))
    parser.add_argument("--base-json", required=True, type=Path)
    parser.add_argument("--replacement-json", required=True, type=Path, action="append")
    args = parser.parse_args()
    data = merge(args.profile, args.base_json, args.replacement_json)
    print(f"merged profile={args.profile}; journeys={len(data['journeys'])}; replacements={len(data['seed_replacements'])}")


if __name__ == "__main__":
    main()
