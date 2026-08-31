"""Hunt CLI: `python3 -m botjirachi` from the repo root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from botjirachi.paths import HuntPaths


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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = resolve_paths(args)
    missing = paths.missing()
    if missing:
        report_missing(missing)
        return 1
    print_header(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
