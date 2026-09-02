"""Unit tests for hunt-loop fail recovery (no Dolphin, no dumps)."""

from __future__ import annotations

import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from botjirachi.__main__ import run_hunt
from botjirachi.huntlog import HuntLog
from botjirachi.party import PartyMon
from botjirachi.sequence import (
    FAIL_A_BETWEEN_S,
    FAIL_A_TIMES,
    FAIL_AFTER_A_S,
    RETRY_JIRACHI_STICK_UP_S,
    TITLE_STICK_UP_S,
    _channel_to_gba_prompt,
    receive_jirachi,
    recover_after_fail,
)


def _mon(*, personality: int, tid: int, sid: int) -> PartyMon:
    return PartyMon(
        slot=5,
        personality=personality,
        tid=tid,
        sid=sid,
        species=409,
        nickname="JIRACHI",
        ot_name="CHANNEL",
        checksum_ok=True,
    )


class RecoverAfterFailTests(unittest.TestCase):
    def test_turns_off_gba_taps_a_then_restores(self) -> None:
        session = MagicMock()
        pad = MagicMock()
        order: list[str] = []
        session.set_port2_none.side_effect = lambda: order.append("off")
        pad.tap_channel.side_effect = lambda *args, **kwargs: order.append("a")
        with (
            patch(
                "botjirachi.sequence.restore_ruby_save",
                side_effect=lambda paths: order.append("restore"),
            ) as restore,
            patch(
                "botjirachi.sequence.time.sleep",
                side_effect=lambda s: order.append(f"sleep:{s}"),
            ),
        ):
            recover_after_fail(session, pad)
        pad.tap_channel.assert_called_once_with(
            "A",
            times=FAIL_A_TIMES,
            between_s=FAIL_A_BETWEEN_S,
        )
        restore.assert_called_once_with(session.paths)
        self.assertEqual(
            order,
            ["off", "a", f"sleep:{FAIL_AFTER_A_S}", "restore"],
        )


class ReceivePalHzTests(unittest.TestCase):
    def test_skips_reset_and_pal_when_requested(self) -> None:
        session = MagicMock()
        session.paths.dolphin_ruby_sav_port2 = Path("/tmp/fake-2.sav")
        pad = MagicMock()
        with (
            patch("botjirachi.sequence._select_pal_hz") as pal,
            patch("botjirachi.sequence._channel_to_gba_prompt"),
            patch("botjirachi.sequence._turn_on_gba"),
            patch("botjirachi.sequence._mtime", return_value=1.0),
            patch("botjirachi.sequence._wait_sav_update", return_value=1.0),
        ):
            receive_jirachi(session, pad, select_pal_hz=False)
        session.reset_emulation.assert_not_called()
        pal.assert_not_called()

    def test_resets_and_selects_pal_by_default(self) -> None:
        session = MagicMock()
        session.paths.dolphin_ruby_sav_port2 = Path("/tmp/fake-2.sav")
        pad = MagicMock()
        with (
            patch("botjirachi.sequence._select_pal_hz") as pal,
            patch("botjirachi.sequence._channel_to_gba_prompt"),
            patch("botjirachi.sequence._turn_on_gba"),
            patch("botjirachi.sequence._mtime", return_value=1.0),
            patch("botjirachi.sequence._wait_sav_update", return_value=1.0),
            patch("botjirachi.sequence.time.sleep"),
        ):
            receive_jirachi(session, pad, pal_hz=60, select_pal_hz=True)
        session.reset_emulation.assert_called_once()
        pal.assert_called_once()

    def test_retry_passes_from_boot_false(self) -> None:
        session = MagicMock()
        session.paths.dolphin_ruby_sav_port2 = Path("/tmp/fake-2.sav")
        pad = MagicMock()
        with (
            patch("botjirachi.sequence._select_pal_hz"),
            patch("botjirachi.sequence._channel_to_gba_prompt") as menus,
            patch("botjirachi.sequence._turn_on_gba"),
            patch("botjirachi.sequence._mtime", return_value=1.0),
            patch("botjirachi.sequence._wait_sav_update", return_value=1.0),
        ):
            receive_jirachi(session, pad, select_pal_hz=False)
        menus.assert_called_once_with(pad, from_boot=False)

    def test_retry_only_adds_jirachi_stick_up(self) -> None:
        pad = MagicMock()
        with patch("botjirachi.sequence.time.sleep"):
            _channel_to_gba_prompt(pad, from_boot=False)
        ups = [
            kwargs["hold_s"]
            for args, kwargs in pad.hold_channel_stick.call_args_list
            if args[:1] == ("Up",) or (args and args[0] == "Up")
        ]
        self.assertEqual(ups, [TITLE_STICK_UP_S, RETRY_JIRACHI_STICK_UP_S])
        retry_up = pad.hold_channel_stick.call_args_list[-1]
        self.assertEqual(retry_up.kwargs.get("refocus"), False)

    def test_boot_title_nudge_keeps_short_up(self) -> None:
        pad = MagicMock()
        with patch("botjirachi.sequence.time.sleep"):
            _channel_to_gba_prompt(pad, from_boot=True)
        ups = [
            kwargs["hold_s"]
            for args, kwargs in pad.hold_channel_stick.call_args_list
            if args[:1] == ("Up",) or (args and args[0] == "Up")
        ]
        self.assertEqual(ups, [TITLE_STICK_UP_S])


