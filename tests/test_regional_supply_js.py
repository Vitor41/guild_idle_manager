import shutil
import subprocess
import unittest
from pathlib import Path


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is needed for the regional supply browser-script regression")
class RegionalSupplyScriptTests(unittest.TestCase):
    def test_prepared_supply_skips_inventory_quote_and_keeps_new_preparation_guard(self):
        script = Path(__file__).resolve().parent / "js" / "regional-supply.test.mjs"
        result = subprocess.run(
            [NODE, "--test", str(script)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
