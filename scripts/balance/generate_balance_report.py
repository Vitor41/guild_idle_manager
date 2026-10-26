import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal
from app.services.progression_simulation_service import build_balance_report


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Relatório de progressão e economia",
        "",
        f"Simulações Monte Carlo por faixa: {report['simulation_runs_per_band']}",
        "",
        "## Progressão",
        "",
        "| Faixa | Missões | Dungeons | XP médio | Ouro/h | p50 | p75 | p90 | p95 | Cobertura |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["progression"]:
        lines.append(
            f"| {row['band']} | {row['mission_count']} | {row['dungeon_count']} | {row['average_xp']} | "
            f"{row['gold_per_hour']} | {row['p50_attempts']} | {row['p75_attempts']} | "
            f"{row['p90_attempts']} | {row['p95_attempts']} | {'OK' if row['content_coverage_ok'] else 'Revisar'} |"
        )
    lines.extend(["", "## Materiais", "", "| Família | Fontes | Quantidade esperada/rotação | Demanda |", "|---|---:|---:|---|"])
    for row in report["materials"]:
        lines.append(f"| {row['family']} | {row['mission_sources']} | {row['expected_quantity_per_full_rotation']} | {'Sim' if row['has_demand'] else 'Não'} |")
    lines.extend(["", "## Fontes e drenos de ouro", "", "As fontes principais são missões e dungeons. O idle é complementar; Mercado e Docas permanecem limitados por tempo, slots e margem.", ""])
    return "\n".join(lines)


def main() -> None:
    output_dir = ROOT / "reports"
    output_dir.mkdir(exist_ok=True)
    with SessionLocal() as db:
        report = build_balance_report(db)
    (output_dir / "content_balance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "content_balance_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"Relatórios gerados em {output_dir}")


if __name__ == "__main__":
    main()
