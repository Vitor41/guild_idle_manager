"""Fast offline check for the frozen desktop bundle and its local campaign migrations."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from app.services.campaign_service import CampaignService
from app.services.mercenary_name_service import choose_random_mercenary_names


def run_offline_smoke() -> None:
    # Form parsing can fail only when the first POST arrives, so check it at package build time.
    from python_multipart.multipart import parse_options_header

    if parse_options_header(b"multipart/form-data; boundary=smoke")[0] != b"multipart/form-data":
        raise RuntimeError("Rotas ou suporte a formularios nao foram incluidos no pacote.")
    configured_result_path = os.environ.get("GIM_SMOKE_RESULT")
    if not configured_result_path:
        raise RuntimeError("GIM_SMOKE_RESULT precisa apontar para o arquivo de resultado do smoke.")
    result_path = Path(configured_result_path)

    def record(message: str) -> None:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(message + "\n", encoding="utf-8")

    record("RUNNING: preparing isolated campaign-selection smoke")

    previous_local_app_data = os.environ.get("LOCALAPPDATA")
    previous_app_data = os.environ.get("APPDATA")
    configured_temp_root = os.environ.get("GIM_SMOKE_TEMP_DIR")
    temporary_root = Path(configured_temp_root) if configured_temp_root else None
    if temporary_root is not None:
        temporary_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix="gim-desktop-smoke-",
            dir=str(temporary_root) if temporary_root is not None else None,
        ) as directory:
            temporary_profile = Path(directory) / "profile"
            os.environ["LOCALAPPDATA"] = str(temporary_profile / "LocalAppData")
            os.environ["APPDATA"] = str(temporary_profile / "Roaming")
            os.environ["APP_MODE"] = "desktop"

            from app.main import app
            from app.desktop.routes import campaigns_page
            from starlette.requests import Request
            record("RUNNING: desktop app routes imported")

            service = CampaignService(temporary_profile / "LocalAppData" / "GuildIdleManager" / "saves")
            campaign = service.create_campaign("Smoke offline DEV", "Guilda de teste")
            listing = service.list_campaigns()
            if not any(entry.campaign_id == campaign.campaign_id for entry in listing):
                raise RuntimeError("A campanha temporária não foi persistida e reconhecida.")
            record(f"RUNNING: temporary campaign persisted at {campaign.database_path}")

            # Render the same campaign-selection route used by the desktop WebView.
            app.state.campaign_service = service
            app.state.clock_guard = object()
            request = Request({
                "type": "http",
                "method": "GET",
                "path": "/desktop/campaigns",
                "headers": [],
                "app": app,
            })
            response = campaigns_page(request)
            campaign_page = response.body.decode("utf-8")
            if response.status_code != 200 or "id=\"campaign-page-title\"" not in campaign_page or "Criar e jogar" not in campaign_page:
                raise RuntimeError("A tela de seleção de campanhas não pôde ser renderizada pelo pacote.")
            record("RUNNING: campaign-selection page rendered")

            names = choose_random_mercenary_names(1)
            if len(names) != 1 or not names[0].strip():
                raise RuntimeError("O catálogo offline de nomes não gerou um nome válido.")

            from app.services.icon_service import DESKTOP_MANIFEST_PATH

            manifest = json.loads(DESKTOP_MANIFEST_PATH.read_text(encoding="utf-8"))
            if not manifest.get("sprites") or not manifest.get("icon_maps"):
                raise RuntimeError("O manifesto local de arte desktop está incompleto.")
            record("RUNNING: local campaign assets validated")
    finally:
        if previous_local_app_data is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = previous_local_app_data
        if previous_app_data is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = previous_app_data

    result_path.write_text(
        "PASS: SQLite, campanhas temporárias, seleção de campanhas, nomes e manifesto local\n",
        encoding="utf-8",
    )
