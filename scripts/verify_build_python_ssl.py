"""Reject build interpreters whose ssl.py depends on an unbundled Codex file."""

from __future__ import annotations

import ssl
import sys
import zipfile
from pathlib import Path


def verify_ssl_source(source_path: Path) -> None:
    source_name = str(source_path)
    if source_path.is_file():
        source = source_path.read_bytes()
    else:
        normalized = source_name.replace("/", "\\")
        marker = ".zip\\"
        archive_end = normalized.lower().find(marker)
        if archive_end < 0:
            raise FileNotFoundError(f"Cannot inspect the selected ssl.py module: {source_path}")
        archive_path = Path(normalized[:archive_end + len(".zip")])
        member = normalized[archive_end + len(marker):].replace("\\", "/")
        with zipfile.ZipFile(archive_path) as archive:
            source = archive.read(member)
    if b"codex-rejected-cas.pem" in source:
        raise RuntimeError(
            "The selected CPython ssl.py has a Codex-only file dependency that PyInstaller "
            "does not bundle. Use an official CPython distribution for release builds."
        )


def main() -> int:
    source_path = Path(ssl.__file__).resolve()
    try:
        verify_ssl_source(source_path)
    except (OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"CPython ssl.py is self-contained: {source_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
