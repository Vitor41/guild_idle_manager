import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import tempfile
import unittest

from app.desktop.gameplay_diagnostics import close_gameplay_logger, gameplay_log_path, log_gameplay_action


class GameplayDiagnosticsTests(unittest.TestCase):
    def test_gameplay_log_is_in_stable_user_data_outside_install_and_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            local_app_data = Path(directory) / "LocalAppData"
            previous = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = str(local_app_data)
            try:
                path = gameplay_log_path()
            finally:
                if previous is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = previous

            self.assertEqual(path, local_app_data / "GuildIdleManager" / "logs" / "gameplay-actions.log")
            self.assertNotIn("saves", path.parts)
            self.assertFalse(path.is_relative_to(Path(__file__).resolve().parents[1]))

    def test_gameplay_log_records_utc_action_status_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logs" / "gameplay-actions.log"
            try:
                raise ValueError("password=hunter2 Authorization=Bearer abc.def token=private-cookie")
            except ValueError as error:
                exception = error

            try:
                log_gameplay_action(
                    action="regional.offer.start", route="/regional/offers/42/start",
                    diagnostic_id="0123456789abcdef", status_code=500,
                    outcome="unexpected_exception", exception=exception, log_path=path,
                )
                contents = path.read_text(encoding="utf-8")
                self.assertRegex(contents, r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00")
                self.assertIn("action=regional.offer.start", contents)
                self.assertIn("route=/regional/offers/42/start", contents)
                self.assertIn("ref=0123456789abcdef status=500 outcome=unexpected_exception", contents)
                self.assertIn("Traceback (most recent call last)", contents)
                self.assertNotIn("hunter2", contents)
                self.assertNotIn("abc.def", contents)
                self.assertNotIn("private-cookie", contents)
                self.assertIn("[REDACTED]", contents)
                handler = next(
                    handler for logger in logging.Logger.manager.loggerDict.values()
                    if isinstance(logger, logging.Logger) and logger.name.startswith("gim.gameplay.")
                    for handler in logger.handlers if isinstance(handler, RotatingFileHandler)
                )
                self.assertEqual((handler.maxBytes, handler.backupCount), (1_000_000, 2))
            finally:
                close_gameplay_logger(path)
