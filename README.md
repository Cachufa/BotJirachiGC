# BotJirachiGC

Bot for shiny hunting Jirachi (Pokémon Channel + Pokémon Ruby).

Game dumps (ISO, GBA, SAV, GCI) belong in `resources/` and are gitignored. Do not commit them.

Save editor (web, no install): [PKMDS](https://pkmds.app/) — PKHeX.Core in the browser. Alternative: [PKHeX.Everywhere](https://pkhex-web.github.io/). Use these for the Ruby `.sav`; Pokémon Channel `.gci` is not a main-series save.

GBA timing: Port 2 starts empty so the GBA window does not open with Channel. When Channel asks to turn the GBA on, Controllers → Port 2 → GBA (Integrated), then in the GBA window Load ROM → `resources/Pokemon - Edicion Rubi (Spain).gba`.

## Run

From the repo root:

```bash
python3 -m botjirachi
```

Requires the Channel ISO, Ruby GBA and original Ruby `.sav` under `resources/`, GBA BIOS at `~/Library/Application Support/Dolphin/GBA/gba_bios.bin`, and Dolphin at `/Applications/Dolphin.app`. Missing paths are listed on stderr (exit `1`).

On a successful path check the original Ruby `.sav` is copied into Dolphin `GBA/Saves` as both `Pokemon - Edicion Rubi (Spain).sav` and `…-2.sav`. `resources/` is never written. Then Dolphin boots Pokémon Channel with Port 2 empty (no GBA window).

Needs **pynput** (`pip3 install pynput` if you are not using the package metadata).

**Accessibility:** System Settings → Privacy & Security → Accessibility → enable the app that runs this command (Terminal, iTerm, Python, or Grok). The bot uses it for Dolphin menus (Port 2, Stop, Play) **and** for keyboard/mouse events. Dolphin Background Input is off, so the Channel render window or the GBA window must be focused before keys.

Pad maps (from `GCPadNew.ini` / `GBA.ini`, not unified): Channel A=`X`, B=`Z`, Start=`Return`; GBA port 2 A=`1`, B=`2`, Start=`6`.

`--probe-inputs` focuses Channel, taps A (`X`), enables GBA on Port 2 (`Rom2` auto-loads Ruby), then focuses GBA2 and taps A (`1`).

`--receive` runs one timed Channel → Ruby Jirachi receive (title → Options → Jirachi → GBA at the prompt → transfer). Delays live in `botjirachi/sequence.py`. After the transfer it parses the Port 2 `.sav` and prints Jirachi SV (shiny iff 0..7).

`--parse-sv` reads a Ruby `.sav` and prints Jirachi SV without restoring the save or starting Dolphin. Default file is Dolphin `GBA/Saves/…-2.sav`; pass a path to parse another file. Missing Jirachi is an error.

Each completed `--receive` writes the same attempt line to stdout and `logs/attempts.txt` (`attempt`, `duration_s`, `sv`, `result=fail|shiny`). The file is append-only; a restart continues `attempt` from the last line and keeps `logs/hunt_started.txt`. `--parse-sv` does not write an attempt.

If SV is 0..7, the receive path **stops**: it does not restore the original Ruby save, appends a summary to stdout and `logs/shiny.txt` (`attempts`, `total_s`, `sv`, working `-2.sav` path), calls a notify stub (`notify_shiny`; Discord later), and exits `0`. `--force-shiny` runs that same path without restore or Dolphin (leaves the working `.sav` as-is). Relaunching after a logged shiny also skips restore so the working `.sav` is not overwritten.

The hunt loop itself is later plans; `python3 -m botjirachi` is the single entry point.

See `CLAUDE.md` for project conventions.
