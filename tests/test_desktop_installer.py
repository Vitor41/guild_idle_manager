import ctypes
import filecmp
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "desktop" / "Install-Desktop-Dev.ps1"
BUILT_PACKAGE = Path(os.environ.get(
    "GIM_TEST_BUILT_PACKAGE",
    str(ROOT / "dist" / "GuildIdleManager-DEV"),
))


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Requires Windows PowerShell")
class DesktopInstallerSafetyTests(unittest.TestCase):
    def _run_installer(
        self,
        local_app_data: Path,
        package: Path,
        setup_result: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = str(local_app_data)
        environment["TEMP"] = str(local_app_data / "Temp")
        if setup_result is not None:
            environment["GIM_SETUP_RESULT"] = str(setup_result)
            environment["GIM_SETUP_EXPECTED_LOCALAPPDATA"] = str(local_app_data)
        Path(environment["TEMP"]).mkdir(parents=True, exist_ok=True)
        command = [
                shutil.which("powershell.exe"),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(package / "Install-Desktop-Dev.ps1"),
                "-NoShortcut",
        ]
        return subprocess.run(
            command,
            cwd=package,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def _make_package(self, directory: Path) -> Path:
        package = directory / "package"
        app = package / "GuildIdleManager"
        app.mkdir(parents=True)
        (app / "GuildIdleManager.exe").write_bytes(b"Installer safety test placeholder")
        (package / "gim-app-version.txt").write_text("0.6.1", encoding="utf-8")
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
            package_version = (package / "gim-app-version.txt").read_text(encoding="utf-8").strip()
            local_app_data = root / "LocalAppData"
            save_marker = local_app_data / "GuildIdleManager" / "saves" / "sentinel.txt"
            save_marker.parent.mkdir(parents=True)
            save_marker.write_text("save-preserved", encoding="utf-8")

            first_install = self._run_installer(local_app_data, package)
            self.assertEqual(first_install.returncode, 0, first_install.stdout + first_install.stderr)
            installed_app = local_app_data / "Programs" / "GuildIdleManager"
            self.assertEqual(
                json.loads((installed_app / ".gim-desktop-install.json").read_text(encoding="utf-8")),
                {"product": "org.guildidlemanager.desktop", "channel": "DEV", "version": package_version},
            )
            self.assertTrue((installed_app / "GuildIdleManager.exe").is_file())
            self.assertEqual(save_marker.read_text(encoding="utf-8"), "save-preserved")

            obsolete = installed_app / "obsolete-from-old-version.txt"
            obsolete.write_text("old version", encoding="utf-8")
            update = self._run_installer(local_app_data, package)
            self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
            self.assertFalse(obsolete.exists())
            self.assertEqual(save_marker.read_text(encoding="utf-8"), "save-preserved")

    @unittest.skipUnless(BUILT_PACKAGE.is_dir(), "Build the DEV package before testing rollback after copy")
    def test_post_copy_failure_restores_previous_install_and_preserves_save(self):
        with tempfile.TemporaryDirectory(prefix="gim-installer-rollback-") as directory:
            root = Path(directory)
            package = root / "package"
            shutil.copytree(BUILT_PACKAGE, package)
            shutil.copy2(INSTALLER, package / INSTALLER.name)
            local_app_data = root / "LocalAppData"
            target = local_app_data / "Programs" / "GuildIdleManager"
            target.mkdir(parents=True)
            old_exe = target / "GuildIdleManager.exe"
            old_exe.write_bytes(b"previous-version-executable")
            old_file = target / "previous-version-only.txt"
            old_file.write_text("previous-version", encoding="utf-8")
            marker = target / ".gim-desktop-install.json"
            marker.write_text(
                '{"product":"org.guildidlemanager.desktop","channel":"DEV","version":"0.6.1"}',
                encoding="utf-8",
            )
            save_marker = local_app_data / "GuildIdleManager" / "saves" / "sentinel.txt"
            save_marker.parent.mkdir(parents=True)
            save_marker.write_text("save-preserved", encoding="utf-8")

            # A directory at the result path makes the final SUCCESS write fail,
            # after the staged app files have already replaced the target files.
            forced_result_failure = root / "result-path-is-directory"
            forced_result_failure.mkdir()
            result = self._run_installer(local_app_data, package, forced_result_failure)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(old_exe.read_bytes(), b"previous-version-executable")
            self.assertEqual(old_file.read_text(encoding="utf-8"), "previous-version")
            self.assertEqual(
                marker.read_text(encoding="utf-8"),
                '{"product":"org.guildidlemanager.desktop","channel":"DEV","version":"0.6.1"}',
            )
            self.assertFalse((target / "gim-app-version.txt").exists())
            self.assertEqual(save_marker.read_text(encoding="utf-8"), "save-preserved")
            self.assertFalse(list(target.parent.glob("GuildIdleManager.backup-*")))

    @unittest.skipUnless(BUILT_PACKAGE.is_dir(), "Build the DEV package before testing backup cleanup failure")
    def test_backup_cleanup_failure_after_success_keeps_new_install_and_backup(self):
        with tempfile.TemporaryDirectory(prefix="gim-installer-cleanup-") as directory:
            root = Path(directory)
            package = root / "package"
            shutil.copytree(BUILT_PACKAGE, package)
            shutil.copy2(INSTALLER, package / INSTALLER.name)
            package_version = (package / "gim-app-version.txt").read_text(encoding="utf-8").strip()
            local_app_data = root / "LocalAppData"
            target = local_app_data / "Programs" / "GuildIdleManager"
            target.mkdir(parents=True)
            (target / "GuildIdleManager.exe").write_bytes(b"previous-version-executable")
            (target / ".gim-desktop-install.json").write_text(
                '{"product":"org.guildidlemanager.desktop","channel":"DEV","version":"0.6.1"}',
                encoding="utf-8",
            )
            lock_contents = b"x" * (2 * 1024 * 1024)
            (target / "cleanup-lock.bin").write_bytes(lock_contents)
            save_marker = local_app_data / "GuildIdleManager" / "saves" / "sentinel.txt"
            save_marker.parent.mkdir(parents=True)
            save_marker.write_text("save-preserved", encoding="utf-8")
            setup_result = root / "setup-result.txt"

            environment = os.environ.copy()
            environment["LOCALAPPDATA"] = str(local_app_data)
            environment["TEMP"] = str(local_app_data / "Temp")
            environment["GIM_SETUP_RESULT"] = str(setup_result)
            environment["GIM_SETUP_EXPECTED_LOCALAPPDATA"] = str(local_app_data)
            Path(environment["TEMP"]).mkdir(parents=True, exist_ok=True)
            command = [
                shutil.which("powershell.exe"),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(package / "Install-Desktop-Dev.ps1"),
                "-NoShortcut",
            ]
            process = subprocess.Popen(
                command,
                cwd=package,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
            ]
            create_file.restype = ctypes.c_void_p
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.c_void_p]
            close_handle.restype = ctypes.c_int
            invalid_handle = ctypes.c_void_p(-1).value
            locked_file = None
            backup = None
            handle = None
            deadline = time.monotonic() + 120
            try:
                while time.monotonic() < deadline and process.poll() is None:
                    for candidate in target.parent.glob("GuildIdleManager.backup-*"):
                        candidate_file = candidate / "cleanup-lock.bin"
                        try:
                            if candidate_file.stat().st_size != len(lock_contents):
                                continue
                        except OSError:
                            continue
                        candidate_handle = create_file(
                            str(candidate_file),
                            0x80000000,  # GENERIC_READ
                            0x00000001,  # FILE_SHARE_READ (disallow deletion)
                            None,
                            3,  # OPEN_EXISTING
                            0x00000080,  # FILE_ATTRIBUTE_NORMAL
                            None,
                        )
                        if candidate_handle != invalid_handle:
                            backup = candidate
                            locked_file = candidate_file
                            handle = candidate_handle
                            break
                    if handle is not None:
                        break
                    time.sleep(0.001)
                self.assertIsNotNone(handle, "Did not acquire the old backup file before cleanup")
                stdout, stderr = process.communicate(timeout=max(1, deadline - time.monotonic()))
            finally:
                if handle is not None:
                    close_handle(handle)
                if process.poll() is None:
                    process.kill()
                    process.communicate()

            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertTrue(setup_result.read_text(encoding="utf-8").startswith("SUCCESS|"))
            self.assertEqual(
                json.loads((target / ".gim-desktop-install.json").read_text(encoding="utf-8")),
                {"product": "org.guildidlemanager.desktop", "channel": "DEV", "version": package_version},
            )
            self.assertTrue(
                filecmp.cmp(
                    target / "GuildIdleManager.exe",
                    package / "GuildIdleManager" / "GuildIdleManager.exe",
                    shallow=False,
                )
            )
            self.assertEqual(save_marker.read_text(encoding="utf-8"), "save-preserved")
            self.assertIsNotNone(backup)
            self.assertTrue(locked_file.is_file())
            self.assertEqual(locked_file.read_bytes(), lock_contents)


if __name__ == "__main__":
    unittest.main()
