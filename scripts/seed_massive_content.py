import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.connection import SessionLocal
from app.seeds import run_massive_content_seed
from app.services.content_validation_service import build_content_report


def main() -> None:
    db = SessionLocal()
    try:
        seed_report = run_massive_content_seed(db)
        validation = build_content_report(db)
        print(json.dumps({"seed": seed_report, "validation": validation}, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
