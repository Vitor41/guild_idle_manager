"""Independent pre-campaign updater shown by the installed desktop shortcut."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from app.core.version import APP_VERSION
from app.desktop.paths import user_log_directory
from app.services.github_releases import (
    PreparedReleaseUpdate,
    check_for_update,
    cleanup_prepared_update,
    configured_source,
    prepared_file_is_valid,
    read_installed_channel,
)


logger = logging.getLogger("gim.update.launcher")
_PALETTE = {
    "background": "#101A1D",
    "surface": "#172327",
    "raised": "#203035",
    "text": "#F1EADB",
    "muted": "#B6C1BD",
    "gold": "#E6B965",
    "teal": "#68C3B5",
    "success": "#9BD498",
    "error": "#E38B75",
}


def _configure_launcher_logging() -> None:
    log_file = user_log_directory() / "update-launcher.log"
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def classify_launcher_result(
    status: dict[str, object], prepared: PreparedReleaseUpdate | None,
) -> str:
    """Map update service outcomes to safe launcher states."""
    if prepared is not None:
        return "update-ready"
    if status.get("failed"):
        return "recoverable-error"
    if status.get("available") is False:
        return "current"
    if not status.get("query_enabled"):
        return "unconfigured"
    return "incomplete"


def _asset_file(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "assets" / "desktop" / "sprites" / "64" / f"{name}.png"


class LauncherWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.messages: queue.Queue[tuple[object, ...]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.prepared: PreparedReleaseUpdate | None = None
        self.required_update = False
        self.close_when_finished = False
        self.transfer_started = False
        self.outcome: str | None = None
        self.log_file = user_log_directory() / "update-launcher.log"
        self._images: dict[str, tk.PhotoImage] = {}
        self._configure_window()
        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(80, self._drain_messages)
        self.root.after(0, self.check_updates)

    def _configure_window(self) -> None:
        self.root.title("Guild Idle Manager")
        self.root.configure(background=_PALETTE["background"])
        self.root.geometry("460x390")
        self.root.minsize(380, 340)
        self.root.resizable(True, True)
        self.root.option_add("*Font", "Segoe UI 10")
        self.root.option_add("*Foreground", _PALETTE["text"])
        self.root.option_add("*Background", _PALETTE["background"])
        try:
            self.root.iconphoto(True, tk.PhotoImage(file=str(_asset_file("guild-sigil"))))
        except tk.TclError:
            logger.info("Launcher application icon could not be loaded")

    def _build_widgets(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Launcher.TFrame", background=_PALETTE["background"])
        style.configure("Surface.TFrame", background=_PALETTE["surface"])
        style.configure("Launcher.TLabel", background=_PALETTE["background"], foreground=_PALETTE["text"])
        style.configure("Muted.TLabel", background=_PALETTE["surface"], foreground=_PALETTE["muted"])
        style.configure("Title.TLabel", background=_PALETTE["background"], foreground=_PALETTE["text"], font=("Georgia", 17, "bold"))
        style.configure("State.TLabel", background=_PALETTE["surface"], foreground=_PALETTE["gold"], font=("Segoe UI", 12, "bold"))
        style.configure("Launcher.Horizontal.TProgressbar", troughcolor=_PALETTE["raised"], background=_PALETTE["gold"], bordercolor=_PALETTE["raised"], lightcolor=_PALETTE["gold"], darkcolor=_PALETTE["gold"])
        style.configure("Primary.TButton", background=_PALETTE["gold"], foreground=_PALETTE["background"], font=("Segoe UI", 10, "bold"), padding=(14, 9))
        style.map("Primary.TButton", background=[("active", "#F0CD85"), ("disabled", "#746546")])
        style.configure("Secondary.TButton", background=_PALETTE["raised"], foreground=_PALETTE["text"], padding=(10, 8))
        style.map("Secondary.TButton", background=[("active", "#30434A")])

        outer = ttk.Frame(self.root, style="Launcher.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer, style="Launcher.TFrame")
        header.pack(fill="x", pady=(0, 14))
        self.brand_image = self._load_icon("guild-sigil", 2)
        if self.brand_image:
            tk.Label(header, image=self.brand_image, background=_PALETTE["background"], borderwidth=0).pack(side="left", padx=(0, 12))
        title_block = ttk.Frame(header, style="Launcher.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        title_row = ttk.Frame(title_block, style="Launcher.TFrame")
        title_row.pack(anchor="w")
        update_image = self._load_icon("nav-updates", 3)
        if update_image:
            tk.Label(title_row, image=update_image, background=_PALETTE["background"], borderwidth=0).pack(side="left", padx=(0, 7))
        ttk.Label(title_row, text="Guild Idle Manager", style="Title.TLabel").pack(side="left")
        config = configured_source()
        channel = config.channel or "não configurado"
        ttk.Label(title_block, text=f"Versão instalada {APP_VERSION}  ·  Canal {channel}", style="Launcher.TLabel", foreground=_PALETTE["muted"]).pack(anchor="w", pady=(4, 0))

        panel = ttk.Frame(outer, style="Surface.TFrame", padding=16)
        panel.pack(fill="both", expand=True)
        state_row = ttk.Frame(panel, style="Surface.TFrame")
        state_row.pack(fill="x", anchor="w")
        self.status_image_label = tk.Label(state_row, background=_PALETTE["surface"], borderwidth=0)
        self.status_image_label.pack(side="left", padx=(0, 9))
        self.state_label = ttk.Label(state_row, text="Verificando atualizações…", style="State.TLabel", wraplength=350)
        self.state_label.pack(side="left", fill="x", expand=True)
        self.detail_label = ttk.Label(panel, text="O launcher verifica a release assinada antes de abrir o jogo.", style="Muted.TLabel", wraplength=380, justify="left")
        self.detail_label.pack(fill="x", anchor="w", pady=(10, 12))
        self.progress = ttk.Progressbar(panel, mode="indeterminate", style="Launcher.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 8))
        self.progress_text = ttk.Label(panel, text="", style="Muted.TLabel", wraplength=380)
        self.progress_text.pack(fill="x", anchor="w")
        self.log_label = ttk.Label(panel, text="", style="Muted.TLabel", wraplength=380)
        self.log_label.pack(fill="x", anchor="w", pady=(8, 0))

        self.actions = ttk.Frame(outer, style="Launcher.TFrame")
        self.actions.pack(fill="x", pady=(14, 0))
        self.primary_button = ttk.Button(self.actions, style="Primary.TButton")
        self.primary_button.pack(fill="x")
        self.secondary_button = ttk.Button(self.actions, style="Secondary.TButton")
        self.secondary_button.pack(fill="x", pady=(7, 0))
        self.tertiary_button = ttk.Button(self.actions, style="Secondary.TButton")
        self.tertiary_button.pack(fill="x", pady=(7, 0))
        self._set_icon("status-progress")

    def _load_icon(self, name: str, divisor: int = 2):
        if name in self._images:
            return self._images[name]
        path = _asset_file(name)
        if not path.is_file():
            return None
        try:
            image = tk.PhotoImage(file=str(path))
            if divisor > 1:
                image = image.subsample(divisor, divisor)
            self._images[name] = image
            return image
        except tk.TclError:
            logger.exception("Could not load launcher sprite: %s", path)
            return None

    def _set_icon(self, name: str) -> None:
        image = self._load_icon(name, 2)
        self.status_image_label.configure(image=image or "")

    def _set_state(self, title: str, detail: str, icon: str, *, color: str | None = None) -> None:
        self.state_label.configure(text=title, foreground=color or _PALETTE["gold"])
        self.detail_label.configure(text=detail)
        self._set_icon(icon)

    def _set_actions(self, primary: tuple[str, object] | None, secondary: tuple[str, object] | None = None,
                     tertiary: tuple[str, object] | None = None) -> None:
        for button, action in ((self.primary_button, primary), (self.secondary_button, secondary), (self.tertiary_button, tertiary)):
            if action is None:
                button.pack_forget()
                continue
            button.configure(text=action[0], command=action[1], state="normal")
            button.pack(fill="x", pady=(0 if button is self.primary_button else 7, 0))

    def _set_busy(self, label: str, detail: str, *, can_cancel: bool) -> None:
        self._set_state(label, detail, "status-progress")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.progress_text.configure(text="")
        self.log_label.configure(text="")
        cancel_action = ("Cancelar", self.cancel_update) if can_cancel else None
        self._set_actions(None, cancel_action)

    def check_updates(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if self.prepared:
            cleanup_prepared_update(self.prepared)
            self.prepared = None
        self.cancel_event = threading.Event()
        self._set_busy("Verificando atualizações…", "Consultando o canal configurado, validando a assinatura e preparando o download seguro.", can_cancel=True)

        def report_progress(current: int, total: int | None) -> None:
            self.messages.put(("progress", current, total))

        def work() -> None:
            try:
                status, prepared = check_for_update(
                    APP_VERSION,
                    read_installed_channel(),
                    progress_callback=report_progress,
                    cancel_event=self.cancel_event,
                )
                self.messages.put(("result", status, prepared))
            except Exception as error:
                logger.exception("Unexpected launcher update check error")
                self.messages.put(("exception", str(error)))

        self.worker = threading.Thread(target=work, name="gim-launcher-update-check", daemon=True)
        self.worker.start()

    def cancel_update(self) -> None:
        self.cancel_event.set()
        self._set_state("Cancelando…", "O launcher vai apagar qualquer download incompleto e não abrirá o Setup.", "status-warning")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._set_actions(None)

    def _drain_messages(self) -> None:
        try:
            while True:
                message = self.messages.get_nowait()
                if message[0] == "progress":
                    _, current, total = message
                    if total:
                        self.progress.stop()
                        self.progress.configure(mode="determinate", maximum=total, value=current)
                        percentage = min(100, round(current * 100 / total))
                        self.progress_text.configure(text=f"Baixando atualização… {current / 1_048_576:.1f} de {total / 1_048_576:.1f} MB ({percentage}%)")
                        self._set_state("Baixando atualização…", "O Setup só será aberto depois da validação da assinatura e do SHA-256.", "status-progress")
                    else:
                        self.progress.configure(mode="indeterminate")
                        self.progress.start(12)
                        self.progress_text.configure(text=f"Baixando atualização… {current / 1_048_576:.1f} MB recebidos")
                        self._set_state("Baixando atualização…", "O servidor não informou o tamanho total; o progresso permanece indeterminado.", "status-progress")
                elif message[0] == "result":
                    self.progress.stop()
                    _, status, prepared = message
                    if self.close_when_finished:
                        if prepared:
                            cleanup_prepared_update(prepared)
                        self._finish(None)
                    else:
                        self._show_result(status, prepared)
                elif message[0] == "exception":
                    self.progress.stop()
                    if self.close_when_finished:
                        self._finish(None)
                    else:
                        self._show_error(str(message[1]))
        except queue.Empty:
            pass
        if self.outcome is not None:
            return
        try:
            if self.root.winfo_exists():
                self.root.after(80, self._drain_messages)
        except tk.TclError:
            return

    def _show_result(self, status: dict[str, object], prepared: PreparedReleaseUpdate | None) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=0)
        self.progress_text.configure(text="")
        self.log_label.configure(text="")
        self.prepared = prepared
        self.required_update = bool(status.get("required_update"))
        state = classify_launcher_result(status, prepared)
        if state == "update-ready" and prepared:
            self._set_state("Atualização disponível", f"{APP_VERSION} → {prepared.version} · assinatura e SHA-256 conferidos.", "status-ready", color=_PALETTE["success"])
            self.detail_label.configure(text="A atualização acontece antes do jogo. O Setup será aberto em uma janela visível e poderá mostrar a confirmação de segurança do Windows.")
            self._set_actions(
                ("Atualizar e jogar", self.install_update),
                None if self.required_update else ("Jogar versão instalada", self.open_game),
                None if self.required_update else ("Adiar", lambda: self._finish(None)),
            )
            return
        if state == "current":
            self._set_state("Versão atualizada", f"Guild Idle Manager {APP_VERSION} está pronto.", "status-ready", color=_PALETTE["success"])
            self._set_actions(("Abrir jogo", self.open_game))
            return
        reason = str(status.get("reason") or "Não foi possível verificar o canal de atualização.")
        if state == "recoverable-error":
            title = "Download cancelado" if status.get("cancelled") else "Não foi possível validar a atualização"
            self._set_state(title, reason, "status-warning" if status.get("cancelled") else "status-failed", color=_PALETTE["error"])
        else:
            self._set_state("Verificação indisponível", reason, "status-warning", color=_PALETTE["muted"])
        self.log_label.configure(text=f"Registro: {self.log_file}")
        self._set_actions(
            ("Tentar novamente", self.check_updates),
            None if self.required_update else ("Jogar versão instalada", self.open_game),
            ("Sair", lambda: self._finish(None)) if self.required_update else None,
        )

    def _show_error(self, reason: str) -> None:
        self._set_state("Falha no launcher", reason, "status-failed", color=_PALETTE["error"])
        self.log_label.configure(text=f"Registro: {self.log_file}")
        self._set_actions(
            ("Tentar novamente", self.check_updates),
            None if self.required_update else ("Jogar versão instalada", self.open_game),
            ("Sair", lambda: self._finish(None)) if self.required_update else None,
        )

    def install_update(self) -> None:
        prepared = self.prepared
        channel = read_installed_channel()
        if prepared is None or not prepared_file_is_valid(prepared, channel):
            if prepared:
                cleanup_prepared_update(prepared)
            self.prepared = None
            self._show_error("O Setup preparado não corresponde mais à versão, ao canal ou ao SHA-256 verificado. Verifique novamente.")
            return
        try:
            from app.desktop.launcher import _verified_update_handoff

            _verified_update_handoff(prepared.installer_path, os.getpid(), prepared.version)
            self.transfer_started = True
            self._set_state("Abrindo Setup validado…", "O launcher encerra agora. O instalador abrirá em janela visível e, ao terminar, mostrará a seleção de campanhas.", "status-progress")
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            self._finish("handoff")
        except Exception as error:
            logger.exception("Could not start the verified Setup")
            self._show_error(f"Não foi possível abrir o Setup validado. O arquivo permanece em {prepared.installer_path}. Motivo: {error}")

    def open_game(self) -> None:
        if self.prepared:
            cleanup_prepared_update(self.prepared)
            self.prepared = None
        self._finish("play")

    def close(self) -> None:
        if self.worker and (self.worker.is_alive() or not self.messages.empty()):
            self.close_when_finished = True
            if self.worker.is_alive():
                self.cancel_update()
            self.close_when_finished = True
            return
        if self.prepared and not self.transfer_started:
            cleanup_prepared_update(self.prepared)
            self.prepared = None
        self._finish(None)

    def _finish(self, outcome: str | None) -> None:
        if self.outcome is not None:
            return
        self.outcome = outcome or "close"
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def run_prelaunch() -> None:
    if os.name != "nt":
        raise RuntimeError("O launcher desktop exige o Windows.")
    os.environ["APP_MODE"] = "desktop"
    from app.desktop.launcher import (
        DesktopAlreadyRunningError,
        _acquire_single_instance_mutex,
        _configure_logging,
        _release_single_instance_mutex,
    )

    _configure_logging()
    _configure_launcher_logging()
    try:
        mutex = _acquire_single_instance_mutex()
    except DesktopAlreadyRunningError as error:
        logger.warning("%s", error)
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, str(error), "Guild Idle Manager", 0x30)
        return

    window: LauncherWindow | None = None
    outcome: str | None = None
    try:
        root = tk.Tk()
        window = LauncherWindow(root)
        root.mainloop()
        outcome = window.outcome
    except Exception as error:
        logger.exception("Could not start the pre-campaign launcher")
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, f"Não foi possível abrir o launcher. Registro: {user_log_directory() / 'desktop.log'}\n\nMotivo: {error}", "Guild Idle Manager", 0x10)
    finally:
        if window and window.prepared and not window.transfer_started:
            cleanup_prepared_update(window.prepared)
        _release_single_instance_mutex(mutex)

    if outcome == "play":
        try:
            environment = os.environ.copy()
            environment["APP_MODE"] = "desktop"
            subprocess.Popen(
                [sys.executable, "--play"],
                cwd=Path(sys.executable).resolve().parent,
                env=environment,
                close_fds=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except Exception as error:
            logger.exception("Could not open the installed game")
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, f"Não foi possível abrir o jogo. Registro: {user_log_directory() / 'desktop.log'}\n\nMotivo: {error}", "Guild Idle Manager", 0x10)


def run_launcher_smoke() -> None:
    """Exercise the packaged launcher's state routing without network or install side effects."""
    checks = (
        ({"available": False, "query_enabled": True}, None, "current"),
        ({"available": True, "query_enabled": True}, object(), "update-ready"),
        ({"failed": True, "query_enabled": True}, None, "recoverable-error"),
        ({"query_enabled": False}, None, "unconfigured"),
    )
    for status, prepared, expected in checks:
        if classify_launcher_result(status, prepared) != expected:
            raise RuntimeError(f"Launcher state smoke failed: expected {expected}")
    result_path = os.environ.get("GIM_LAUNCHER_SMOKE_RESULT")
    if result_path:
        Path(result_path).write_text("PASS: packaged launcher entry and update states\n", encoding="utf-8")
    print("PASS: packaged launcher entry and update states")
