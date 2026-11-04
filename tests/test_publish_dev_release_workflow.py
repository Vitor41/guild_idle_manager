from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish-dev-release.yml"


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

    def test_signer_sidecar_resolution_matches_the_built_package_layout(self):
        signer_step = self.workflow_text.split("- name: Assinar manifesto do Setup", 1)[1]
        signer_step = signer_step.split("- name: Publicar release", 1)[0]
        assignment = re.search(r"^\s*\$appVersionFile\s*=\s*(.+)$", signer_step, re.MULTILINE)
        self.assertIsNotNone(assignment, "the signing step must resolve its packaged version sidecar")
        package_root_assignment = re.search(r"^\s*\$packageRoot\s*=\s*(.+)$", signer_step, re.MULTILINE)
        self.assertIsNotNone(package_root_assignment, "the signing step must resolve the built package root")

        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is unavailable for evaluating the workflow path")

        with tempfile.TemporaryDirectory(prefix="gim-release-package-layout-") as directory:
            output = Path(directory) / "dist" / "staging" / "release-DEV-v0.6.3"
            package_root = output / "GuildIdleManager"
            package_root.mkdir(parents=True)
            sidecar = package_root / "gim-app-version.txt"
            sidecar.write_text("0.6.3\n", encoding="utf-8")
            # The failed workflow looked in output itself; this decoy makes that path wrong.
            (output / "gim-app-version.txt").write_text("0.6.2\n", encoding="utf-8")

            escaped_output = str(output).replace("'", "''")
            command = (
                "$ErrorActionPreference = 'Stop'; "
                f"$output = '{escaped_output}'; "
                f"$packageRoot = {package_root_assignment.group(1).strip()}; "
                f"$appVersionFile = {assignment.group(1).strip()}; "
                "if (-not (Test-Path -LiteralPath $appVersionFile -PathType Leaf)) { exit 41 }; "
                "[System.IO.File]::ReadAllText($appVersionFile).Trim()"
            )
            result = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-Command", command],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.stdout.strip(), "0.6.3")


if __name__ == "__main__":
    unittest.main()
