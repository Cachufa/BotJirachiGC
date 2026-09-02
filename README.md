# BotJirachiGC

Shiny hunt Jirachi via **Pokémon Channel (Europe)** + **Pokémon Ruby (Spain)** in Dolphin.

## Start

Homebrew Python blocks `pip3 install pynput` (PEP 668). Use the project venv from the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install pynput
.venv/bin/python -m botjirachi
```

If `.venv` already exists, only the last line is needed.

That is the hunt: it repeats Channel → Ruby until Jirachi’s shiny value is **0..7**. No attempt cap. **Ctrl+C** stops the bot and leaves Dolphin and the saves as they are.

Needs macOS **Accessibility** for the app that launches the command (Terminal, iTerm, Python, or Grok): System Settings → Privacy & Security → Accessibility.

## What one attempt does

1. Boot Channel with Port 2 empty (no GBA window). First boot also picks PAL **60 Hz**.
2. Title → Opciones → Jirachi → Oak prompts (timed pads, not RAM).
3. When Channel asks to turn the GBA on: Port 2 = GBA (Integrated). Rom2 auto-loads Ruby. No extra GBA Reset / right-click if the ROM is already loaded.
4. Wait until the port-2 `.sav` updates (~17 s). Then Port 2 None so the GBA can flush. Parse the party Jirachi (OT CHANNEL, TID 40122). Shiny iff SV is 0..7.

**Fail (not shiny):** Port 2 None (turn off GBA) → Channel **A × 3** → wait 1 s → copy the original Ruby `.sav` onto both Dolphin GBA slots. Next attempt **skips 60 Hz**. On the Options 2×2 it nudges the stick **Up 0.02 s** (HID only) so the cursor hits Jirachi, then the same menus again. **Five `sv=-1` in a row:** kill Dolphin, restore, boot Channel, pick 60 Hz again.

**Shiny:** stop. Do **not** restore. Log a summary. `notify_shiny` is a stub (Discord later). Exit `0`. A later launch also skips restore if the last log line is `result=shiny`.

`resources/` is never written. Only Dolphin `GBA/Saves/` is overwritten on fail.

## Logs

Same attempt line on stdout and `logs/attempts.txt` (append-only):

```
2026-09-02T14:54:06Z  attempt=5  duration_s=129.6  sv=38123  result=fail
```

Restart continues `attempt` from that file. `logs/hunt_started.txt` is the wall-clock hunt start (not reset). A shiny also appends `logs/shiny.txt`. If the `.sav` does not update or Jirachi is missing: `sv=-1  result=miss` (still has `attempt` and `duration_s`). Five misses in a row: kill Dolphin, restore the original `.sav`, boot Channel again (PAL Hz), keep hunting.

## Other commands

| Flag | What |
|------|------|
| `--receive` | One transfer only (Channel reset + 60 Hz), then parse SV |
| `--parse-sv [SAV]` | Parse Jirachi SV only (default: Dolphin `…-2.sav`). No restore, no Dolphin |
| `--force-shiny` | Fake a shiny hit: logs + stub notify, no restore, no Dolphin |
| `--probe-inputs` | Tap Channel A, load Ruby on GBA2, tap GBA A |
| `--max-attempts N` | Stop after N logged attempts (testing). Default hunt has no cap |
| `--pal-hz 50\|60` | PAL boot Hz (default 60) |
| `--iso` `--gba` `--sav` `--bios` `--dolphin` `--dolphin-user-dir` | Path overrides |

Missing ISO / GBA / original `.sav` / GBA BIOS / Dolphin binary: all missing paths on stderr, exit `1`.

## Requirements

- Python 3.10+ and **pynput** in a venv (Homebrew `pip3 install` is blocked).
- Dumps in `resources/` (gitignored; do not commit them):
  - `Pokemon Channel (Europe) (En,Fr,De,Es,It) (v1.00).iso`
  - `Pokemon - Edicion Rubi (Spain).gba`
  - `Pokemon - Edicion Rubi (Spain).sav` — Hall of Fame, free party slot. Never overwritten.
- Channel `.gci` already in Dolphin `GC/EUR/Card A/`.
- GBA BIOS: `~/Library/Application Support/Dolphin/GBA/gba_bios.bin`
- Dolphin: `/Applications/Dolphin.app`
- Controllers → Common → **Background Input** on (so GBA2 gets keys). Do not pass `SIDevice` on the Dolphin command line (it blocks live Port 2 changes).

Pad maps (`GCPadNew.ini` / `GBA.ini`): Channel A=`X`; GBA2 A=`1` (number row, not numpad).

Save editors for the Ruby `.sav`: [PKMDS](https://pkmds.app/), [PKHeX.Everywhere](https://pkhex-web.github.io/). Channel `.gci` is not a main-series save.

See `CLAUDE.md` for project conventions.
