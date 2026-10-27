from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from app.core.time import prepare_timer_context


class TimerContextTests(unittest.TestCase):
    def test_prepare_timer_context_handles_sqlite_naive_utc_timestamp(self):
        now = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
        run = SimpleNamespace(ends_at=datetime(2026, 10, 27, 11, 59))

        prepare_timer_context(run, now)

        self.assertTrue(run.ready_for_loot)
        self.assertEqual(run.ends_at_iso, "2026-10-27T11:59:00+00:00")

    def test_prepare_timer_context_keeps_future_timer_disabled(self):
        now = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
        run = SimpleNamespace(ends_at=now + timedelta(seconds=5))

        prepare_timer_context(run, now)

        self.assertFalse(run.ready_for_loot)
        self.assertEqual(run.ends_at_iso, "2026-10-27T12:00:05+00:00")

    def test_prepare_timer_context_normalizes_mapping_and_non_utc_offsets(self):
        now = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
        run = {"ends_at": datetime(2026, 10, 27, 15, 0, tzinfo=timezone(timedelta(hours=3)))}

        prepare_timer_context(run, now)

        self.assertTrue(run["ready_for_loot"])
        self.assertEqual(run["ends_at_iso"], "2026-10-27T12:00:00+00:00")
