"""Regression coverage for the Codex-patched ssl.py packaging failure."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.verify_build_python_ssl import verify_ssl_source


PATCHED_SSL_FIXTURE = '''import os

class _SSLContext:
    @staticmethod
    def load_verify_locations(self, cafile=None):
        if not os.path.isfile(cafile):
            raise FileNotFoundError(2, "No such file or directory", cafile)

class SSLContext:
    def __new__(cls):
        self = object.__new__(cls)
        # Codex: distrust emSign ECC Root CA - G3.
        _SSLContext.load_verify_locations(
            self, cafile=os.path.join(os.path.dirname(__file__), 'codex-rejected-cas.pem')
        )
        self.verify_mode = "CERT_REQUIRED"
        self.check_hostname = True
        return self
'''


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DesktopBuildSslTests(unittest.TestCase):
    def test_packaged_ssl_patch_reproduces_errno_2_and_build_guard_rejects_it(self):
        with tempfile.TemporaryDirectory(prefix="gim-ssl-build-test-") as directory:
            source = Path(directory) / "ssl.py"
            source.write_text(PATCHED_SSL_FIXTURE, encoding="utf-8")
            patched = _load_module(source, "gim_patched_ssl_fixture")

            with self.assertRaises(FileNotFoundError) as raised:
                patched.SSLContext()
            self.assertEqual(raised.exception.errno, 2)
            with self.assertRaisesRegex(RuntimeError, "official CPython"):
                verify_ssl_source(source)

    def test_clean_ssl_source_passes_build_guard(self):
        with tempfile.TemporaryDirectory(prefix="gim-ssl-build-test-") as directory:
            source = Path(directory) / "ssl.py"
            source.write_text("class SSLContext: pass\n", encoding="utf-8")
            verify_ssl_source(source)

    def test_zipimported_ssl_patch_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="gim-ssl-build-test-") as directory:
            archive_path = Path(directory) / "python314.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("ssl.pyc", b"module references codex-rejected-cas.pem")

            source = Path(f"{archive_path}\\ssl.pyc")
            with self.assertRaisesRegex(RuntimeError, "official CPython"):
                verify_ssl_source(source)


if __name__ == "__main__":
    unittest.main()
