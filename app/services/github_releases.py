"""Fail-closed configuration boundary for the future signed GitHub Releases feed.

This module deliberately performs no network or installation work. The release
contract and its verifier/installer must be implemented before a feed can be
queried, even if an operator supplies all settings.
"""

from dataclasses import dataclass
import base64
import binascii
import re

from app.core.config import settings


_GITHUB_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_CHANNEL = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_MANIFEST_ASSET = re.compile(r"^[A-Za-z0-9_.-]+\.json$")


@dataclass(frozen=True)
class GitHubReleasesConfig:
    owner: str | None
    repo: str | None
    channel: str | None
    public_key_b64: str | None
    manifest_asset: str


def configured_source() -> GitHubReleasesConfig:
    return GitHubReleasesConfig(
        owner=settings.github_releases_owner,
        repo=settings.github_releases_repo,
        channel=settings.github_releases_channel,
        public_key_b64=settings.github_releases_public_key,
        manifest_asset=settings.github_releases_manifest_asset,
    )


def configuration_issues(config: GitHubReleasesConfig | None = None) -> list[str]:
    """Return safe-to-display configuration issues; never performs I/O."""
    config = config or configured_source()
    issues: list[str] = []
    if not config.owner or not _GITHUB_COMPONENT.fullmatch(config.owner):
        issues.append("owner GitHub ausente ou inválido")
    if not config.repo or not _GITHUB_COMPONENT.fullmatch(config.repo):
        issues.append("repositório GitHub ausente ou inválido")
    if not config.channel or not _CHANNEL.fullmatch(config.channel):
        issues.append("canal de release ausente ou inválido")
    if not config.public_key_b64:
        issues.append("chave pública de assinatura ausente")
    else:
        try:
            public_key = base64.b64decode(config.public_key_b64, validate=True)
        except (binascii.Error, ValueError):
            issues.append("chave pública deve estar em Base64 válido")
        else:
            if len(public_key) != 32:
                issues.append("chave pública Ed25519 deve conter 32 bytes")
    if not config.manifest_asset or not _MANIFEST_ASSET.fullmatch(config.manifest_asset):
        issues.append("nome do asset de manifesto ausente ou inválido")
    return issues


def releases_api_url(config: GitHubReleasesConfig | None = None) -> str | None:
    """Build the official API URL only after validating all URL components."""
    config = config or configured_source()
    if configuration_issues(config):
        return None
    return f"https://api.github.com/repos/{config.owner}/{config.repo}/releases"


def provider_status() -> dict[str, object]:
    """Describe the provider gate without contacting GitHub."""
    issues = configuration_issues()
    if issues:
        reason = "Consulta e instalação via GitHub Releases estão desativadas: " + "; ".join(issues) + "."
    else:
        reason = (
            "Configuração reconhecida, mas consulta e instalação continuam desativadas até a implementação "
            "e revisão do leitor de releases, verificador de assinatura e aplicador transacional."
        )
    return {
        "channel": "github-releases",
        "configured": not issues,
        "available": None,
        "query_enabled": False,
        "install_enabled": False,
        "reason": reason,
    }