class HuntLoopTests(unittest.TestCase):
    def test_leftover_gba_recovers_then_skips_hz_until_shiny(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sav = root / "port2.sav"
            sav.write_bytes(b"working")
            session = MagicMock()
            session.paths.dolphin_ruby_sav_port2 = sav
            session.has_gba_window.return_value = True
            pad = MagicMock()
            stdout = io.StringIO()
            hunt_log = HuntLog(root / "logs", stdout=stdout)
            fail = _mon(personality=0, tid=40122, sid=0)
            shiny = _mon(personality=0, tid=0, sid=0)
            self.assertFalse(fail.is_shiny)
            self.assertTrue(shiny.is_shiny)
            pal_flags: list[bool] = []

            def fake_receive(_session, _pad, *, pal_hz, select_pal_hz):
                pal_flags.append(select_pal_hz)
                return sav

            with (
                patch(
                    "botjirachi.__main__.recover_after_fail",
                ) as recover,
                patch(
                    "botjirachi.__main__.receive_jirachi",
                    side_effect=fake_receive,
                ),
                patch(
                    "botjirachi.__main__.jirachi_from_save",
                    side_effect=[fail, shiny],
                ),
                patch("botjirachi.__main__.restore_ruby_save") as restore,
            ):
                code = run_hunt(session, 60, hunt_log, pad=pad)
            self.assertEqual(code, 0)
            restore.assert_not_called()
            self.assertEqual(pal_flags, [False, False])
            self.assertEqual(recover.call_count, 2)
            attempts = hunt_log.attempts_path.read_text(encoding="utf-8")
            self.assertIn("result=fail", attempts)
            self.assertIn("result=shiny", attempts)
            self.assertTrue(hunt_log.shiny_path.is_file())
            self.assertEqual(sav.read_bytes(), b"working")

    def test_does_not_recover_after_shiny_on_first_hit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sav = root / "port2.sav"
            sav.write_bytes(b"working")
            session = MagicMock()
            session.paths.dolphin_ruby_sav_port2 = sav
            session.has_gba_window.return_value = False
            session.has_channel_window.return_value = False
            session.paths = session.paths
            pad = MagicMock()
            hunt_log = HuntLog(root / "logs", stdout=io.StringIO())
            shiny = _mon(personality=0, tid=0, sid=0)
            dests = (root / "a.sav", root / "b.sav")
            pal_flags: list[bool] = []

            def fake_receive(_session, _pad, *, pal_hz, select_pal_hz):
                pal_flags.append(select_pal_hz)
                return sav

            with (
                patch("botjirachi.__main__.recover_after_fail") as recover,
                patch(
                    "botjirachi.__main__.receive_jirachi",
                    side_effect=fake_receive,
                ),
                patch(
                    "botjirachi.__main__.jirachi_from_save",
                    return_value=shiny,
                ),
                patch(
                    "botjirachi.__main__.restore_ruby_save",
                    return_value=dests,
                ) as restore,
            ):
                code = run_hunt(session, 60, hunt_log, pad=pad)
            self.assertEqual(code, 0)
            restore.assert_called_once()
            session.ensure_channel_booted.assert_called_once()
            self.assertEqual(pal_flags, [True])
            recover.assert_not_called()
            self.assertIn("result=shiny", hunt_log.attempts_path.read_text())

    def test_max_attempts_stops_after_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sav = root / "port2.sav"
            sav.write_bytes(b"working")
            session = MagicMock()
            session.paths.dolphin_ruby_sav_port2 = sav
            session.has_gba_window.return_value = True
            pad = MagicMock()
            hunt_log = HuntLog(root / "logs", stdout=io.StringIO())
            fail = _mon(personality=0, tid=40122, sid=0)
            pal_flags: list[bool] = []

            def fake_receive(_session, _pad, *, pal_hz, select_pal_hz):
                pal_flags.append(select_pal_hz)
                return sav

            with (
                patch("botjirachi.__main__.recover_after_fail") as recover,
                patch(
                    "botjirachi.__main__.receive_jirachi",
                    side_effect=fake_receive,
                ),
                patch(
                    "botjirachi.__main__.jirachi_from_save",
                    return_value=fail,
                ),
            ):
                code = run_hunt(
                    session, 60, hunt_log, pad=pad, max_attempts=2
                )
            self.assertEqual(code, 0)
            self.assertEqual(pal_flags, [False, False])
            self.assertEqual(recover.call_count, 3)
            attempts = hunt_log.attempts_path.read_text(encoding="utf-8")
            self.assertEqual(attempts.count("result=fail"), 2)
            self.assertNotIn("result=shiny", attempts)


if __name__ == "__main__":
    unittest.main()
