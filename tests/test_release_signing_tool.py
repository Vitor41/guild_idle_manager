import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.services import github_releases
from scripts.sign_github_release import create_signed_manifest


class ReleaseSigningToolTests(unittest.TestCase):
    def test_manifest_signature_and_setup_hash_match_release_client_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup = root / "GuildIdleManager-DEV-Setup.exe"
            setup.write_bytes(b"disposable signed setup bytes")
            key = Ed25519PrivateKey.generate()
            raw_private_key = key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            private_key_file = root / "release-private-key.base64"
            private_key_file.write_text(base64.b64encode(raw_private_key).decode("ascii"), encoding="ascii")

            manifest_bytes, signature_b64, public_key_b64 = create_signed_manifest(
                setup, private_key_file, "0.3.1", "DEV", "0.3.1",
            )

            manifest = json.loads(manifest_bytes)
            self.assertEqual(manifest["app_id"], "guild-idle-manager")
            self.assertEqual(manifest["version"], "0.3.1")
            self.assertEqual(manifest["channel"], "DEV")
            self.assertEqual(manifest["asset_name"], "GuildIdleManager-DEV-Setup.exe")
            self.assertEqual(manifest["asset_sha256"], hashlib.sha256(setup.read_bytes()).hexdigest())
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
            public_key.verify(base64.b64decode(signature_b64, validate=True), manifest_bytes)
            root_url = "https://github.com/Vitor41/guild_idle_manager/releases/download/DEV-v0.3.1/"
            release = {
                "tag_name": "DEV-v0.3.1",
                "draft": False,
                "prerelease": True,
                "assets": [
                    {"name": "gim-release.json", "browser_download_url": root_url + "gim-release.json"},
                    {"name": "gim-release.json.sig", "browser_download_url": root_url + "gim-release.json.sig"},
                    {"name": "GuildIdleManager-DEV-Setup.exe", "browser_download_url": root_url + "GuildIdleManager-DEV-Setup.exe"},
                ],
            }
            bodies = {
                root_url + "gim-release.json": manifest_bytes,
                root_url + "gim-release.json.sig": signature_b64,
            }
            config = github_releases.GitHubReleasesConfig(
                "Vitor41", "guild_idle_manager", "DEV", public_key_b64, "gim-release.json",
            )
            with patch.object(github_releases, "_request_bytes", side_effect=lambda url, _limit, **_kwargs: bodies[url]):
                verified = github_releases._load_and_verify_manifest(release, config, "0.3.1")
            self.assertEqual(verified["asset_sha256"], manifest["asset_sha256"])

            class FakeResponse(io.BytesIO):
                headers = {"Content-Length": str(len(setup.read_bytes()))}

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    self.close()

                def geturl(self):
                    return "https://release-assets.githubusercontent.com/download/setup"

            class FakeOpener:
                def open(self, *_args, **_kwargs):
                    return FakeResponse(setup.read_bytes())

            def mock_request(url, _limit, *, api_json=False):
                if api_json:
                    return json.dumps([release]).encode("utf-8")
                return bodies[url]

            with tempfile.TemporaryDirectory() as staging_root, \
                    patch.object(github_releases.tempfile, "gettempdir", return_value=staging_root), \
                    patch.object(github_releases, "_request_bytes", side_effect=mock_request), \
                    patch.object(github_releases, "build_opener", return_value=FakeOpener()):
                status, prepared = github_releases.check_for_update("0.3.0", "DEV", config=config)
                self.assertTrue(status["install_enabled"], status)
                self.assertEqual(status["available_version"], "0.3.1")
                self.assertTrue(github_releases.prepared_file_is_valid(prepared, "DEV"))
                github_releases.cleanup_prepared_update(prepared)

    def test_signer_refuses_private_keys_inside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            setup = Path(directory) / "setup.exe"
            setup.write_bytes(b"bytes")
            with self.assertRaisesRegex(ValueError, "fora da pasta do repositório"):
                create_signed_manifest(
                    setup, Path(__file__).resolve().parents[1] / "not-a-real-key.txt",
                    "0.3.1", "DEV", "0.3.1",
                )

    def test_development_updater_resolves_repository_but_stays_disabled_without_trust_key(self):
        config = github_releases.configured_source()
        self.assertEqual((config.owner, config.repo), ("Vitor41", "guild_idle_manager"))
        self.assertEqual(config.channel, "DEV")
        self.assertIsNone(config.public_key_b64)
        status = github_releases.provider_status("DEV", config)
        self.assertFalse(status["query_enabled"])
        self.assertFalse(status["install_enabled"])
        self.assertIn("chave pública", status["reason"])
        with patch.object(
            github_releases, "_request_bytes",
            side_effect=AssertionError("the updater must not contact GitHub without a trust key"),
        ):
            status, prepared = github_releases.check_for_update("0.3.0", "DEV", config=config)
        self.assertIsNone(prepared)
        self.assertFalse(status["query_enabled"])

    def test_packaged_update_channel_is_taken_from_installation_marker(self):
        with patch.object(github_releases.sys, "frozen", True, create=True), patch.object(
            github_releases, "read_installed_channel", return_value="stable",
        ):
            config = github_releases.configured_source()
        self.assertEqual(config.channel, "stable")


if __name__ == "__main__":
    unittest.main()
