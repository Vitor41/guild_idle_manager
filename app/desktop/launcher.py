"""Start the desktop-only FastAPI server and host it in a pywebview window."""

from __future__ import annotations

import ctypes
import hashlib
import http.client
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

import uvicorn

from app.desktop.paths import user_data_directory, user_log_directory


class DesktopAlreadyRunningError(RuntimeError):
    pass


def _acquire_single_instance_mutex(local_app_data: str | None = None):
    if os.name != "nt":
        return None
    profile_root = local_app_data or os.environ.get("LOCALAPPDATA")
    if not profile_root:
        raise RuntimeError("A pasta de dados local não está disponível.")
    identity = os.path.normcase(os.path.abspath(profile_root)).encode("utf-8")
    suffix = hashlib.sha256(identity).hexdigest()[:24]
    mutex_name = f"Local\\GuildIdleManager-{suffix}"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel32.ReleaseMutex.restype = ctypes.c_int
    kernel32.SetLastError.argtypes = [ctypes.c_ulong]
    kernel32.SetLastError.restype = None
    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = ctypes.c_ulong
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, 1, mutex_name)
    if not handle:
        raise ctypes.WinError(kernel32.GetLastError())
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        raise DesktopAlreadyRunningError(
            "O Guild Idle Manager já está aberto para este perfil de dados."
        )
    return handle, kernel32


def _release_single_instance_mutex(mutex) -> None:
    if mutex is None:
        return
    handle, kernel32 = mutex
    try:
        kernel32.ReleaseMutex(handle)
    finally:
        kernel32.CloseHandle(handle)


def _configure_logging() -> None:
    log_file = user_log_directory() / "desktop.log"
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[handler],
        force=True,
    )


def _wait_for_health(url: str, server: uvicorn.Server, timeout_seconds: float = 15) -> None:
    deadline = time.monotonic() + timeout_seconds
    target = urlsplit(url)
    if target.scheme != "http" or not target.hostname or target.port is None:
        raise ValueError("O healthcheck desktop deve apontar para o servidor HTTP local.")
    request_target = target.path or "/"
    if target.query:
        request_target += f"?{target.query}"
    last_error: OSError | http.client.HTTPException | None = None
    while time.monotonic() < deadline:
        if server.started:
            connection = http.client.HTTPConnection(target.hostname, target.port, timeout=0.5)
            try:
                connection.request("GET", request_target, headers={"Host": target.netloc})
                response = connection.getresponse()
                if response.status == 200:
                    logging.info("Local healthcheck passed at %s", url)
                    return
                last_error = OSError(f"healthcheck returned HTTP {response.status}")
            except (OSError, http.client.HTTPException) as exc:
                last_error = exc
            finally:
                connection.close()
        if not server.started and not getattr(server, "_started", False):
            time.sleep(0.05)
        else:
            time.sleep(0.1)
    message = "O servidor local não respondeu dentro do tempo esperado."
    raise RuntimeError(message) from last_error


def _show_startup_error(message: str) -> None:
    logging.exception(message)
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, message, "Guild Idle Manager", 0x10)


def _skip_pywebview_early_webview_focus(webview_module=None) -> None:
    """Avoid focusing WebView2 before its CoreWebView2 instance is ready.

    pywebview 6.2.1's WinForms Shown handler focuses the WebView2 control
    synchronously. On this runtime that blocks the UI thread before
    CoreWebView2InitializationCompleted, leaving the desktop window blank.
    The window manager still activates the form normally; mouse interaction
    focuses the browser after it is ready.
    """
    if os.name != "nt":
        return
    if webview_module is None:
        import webview as webview_module

    from webview.platforms import winforms

    browser_form = winforms.BrowserView.BrowserForm
    if getattr(browser_form, "_gim_skip_early_webview_focus", False):
        return
    if not hasattr(browser_form, "on_shown") or not hasattr(winforms, "is_cef"):
        raise RuntimeError("A versão do pywebview não oferece o ponto de compatibilidade WinForms esperado.")

    def on_shown_without_early_focus(form, *_args):
        if not winforms.is_cef:
            form.shown.set()

    browser_form.on_shown = on_shown_without_early_focus
    browser_form._gim_skip_early_webview_focus = True
    logging.info("Applied WinForms WebView2 early-focus compatibility for pywebview")


