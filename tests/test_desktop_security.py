import os
from pathlib import Path
import subprocess
import sys
import unittest


class DesktopSecurityTests(unittest.TestCase):
    def test_loopback_allowlist_fails_closed_and_rejects_cross_origin_requests(self):
        script = r'''
import asyncio
from app.main import app
app.state.desktop_allowed_host = "127.0.0.1:8123"
app.state.desktop_allowed_origin = "http://127.0.0.1:8123"

async def invoke(path, method="GET", host="127.0.0.1:8123", origin=None, fetch_site=None):
    sent = []
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if fetch_site is not None:
        headers.append((b"sec-fetch-site", fetch_site.encode()))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": headers, "server": ("127.0.0.1", 8123),
        "client": ("127.0.0.1", 12345)}
    async def receive(): return {"type": "http.request", "body": b"{}", "more_body": False}
    async def send(message): sent.append(message)
    await app(scope, receive, send)
    return sent[0]["status"]

async def main():
    assert await invoke("/desktop/health") == 200
    assert await invoke("/desktop/health", host="evil.example") == 403
    assert await invoke("/desktop/health", fetch_site="cross-site") == 403
    assert await invoke("/desktop/api/campaigns", method="POST") == 403
    assert await invoke("/desktop/api/campaigns", method="POST", origin="http://127.0.0.1:8123") != 403
    app.state.desktop_allowed_host = None
    assert await invoke("/desktop/health") == 503

asyncio.run(main())
'''
        environment = os.environ.copy()
        environment["APP_MODE"] = "desktop"
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
