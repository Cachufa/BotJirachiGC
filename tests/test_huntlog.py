"""Unit tests for attempt logging (temp dirs; no ROM dumps)."""

from __future__ import annotations

import io
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from botjirachi.huntlog import (
    HuntLog,
    format_shiny_summary,
    format_utc,
    last_attempt_number,
    last_attempt_result,
    result_for_sv,
    total_hunt_seconds,
)


class LastAttemptTests(unittest.TestCase):
    def test_empty_and_headers(self) -> None:
        self.assertIsNone(last_attempt_number(""))
        self.assertIsNone(last_attempt_number("# hunt start\nmalformed line\n"))

    def test_last_line_wins(self) -> None:
        text = (
            "2026-08-31T18:00:00Z  attempt=1  duration_s=42.1  sv=1842  result=fail\n"
            "# note\n"
            "2026-08-31T18:01:12Z  attempt=2  duration_s=40.8  sv=3  result=shiny\n"
        )
        self.assertEqual(last_attempt_number(text), 2)
        self.assertEqual(last_attempt_result(text), "shiny")
        self.assertIsNone(last_attempt_result("# hunt start\nmalformed line\n"))
        self.assertEqual(
            last_attempt_result(
                "2026-08-31T18:00:00Z  attempt=1  duration_s=42.1  sv=1842  result=fail\n"
            ),
            "fail",
        )


class ResultTests(unittest.TestCase):
    def test_shiny_iff_sv_0_to_7(self) -> None:
        self.assertEqual(result_for_sv(0), "shiny")
        self.assertEqual(result_for_sv(7), "shiny")
        self.assertEqual(result_for_sv(8), "fail")
        self.assertEqual(result_for_sv(63216), "fail")


class HuntLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.log_dir = Path(self._tmp.name)
        self.stdout = io.StringIO()
        self.log = HuntLog(self.log_dir, stdout=self.stdout)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_file_starts_at_one(self) -> None:
        self.assertEqual(self.log.next_attempt_number(), 1)

    def test_prepare_persists_hunt_start_and_does_not_reset(self) -> None:
        first = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)
        started = self.log.ensure_hunt_started(now=first)
        self.assertEqual(format_utc(started), "2026-08-31T18:00:00Z")
        later = HuntLog(self.log_dir, stdout=io.StringIO())
        again = later.ensure_hunt_started(
            now=datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(again, started)
        self.assertEqual(
            later.hunt_started_path.read_text(encoding="utf-8").strip(),
            "2026-08-31T18:00:00Z",
        )

    def test_malformed_hunt_started_is_replaced(self) -> None:
        self.log.hunt_started_path.write_text("not a timestamp\n", encoding="utf-8")
        now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
        started = self.log.ensure_hunt_started(now=now)
        self.assertEqual(format_utc(started), "2026-09-02T12:00:00Z")

    def test_kill_and_rerun_continues_attempt_and_keeps_old_lines(self) -> None:
        when = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)
        line1 = self.log.write_attempt(
            attempt=1,
            duration_s=42.1,
            sv=1842,
            when=when,
        )
        self.assertEqual(
            line1,
            "2026-08-31T18:00:00Z  attempt=1  duration_s=42.1  sv=1842  result=fail",
        )
        self.assertEqual(self.stdout.getvalue().splitlines()[-1], line1)

        resumed = HuntLog(self.log_dir, stdout=io.StringIO())
        self.assertEqual(resumed.next_attempt_number(), 2)
        line2 = resumed.write_attempt(
            attempt=resumed.next_attempt_number(),
            duration_s=40.8,
            sv=3,
            when=datetime(2026, 8, 31, 18, 1, 12, tzinfo=timezone.utc),
        )
        self.assertIn("attempt=2", line2)
        self.assertIn("result=shiny", line2)
        text = self.log.attempts_path.read_text(encoding="utf-8")
        self.assertEqual(text.splitlines(), [line1, line2])
        self.assertTrue(text.startswith(line1))

    def test_write_attempt_does_not_truncate(self) -> None:
        self.log.write_attempt(attempt=1, duration_s=1.0, sv=9)
        self.log.write_attempt(attempt=2, duration_s=1.0, sv=9)
        lines = self.log.attempts_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("attempt=1", lines[0])
        self.assertIn("attempt=2", lines[1])

    def test_dual_write_same_line(self) -> None:
        when = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)
        line = self.log.write_attempt(
            attempt=1,
            duration_s=10.04,
            sv=1,
            when=when,
        )
        expected = (
            "2026-08-31T18:00:00Z  attempt=1  duration_s=10.0  sv=1  result=shiny"
        )
        self.assertEqual(line, expected)
        self.assertEqual(self.stdout.getvalue().strip(), expected)
        self.assertEqual(
            self.log.attempts_path.read_text(encoding="utf-8").strip(),
            expected,
        )

    def test_run_header_is_stdout_only(self) -> None:
        started, nxt = self.log.prepare()
        self.log.write_run_header(started, nxt)
        self.assertFalse(self.log.attempts_path.exists())
        header = self.stdout.getvalue()
        self.assertIn("next_attempt=1", header)
        self.assertIn("started=", header)
        self.assertNotIn("password", header.lower())
        self.assertNotIn("secret", header.lower())

    def test_shiny_summary_dual_write_and_append(self) -> None:
        when = datetime(2026, 8, 31, 20, 15, tzinfo=timezone.utc)
        save = Path("/tmp/Pokemon - Edicion Rubi (Spain)-2.sav")
        line = self.log.write_shiny_summary(
            attempts=812,
            total_s=28940.2,
            sv=4,
            save=save,
            when=when,
        )
        expected = (
            "SHINY  2026-08-31T20:15:00Z  attempts=812  "
            "total_s=28940.2  sv=4  "
            "save=/tmp/Pokemon - Edicion Rubi (Spain)-2.sav"
        )
        self.assertEqual(line, expected)
        self.assertEqual(format_shiny_summary(
            when=when,
            attempts=812,
            total_s=28940.2,
            sv=4,
            save=save,
        ), expected)
        self.assertEqual(self.stdout.getvalue().strip(), expected)
        self.assertEqual(
            self.log.shiny_path.read_text(encoding="utf-8").strip(),
            expected,
        )
        self.log.write_shiny_summary(
            attempts=813,
            total_s=1.0,
            sv=0,
            save=save,
            when=when,
        )
        self.assertEqual(
            len(self.log.shiny_path.read_text(encoding="utf-8").splitlines()),
            2,
        )

    def test_total_hunt_seconds_includes_gaps(self) -> None:
        started = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
        when = datetime(2026, 8, 31, 20, 15, tzinfo=timezone.utc)
        self.assertAlmostEqual(total_hunt_seconds(started, when), 29700.0)
        self.assertEqual(
            total_hunt_seconds(when, started),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()

