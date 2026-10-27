from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from app.desktop.bridge import DesktopBridge


class FakeWindow:
    def __init__(self, selected):
        self.selected = selected

    def create_file_dialog(self, *_args, **_kwargs):
        return self.selected


class FakeCampaignService:
    def __init__(self):
        self.exports = []

    def inspect_campaign(self, campaign_id):
        return SimpleNamespace(campaign_id=campaign_id, campaign_name="Campanha")

    def export_campaign(self, campaign_id, destination, overwrite=False):
        self.exports.append((campaign_id, Path(destination), overwrite))


class DesktopBridgeTests(unittest.TestCase):
    def _bridge(self, selected):
        campaigns = FakeCampaignService()
        bridge = DesktopBridge(campaigns, object())
        bridge._window = FakeWindow(selected)
        webview_api = SimpleNamespace(SAVE_DIALOG=1)
        return bridge, campaigns, patch.object(bridge, "_webview", return_value=webview_api)

    def test_cancel_export_does_not_write_any_file(self):
        bridge, campaigns, patched = self._bridge(None)
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.desktop.bridge.user_data_directory", return_value=Path(temp_dir)
        ), patched:
            result = bridge.export_campaign("campaign-1")
        self.assertEqual(result, {"cancelled": True})
        self.assertEqual(campaigns.exports, [])

    def test_pywebview_exports_only_the_bridge_methods(self):
        import inspect

        bridge, _campaigns, _patched = self._bridge(None)
        exposed = {
            name for name in dir(bridge)
            if not name.startswith("_") and not callable(getattr(bridge, name))
        }
        methods = {
            name for name in dir(bridge)
            if not name.startswith("_") and inspect.ismethod(getattr(bridge, name))
        }
        self.assertEqual(
            exposed | methods,
            {"export_campaign", "confirm_export", "import_campaign", "restore_backup"},
        )

    def test_existing_export_requires_token_confirmation_without_exposing_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "existing.gimcampaign"
            existing.write_text("previous export", encoding="utf-8")
            bridge, campaigns, patched = self._bridge((str(existing),))
            with patch("app.desktop.bridge.user_data_directory", return_value=Path(temp_dir)), patched:
                pending = bridge.export_campaign("campaign-1")
                self.assertTrue(pending["needs_confirmation"])
                self.assertNotIn("destination", pending)
                self.assertNotIn(str(existing), repr(pending))
                self.assertEqual(campaigns.exports, [])
                self.assertEqual(bridge.confirm_export(pending["confirmation_token"], False), {"cancelled": True})
                self.assertEqual(campaigns.exports, [])

                pending = bridge.export_campaign("campaign-1")
                result = bridge.confirm_export(pending["confirmation_token"], True)
            self.assertTrue(result["ok"])
            self.assertEqual(campaigns.exports, [("campaign-1", existing, True)])
            with self.assertRaises(TypeError):
                bridge.export_campaign("campaign-1", str(existing), True)


if __name__ == "__main__":
    unittest.main()
