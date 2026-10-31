import base64
import hashlib
import io
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services import github_releases as updates


class _FakeResponse(io.BytesIO):
    def __init__(self, body):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def geturl(self):
        return "https://release-assets.githubusercontent.com/download/setup"


class _FakeOpener:
    def __init__(self, body):
        self.body = body

    def open(self, *_args, **_kwargs):
        return _FakeResponse(self.body)


def _config(public_key: bytes, channel: str = "stable"):
    return updates.GitHubReleasesConfig(
        owner="guild-idle-manager",
        repo="desktop",
        channel=channel,
        public_key_b64=base64.b64encode(public_key).decode("ascii"),
        manifest_asset="gim-release.json",
    )


def _release_payload(private_key: Ed25519PrivateKey, *, asset_hash: str | None = None):
    setup = b"verified setup bytes"
    manifest = json.dumps({
        "schema_version": 1,
        "app_id": "guild-idle-manager",
        "version": "1.2.0",
        "channel": "stable",
        "minimum_supported_version": "1.0.0",
        "asset_name": "GuildIdleManager-stable-Setup.exe",
        "asset_sha256": asset_hash or hashlib.sha256(setup).hexdigest(),
    }, separators=(",", ":")).encode("utf-8")
    signature = base64.b64encode(private_key.sign(manifest))
    root = "https://github.com/guild-idle-manager/desktop/releases/download/stable-v1.2.0/"
    release = {
        "tag_name": "stable-v1.2.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": "gim-release.json", "browser_download_url": root + "gim-release.json"},
            {"name": "gim-release.json.sig", "browser_download_url": root + "gim-release.json.sig"},
            {"name": "GuildIdleManager-stable-Setup.exe", "browser_download_url": root + "GuildIdleManager-stable-Setup.exe"},
        ],
    }
    bodies = {
        root + "gim-release.json": manifest,
        root + "gim-release.json.sig": signature,
        root + "GuildIdleManager-stable-Setup.exe": setup,
    }
    return release, bodies, setup


def test_incomplete_configuration_does_not_contact_github(monkeypatch):
    def fail_if_requested(*_args, **_kwargs):
        raise AssertionError("incomplete configuration must not make a request")

    monkeypatch.setattr(updates, "_request_bytes", fail_if_requested)
    status, prepared = updates.check_for_update("1.0.0", "stable", config=_config(b"x" * 31))

    assert prepared is None
    assert status["query_enabled"] is False
    assert status["install_enabled"] is False


def test_release_requires_matching_channel_and_installed_marker():
    config = _config(b"x" * 32)
    assert updates.check_for_update("1.0.0", "beta", config=config)[1] is None
    assert updates.provider_status("beta", config)["query_enabled"] is False


def test_signed_release_is_staged_after_hash_verification(monkeypatch, tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    release, bodies, setup = _release_payload(private_key)
    monkeypatch.setattr(updates.tempfile, "gettempdir", lambda: str(tmp_path))

    def request(url, _limit, *, api_json=False):
        return json.dumps([release]).encode() if api_json else bodies[url]

    monkeypatch.setattr(updates, "_request_bytes", request)
    monkeypatch.setattr(updates, "build_opener", lambda *_args, **_kwargs: _FakeOpener(setup))
    status, prepared = updates.check_for_update("1.0.0", "stable", config=_config(public_key))

    assert status["install_enabled"] is True
    assert status["available_version"] == "1.2.0"
    assert prepared is not None
    assert updates.prepared_file_is_valid(prepared, "stable")
    updates.cleanup_prepared_update(prepared)


def test_invalid_signature_never_stages_setup(monkeypatch, tmp_path):
    key = Ed25519PrivateKey.generate()
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    release, bodies, _setup = _release_payload(Ed25519PrivateKey.generate())
    monkeypatch.setattr(updates.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        updates, "_request_bytes",
        lambda url, _limit, *, api_json=False: json.dumps([release]).encode() if api_json else bodies[url],
    )
    monkeypatch.setattr(updates, "build_opener", lambda *_args, **_kwargs: _FakeOpener(b"setup"))
    status, prepared = updates.check_for_update("1.0.0", "stable", config=_config(public_key))

    assert prepared is None
    assert status["install_enabled"] is False
    assert "assinatura" in status["reason"]
    assert list(tmp_path.iterdir()) == []


def test_bad_setup_hash_is_rejected(monkeypatch, tmp_path):
    key = Ed25519PrivateKey.generate()
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    release, bodies, setup = _release_payload(key, asset_hash="0" * 64)
    monkeypatch.setattr(updates.tempfile, "gettempdir", lambda: str(tmp_path))

    def request(url, _limit, *, api_json=False):
        return json.dumps([release]).encode() if api_json else bodies[url]

    monkeypatch.setattr(updates, "_request_bytes", request)
    monkeypatch.setattr(updates, "build_opener", lambda *_args, **_kwargs: _FakeOpener(setup))
    status, prepared = updates.check_for_update("1.0.0", "stable", config=_config(public_key))

    assert prepared is None
    assert status["install_enabled"] is False


def test_release_install_confirmation_uses_the_shared_accessible_dialog():
    root = Path(__file__).resolve().parents[1]
    template = (root / "app" / "templates" / "updates.html").read_text(encoding="utf-8")
    main_js = (root / "app" / "static" / "js" / "main.js").read_text(encoding="utf-8")
    launcher = (root / "app" / "desktop" / "launcher.py").read_text(encoding="utf-8")

    assert "window.confirm" not in template
    assert "data-confirm-always" in template
    assert 'aria-haspopup="dialog" aria-controls="confirmation-dialog"' in template
    assert "`Instalar versão ${preparedReleaseVersion}?`" in template
    assert "!form.dataset.confirmAlways" in main_js
    message_assignment = template.index("releaseInstallForm.dataset.confirmMessage =")
    submit_listener = template.index("releaseInstallForm?.addEventListener('submit'")
    make_button_available = template.index("releaseInstallForm.hidden = false")
    assert message_assignment < make_button_available < submit_listener
    assert "O arquivo baixado foi preservado para tentativa manual" in launcher
    assert "Motivo: $($_.Exception.Message)" in launcher
