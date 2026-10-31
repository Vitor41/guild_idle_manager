"""Generate an Ed25519 release key pair without placing it in the checkout."""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def generate_key(private_key_path: Path) -> str:
    target = private_key_path.expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[1]
    if target == repository_root or repository_root in target.parents:
        raise ValueError("Salve a chave privada fora da pasta do repositório.")
    target.parent.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with target.open("x", encoding="ascii", newline="\n") as key_file:
        key_file.write(base64.b64encode(private_bytes).decode("ascii") + "\n")

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(public_bytes).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-key-file", required=True, type=Path)
    args = parser.parse_args()
    public_key = generate_key(args.private_key_file)
    print(f"Chave privada criada fora do repositório: {args.private_key_file.expanduser().resolve()}")
    print("Cadastre o conteúdo desse arquivo como segredo GIM_RELEASE_PRIVATE_KEY_B64.")
    print(f"Cadastre este valor como variável GIM_RELEASE_PUBLIC_KEY_B64: {public_key}")


if __name__ == "__main__":
    main()
