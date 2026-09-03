"""Unit tests for the when-shiny path (temp dirs; no ROM dumps)."""

from __future__ import annotations

import io
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from botjirachi.__main__ import main, run_force_shiny
from botjirachi.huntlog import HuntLog, parse_utc
from botjirachi.paths import HuntPaths, RUBY_SAV_PORT2_NAME
from botjirachi.shiny import handle_shiny


def _paths(root: Path) -> HuntPaths:
    return HuntPaths(
        repo_root=root,
        channel_iso=root / "missing.iso",
        ruby_gba=root / "missing.gba",
        ruby_sav=root / "original.sav",
        gba_bios=root / "gba_bios.bin",
        dolphin_binary=root / "Dolphin",
        dolphin_user_dir=root / "dolphin-user",
    )


class HandleShinyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.stdout = io.StringIO()
        self.log = HuntLog(self.root / "logs", stdout=self.stdout)
        self.log.ensure_hunt_started(
            now=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )
        self.sav = self.root / RUBY_SAV_PORT2_NAME
        self.sav.write_bytes(b"working-save")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_writes_attempt_and_summary_and_keeps_save(self) -> None:
        when = datetime(2026, 8, 31, 20, 15, tzinfo=timezone.utc)
        with patch("botjirachi.shiny.notify_shiny") as notify:
            code = handle_shiny(
                self.log,
                attempt=812,
                duration_s=40.8,
                sv=4,
                save_path=self.sav,
                when=when,
            )
        self.assertEqual(code, 0)
        notify.assert_called_once()
        kwargs = notify.call_args.kwargs
        self.assertEqual(kwargs["attempt"], 812)
        self.assertEqual(kwargs["sv"], 4)
        self.assertEqual(kwargs["save_path"], self.sav)
        self.assertAlmostEqual(kwargs["total_s"], 29700.0)

        attempt_line = (
            "2026-08-31T20:15:00Z  attempt=812  "
            "duration_s=40.8  sv=4  result=shiny"
        )
        summary = (
            f"SHINY  2026-08-31T20:15:00Z  attempts=812  "
            f"total_s=29700.0  sv=4  save={self.sav}"
        )
        lines = self.stdout.getvalue().splitlines()
        self.assertEqual(lines, [attempt_line, summary])
        self.assertEqual(
            self.log.attempts_path.read_text(encoding="utf-8").splitlines(),
            [attempt_line],
        )
        self.assertEqual(
            self.log.shiny_path.read_text(encoding="utf-8").splitlines(),
            [summary],
        )
        self.assertEqual(self.sav.read_bytes(), b"working-save")

    def test_summary_appends(self) -> None:
        when = datetime(2026, 8, 31, 20, 15, tzinfo=timezone.utc)
        handle_shiny(
            self.log,
            attempt=1,
            duration_s=1.0,
            sv=0,
            save_path=self.sav,
            when=when,
        )
        handle_shiny(
            self.log,
            attempt=2,
            duration_s=1.0,
            sv=7,
            save_path=self.sav,
            when=when,
        )
        shiny_lines = self.log.shiny_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(shiny_lines), 2)
        self.assertIn("attempts=1", shiny_lines[0])
        self.assertIn("attempts=2", shiny_lines[1])


class ForceShinyCliTests(unittest.TestCase):
    def test_run_force_shiny_skips_restore_and_writes_logs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _paths(root)
            sav = paths.dolphin_ruby_sav_port2
            sav.parent.mkdir(parents=True, exist_ok=True)
            sav.write_bytes(b"keep-me")
            with patch("botjirachi.__main__.restore_ruby_save") as restore:
                code = run_force_shiny(paths)
            self.assertEqual(code, 0)
            restore.assert_not_called()
            self.assertEqual(sav.read_bytes(), b"keep-me")
            attempts = (root / "logs" / "attempts.txt").read_text(encoding="utf-8")
            summary = (root / "logs" / "shiny.txt").read_text(encoding="utf-8")
            self.assertIn("result=shiny", attempts)
            self.assertIn("sv=0", attempts)
            self.assertTrue(summary.startswith("SHINY  "))
            self.assertIn(f"save={sav}", summary)
            started = (root / "logs" / "hunt_started.txt").read_text(
                encoding="utf-8"
            )
            self.assertIsNotNone(parse_utc(started))

    def test_main_skips_restore_if_last_attempt_was_shiny(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _paths(root)
            sav = paths.dolphin_ruby_sav_port2
            sav.parent.mkdir(parents=True, exist_ok=True)
            sav.write_bytes(b"keep-me")
            HuntLog(paths.logs_dir).write_attempt(
                attempt=812,
                duration_s=1.0,
                sv=4,
            )
            with (
                patch("botjirachi.__main__.resolve_paths", return_value=paths),
                patch.object(HuntPaths, "missing", return_value=[]),
                patch("botjirachi.__main__.restore_ruby_save") as restore,
                patch("botjirachi.__main__.DolphinSession") as session,
            ):
                code = main([])
            self.assertEqual(code, 0)
            restore.assert_not_called()
            session.assert_not_called()
            self.assertEqual(sav.read_bytes(), b"keep-me")

    def test_main_force_shiny_does_not_restore_or_boot_dolphin(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _paths(root)
            sav = paths.dolphin_ruby_sav_port2
            sav.parent.mkdir(parents=True, exist_ok=True)
            sav.write_bytes(b"keep-me")
            with (
                patch("botjirachi.__main__.resolve_paths", return_value=paths),
                patch("botjirachi.__main__.restore_ruby_save") as restore,
                patch("botjirachi.__main__.DolphinSession") as session,
            ):
                code = main(["--force-shiny"])
            self.assertEqual(code, 0)
            restore.assert_not_called()
            session.assert_not_called()
            self.assertEqual(sav.read_bytes(), b"keep-me")
            self.assertTrue((root / "logs" / "shiny.txt").is_file())


if __name__ == "__main__":
    unittest.main()
