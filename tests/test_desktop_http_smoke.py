import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DesktopHttpSmokeTests(unittest.TestCase):
    def test_gameplay_pages_and_mutations_work_through_loopback_without_http_sessions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            script = r'''
import gc, http.client, os, socket, tempfile, threading, time
from pathlib import Path
from datetime import datetime, timezone
os.environ["APP_MODE"] = "desktop"
from app.main import app
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.desktop.lifecycle import open_campaign
from app.services.campaign_service import CampaignService
from app.database.connection import SessionLocal, configure_database
from app.models import CampaignMetadata
from sqlalchemy import select
import uvicorn

with tempfile.TemporaryDirectory() as data_dir:
    saves = CampaignService(Path(data_dir) / "saves")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    port = sock.getsockname()[1]
    host = f"127.0.0.1:{port}"
    origin = f"http://{host}"
    app.state.desktop_allowed_host = host
    app.state.desktop_allowed_origin = origin
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline: time.sleep(.05)
    assert server.started, "server did not start"
    campaign = saves.create_campaign("Smoke desktop")
    guard = ClockGuard(MemoryAnchorStore(), lambda: datetime.now(timezone.utc), time.monotonic)
    guard.initialize_campaign(campaign.campaign_id)
    app.state.campaign_service = saves
    app.state.clock_guard = guard
    app.state.suspended_campaigns = set()
    open_campaign(app, saves, guard, campaign.campaign_id)

    def request(path, method="GET", body=None):
        client = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
        headers = {"Host": host}
        if method not in {"GET", "HEAD"}:
            headers["Origin"] = origin
        if body is not None: headers["Content-Type"] = "application/x-www-form-urlencoded"
        client.request(method, path, body=body, headers=headers)
        response = client.getresponse()
        result = response.status, response.getheader("location"), response.read()
        client.close()
        return result

    try:
        for path in ("/dashboard", "/tavern", "/missions", "/dungeons", "/inventory", "/buildings", "/market", "/blacksmith", "/tutorial"):
            status, _location, body = request(path)
            assert status == 200, (path, status, body[:400])
            assert b"Internal Server Error" not in body, path
        assert not any(item.cls.__name__ == "SessionMiddleware" for item in app.user_middleware)
        status, location, _body = request("/tutorial/start", method="POST")
        assert status == 303 and location == "/tutorial?step=1", (status, location)
        status, _location, _body = request(
            "/session/confirmation-preferences", method="POST", body="key=desktop_smoke"
        )
        assert status == 204, status
        with SessionLocal() as db:
            metadata = db.get(CampaignMetadata, campaign.campaign_id)
            assert '"desktop_smoke":false' in metadata.confirmation_preferences
    finally:
        from app.desktop.lifecycle import close_campaign
        close_campaign(app, saves, guard)
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        configure_database("sqlite:///:memory:")
        gc.collect()
'''
            environment = os.environ.copy()
            environment["APP_MODE"] = "desktop"
            environment["LOCALAPPDATA"] = temp_dir
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
