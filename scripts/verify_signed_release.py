"""Verify a local signed release manifest and the exact Setup bytes it describes."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def verify_signed_release(
    setup_path: Path,
    manifest_path: Path,
    signature_path: Path,
    public_key_b64: str,
    expected_version: str,
    expected_channel: str = "DEV",
    expected_minimum_supported_version: str = "0.3.1",
) -> dict[str, object]:
    """Validate Ed25519, manifest identity/version, and the Setup SHA-256."""
    setup_path = Path(setup_path)
    manifest_bytes = Path(manifest_path).read_bytes()
    try:
        signature = base64.b64decode(Path(signature_path).read_bytes().strip(), validate=True)
        public_key_bytes = base64.b64decode(public_key_b64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Chave pública ou assinatura Base64 inválida.") from error
    if len(public_key_bytes) != 32:
        raise ValueError("A chave pública Ed25519 precisa conter 32 bytes.")
    if not setup_path.is_file():
        raise ValueError("O Setup assinado não existe.")
    if not _SEMVER.fullmatch(expected_version) or not _SEMVER.fullmatch(expected_minimum_supported_version):
        raise ValueError("Versão esperada inválida.")

    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, manifest_bytes)
    except (InvalidSignature, ValueError) as error:
        raise ValueError("A assinatura Ed25519 do manifesto é inválida.") from error

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("O manifesto assinado não é JSON UTF-8 válido.") from error
    if not isinstance(manifest, dict):
        raise ValueError("O manifesto assinado precisa ser um objeto JSON.")
    if manifest.get("schema_version") != 1 or isinstance(manifest.get("schema_version"), bool):
        raise ValueError("Versão do schema do manifesto não suportada.")
    if manifest.get("app_id") != "guild-idle-manager":
        raise ValueError("O manifesto pertence a outro produto.")
    if manifest.get("version") != expected_version or manifest.get("channel") != expected_channel:
        raise ValueError("Canal ou versão do manifesto não corresponde ao candidato.")
    if manifest.get("minimum_supported_version") != expected_minimum_supported_version:
        raise ValueError("Versão mínima do manifesto não corresponde à política esperada.")
    expected_asset_name = f"GuildIdleManager-{expected_channel}-Setup.exe"
    if manifest.get("asset_name") != expected_asset_name:
        raise ValueError("Nome de Setup no manifesto não corresponde ao candidato.")

    expected_digest = manifest.get("asset_sha256")
    if not isinstance(expected_digest, str) or not _SHA256.fullmatch(expected_digest):
        raise ValueError("SHA-256 do Setup no manifesto é inválido.")
    actual_digest = hashlib.sha256(setup_path.read_bytes()).hexdigest()
    if actual_digest != expected_digest:
        raise ValueError("SHA-256 do Setup difere do manifesto assinado.")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--public-key-base64", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--channel", choices=("DEV", "beta", "stable"), default="DEV")
    parser.add_argument("--minimum-supported-version", default="0.3.1")
    args = parser.parse_args()

    manifest = verify_signed_release(
        args.setup,
        args.manifest,
        args.signature,
        args.public_key_base64,
        args.version,
        args.channel,
        args.minimum_supported_version,
    )
    print(f"VERIFIED: {manifest['channel']} {manifest['version']} Setup SHA-256 {manifest['asset_sha256']}")


if __name__ == "__main__":
    main()
