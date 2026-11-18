import tempfile
import unittest
from pathlib import Path

from scripts.balance.compare_ml050_cpu_campaigns import (
    PROFILE_NAMES,
    _aggregate_checkpoint,
    _blank_profile_metrics,
    _configuration_sha256,
    _load_or_create_checkpoint,
    _validate_checkpoint_results,
    _write_json_atomic,
)


ROOT = Path(__file__).resolve().parents[1]


class ML050ComparisonAggregationTests(unittest.TestCase):
    def test_aggregates_raw_profile_counters_and_rejects_missing_metrics(self):
        configuration = {
            "seed_start": 2026110301,
            "campaign_count": 1,
            "horizon_cycles": 100,
            "seeds": [2026110301],
            "profiles": list(PROFILE_NAMES),
            "variants": ["previous", "ml050"],
            "action_types": ["contract", "dungeon", "boss", "portal", "other"],
            "app_mode": "desktop",
            "python_version": "test",
            "source_sha256": {"fixture.py": "fixture-hash"},
        }
        arms = {}
        for variant, contract_starts in (("previous", 3), ("ml050", 2)):
            profiles = {}
            for profile in PROFILE_NAMES:
                metrics = _blank_profile_metrics()
                metrics["cpu_guild_states"] = 1
                metrics["action_starts_by_type"]["contract"] = contract_starts
                metrics["guild_level_final_sum"] = 6
                metrics["guild_level_gain_sum"] = 5
                metrics["mercenary_level_final_sum"] = 4
                metrics["active_mercenary_count"] = 1
                metrics["xp_earned"] = 250
                metrics["active_cycles"] = 80
                metrics["possible_guild_cycles"] = 100
                metrics["max_inactive_streak_sum"] = 12
                metrics["max_inactive_streak"] = 12
                profiles[profile] = metrics
            arms[variant] = {
                "profiles": profiles,
                "cpu_actions_total": contract_starts,
                "cpu_xp_net": 250,
            }
        checkpoint = {
            "schema_version": 1,
            "configuration": configuration,
            "configuration_sha256": "fixture-config-hash",
            "results": {str(configuration["seed_start"]): arms},
        }

        with tempfile.TemporaryDirectory(prefix="ml050-aggregate-test-", dir=ROOT) as directory:
            root = Path(directory)
            report = _aggregate_checkpoint(
                checkpoint,
                root / "checkpoint.json",
                root / "paired",
            )
            self.assertEqual(
                report["profile_summary"]["strong"]["previous"]["action_starts_by_type"]["contract"],
                3,
            )
            self.assertEqual(
                report["profile_summary"]["strong"]["ml050"]["activity_starts_total"],
                2,
            )
            self.assertTrue((root / "paired.json").is_file())
            self.assertTrue((root / "paired.md").is_file())

        del checkpoint["results"][str(configuration["seed_start"])]["ml050"]["profiles"]["new"]["xp_earned"]
        with self.assertRaisesRegex(ValueError, "missing required metrics: xp_earned"):
            _aggregate_checkpoint(checkpoint, Path("checkpoint.json"), Path("paired"))

    def test_checkpoint_rejects_changed_sources_and_partial_seed_pairs(self):
        configuration = {
            "seed_start": 10,
            "campaign_count": 1,
            "horizon_cycles": 2,
            "seeds": [10],
            "profiles": list(PROFILE_NAMES),
            "variants": ["previous", "ml050"],
            "action_types": ["contract", "dungeon", "boss", "portal", "other"],
            "app_mode": "desktop",
            "python_version": "test",
            "source_sha256": {"regional_cycle_service.py": "old"},
        }
        with tempfile.TemporaryDirectory(prefix="ml050-checkpoint-test-", dir=ROOT) as directory:
            checkpoint_path = Path(directory) / "checkpoint.json"
            original_hash = _configuration_sha256(configuration)
            _write_json_atomic(checkpoint_path, {
                "schema_version": 1,
                "configuration": configuration,
                "configuration_sha256": original_hash,
                "results": {},
            })
            changed_configuration = dict(configuration)
            changed_configuration["source_sha256"] = {"regional_cycle_service.py": "new"}
            with self.assertRaisesRegex(ValueError, "configuration/source hashes differ"):
                _load_or_create_checkpoint(
                    checkpoint_path,
                    changed_configuration,
                    _configuration_sha256(changed_configuration),
                )

        partial = {
            "results": {
                "10": {
                    "previous": {
                        "profiles": {profile: _blank_profile_metrics() for profile in PROFILE_NAMES},
                        "cpu_actions_total": 0,
                        "cpu_xp_net": 0,
                    },
                },
            },
        }
        with self.assertRaisesRegex(ValueError, "seed 10, variant ml050"):
            _validate_checkpoint_results({**partial}, configuration, require_complete=True)


if __name__ == "__main__":
    unittest.main()
