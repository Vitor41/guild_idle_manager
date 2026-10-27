import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "desktop" / "Install-Desktop-Dev.ps1"
BUILT_PACKAGE = ROOT / "dist" / "GuildIdleManager-DEV"


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Requires Windows PowerShell")
class DesktopInstallerSafetyTests(unittest.TestCase):
    def _run_installer(self, local_app_data: Path, package: Path) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = str(local_app_data)
        environment["TEMP"] = str(local_app_data / "Temp")
        Path(environment["TEMP"]).mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            [
                shutil.which("powershell.exe"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(package / "Install-Desktop-Dev.ps1"),
                "-NoShortcut",
            ],
            cwd=package,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def _make_package(self, directory: Path) -> Path:
        package = directory / "package"
        app = package / "GuildIdleManager"
        app.mkdir(parents=True)
        (app / "GuildIdleManager.exe").write_bytes(b"Installer safety test placeholder")
        shutil.copy2(INSTALLER, package / INSTALLER.name)
        return package

    def test_foreign_install_folder_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="gim-installer-foreign-") as directory:
            root = Path(directory)
            package = self._make_package(root)
            local_app_data = root / "LocalAppData"
            target = local_app_data / "Programs" / "GuildIdleManager"
            target.mkdir(parents=True)
            sentinel = target / "user-file.txt"
            sentinel.write_text("preserve", encoding="utf-8")

            result = self._run_installer(local_app_data, package)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
            self.assertFalse((target / ".gim-desktop-install.json").exists())

    def test_junction_install_target_is_refused_without_touching_target(self):
        with tempfile.TemporaryDirectory(prefix="gim-installer-junction-") as directory:
            root = Path(directory)
            package = self._make_package(root)
            local_app_data = root / "LocalAppData"
            programs = local_app_data / "Programs"
            programs.mkdir(parents=True)
            external = root / "external-target"
            external.mkdir()
            sentinel = external / "user-file.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            junction = programs / "GuildIdleManager"
            ps_quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            create_junction = (
                f"New-Item -ItemType Junction -Path {ps_quote(junction)} "
                f"-Target {ps_quote(external)} | Out-Null"
            )
            created = subprocess.run(
                [shutil.which("powershell.exe"), "-NoProfile", "-Command", create_junction],
                capture_output=True,
                text=True,
                check=False,
            )
            if created.returncode != 0:
                self.skipTest(f"Could not create a test junction: {created.stderr}")

            result = self._run_installer(local_app_data, package)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
            self.assertTrue(junction.exists())

    @unittest.skipUnless(BUILT_PACKAGE.is_dir(), "Build the DEV package before testing first install and update")
    def test_first_install_and_managed_update_preserve_saves_and_replace_app_files(self):
        with tempfile.TemporaryDirectory(prefix="gim-installer-managed-") as directory:
            root = Path(directory)
            package = root / "package"
            shutil.copytree(BUILT_PACKAGE, package)
            shutil.copy2(INSTALLER, package / INSTALLER.name)
            local_app_data = root / "LocalAppData"
            save_marker = local_app_data / "GuildIdleManager" / "saves" / "sentinel.txt"
            save_marker.parent.mkdir(parents=True)
            save_marker.write_text("save-preserved", encoding="utf-8")

            first_install = self._run_installer(local_app_data, package)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            installed_app = local_app_data / "Programs" / "GuildIdleManager"
            self.assertEqual(
                (installed_app / ".gim-desktop-install.json").read_text(encoding="utf-8").strip(),
                '{"product":"org.guildidlemanager.desktop","channel":"DEV"}',
            )
            self.assertTrue((installed_app / "GuildIdleManager.exe").is_file())
            self.assertEqual(save_marker.read_text(encoding="utf-8"), "save-preserved")

            obsolete = installed_app / "obsolete-from-old-version.txt"
            obsolete.write_text("old version", encoding="utf-8")
            update = self._run_installer(local_app_data, package)
            self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
            self.assertFalse(obsolete.exists())
            self.assertEqual(save_marker.read_text(encoding="utf-8"), "save-preserved")


if __name__ == "__main__":
    unittest.main()
