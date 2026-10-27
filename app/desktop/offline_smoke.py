"""Fast offline check for the frozen desktop bundle and its local campaign migrations."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from app.services.campaign_service import CampaignService
from app.services.mercenary_name_service import choose_random_mercenary_names


def run_offline_smoke() -> None:
    configured_result_path = os.environ.get("GIM_SMOKE_RESULT")
    if not configured_result_path:
        raise RuntimeError("GIM_SMOKE_RESULT precisa apontar para o arquivo de resultado do smoke.")
    result_path = Path(configured_result_path)

    with tempfile.TemporaryDirectory(prefix="gim-desktop-smoke-") as directory:
        service = CampaignService(Path(directory) / "saves")
        campaign = service.create_campaign("Smoke offline DEV", "Guilda de teste")
        listing = service.list_campaigns()
        if not any(entry.campaign_id == campaign.campaign_id for entry in listing):
            raise RuntimeError("A campanha temporária não foi persistida e reconhecida.")
        names = choose_random_mercenary_names(1)
        if len(names) != 1 or not names[0].strip():
            raise RuntimeError("O catálogo offline de nomes não gerou um nome válido.")

        from app.services.icon_service import DESKTOP_MANIFEST_PATH

        manifest = json.loads(DESKTOP_MANIFEST_PATH.read_text(encoding="utf-8"))
        if not manifest.get("sprites") or not manifest.get("icon_maps"):
            raise RuntimeError("O manifesto local de arte desktop está incompleto.")

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text("PASS: SQLite, Alembic, conteúdo inicial, nomes e manifesto local\n", encoding="utf-8")
