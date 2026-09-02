# Toolchain

- Language: **Python 3.10+**, stdlib first.
- Hunt command (repo root): `python3 -m botjirachi`
- Optional path overrides: `--iso`, `--gba`, `--sav`, `--bios`, `--dolphin`, `--dolphin-user-dir`
- Missing ISO / GBA / original `.sav` / GBA BIOS / Dolphin binary: print all missing paths on stderr and exit `1`
- After paths are OK, copy `resources/*.sav` onto both Dolphin GBA save names (`.sav` and `-2.sav`), except the hunt fail path which turns GBA off first. Never write into `resources/`.
- Then start (or reuse) Dolphin and boot Channel with Port 2 empty. Ctrl+C does not kill Dolphin (`start_new_session`). macOS Accessibility is required to change Port 2 / Stop / Play via menus **and** to send keyboard/mouse events (`pynput`).
- Extra deps: `pynput` (keyboard + mouse to Dolphin). Channel keys follow `GCPadNew.ini` (A=`X`); GBA2 keys follow `GBA.ini` (A=`1`, number-row not numpad). `--probe-inputs` dry-runs Channel A, Port 2 GBA + Rom2 auto-load, GBA2 A. Default `python3 -m botjirachi` loops receive until SV 0..7. Fail path: Port 2 None, Channel A ×3, wait 1 s, restore `.sav`; retries skip PAL Hz. `--receive` is one transfer from Channel reset + Hz, then parses SV from `-2.sav` and appends the same attempt line to stdout and `logs/attempts.txt`. Restart continues `attempt` from that file; `logs/hunt_started.txt` is not reset. On SV 0..7: no restore, append summary to stdout + `logs/shiny.txt`, `notify_shiny` stub, exit `0`. `--force-shiny` fakes that path (no restore, no Dolphin). A later default/`--receive` launch skips restore if the last attempt is `result=shiny`. `--parse-sv [SAV]` parses Jirachi SV only (no restore, no Dolphin, no attempt log). Gen 3 internal species for Jirachi is 409 (National Dex 385). Shiny iff SV in 0..7. Do not pass `SIDevice` on the Dolphin command line (it blocks live Port 2 changes / blacks Channel). Enable Controllers → Common → Background Input so GBA2 receives keys. Ruby title: 7 s after soft-reset, A, 7 s, A.
- Accessibility: System Settings → Privacy & Security → Accessibility → Terminal / Python / the app that launches the bot.
- venv: optional; `.venv/` is gitignored. No venv is required to run.
