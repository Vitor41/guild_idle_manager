import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-dev-release.yml"
BUILD_ONLY_WORKFLOW = ROOT / ".github" / "workflows" / "build-dev-candidate.yml"
BUILD_SCRIPT = ROOT / "scripts" / "build_desktop_dev.ps1"
SIGNER = ROOT / "scripts" / "sign_github_release.py"


class PublishDevReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_text = WORKFLOW.read_text(encoding="utf-8")

    def test_tag_fetch_refspec_expands_to_matching_remote_and_local_refs(self):
        match = re.search(
            r'^\s*git fetch --no-tags origin "([^"\r\n]+)"$',
            self.workflow_text,
            re.MULTILINE,
        )
        self.assertIsNotNone(match, "expected exactly one quoted git fetch refspec")
        refspec_expression = match.group(1)
        self.assertIn("${env:RELEASE_TAG}", refspec_expression)

        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is unavailable for evaluating the workflow interpolation")
        command = (
            "$env:RELEASE_TAG = 'DEV-v0.3.2'; "
            f'"{refspec_expression}"'
        )
        result = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.stdout.strip(),
            "refs/tags/DEV-v0.3.2:refs/tags/DEV-v0.3.2",
        )

    def test_workflow_has_no_ambiguous_env_variable_colon_interpolation(self):
        ambiguous = re.findall(r"\$env:[A-Za-z_][A-Za-z0-9_]*:", self.workflow_text)
        self.assertEqual(ambiguous, [])

    def test_signer_receives_version_sidecar_from_the_same_release_package(self):
        assignment = re.search(
            r"^\s*\$appVersionFile\s*=\s*(.+)$",
            self.workflow_text.split("- name: Assinar manifesto do Setup", 1)[1].split(
                "- name: Publicar release", 1
            )[0],
            re.MULTILINE,
        )
        self.assertIsNotNone(assignment, "the signing step must resolve its packaged version sidecar")
        self.assertIn("Test-Path -LiteralPath $appVersionFile -PathType Leaf", self.workflow_text)
        signer_step = self.workflow_text.split("- name: Assinar manifesto do Setup", 1)[1]
        signer_step = signer_step.split("- name: Publicar release", 1)[0]
        self.assertIn("--setup \"$output/GuildIdleManager-DEV-Setup.exe\"", signer_step)
        self.assertIn("--app-version-file $appVersionFile", signer_step)

    def test_release_smokes_use_an_isolated_profile_and_check_campaigns_and_launcher(self):
        smoke_step = self.workflow_text.split("- name: Verificar pacote em perfil temporario isolado", 1)[1].split(
            "- name: Assinar manifesto do Setup", 1
        )[0]
        for required in (
            "$env:RUNNER_TEMP",
            "$env:LOCALAPPDATA",
            "$env:APPDATA",
            "$env:GIM_SMOKE_TEMP_DIR",
            "$env:TEMP",
            "$env:TMP",
            "--smoke",
            "--launcher-smoke",
            "WaitForExit(120000)",
            "WaitForExit(30000)",
            "seleção de campanhas",
            "PASS: packaged launcher entry",
        ):
            with self.subTest(required=required):
                self.assertIn(required, smoke_step)

    def test_build_only_candidate_workflow_is_sha_pinned_secret_free_and_non_publishing(self):
        workflow = BUILD_ONLY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("candidate_commit_sha", workflow)
        self.assertIn("runs-on: windows-2025", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("${{ inputs.candidate_commit_sha }}", workflow)
        self.assertIn("validate_desktop_setup_candidate.ps1", workflow)
        self.assertIn("GIM_RELEASE_PUBLIC_KEY_B64", workflow)
        self.assertIn("actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9", workflow)
        self.assertNotIn("GIM_RELEASE_PRIVATE_KEY_B64", workflow)
        self.assertNotIn("gh release create", workflow)
        self.assertNotIn("workflow_run:", workflow)
        self.assertFalse((ROOT / ".github" / "workflows" / "sign-dev-candidate.yml").exists())

    def test_release_verifies_signed_manifest_before_publishing(self):
        verify_step = self.workflow_text.split("- name: Verificar assinatura do manifesto localmente", 1)[1].split(
            "- name: Publicar release", 1
        )[0]
        for required in (
            "scripts/verify_signed_release.py",
            "--setup \"$output/GuildIdleManager-DEV-Setup.exe\"",
            "--manifest \"$output/gim-release.json\"",
            "--signature \"$output/gim-release.json.sig\"",
            "--public-key-base64 $env:RELEASE_PUBLIC_KEY_B64",
            "--version $version",
            "--channel DEV",
        ):
            with self.subTest(required=required):
                self.assertIn(required, verify_step)
        self.assertLess(
            self.workflow_text.index("- name: Verificar assinatura do manifesto localmente"),
            self.workflow_text.index("- name: Publicar release"),
        )

    def test_release_signing_requires_default_branch_merged_tag_and_environment(self):
        for required in (
            "if: github.ref == format('refs/heads/{0}', github.event.repository.default_branch)",
            "environment: release-signing",
            "git merge-base --is-ancestor $env:RELEASE_TAG HEAD",
            "github.event_name == 'workflow_dispatch'",
            "RELEASE_PRIVATE_KEY_B64: ${{ secrets.GIM_RELEASE_PRIVATE_KEY_B64 }}",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.workflow_text)

    def test_signer_sidecar_resolution_matches_the_built_package_layout(self):
        signer_step = self.workflow_text.split("- name: Assinar manifesto do Setup", 1)[1]
        signer_step = signer_step.split("- name: Publicar release", 1)[0]
        assignment = re.search(r"^\s*\$appVersionFile\s*=\s*(.+)$", signer_step, re.MULTILINE)
        self.assertIsNotNone(assignment, "the signing step must resolve its packaged version sidecar")
        package_root_assignment = re.search(r"^\s*\$packageRoot\s*=\s*(.+)$", signer_step, re.MULTILINE)
        self.assertIsNotNone(package_root_assignment, "the signing step must resolve the built package root")
        build_script = BUILD_SCRIPT.read_text(encoding="utf-8")
        built_root_assignment = re.search(r"^\s*\$packageRoot\s*=\s*(.+)$", build_script, re.MULTILINE)
        self.assertIsNotNone(built_root_assignment, "the build script must define its package root")
        built_sidecar_assignment = re.search(
            r"^\s*\(Join-Path \$packageRoot '([^']+)'\),\s*$", build_script, re.MULTILINE
        )
        self.assertIsNotNone(built_sidecar_assignment, "the build script must write the version inside its package root")

        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is unavailable for evaluating the build and workflow paths")

        with tempfile.TemporaryDirectory(prefix="gim-release-package-layout-") as directory:
            output = Path(directory) / "dist" / "staging" / "release-DEV-v0.6.3"
            escaped_output = str(output).replace("'", "''")
            build_path_command = (
                "$ErrorActionPreference = 'Stop'; "
                f"$buildRoot = '{escaped_output}'; $Channel = 'DEV'; "
                f"$packageRoot = {built_root_assignment.group(1).strip()}; "
                "[System.IO.Path]::GetFileName($packageRoot)"
            )
            built_name_result = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-Command", build_path_command],
                check=True,
                capture_output=True,
                text=True,
            )
            package_name = built_name_result.stdout.strip()
            self.assertTrue(package_name, "the build script must produce a package directory name")

            package_root = output / package_name
            package_root.mkdir(parents=True)
            sidecar = package_root / built_sidecar_assignment.group(1)
            sidecar.write_text("0.6.3\n", encoding="utf-8")
            (output / "gim-app-version.txt").write_text("0.6.2\n", encoding="utf-8")

            command = (
                "$ErrorActionPreference = 'Stop'; "
                f"$output = '{escaped_output}'; "
                f"$packageRoot = {package_root_assignment.group(1).strip()}; "
                f"$appVersionFile = {assignment.group(1).strip()}; "
                "if (-not (Test-Path -LiteralPath $appVersionFile -PathType Leaf)) { exit 41 }; "
                "[System.IO.Path]::GetFullPath($appVersionFile)"
            )
            result = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-Command", command],
                check=True,
                capture_output=True,
                text=True,
            )
            resolved_sidecar = Path(result.stdout.strip())
            self.assertEqual(resolved_sidecar, sidecar.resolve())

            setup = output / "GuildIdleManager-DEV-Setup.exe"
            setup.write_bytes(b"isolated package setup bytes for the workflow signing smoke")
            key = Ed25519PrivateKey.generate()
            raw_private_key = key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            private_key_file = Path(directory) / "temporary-test-private-key.b64"
            private_key_file.write_text(base64.b64encode(raw_private_key).decode("ascii"), encoding="ascii")
            public_key = key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            public_key_b64 = base64.b64encode(public_key).decode("ascii")
            subprocess.run(
                [
                    sys.executable,
                    str(SIGNER),
                    "--setup", str(setup),
                    "--private-key-file", str(private_key_file),
                    "--version", "0.6.3",
                    "--channel", "DEV",
                    "--minimum-supported-version", "0.3.1",
                    "--expected-public-key-base64", public_key_b64,
                    "--app-version-file", str(resolved_sidecar),
                    "--output-directory", str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest_bytes = (output / "gim-release.json").read_bytes()
            manifest = json.loads(manifest_bytes)
            self.assertEqual(manifest["version"], "0.6.3")
            self.assertEqual(manifest["asset_name"], setup.name)
            self.assertEqual(manifest["asset_sha256"], hashlib.sha256(setup.read_bytes()).hexdigest())
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                base64.b64decode((output / "gim-release.json.sig").read_bytes(), validate=True),
                manifest_bytes,
            )


if __name__ == "__main__":
    unittest.main()
