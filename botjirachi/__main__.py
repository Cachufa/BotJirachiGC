"""Hunt CLI: `python3 -m botjirachi` from the repo root."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from botjirachi.dolphin import DolphinError, DolphinSession
from botjirachi.huntlog import HuntLog
from botjirachi.inputs import InputError, PadDriver
from botjirachi.party import SavError, jirachi_from_save
from botjirachi.paths import HuntPaths
from botjirachi.restore import RestoreError, restore_ruby_save
from botjirachi.sequence import (
    PAL_HZ,
    SequenceError,
    receive_jirachi,
    recover_after_fail,
)
from botjirachi.shiny import handle_shiny


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="botjirachi",
        description="Shiny hunt Jirachi via Pokémon Channel and Ruby in Dolphin.",
    )
    parser.add_argument("--iso", type=Path, help="Pokémon Channel ISO")
    parser.add_argument("--gba", type=Path, help="Pokémon Ruby GBA ROM")
    parser.add_argument("--sav", type=Path, help="Original Ruby .sav (never overwritten)")
    parser.add_argument("--bios", type=Path, help="GBA BIOS (gba_bios.bin)")
    parser.add_argument("--dolphin", type=Path, help="Dolphin.app or Dolphin executable")
    parser.add_argument(
        "--dolphin-user-dir",
        type=Path,
        help="Dolphin user data directory",
    )
    parser.add_argument(
        "--probe-inputs",
        action="store_true",
        help="After Channel boots: tap Channel A (X), load Ruby on GBA2, tap GBA A",
    )
    parser.add_argument(
        "--receive",
        action="store_true",
        help="One Channel → Ruby Jirachi receive, then parse SV from -2.sav",
    )
    parser.add_argument(
        "--pal-hz",
        type=int,
        choices=(50, 60),
        default=None,
        help="PAL boot 50 or 60 Hz (default 60; 60 is the upper option)",
    )
    parser.add_argument(
        "--parse-sv",
        nargs="?",
        const="",
        default=None,
        metavar="SAV",
        help=(
            "Parse Channel Jirachi SV from a Ruby .sav and exit "
            "(default: Dolphin port-2 -2.sav). Skips restore and Dolphin."
        ),
    )
    parser.add_argument(
        "--force-shiny",
        action="store_true",
        help=(
            "Fake a shiny hit: log attempt + summary, skip restore and Dolphin, "
            "leave the working .sav as-is, exit 0"
        ),
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=None,
        metavar="N",
        help="Stop the hunt loop after N logged attempts (fail or shiny)",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> HuntPaths:
    return HuntPaths.defaults(
        channel_iso=args.iso,
        ruby_gba=args.gba,
        ruby_sav=args.sav,
        gba_bios=args.bios,
        dolphin_binary=args.dolphin,
        dolphin_user_dir=args.dolphin_user_dir,
    )


def report_missing(missing: list[tuple[str, Path]]) -> None:
    print("Missing required paths:", file=sys.stderr)
    for label, path in missing:
        print(f"  {label}: {path}", file=sys.stderr)


def print_header(paths: HuntPaths) -> None:
    print("BotJirachiGC — required paths found")
    print(f"  repo:    {paths.repo_root}")
    print(f"  iso:     {paths.channel_iso}")
    print(f"  gba:     {paths.ruby_gba}")
    print(f"  sav:     {paths.ruby_sav}")
    print(f"  bios:    {paths.gba_bios}")
    print(f"  dolphin: {paths.dolphin_binary}")
    print(f"  user:    {paths.dolphin_user_dir}")
    print(f"  gba sav: {paths.dolphin_ruby_sav}")
    print(f"  gba -2:  {paths.dolphin_ruby_sav_port2}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = resolve_paths(args)
    if args.parse_sv is not None:
        sav = Path(args.parse_sv).expanduser() if args.parse_sv else paths.dolphin_ruby_sav_port2
        return run_parse_sv(sav.resolve())
    if args.force_shiny:
        return run_force_shiny(paths)
    missing = paths.missing()
    if missing:
        report_missing(missing)
        return 1
    print_header(paths)
    hunt_log = HuntLog(paths.logs_dir)
    if hunt_log.last_logged_result() == "shiny" and not args.probe_inputs:
        print(
            "Shiny already logged; not restoring the working Ruby save. "
            f"See {hunt_log.shiny_path}",
            file=sys.stderr,
        )
        return 0
    session = DolphinSession(paths)
    hz = args.pal_hz if args.pal_hz is not None else PAL_HZ
    if args.probe_inputs or args.receive:
        try:
            dests = restore_ruby_save(paths)
        except RestoreError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("Restored original Ruby save to:")
        for dest in dests:
            print(f"  {dest}")
        try:
            session.ensure_channel_booted()
        except DolphinError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("Channel running with Port 2 empty (no GBA window)")
        for title in session.window_titles():
            print(f"  window: {title}")
        if args.probe_inputs:
            return probe_inputs(session)
        started, next_attempt = hunt_log.prepare()
        hunt_log.write_run_header(started, next_attempt)
        print(f"Receive: PAL {hz} Hz")
        return run_receive(session, hz, hunt_log)
    started, next_attempt = hunt_log.prepare()
    hunt_log.write_run_header(started, next_attempt)
    print(f"Hunt loop: PAL {hz} Hz on boot; retries skip Hz")
    try:
        return run_hunt(
            session,
            hz,
            hunt_log,
            max_attempts=args.max_attempts,
        )
    except KeyboardInterrupt:
        print(
            "Interrupted; leaving Dolphin and saves as-is",
            file=sys.stderr,
        )
        return 130


def run_receive(session: DolphinSession, pal_hz: int, hunt_log: HuntLog) -> int:
    attempt = hunt_log.next_attempt_number()
    started_at = time.perf_counter()
    try:
        sav = receive_jirachi(session, pal_hz=pal_hz, select_pal_hz=True)
    except (DolphinError, InputError, SequenceError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Receive: GBA on, no further inputs. Working save: {sav}")
    return report_jirachi_sv(
        sav,
        hunt_log=hunt_log,
        attempt=attempt,
        started_at=started_at,
    )


def run_hunt(
    session: DolphinSession,
    pal_hz: int,
    hunt_log: HuntLog,
    pad: PadDriver | None = None,
    max_attempts: int | None = None,
) -> int:
    """Repeat receive until SV is 0..7. Restores only on the fail path."""
    if pad is None:
        pad = PadDriver(session)
    select_pal_hz = True
    try:
        if session.has_gba_window():
            recover_after_fail(session, pad)
            select_pal_hz = False
        else:
            dests = restore_ruby_save(session.paths)
            print("Restored original Ruby save to:")
            for dest in dests:
                print(f"  {dest}")
            was_running = session.has_channel_window()
            session.ensure_channel_booted()
            select_pal_hz = not was_running
            print("Channel running with Port 2 empty (no GBA window)")
            for title in session.window_titles():
                print(f"  window: {title}")
    except (DolphinError, InputError, SequenceError, RestoreError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    logged = 0
    while True:
        attempt = hunt_log.next_attempt_number()
        started_at = time.perf_counter()
        print(
            f"Attempt {attempt}: "
            f"{'PAL Hz + title' if select_pal_hz else 'in-game, no Hz'}"
        )
        try:
            sav = receive_jirachi(
                session,
                pad,
                pal_hz=pal_hz,
                select_pal_hz=select_pal_hz,
            )
        except (DolphinError, InputError, SequenceError) as exc:
            print(str(exc), file=sys.stderr)
            log_missed_attempt(hunt_log, attempt=attempt, started_at=started_at)
            try:
                recover_after_fail(session, pad)
            except (DolphinError, InputError, SequenceError) as recover_exc:
                print(str(recover_exc), file=sys.stderr)
                return 1
            logged += 1
            select_pal_hz = False
            if max_attempts is not None and logged >= max_attempts:
                print(f"Stopped after {logged} attempt(s) (--max-attempts)")
                return 0
            continue
        print(f"Receive: GBA on, no further inputs. Working save: {sav}")
        code = report_jirachi_sv(
            sav,
            hunt_log=hunt_log,
            attempt=attempt,
            started_at=started_at,
        )
        if hunt_log.last_logged_result() == "shiny":
            return 0
        if code != 0:
            try:
                recover_after_fail(session, pad)
            except (DolphinError, InputError, SequenceError) as recover_exc:
                print(str(recover_exc), file=sys.stderr)
                return 1
            logged += 1
            select_pal_hz = False
            if max_attempts is not None and logged >= max_attempts:
                print(f"Stopped after {logged} attempt(s) (--max-attempts)")
                return 0
            continue
        logged += 1
        try:
            recover_after_fail(session, pad)
        except (DolphinError, InputError, SequenceError) as recover_exc:
            print(str(recover_exc), file=sys.stderr)
            return 1
        print("Fail path done. Windows:")
        for title in session.window_titles():
            print(f"  window: {title}")
        select_pal_hz = False
        if max_attempts is not None and logged >= max_attempts:
            print(f"Stopped after {logged} attempt(s) (--max-attempts)")
            return 0


def run_parse_sv(sav: Path) -> int:
    print(f"Parse SV: {sav}")
    return report_jirachi_sv(sav)


def run_force_shiny(paths: HuntPaths) -> int:
    """Shiny path without restore or Dolphin. Does not touch the working .sav."""
    hunt_log = HuntLog(paths.logs_dir)
    started, next_attempt = hunt_log.prepare()
    hunt_log.write_run_header(started, next_attempt)
    print("Force shiny: skipping restore and Dolphin")
    return handle_shiny(
        hunt_log,
        attempt=next_attempt,
        duration_s=0.0,
        sv=0,
        save_path=paths.dolphin_ruby_sav_port2,
    )


def log_missed_attempt(
    hunt_log: HuntLog,
    *,
    attempt: int,
    started_at: float,
) -> None:
    """Log a completed attempt that did not land a Jirachi (stdout + attempts.txt)."""
    hunt_log.write_attempt(
        attempt=attempt,
        duration_s=time.perf_counter() - started_at,
        sv=-1,
        result="miss",
    )


def report_jirachi_sv(
    sav: Path,
    hunt_log: HuntLog | None = None,
    attempt: int | None = None,
    started_at: float | None = None,
) -> int:
    try:
        mon = jirachi_from_save(sav)
    except SavError as exc:
        print(str(exc), file=sys.stderr)
        if hunt_log is not None and attempt is not None and started_at is not None:
            log_missed_attempt(hunt_log, attempt=attempt, started_at=started_at)
        return 1
    print(
        "Jirachi: "
        f"slot={mon.slot}  pid={mon.personality:08X}  "
        f"tid={mon.tid}  sid={mon.sid}  ot={mon.ot_name}  "
        f"sv={mon.shiny_value}  shiny={mon.is_shiny}"
    )
    if hunt_log is not None and attempt is not None and started_at is not None:
        duration_s = time.perf_counter() - started_at
        if mon.is_shiny:
            return handle_shiny(
                hunt_log,
                attempt=attempt,
                duration_s=duration_s,
                sv=mon.shiny_value,
                save_path=sav,
            )
        hunt_log.write_attempt(
            attempt=attempt,
            duration_s=duration_s,
            sv=mon.shiny_value,
            result="fail",
        )
    return 0


def probe_inputs(session: DolphinSession) -> int:
    try:
        pad = PadDriver(session)
        print(
            "Input maps: "
            f"Channel A={pad.channel_map['A']!r}  "
            f"GBA2 A={pad.gba_map['A']!r}"
        )
        print("Focus Channel, tap A")
        pad.tap_channel("A")
        time.sleep(0.6)
        print("Load Ruby on GBA2 (Rom2 + Reset; Load ROM dialog if needed)")
        session.load_ruby_rom()
        print("Focus GBA2, tap A")
        pad.tap_gba("A")
    except (DolphinError, InputError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Input probe sent. Windows:")
    for title in session.window_titles():
        print(f"  window: {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
