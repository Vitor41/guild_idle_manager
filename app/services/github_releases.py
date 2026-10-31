"""Signed, fail-closed GitHub Releases client for managed desktop installs."""

from dataclasses import dataclass
import base64
import binascii
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.config import settings


_GITHUB_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_CHANNELS = {"stable", "beta", "DEV"}
_MANIFEST_ASSET = re.compile(r"^[A-Za-z0-9_.-]+\.json$")
_ASSET_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_MAX_API_BYTES = 2 * 1024 * 1024
_MAX_MANIFEST_BYTES = 128 * 1024
_MAX_SIGNATURE_BYTES = 4096
_MAX_INSTALLER_BYTES = 1024 * 1024 * 1024
_READ_CHUNK = 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 20
_ALLOWED_REDIRECT_HOSTS = {
    "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
}


@dataclass(frozen=True)
class GitHubReleasesConfig:
    owner: str | None
    repo: str | None
    channel: str | None
    public_key_b64: str | None
    manifest_asset: str


@dataclass(frozen=True)
class PreparedReleaseUpdate:
    channel: str
    version: str
    minimum_supported_version: str
    asset_name: str
    asset_sha256: str
    installer_path: Path
    staging_directory: Path


class GitHubReleasesError(ValueError):
    pass


def configured_source() -> GitHubReleasesConfig:
    installed_channel = read_installed_channel() if getattr(sys, "frozen", False) else None
    packaged_key_path = Path(__file__).resolve().parents[1] / "data" / "gim-release-public-key.txt"
    packaged_key = None
    if getattr(sys, "frozen", False):
        try:
            packaged_key = packaged_key_path.read_text(encoding="ascii").strip() or None
        except OSError:
            packaged_key = None
    return GitHubReleasesConfig(
        owner=settings.github_releases_owner or "Vitor41",
        repo=settings.github_releases_repo or "guild_idle_manager",
        channel=settings.github_releases_channel or installed_channel or "DEV",
        public_key_b64=settings.github_releases_public_key or packaged_key,
        manifest_asset=settings.github_releases_manifest_asset,
    )


def _decode_public_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("chave pública deve estar em Base64 válido") from error
    if len(key) != 32:
        raise ValueError("chave pública Ed25519 deve conter 32 bytes")
    return key


def configuration_issues(config: GitHubReleasesConfig | None = None) -> list[str]:
    """Validate every value needed before constructing a request URL."""
    config = config or configured_source()
    issues: list[str] = []
    if not config.owner or not _GITHUB_COMPONENT.fullmatch(config.owner):
        issues.append("owner GitHub ausente ou inválido")
    if not config.repo or not _GITHUB_COMPONENT.fullmatch(config.repo):
        issues.append("repositório GitHub ausente ou inválido")
    if config.channel not in _CHANNELS:
        issues.append("canal de release ausente ou não suportado (stable, beta ou DEV)")
    if not config.public_key_b64:
        issues.append("chave pública de assinatura ausente")
    else:
        try:
            _decode_public_key(config.public_key_b64)
        except ValueError as error:
            issues.append(str(error))
    if not config.manifest_asset or not _MANIFEST_ASSET.fullmatch(config.manifest_asset):
        issues.append("nome do asset de manifesto ausente ou inválido")
    return issues


def releases_api_url(config: GitHubReleasesConfig | None = None) -> str | None:
    config = config or configured_source()
    if configuration_issues(config):
        return None
    return f"https://api.github.com/repos/{config.owner}/{config.repo}/releases?per_page=100&page=1"


def read_installed_channel(install_directory: Path | None = None) -> str | None:
    """Read the installer-owned marker; never infer a channel from config alone."""
    directory = install_directory or Path(sys.executable).resolve().parent
    marker = directory / ".gim-desktop-install.json"
    try:
        identity = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(identity, dict) or identity.get("product") != "org.guildidlemanager.desktop":
        return None
    channel = identity.get("channel")
    return channel if channel in _CHANNELS else None


def provider_status(
    installed_channel: str | None = None,
    config: GitHubReleasesConfig | None = None,
) -> dict[str, object]:
    config = config or configured_source()
    issues = configuration_issues(config)
    if issues:
        reason = "Consulta e instalação via GitHub Releases estão desativadas: " + "; ".join(issues) + "."
        query_enabled = False
    elif installed_channel not in _CHANNELS:
        reason = "Esta instalação não tem um marcador de canal reconhecido; a consulta foi desativada."
        query_enabled = False
    elif config.channel != installed_channel:
        reason = "O canal configurado não corresponde ao canal desta instalação; a consulta foi desativada."
        query_enabled = False
    else:
        reason = f"Canal {installed_channel} configurado. Verifique para consultar releases assinadas."
        query_enabled = True
    return {
        "channel": "github-releases",
        "configured": not issues,
        "available": None,
        "query_enabled": query_enabled,
        "install_enabled": False,
        "reason": reason,
    }