def run() -> None:
    if os.name != "nt":
        raise RuntimeError("O aplicativo desktop exige o Windows.")
    os.environ["APP_MODE"] = "desktop"
    _configure_logging()
    try:
        instance_mutex = _acquire_single_instance_mutex()
    except DesktopAlreadyRunningError as exc:
        logging.warning("%s", exc)
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, str(exc), "Guild Idle Manager", 0x30)
        return

    listener = None
    server: uvicorn.Server | None = None
    server_thread: threading.Thread | None = None
    restart_requested = threading.Event()

    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(8)
        port = listener.getsockname()[1]
        allowed_host = f"127.0.0.1:{port}"
        origin = f"http://{allowed_host}"
        logging.info("Starting loopback server at %s", origin)

        from app.main import app

        app.state.desktop_allowed_host = allowed_host
        app.state.desktop_allowed_origin = origin
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_config=None,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server_thread = threading.Thread(
            target=lambda: server.run(sockets=[listener]),
            name="gim-local-api",
            daemon=True,
        )
        server_thread.start()
        _wait_for_health(f"{origin}/desktop/health", server)

        import webview

        _skip_pywebview_early_webview_focus(webview)

        from app.desktop.bridge import DesktopBridge

        bridge = DesktopBridge(app.state.campaign_service, app.state.clock_guard)
        logging.info("Opening pywebview window")
        window = webview.create_window(
            "Guild Idle Manager",
            url=f"{origin}/desktop/campaigns",
            js_api=bridge,
            width=1120,
            height=820,
            min_size=(760, 600),
            resizable=True,
            confirm_close=True,
            text_select=True,
        )

        def request_local_checkout_restart() -> None:
            restart_requested.set()
            if server is not None:
                server.should_exit = True
            try:
                window.destroy()
            except Exception:
                logging.exception("Could not close the desktop window for local checkout restart")

        app.state.request_local_checkout_restart = request_local_checkout_restart
        bridge._window = window
        window.events.closed += lambda: setattr(server, "should_exit", True)
        webview_storage = user_data_directory() / "webview"
        webview_storage.mkdir(parents=True, exist_ok=True)
        logging.info("Using stable WebView2 user data at %s", webview_storage)
        webview.start(gui="edgechromium", storage_path=str(webview_storage))
    except Exception as exc:
        _show_startup_error(f"Não foi possível iniciar o Guild Idle Manager: {exc}")
        raise
    finally:
        if server is not None:
            server.should_exit = True
        if server_thread is not None:
            server_thread.join(timeout=12)
            if server_thread.is_alive():
                logging.error("O servidor local nao encerrou dentro do prazo.")
        try:
            if listener is not None:
                listener.close()
        finally:
            _release_single_instance_mutex(instance_mutex)

    if restart_requested.is_set():
        if server_thread is not None and server_thread.is_alive():
            logging.error("O servidor local ainda está ativo; o checkout não será reiniciado para evitar duas instâncias.")
            _show_startup_error("O aplicativo não encerrou completamente. Feche-o antes de reiniciar a versão local.")
            return
        try:
            environment = os.environ.copy()
            environment["APP_MODE"] = "desktop"
            repository_root = Path(__file__).resolve().parents[2]
            subprocess.Popen(
                [sys.executable, "-m", "app.desktop"],
                cwd=repository_root,
                env=environment,
                close_fds=True,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            logging.info("Restarted the desktop app from the current local checkout")
        except Exception as exc:
            logging.exception("Could not restart the desktop app from the local checkout")
            _show_startup_error(f"Não foi possível reiniciar o checkout local: {exc}")


if __name__ == "__main__":
    run()
