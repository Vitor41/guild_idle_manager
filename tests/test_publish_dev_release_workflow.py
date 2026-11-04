from pathlib import Path
import re
import shutil
import subprocess
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
        self.assertIn("$appVersionFile = Join-Path $output 'gim-app-version.txt'", self.workflow_text)
        self.assertIn("Test-Path -LiteralPath $appVersionFile -PathType Leaf", self.workflow_text)
        signer_step = self.workflow_text.split("- name: Assinar manifesto do Setup", 1)[1]
        signer_step = signer_step.split("- name: Publicar release", 1)[0]
        self.assertIn("--setup \"$output/GuildIdleManager-DEV-Setup.exe\"", signer_step)
        self.assertIn("--app-version-file $appVersionFile", signer_step)


if __name__ == "__main__":
    unittest.main()