def _semver_key(value: object) -> tuple[object, ...]:
    if not isinstance(value, str):
        raise GitHubReleasesError("A versão do release não é texto.")
    match = _SEMVER.fullmatch(value)
    if not match:
        raise GitHubReleasesError(f"Versão SemVer inválida: {value}.")
    major, minor, patch, prerelease = match.groups()
    if prerelease is None:
        pre_key: tuple[tuple[int, object], ...] = ()
        stable_marker = 1
    else:
        identifiers: list[tuple[int, object]] = []
        for component in prerelease.split("."):
            if component.isdigit():
                identifiers.append((0, int(component)))
            else:
                identifiers.append((1, component))
        pre_key = tuple(identifiers)
        stable_marker = 0
    return int(major), int(minor), int(patch), stable_marker, pre_key


class _GitHubHttpsRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        target = urlsplit(new_url)
        if (target.scheme != "https" or target.hostname not in _ALLOWED_REDIRECT_HOSTS
                or target.username or target.password or target.port not in (None, 443)):
            raise GitHubReleasesError("O servidor de release redirecionou para uma origem não confiável.")
        return super().redirect_request(request, response, code, message, headers, new_url)


def _request_bytes(url: str, limit: int, *, api_json: bool = False) -> bytes:
    parsed = urlsplit(url)
    allowed_hosts = {"api.github.com"} if api_json else _ALLOWED_REDIRECT_HOSTS
    if (parsed.scheme != "https" or parsed.hostname not in allowed_hosts
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.fragment):
        raise GitHubReleasesError("URL GitHub inválida ou não segura.")
    headers = {
        "User-Agent": "GuildIdleManager-Desktop-Updater/1",
        "Accept": "application/vnd.github+json" if api_json else "application/octet-stream",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    request = Request(url, headers=headers, method="GET")
    opener = build_opener(_GitHubHttpsRedirects())
    try:
        with opener.open(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            final = urlsplit(response.geturl())
            if (final.scheme != "https" or final.hostname not in allowed_hosts | _ALLOWED_REDIRECT_HOSTS
                    or final.username or final.password or final.port not in (None, 443)
                    or final.fragment):
                raise GitHubReleasesError("Resposta recebida de uma origem não confiável.")
            length = response.headers.get("Content-Length")
            if length and int(length) > limit:
                raise GitHubReleasesError("O asset remoto excede o tamanho permitido.")
            payload = response.read(limit + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise GitHubReleasesError("Não foi possível consultar o GitHub Releases.") from error
    if len(payload) > limit:
        raise GitHubReleasesError("O conteúdo remoto excede o tamanho permitido.")
    return payload


def _release_asset_url(config: GitHubReleasesConfig, tag: str, name: str) -> str:
    return (
        f"https://github.com/{quote(config.owner, safe='')}/{quote(config.repo, safe='')}"
        f"/releases/download/{quote(tag, safe='')}/{quote(name, safe='')}"
    )


def _select_release(releases: object, config: GitHubReleasesConfig) -> dict[str, object] | None:
    if not isinstance(releases, list):
        raise GitHubReleasesError("A resposta do GitHub não contém uma lista de releases.")
    candidates: list[tuple[tuple[object, ...], dict[str, object], str]] = []
    prefix = f"{config.channel}-v"
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") is True:
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str) or not tag.startswith(prefix):
            continue
        version = tag[len(prefix):]
        version_key = _semver_key(version)
        expected_prerelease = config.channel != "stable"
        if release.get("prerelease") is not expected_prerelease:
            raise GitHubReleasesError("O marcador prerelease não corresponde ao canal configurado.")
        candidates.append((version_key, release, version))
    if not candidates:
        return None
    _, selected, version = max(candidates, key=lambda candidate: candidate[0])
    return {**selected, "_version": version}


def _release_asset(release: dict[str, object], name: str) -> dict[str, object]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise GitHubReleasesError("A release não contém assets reconhecíveis.")
    matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == name]
    if len(matches) != 1:
        raise GitHubReleasesError(f"A release precisa conter exatamente um asset {name}.")
    return matches[0]


def _validate_asset_url(asset: dict[str, object], expected_url: str) -> str:
    provided = asset.get("browser_download_url")
    if not isinstance(provided, str):
        raise GitHubReleasesError("Asset sem URL de download.")
    actual = urlsplit(provided)
    expected = urlsplit(expected_url)
    if (actual.scheme != "https" or actual.hostname != "github.com" or actual.path != expected.path
            or actual.username or actual.password or actual.port not in (None, 443) or actual.fragment):
        raise GitHubReleasesError("URL do asset não corresponde ao repositório e tag esperados.")
    return provided


def _load_and_verify_manifest(
    release: dict[str, object],
    config: GitHubReleasesConfig,
    version: str,
) -> dict[str, object]:
    tag = release["tag_name"]
    manifest_asset = _release_asset(release, config.manifest_asset)
    signature_name = f"{config.manifest_asset}.sig"
    signature_asset = _release_asset(release, signature_name)
    manifest_url = _validate_asset_url(
        manifest_asset, _release_asset_url(config, tag, config.manifest_asset)
    )
    signature_url = _validate_asset_url(
        signature_asset, _release_asset_url(config, tag, signature_name)
    )
    raw_manifest = _request_bytes(manifest_url, _MAX_MANIFEST_BYTES)
    raw_signature = _request_bytes(signature_url, _MAX_SIGNATURE_BYTES)
    try:
        signature = base64.b64decode(raw_signature.strip(), validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(_decode_public_key(config.public_key_b64))
        public_key.verify(signature, raw_manifest)
    except (binascii.Error, ValueError, InvalidSignature) as error:
        raise GitHubReleasesError("A assinatura Ed25519 do manifesto é inválida.") from error
    try:
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GitHubReleasesError("O manifesto assinado não é JSON UTF-8 válido.") from error
    if not isinstance(manifest, dict):
        raise GitHubReleasesError("O manifesto assinado precisa ser um objeto JSON.")
    if manifest.get("schema_version") != 1 or isinstance(manifest.get("schema_version"), bool):
        raise GitHubReleasesError("Versão do schema do manifesto não suportada.")
    if manifest.get("app_id") != "guild-idle-manager":
        raise GitHubReleasesError("O manifesto pertence a outro produto.")
    if manifest.get("channel") != config.channel or manifest.get("version") != version:
        raise GitHubReleasesError("Canal ou versão do manifesto não corresponde à tag da release.")
    minimum = manifest.get("minimum_supported_version")
    minimum_key = _semver_key(minimum)
    if minimum_key > _semver_key(version):
        raise GitHubReleasesError("Versão mínima não pode ser superior à versão do asset.")
    asset_name = manifest.get("asset_name")
    if not isinstance(asset_name, str) or not _ASSET_NAME.fullmatch(asset_name):
        raise GitHubReleasesError("Nome do Setup inválido no manifesto.")
    if not asset_name.casefold().endswith("-setup.exe"):
        raise GitHubReleasesError("O asset configurado não é um Setup Windows reconhecido.")
    digest = manifest.get("asset_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise GitHubReleasesError("SHA-256 do Setup inválido no manifesto.")
    _release_asset(release, asset_name)
    return {**manifest, "minimum_supported_version": minimum}


def _stream_download(url: str, destination: Path, expected_sha256: str) -> int:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username
            or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
        raise GitHubReleasesError("URL do Setup não é um download HTTPS do GitHub.")
    request = Request(url, headers={
        "User-Agent": "GuildIdleManager-Desktop-Updater/1",
        "Accept": "application/octet-stream",
    }, method="GET")
    opener = build_opener(_GitHubHttpsRedirects())
    digest = hashlib.sha256()
    total = 0
    try:
        with opener.open(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            final = urlsplit(response.geturl())
            if (final.scheme != "https" or final.hostname not in _ALLOWED_REDIRECT_HOSTS
                    or final.username or final.password or final.port not in (None, 443)
                    or final.fragment):
                raise GitHubReleasesError("Download do Setup redirecionado para origem não confiável.")
            length = response.headers.get("Content-Length")
            if length and int(length) > _MAX_INSTALLER_BYTES:
                raise GitHubReleasesError("Setup excede o limite máximo de tamanho.")
            with destination.open("xb") as output:
                while True:
                    chunk = response.read(_READ_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > _MAX_INSTALLER_BYTES:
                        raise GitHubReleasesError("Setup excede o limite máximo de tamanho.")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        destination.unlink(missing_ok=True)
        raise GitHubReleasesError("Não foi possível baixar o Setup assinado.") from error
    if total == 0 or digest.hexdigest() != expected_sha256:
        destination.unlink(missing_ok=True)
        raise GitHubReleasesError("O SHA-256 do Setup não corresponde ao manifesto assinado.")
    return total


def cleanup_prepared_update(prepared: PreparedReleaseUpdate | None) -> None:
    if prepared is None:
        return
    root = Path(tempfile.gettempdir()).resolve()
    directory = prepared.staging_directory.resolve()
    if directory.parent == root and directory.name.startswith("gim-release-update-"):
        shutil.rmtree(directory, ignore_errors=True)


def check_for_update(
    current_version: str,
    installed_channel: str | None,
    *,
    config: GitHubReleasesConfig | None = None,
) -> tuple[dict[str, object], PreparedReleaseUpdate | None]:
    """Query, verify and stage a newer signed Setup. Incomplete config makes no request."""
    config = config or configured_source()
    issues = configuration_issues(config)
    if issues:
        return provider_status(installed_channel, config), None
    if installed_channel not in _CHANNELS or config.channel != installed_channel:
        return provider_status(installed_channel, config), None
    current_key = _semver_key(current_version)
    api_url = releases_api_url(config)
    if api_url is None:
        return provider_status(installed_channel, config), None
    try:
        releases = json.loads(_request_bytes(api_url, _MAX_API_BYTES, api_json=True).decode("utf-8"))
        release = _select_release(releases, config)
        if release is None:
            return {
                **provider_status(installed_channel, config), "query_enabled": True,
                "available": False, "reason": f"Nenhuma release válida do canal {config.channel} foi publicada.",
            }, None
        version = str(release["_version"])
        manifest = _load_and_verify_manifest(release, config, version)
        version_key = _semver_key(version)
        if version_key <= current_key:
            return {
                **provider_status(installed_channel, config), "query_enabled": True,
                "available": False, "available_version": version,
                "reason": f"Este aplicativo já está atualizado no canal {config.channel}.",
            }, None
        asset_name = str(manifest["asset_name"])
        asset = _release_asset(release, asset_name)
        asset_url = _validate_asset_url(
            asset, _release_asset_url(config, str(release["tag_name"]), asset_name)
        )
        staging = Path(tempfile.mkdtemp(prefix="gim-release-update-"))
        installer_path = staging / asset_name
        try:
            size = _stream_download(asset_url, installer_path, str(manifest["asset_sha256"]))
        except Exception:
            cleanup_prepared_update(PreparedReleaseUpdate(
                str(config.channel), version, str(manifest["minimum_supported_version"]),
                asset_name, str(manifest["asset_sha256"]), installer_path, staging,
            ))
            raise
        minimum_key = _semver_key(manifest["minimum_supported_version"])
        prepared = PreparedReleaseUpdate(
            channel=str(config.channel),
            version=version,
            minimum_supported_version=str(manifest["minimum_supported_version"]),
            asset_name=asset_name,
            asset_sha256=str(manifest["asset_sha256"]),
            installer_path=installer_path,
            staging_directory=staging,
        )
        required = current_key < minimum_key
        return {
            **provider_status(installed_channel, config),
            "query_enabled": True,
            "available": True,
            "install_enabled": True,
            "available_version": version,
            "minimum_supported_version": prepared.minimum_supported_version,
            "required_update": required,
            "asset_name": asset_name,
            "asset_size": size,
            "reason": (
                f"Versão {version} validada por assinatura e SHA-256 e pronta para instalar."
                if not required else
                f"Atualização obrigatória: instale {version}; esta versão instalada está abaixo do mínimo suportado."
            ),
        }, prepared
    except (GitHubReleasesError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, OSError) as error:
        return {
            **provider_status(installed_channel, config),
            "query_enabled": True,
            "available": None,
            "install_enabled": False,
            "reason": str(error),
        }, None


def prepared_file_is_valid(prepared: PreparedReleaseUpdate, installed_channel: str | None) -> bool:
    """Recheck local staging and channel immediately before handing off to Setup."""
    if installed_channel != prepared.channel:
        return False
    try:
        directory = prepared.staging_directory.resolve()
        root = Path(tempfile.gettempdir()).resolve()
        installer = prepared.installer_path.resolve(strict=True)
        if directory.parent != root or not directory.name.startswith("gim-release-update-"):
            return False
        if installer.parent != directory or not installer.is_file() or installer.stat().st_size == 0:
            return False
        digest_state = hashlib.sha256()
        with installer.open("rb") as stream:
            for chunk in iter(lambda: stream.read(_READ_CHUNK), b""):
                digest_state.update(chunk)
        digest = digest_state.hexdigest()
    except OSError:
        return False
    return digest == prepared.asset_sha256
