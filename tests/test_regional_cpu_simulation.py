import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.balance.simulate_regional_cpu_campaigns import (
    _align_rebellion_funnel_to_roll_cycles,
    _clone_campaign_database,
)


class RegionalCpuSimulationTests(unittest.TestCase):
    def test_clone_rekeys_campaign_rows_and_keeps_template_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / "template.db"
            clone = Path(temp_dir) / "clone.db"
            old_id = "00000000-0000-4000-8000-000000000001"
            new_id = "00000000-0000-4000-8000-000000000002"
            with closing(sqlite3.connect(template)) as db:
                db.execute(
                    "CREATE TABLE campaign_metadata (campaign_id TEXT PRIMARY KEY, campaign_name TEXT, home_region TEXT)"
                )
                db.execute(
                    "INSERT INTO campaign_metadata VALUES (?, ?, ?)",
                    (old_id, "Template", "Vale da Fronteira"),
                )
                db.execute("CREATE TABLE owned_rows (id INTEGER PRIMARY KEY, campaign_id TEXT, value TEXT)")
                db.execute("INSERT INTO owned_rows VALUES (1, ?, 'scoped')", (old_id,))
                db.execute("INSERT INTO owned_rows VALUES (2, NULL, 'global')")
                db.execute("CREATE TABLE shared_rows (id INTEGER PRIMARY KEY, value TEXT)")
                db.execute("INSERT INTO shared_rows VALUES (1, 'shared')")
                db.commit()

            _clone_campaign_database(template, clone, new_id)

            with closing(sqlite3.connect(clone)) as db:
                metadata = db.execute(
                    "SELECT campaign_id, campaign_name, home_region FROM campaign_metadata"
                ).fetchone()
                owned = db.execute("SELECT campaign_id, value FROM owned_rows").fetchone()
                global_row = db.execute("SELECT campaign_id, value FROM owned_rows WHERE id = 2").fetchone()
                shared = db.execute("SELECT value FROM shared_rows").fetchone()
            regions = (
                "Vale da Fronteira", "Bosque de Âmbar", "Costa das Brumas",
                "Terras de Cinza", "Picos do Norte",
            )
            expected_home = regions[int.from_bytes(hashlib.sha256(new_id.encode("utf-8")).digest()[:4], "big") % 5]
            self.assertEqual(metadata, (new_id, f"CPU balance {new_id}", expected_home))
            self.assertEqual(owned, (new_id, "scoped"))
            self.assertEqual(global_row, (None, "global"))
            self.assertEqual(shared, ("shared",))
            with closing(sqlite3.connect(template)) as db:
                self.assertEqual(
                    db.execute("SELECT campaign_id, campaign_name FROM campaign_metadata").fetchone(),
                    (old_id, "Template"),
                )
                self.assertEqual(db.execute("SELECT campaign_id FROM owned_rows").fetchone()[0], old_id)

    def test_rebellion_funnel_aligns_prior_snapshot_and_attributes_cooldown(self):
        campaign = {
            "rebellion_funnel_by_cycle": [
                {
                    "cycle": 0, "pressure_target_regions": ["vale-fronteira"],
                    "threshold_eligible_regions": ["vale-fronteira"],
                    "selected_roll_region": None, "selected_roll_count": 0,
                    "rebellion_opened_regions": [],
                },
                {
                    "cycle": 1, "pressure_target_regions": ["vale-fronteira"],
                    "threshold_eligible_regions": ["vale-fronteira"],
                    "selected_roll_region": "vale-fronteira", "selected_roll_count": 1,
                    "rebellion_opened_regions": [],
                },
                {
                    "cycle": 2, "pressure_target_regions": [],
                    "threshold_eligible_regions": [],
                    "selected_roll_region": None, "selected_roll_count": 0,
                    "rebellion_opened_regions": [],
                },
            ],
        }

        _align_rebellion_funnel_to_roll_cycles([campaign])

        funnel = campaign["rebellion_funnel_by_cycle"]
        self.assertEqual(funnel[0]["threshold_eligible_regions"], [])
        self.assertEqual(funnel[1]["threshold_eligible_regions"], ["vale-fronteira"])
        self.assertEqual(funnel[1]["selected_roll_region"], "vale-fronteira")
        self.assertEqual(funnel[2]["cooldown_veto_regions"], ["vale-fronteira"])
        self.assertEqual(
            campaign["regional_rebellion_funnel"]["vale-fronteira"]["pressure_target_cycles"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
