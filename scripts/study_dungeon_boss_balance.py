import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal
from app.services.dungeon_balance_study_service import build_dungeon_balance_study, render_dungeon_balance_study


def main() -> None:
    with SessionLocal() as db:
        report = build_dungeon_balance_study(db)
    (ROOT / "estudo_balanceamento_masmorras_chefes.md").write_text(
        render_dungeon_balance_study(report), encoding="utf-8"
    )
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "dungeon_boss_balance_study.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Estudo de Masmorras e Chefes gerado com sucesso.")


if __name__ == "__main__":
    main()
