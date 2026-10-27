"""Narrow native-dialog bridge; filesystem paths never come from HTTP requests."""

from pathlib import Path
import secrets
from time import monotonic

from app.desktop.paths import user_data_directory


class DesktopBridge:
    def __init__(self, campaigns, clock_guard):
        self.campaigns = campaigns
        self.clock_guard = clock_guard
        self.window = None
        self._pending_exports: dict[str, tuple[str, Path, float]] = {}

    def _webview(self):
        import webview

        if self.window is None:
            raise RuntimeError("A janela desktop ainda nao esta pronta.")
        return webview

    def export_campaign(self, campaign_id: str):
        try:
            webview = self._webview()
            info = self.campaigns.inspect_campaign(campaign_id)
            export_dir = user_data_directory() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            result = self.window.create_file_dialog(
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
            self.campaigns.export_campaign(campaign_id, destination)
            return {"ok": True, "message": "Campanha exportada com sucesso."}
        except Exception as exc:
            return {"error": str(exc)}

    def confirm_export(self, confirmation_token: str, overwrite: bool):
        pending = self._pending_exports.pop(confirmation_token, None)
        if pending is None or pending[2] < monotonic():
            return {"error": "A confirmacao da exportacao expirou. Tente novamente."}
        campaign_id, destination, _expires = pending
        if not overwrite:
            return {"cancelled": True}
        try:
            self.campaigns.export_campaign(campaign_id, destination, overwrite=True)
            return {"ok": True, "message": "Arquivo substituido e campanha exportada com sucesso."}
        except Exception as exc:
            return {"error": str(exc)}

    def import_campaign(self):
        try:
            webview = self._webview()
            result = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Guild Idle Manager (*.gimcampaign)", "SQLite (*.db)"),
            )
            if not result:
                return {"cancelled": True}
            info = self.campaigns.import_campaign(result[0])
            self.clock_guard.initialize_campaign(info.campaign_id)
            return {"ok": True, "message": "Campanha importada. A ancora local foi iniciada agora."}
        except Exception as exc:
            return {"error": str(exc)}

    def restore_backup(self, campaign_id: str):
        try:
            webview = self._webview()
            backup_dir = user_data_directory() / "backups" / campaign_id
            result = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=str(backup_dir),
                allow_multiple=False,
                file_types=("Backups SQLite (*.db)",),
            )
            if not result:
                return {"cancelled": True}
            self.campaigns.restore_backup(campaign_id, result[0])
            return {"ok": True, "message": "Backup restaurado. Abra a campanha para continuar."}
        except Exception as exc:
            return {"error": str(exc)}
