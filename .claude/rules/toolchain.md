# Toolchain

- Language: **Python 3.10+**, stdlib first.
- Hunt command (repo root): `python3 -m botjirachi`
- Optional path overrides: `--iso`, `--gba`, `--sav`, `--bios`, `--dolphin`, `--dolphin-user-dir`
- Missing ISO / GBA / original `.sav` / GBA BIOS / Dolphin binary: print all missing paths on stderr and exit `1`
- After paths are OK, copy `resources/*.sav` onto both Dolphin GBA save names (`.sav` and `-2.sav`). Never write into `resources/`.
- Then start (or reuse) Dolphin and boot Channel with Port 2 empty. Ctrl+C does not kill Dolphin (`start_new_session`). macOS Accessibility is required to change Port 2 / Stop / Play via menus.
- Extra deps: none in plan 01. Plan 04 will add `pynput` (or `pyautogui`) to send keyboard events to Dolphin.
- venv: optional; `.venv/` is gitignored. No venv is required to run.
