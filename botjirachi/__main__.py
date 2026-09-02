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
from botjirachi.sequence import PAL_HZ, SequenceError, receive_jirachi


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
    missing = paths.missing()
    if missing:
        report_missing(missing)
        return 1
    print_header(paths)
    try:
        dests = restore_ruby_save(paths)
    except RestoreError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Restored original Ruby save to:")
    for dest in dests:
        print(f"  {dest}")
    session = DolphinSession(paths)
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
    hunt_log = HuntLog(paths.logs_dir)
    started, next_attempt = hunt_log.prepare()
    hunt_log.write_run_header(started, next_attempt)
    if args.receive:
        hz = args.pal_hz if args.pal_hz is not None else PAL_HZ
        print(f"Receive: PAL {hz} Hz")
        return run_receive(session, hz, hunt_log)
    print("Channel running with Port 2 empty. Use --receive for one transfer.")
    return 0


def run_receive(session: DolphinSession, pal_hz: int, hunt_log: HuntLog) -> int:
    attempt = hunt_log.next_attempt_number()
    started_at = time.perf_counter()
    try:
        sav = receive_jirachi(session, pal_hz=pal_hz)
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


def run_parse_sv(sav: Path) -> int:
    print(f"Parse SV: {sav}")
    return report_jirachi_sv(sav)


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
        return 1
    print(
        "Jirachi: "
        f"slot={mon.slot}  pid={mon.personality:08X}  "
        f"tid={mon.tid}  sid={mon.sid}  ot={mon.ot_name}  "
        f"sv={mon.shiny_value}  shiny={mon.is_shiny}"
    )
    if hunt_log is not None and attempt is not None and started_at is not None:
        hunt_log.write_attempt(
            attempt=attempt,
            duration_s=time.perf_counter() - started_at,
            sv=mon.shiny_value,
            result="shiny" if mon.is_shiny else "fail",
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
