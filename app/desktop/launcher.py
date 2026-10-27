"""Start the desktop-only FastAPI server and host it in a pywebview window."""

from __future__ import annotations

import ctypes
import http.client
import logging
from logging.handlers import RotatingFileHandler
import os
import socket
import threading
import time
from urllib.parse import urlsplit

import uvicorn

from app.desktop.paths import user_log_directory


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


def run() -> None:
    if os.name != "nt":
        raise RuntimeError("O aplicativo desktop exige o Windows.")
    os.environ["APP_MODE"] = "desktop"
    _configure_logging()

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    allowed_host = f"127.0.0.1:{port}"
    origin = f"http://{allowed_host}"
    logging.info("Starting loopback server at %s", origin)

    try:
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
        bridge._window = window
        window.events.closed += lambda: setattr(server, "should_exit", True)
        try:
            webview.start(gui="edgechromium")
        finally:
            server.should_exit = True
            server_thread.join(timeout=12)
            if server_thread.is_alive():
                logging.error("O servidor local nao encerrou dentro do prazo.")
    except Exception as exc:
        _show_startup_error(f"Não foi possível iniciar o Guild Idle Manager: {exc}")
        raise
    finally:
        listener.close()


if __name__ == "__main__":
    run()
