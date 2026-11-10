"""Narrow native-dialog bridge; filesystem paths never come from HTTP requests."""

import logging
import secrets
from pathlib import Path
from time import monotonic

from app.desktop.paths import user_data_directory


class DesktopBridge:
    def __init__(self, campaigns, clock_guard):
        # pywebview recursively exposes public object attributes as JS API.
        # Keep service/window references private so it only exports the methods below.
        self._campaigns = campaigns
        self._clock_guard = clock_guard
        self._window = None
        self._pending_exports: dict[str, tuple[str, Path, float]] = {}

    def _webview(self):
        import webview

        if self._window is None:
            raise RuntimeError("A janela do aplicativo ainda está iniciando. Tente novamente em instantes.")
        return webview

    def export_campaign(self, campaign_id: str):
        try:
            webview = self._webview()
            info = self._campaigns.inspect_campaign(campaign_id)
            export_dir = user_data_directory() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=str(export_dir),
                save_filename=f"{info.campaign_name}-{info.campaign_id[:8]}.gimcampaign",
                file_types=("Guild Idle Manager (*.gimcampaign)", "SQLite (*.db)"),
            )
            if not result:
                return {"cancelled": True}
            destination = Path(result[0])
            if destination.suffix.lower() not in {".gimcampaign", ".db"}:
                destination = destination.with_suffix(".gimcampaign")
            if destination.exists():
                token = secrets.token_urlsafe(24)
                self._pending_exports[token] = (info.campaign_id, destination, monotonic() + 120)
                return {"needs_confirmation": True, "confirmation_token": token}
            self._campaigns.export_campaign(campaign_id, destination)
            return {"ok": True, "message": "Campanha exportada com sucesso."}
        except Exception as exc:
            return {"error": str(exc)}

    def export_guide_markdown(self, markdown: str):
        try:
            if not isinstance(markdown, str) or not markdown.strip():
                return {"error": "O Guia retornou um arquivo vazio ou inválido."}
            if len(markdown.encode("utf-8")) > 5_000_000:
                return {"error": "O arquivo do Guia excedeu o tamanho permitido."}
            webview = self._webview()
            export_dir = user_data_directory() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=str(export_dir),
                save_filename="guia-guild-idle-manager.md",
                file_types=("Markdown (*.md)",),
            )
            if not result:
                return {"cancelled": True}
            destination = Path(result[0])
            if destination.suffix.lower() != ".md":
                destination = destination.with_suffix(".md")
            content = markdown.encode("utf-8")
            destination.write_bytes(content)
            if not destination.is_file() or destination.read_bytes() != content:
                raise OSError("A gravação não pôde ser confirmada.")
            return {"ok": True, "file_name": destination.name, "path": str(destination)}
        except Exception as exc:
            logging.getLogger("gim.guide_export").exception("Falha ao salvar exportação Markdown do Guia")
            return {"error": f"Não foi possível salvar o Guia: {exc}"}

    def confirm_export(self, confirmation_token: str, overwrite: bool):
        pending = self._pending_exports.pop(confirmation_token, None)
        if pending is None or pending[2] < monotonic():
            return {"error": "A confirmação da exportação expirou. Tente novamente."}
        campaign_id, destination, _expires = pending
        if not overwrite:
            return {"cancelled": True}
        try:
            self._campaigns.export_campaign(campaign_id, destination, overwrite=True)
            return {"ok": True, "message": "Arquivo substituído e campanha exportada com sucesso."}
        except Exception as exc:
            return {"error": str(exc)}

    def import_campaign(self):
        try:
            webview = self._webview()
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Guild Idle Manager (*.gimcampaign)", "SQLite (*.db)"),
            )
            if not result:
                return {"cancelled": True}
            info = self._campaigns.import_campaign(result[0])
            self._clock_guard.initialize_campaign(info.campaign_id)
            return {"ok": True, "message": "Campanha importada. O controle local de progresso foi iniciado."}
        except Exception as exc:
            return {"error": str(exc)}

    def restore_backup(self, campaign_id: str):
        try:
            webview = self._webview()
            backup_dir = user_data_directory() / "backups" / campaign_id
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=str(backup_dir),
                allow_multiple=False,
                file_types=("Cópias de segurança SQLite (*.db)",),
            )
            if not result:
                return {"cancelled": True}
            self._campaigns.restore_backup(campaign_id, result[0])
            return {"ok": True, "message": "Cópia de segurança restaurada. Abra a campanha para continuar."}
        except Exception as exc:
            return {"error": str(exc)}
