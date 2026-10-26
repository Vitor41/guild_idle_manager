import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal
from app.services.prd3_dungeon_qa_service import build_prd3_qa_report, render_prd3_markdown


def main() -> None:
    with SessionLocal() as db:
        report = build_prd3_qa_report(db)
    (ROOT / "relatorio_qa_masmorras_chefes.md").write_text(render_prd3_markdown(report), encoding="utf-8")
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    serializable = {key: value for key, value in report.items() if key != "catalog"}
    (reports / "prd3_dungeons_bosses_qa.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Relatório PRD 3 de Masmorras e Chefes gerado com sucesso.")


if __name__ == "__main__":
    main()
