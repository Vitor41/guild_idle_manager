"""Create the signed manifest assets required by the desktop updater."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


_CHANNELS = {"DEV", "beta", "stable"}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def create_signed_manifest(
    setup_path: Path,
    private_key_path: Path,
    version: str,
    channel: str,
    minimum_supported_version: str,
) -> tuple[bytes, bytes, str]:
    setup_path = setup_path.resolve()
    private_key_path = private_key_path.resolve()
    repository_root = Path(__file__).resolve().parents[1]
    if repository_root == private_key_path or repository_root in private_key_path.parents:
        raise ValueError("Guarde a chave privada fora da pasta do repositório.")
    if not setup_path.is_file():
        raise ValueError("O Setup indicado não existe.")
    if channel not in _CHANNELS or not _SEMVER.fullmatch(version) or not _SEMVER.fullmatch(minimum_supported_version):
        raise ValueError("Canal ou versão SemVer inválida.")

    encoded_key = private_key_path.read_text(encoding="ascii").strip()
    raw_key = base64.b64decode(encoded_key, validate=True)
    if len(raw_key) != 32:
        raise ValueError("A chave privada Ed25519 Base64 precisa conter 32 bytes.")
    private_key = Ed25519PrivateKey.from_private_bytes(raw_key)
    setup_bytes = setup_path.read_bytes()
    manifest = {
        "schema_version": 1,
        "app_id": "guild-idle-manager",
        "version": version,
        "channel": channel,
        "minimum_supported_version": minimum_supported_version,
        "asset_name": f"GuildIdleManager-{channel}-Setup.exe",
        "asset_sha256": hashlib.sha256(setup_bytes).hexdigest(),
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature_bytes = base64.b64encode(private_key.sign(manifest_bytes))
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return manifest_bytes, signature_bytes, base64.b64encode(public_key_bytes).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", required=True, type=Path)
    parser.add_argument("--private-key-file", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--channel", required=True, choices=sorted(_CHANNELS))
    parser.add_argument("--minimum-supported-version", required=True)
    parser.add_argument("--output-directory", type=Path)
    arguments = parser.parse_args()

    manifest, signature, public_key = create_signed_manifest(
        arguments.setup, arguments.private_key_file, arguments.version,
        arguments.channel, arguments.minimum_supported_version,
    )
    output = (arguments.output_directory or arguments.setup.resolve().parent).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "gim-release.json").write_bytes(manifest)
    (output / "gim-release.json.sig").write_bytes(signature)
    print(f"Manifesto assinado: {output / 'gim-release.json'}")
    print(f"Assinatura Ed25519: {output / 'gim-release.json.sig'}")
    print(f"Chave pública Base64 (use no build e no registro de distribuição): {public_key}")


if __name__ == "__main__":
    main()
