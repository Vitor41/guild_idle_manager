import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import SessionLocal
from app.services.progression_simulation_service import simulate_progression


with SessionLocal() as db:
    print(json.dumps(simulate_progression(db), ensure_ascii=False, indent=2))
