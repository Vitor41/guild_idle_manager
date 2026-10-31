import base64
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.services import github_releases
from scripts.generate_release_key import generate_key
from scripts.sign_github_release import create_signed_manifest


class ReleaseSigningToolTests(unittest.TestCase):
    def test_key_generation_returns_public_key_matching_private_key_saved_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            private_key_file = Path(directory) / "release-private-key.base64"
            public_key_b64 = generate_key(private_key_file)
            private_key_bytes = base64.b64decode(private_key_file.read_text(encoding="ascii").strip(), validate=True)
            private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            derived_public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            self.assertEqual(base64.b64decode(public_key_b64, validate=True), derived_public_key)

    def test_key_generation_refuses_private_key_inside_repository(self):
        with self.assertRaisesRegex(ValueError, "fora da pasta do repositório"):
            generate_key(Path(__file__).resolve().parents[1] / "not-a-real-key.txt")

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
            self.assertEqual(
                create_signed_manifest(
                    setup, private_key_file, "0.3.1", "DEV", "0.3.1", public_key_b64,
                )[2],
                public_key_b64,
            )
            with self.assertRaisesRegex(ValueError, "não corresponde"):
                create_signed_manifest(
                    setup, private_key_file, "0.3.1", "DEV", "0.3.1",
                    base64.b64encode(bytes(32)).decode("ascii"),
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

    def test_build_script_keeps_distribution_defaults_and_packages_the_config(self):
        root = Path(__file__).resolve().parents[1]
        build_script = (root / "scripts" / "build_desktop_dev.ps1").read_text(encoding="utf-8")
        spec = (root / "packaging" / "desktop" / "GuildIdleManager.spec").read_text(encoding="utf-8")
        self.assertIn("[string]$GitHubOwner = 'Vitor41'", build_script)
        self.assertIn("[string]$GitHubRepo = 'guild_idle_manager'", build_script)
        self.assertIn("schema_version = 1", build_script)
        self.assertIn("public_key_b64 = $GitHubPublicKeyBase64", build_script)
        self.assertIn("'gim-release-config.json'", build_script)
        self.assertIn("GIM_BUILD_RELEASE_CONFIG_FILE", build_script)
        self.assertIn('GIM_BUILD_RELEASE_CONFIG_FILE', spec)

    def test_packaged_update_channel_is_taken_from_installation_marker(self):
        with patch.object(github_releases, "_packaged_distribution_config_path", return_value=Path("missing-config.json")), \
                patch.object(github_releases, "_legacy_packaged_key_path", return_value=Path("missing-key.txt")), \
                patch.object(github_releases.sys, "frozen", True, create=True), \
                patch.object(github_releases, "read_installed_channel", return_value="stable"):
            config = github_releases.configured_source()
        self.assertEqual(config.channel, "stable")
        self.assertEqual((config.owner, config.repo), ("Vitor41", "guild_idle_manager"))

    def test_packaged_distribution_config_overrides_owner_repo_and_public_key(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "gim-release-config.json"
            public_key = base64.b64encode(bytes(range(32))).decode("ascii")
            config_path.write_text(json.dumps({
                "schema_version": 1,
                "owner": "Chosen-Owner",
                "repo": "chosen_repo.v2",
                "public_key_b64": public_key,
            }), encoding="utf-8")
            with patch.object(github_releases, "_packaged_distribution_config_path", return_value=config_path), \
                    patch.object(github_releases.sys, "frozen", True, create=True), \
                    patch.object(github_releases, "read_installed_channel", return_value="stable"), \
                    patch.dict(os.environ, {
                        "GIM_GITHUB_RELEASES_OWNER": "must-not-override",
                        "GIM_GITHUB_RELEASES_REPO": "must-not-override",
                        "GIM_GITHUB_RELEASES_PUBLIC_KEY": "must-not-override",
                    }, clear=False):
                config = github_releases.configured_source()
            self.assertEqual((config.owner, config.repo), ("Chosen-Owner", "chosen_repo.v2"))
            self.assertEqual(config.public_key_b64, public_key)
            self.assertEqual(config.channel, "stable")
            self.assertEqual(github_releases.configuration_issues(config), [])

    def test_packaged_dev_environment_can_override_config_but_other_channels_ignore_it(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "gim-release-config.json"
            config_path.write_text(json.dumps({
                "schema_version": 1,
                "owner": "Bundle-Owner",
                "repo": "bundle-repo",
                "public_key_b64": base64.b64encode(bytes(range(32))).decode("ascii"),
            }), encoding="utf-8")
            env = {
                "GIM_GITHUB_RELEASES_OWNER": "Dev-Owner",
                "GIM_GITHUB_RELEASES_REPO": "dev-repo",
                "GIM_GITHUB_RELEASES_PUBLIC_KEY": base64.b64encode(bytes(reversed(range(32)))).decode("ascii"),
            }
            with patch.object(github_releases, "_packaged_distribution_config_path", return_value=config_path), \
                    patch.object(github_releases.sys, "frozen", True, create=True), \
                    patch.dict(os.environ, env, clear=False), \
                    patch.object(github_releases, "read_installed_channel", return_value="DEV"):
                dev_config = github_releases.configured_source()
            self.assertEqual((dev_config.owner, dev_config.repo), ("Dev-Owner", "dev-repo"))
            self.assertEqual(dev_config.public_key_b64, env["GIM_GITHUB_RELEASES_PUBLIC_KEY"])

            with patch.object(github_releases, "_packaged_distribution_config_path", return_value=config_path), \
                    patch.object(github_releases.sys, "frozen", True, create=True), \
                    patch.dict(os.environ, env, clear=False), \
                    patch.object(github_releases, "read_installed_channel", return_value="beta"):
                beta_config = github_releases.configured_source()
            self.assertEqual((beta_config.owner, beta_config.repo), ("Bundle-Owner", "bundle-repo"))

    def test_invalid_packaged_distribution_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "gim-release-config.json"
            config_path.write_text(json.dumps({
                "schema_version": 1,
                "owner": "../attacker",
                "repo": "bad..repo.git",
                "public_key_b64": base64.b64encode(bytes(range(32))).decode("ascii"),
            }), encoding="utf-8")
            with patch.object(github_releases, "_packaged_distribution_config_path", return_value=config_path), \
                    patch.object(github_releases.sys, "frozen", True, create=True), \
                    patch.object(github_releases, "read_installed_channel", return_value="stable"):
                config = github_releases.configured_source()
            issues = github_releases.configuration_issues(config)
            self.assertTrue(any("owner" in issue for issue in issues), issues)
            self.assertTrue(any("repositório" in issue for issue in issues), issues)
            self.assertIsNone(github_releases.releases_api_url(config))

    def test_legacy_031_bundle_without_distribution_config_keeps_defaults_and_key_file(self):
        legacy_key = base64.b64encode(bytes(range(32))).decode("ascii")
        with patch.object(github_releases, "_read_packaged_distribution_config", return_value=None), \
                patch.object(github_releases, "_read_legacy_packaged_key", return_value=legacy_key), \
                patch.object(github_releases.sys, "frozen", True, create=True), \
                patch.object(github_releases, "read_installed_channel", return_value="DEV"):
            config = github_releases.configured_source()
        self.assertEqual((config.owner, config.repo), ("Vitor41", "guild_idle_manager"))
        self.assertEqual(config.public_key_b64, legacy_key)
        self.assertEqual(config.channel, "DEV")


if __name__ == "__main__":
    unittest.main()
