import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal
from app.services.content_validation_service import build_refinement_validation_report


def main() -> None:
    output_dir = ROOT / "reports"
    output_dir.mkdir(exist_ok=True)
    with SessionLocal() as db:
        report = build_refinement_validation_report(db)
    path = output_dir / "content_validation_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "issues": len(report["issues"]), "report": str(path)}, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
