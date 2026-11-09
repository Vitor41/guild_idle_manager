import base64
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.desktop.update_launcher import classify_launcher_result
from app.services import github_releases as updates


class _Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def geturl(self):
        return "https://release-assets.githubusercontent.com/setup"


class LauncherUpdateFlowTests(unittest.TestCase):
    def test_launcher_state_routing_covers_current_update_error_and_unconfigured(self):
        self.assertEqual(classify_launcher_result({"available": False, "query_enabled": True}, None), "current")
        self.assertEqual(classify_launcher_result({"available": True}, object()), "update-ready")
        self.assertEqual(classify_launcher_result({"failed": True}, None), "recoverable-error")
        self.assertEqual(classify_launcher_result({"query_enabled": False}, None), "unconfigured")

    def test_download_false_verifies_signed_manifest_without_downloading_setup(self):
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        setup = b"verified setup"
        root = "https://github.com/example/desktop/releases/download/stable-v1.2.0/"
        manifest = json.dumps({
            "schema_version": 1, "app_id": "guild-idle-manager", "version": "1.2.0",
            "channel": "stable", "minimum_supported_version": "1.0.0",
            "asset_name": "GuildIdleManager-stable-Setup.exe",
            "asset_sha256": hashlib.sha256(setup).hexdigest(),
        }, separators=(",", ":")).encode()
        release = {"tag_name": "stable-v1.2.0", "draft": False, "prerelease": False, "assets": [
            {"name": "gim-release.json", "browser_download_url": root + "gim-release.json"},
            {"name": "gim-release.json.sig", "browser_download_url": root + "gim-release.json.sig"},
            {"name": "GuildIdleManager-stable-Setup.exe", "browser_download_url": root + "GuildIdleManager-stable-Setup.exe"},
        ]}
        bodies = {root + "gim-release.json": manifest,
            root + "gim-release.json.sig": base64.b64encode(private.sign(manifest))}
        config = updates.GitHubReleasesConfig("example", "desktop", "stable", base64.b64encode(public).decode(), "gim-release.json")

        def request(url, _limit, *, api_json=False):
            if api_json:
                return json.dumps([release]).encode()
            if url.endswith("Setup.exe"):
                raise AssertionError("download=False must not download the Setup")
            return bodies[url]

        with patch.object(updates, "_request_bytes", side_effect=request):
            status, prepared = updates.check_for_update("1.0.0", "stable", config=config, download=False)
        self.assertIsNone(prepared)
        self.assertTrue(status["available"])
        self.assertFalse(status["install_enabled"])
        self.assertEqual(status["available_version"], "1.2.0")

    def test_cancelled_stream_deletes_partial_file_and_reports_progress(self):
        payload = b"x" * (updates._READ_CHUNK + 10)
        event = Event()
        progress = []

        class CancellingResponse(_Response):
            def read(self, size=-1):
                chunk = super().read(size)
                if chunk:
                    event.set()
                return chunk

        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "partial.exe"
            with patch.object(updates, "build_opener", return_value=type("Opener", (), {"open": lambda *_a, **_k: CancellingResponse(payload)})()):
                with self.assertRaises(updates.ReleaseDownloadCancelled):
                    updates._stream_download(
                        "https://github.com/example/setup", destination, hashlib.sha256(payload).hexdigest(),
                        progress_callback=lambda current, total: progress.append((current, total)), cancel_event=event,
                    )
            self.assertFalse(destination.exists())
            self.assertEqual(progress, [(0, len(payload)), (updates._READ_CHUNK, len(payload))])

    def test_hash_mismatch_never_leaves_an_executable_setup(self):
        payload = b"untrusted installer bytes"
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "setup.exe"
            opener = type("Opener", (), {"open": lambda *_args, **_kwargs: _Response(payload)})()
            with patch.object(updates, "build_opener", return_value=opener):
                with self.assertRaisesRegex(updates.GitHubReleasesError, "SHA-256"):
                    updates._stream_download(
                        "https://github.com/example/setup", destination, "0" * 64,
                    )
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
