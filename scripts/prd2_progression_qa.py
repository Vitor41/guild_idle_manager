import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal
from app.services.prd2_qa_service import build_prd2_qa_report, render_prd2_markdown


def main() -> None:
    with SessionLocal() as db:
        report = build_prd2_qa_report(db)
    (ROOT / "relatorio_qa_progressao_end_to_end.md").write_text(
        render_prd2_markdown(report), encoding="utf-8"
    )
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "prd2_progression_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Relatório PRD 2 gerado com sucesso.")


if __name__ == "__main__":
    main()
