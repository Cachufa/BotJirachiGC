# Jirachi shiny loop (requirements)

This file is the **umbrella** snapshot. Do not delete it.

- **Number:** 00 (umbrella)
- **Status:** done

Work is split into:

| # | Plan | Topic | Status |
|---|------|--------|--------|
| 01 | [python-project.md](python-project.md) | Python layout, CLI, deps | done |
| 02 | [restore-ruby-save.md](restore-ruby-save.md) | Copy original `.sav` into Dolphin | done |
| 03 | [dolphin-process.md](dolphin-process.md) | Keep Dolphin alive, Port 2, boot Channel | done |
| 04 | [inputs-macos.md](inputs-macos.md) | Keyboard, window focus, Load ROM | done |
| 05 | [channel-gba-sequence.md](channel-gba-sequence.md) | Timed Channel → GBA transfer + Ruby save | done |
| 06 | [parse-shiny-value.md](parse-shiny-value.md) | Party parse, SV 0..7 | done |
| 07 | [logging.md](logging.md) | Terminal + files, resume attempt number | done |
| 08 | [when-shiny.md](when-shiny.md) | Stop loop, summary, notify TODO | done |
| 09 | [hunt-loop.md](hunt-loop.md) | Wire the pieces into the repeat loop | done |

## Goal

A **Python** program that repeats the Pokémon Channel → Ruby Jirachi transfer until a **shiny** Jirachi is found. Each failed attempt restores the original Ruby save and starts over. Each attempt is logged to a text file **and** to the terminal.

## Context

- Bot: shiny hunt Jirachi via **Pokémon Channel (Europe)** + **Pokémon Ruby (Spain)** in **Dolphin** (integrated GBA).
- Channel GCI is already in `~/Library/Application Support/Dolphin/GC/EUR/Card A/`.
- Original Ruby save: `resources/Pokemon - Edicion Rubi (Spain).sav`.
- Dolphin GBA port 2 uses: `~/Library/Application Support/Dolphin/GBA/Saves/Pokemon - Edicion Rubi (Spain)-2.sav`.
- Channel must **not** boot the GBA at the same time. Port 2 starts **empty**. When Channel asks to turn the GBA on: set Port 2 to **GBA (Integrated)**, then **Load ROM** (Ruby).
- One Jirachi per Ruby save (event flag). That is why the save must be replaced after a non-shiny receive.
- Manual steps live in `jirachi-steps.txt`.

## Shiny test (Gen 3)

Do **not** use PKHeX GUI. Parse the received Jirachi (party slot) from the Ruby save (or GBA RAM if that is faster and reliable).

Shiny value:

```
SV = (PID_high XOR PID_low XOR TID XOR SID) & 0xFFFF
```

- `PID_high` / `PID_low`: upper / lower 16 bits of the personality ID.
- `TID` / `SID`: trainer ID / secret ID on that Pokémon (Channel Jirachi OT is CHANNEL, TID 40122; SID still comes from the generated data).

**Shiny if and only if `SV` is in 0..7 (inclusive).**

Log `SV` on every attempt, shiny or not.

## Loop (happy path)

1. Restore the original Ruby `.sav` onto both Dolphin GBA save names (`.sav` and `-2.sav`).
2. Start (or resume) Dolphin and boot Pokémon Channel. Port 2 = none. No GBA window.
3. Automate Channel: title → Options → Jirachi → Yes on Oak prompts until it asks to turn on the GBA.
4. Switch Port 2 to GBA (Integrated). Load `resources/Pokemon - Edicion Rubi (Spain).gba`.
5. On Ruby: Continue (not New Game). Complete the transfer.
6. Persist the party to the `.sav` (in-game save on Ruby, or flush GBA save if the emulator already wrote it).
7. Read Jirachi from the party. Compute `SV`.
8. Append a log line (see Logs).
9. If `SV` is **not** in 0..7: go to step 1 (replace save with original, repeat).
10. If `SV` is in 0..7: run **When shiny** (below), then exit.

## Language and layout

- Implementation language: **Python 3** (stdlib first; extra deps only if needed to drive Dolphin).
- Entry point: a single runnable module/script (name chosen at implement time, e.g. `python -m bot` or `python hunt.py`).
- Code, comments, identifiers: English.

## Logs

Every attempt line is written in **both** places, same content:

- **Terminal (stdout)** — so the user sees progress while it runs.
- **Append-only UTF-8 file** — `logs/attempts.txt` (create `logs/`). Gitignore `logs/`.

Do not only log to one of them.

One line per attempt, at least:

- attempt number (1-based)
- duration of the attempt (seconds, from Channel boot to SV computed)
- shiny value (`SV`, decimal)
- result: `fail` or `shiny`

Example:

```
2026-08-31T18:00:00Z  attempt=1  duration_s=42.1  sv=1842  result=fail
2026-08-31T18:01:12Z  attempt=2  duration_s=40.8  sv=3      result=shiny
```

A run header at start (timestamp, paths) is useful. Do not log secrets.

### Resume attempt number

If the program stops (Ctrl+C, crash, quit) and is started again:

- Open the existing `logs/attempts.txt` if it exists.
- Parse the last `attempt=N` among attempt lines (ignore headers / malformed lines).
- Next attempt is `N + 1`.
- If the file is missing or has no attempt lines, start at `1`.
- **Append** to the same file; never truncate it on startup.
- Resuming the counter does **not** resume a half-finished in-game attempt; always restore the original Ruby save and start the Channel flow from the beginning. Only the **number** continues.

Wall-clock **total hunt time** for the shiny summary: persist a hunt start timestamp (e.g. first line of the log file, or `logs/hunt_started.txt`). On resume, **do not** reset that timestamp, so `total_time` spans all sessions until shiny.

## When shiny (v1)

On `SV` in 0..7:

1. **Stop the loop.** Do not start another attempt.
2. **Do not** restore/overwrite the Ruby `.sav`. Leave Dolphin and `GBA/Saves` as they are.
3. Write the usual **per-attempt** line (`result=shiny`) to terminal + `logs/attempts.txt`.
4. Write a **summary** to terminal **and** to a second file `logs/shiny.txt` (append; one block per shiny, should be once per hunt). Include at least:
   - total attempts (the `attempt` number of this hit, which is cumulative across restarts)
   - total time (wall clock from hunt start, including pauses between process restarts)
   - `SV`
   - timestamp
   - path of the working Ruby save (the `-2.sav`)

Example summary:

```
SHINY  2026-08-31T20:15:00Z  attempts=812  total_s=28940.2  sv=4  save=.../Pokemon - Edicion Rubi (Spain)-2.sav
```

Process exit code: `0` on shiny stop.

### Future: notify (not v1)

After the summary is written, a later change can **alert** the user (Discord webhook, macOS notification, or another channel — pick at implement time of that feature). v1 only stops + logs. Leave a `TODO` in code at the end of the shiny path, e.g. `notify_shiny(...)`, empty or `pass`.

## Non-functional

- Chat with the user may be Spanish; **code, identifiers, comments, this plan: English**.
- No git commit unless asked.
- Do not copy or commit dumps from `resources/`.
- Fail loudly if dumps, BIOS, or Dolphin paths are missing. No stubs.
- Safe restore: never overwrite `resources/*.sav`; only copy **from** resources **to** Dolphin `GBA/Saves`.
- On shiny: leave Dolphin and the GBA save as they are (user inspects).
- On crash / Ctrl+C: leave emulator/saves as-is; do not delete or rewrite logs. Next launch continues `attempt` from the file.

## Decisions (recommended)

These replace the old open list. Change them here if you disagree before implement.

### 1. Dolphin process: keep alive, restart the game

**Choice:** Start Dolphin once. Each attempt: Port 2 back to None, restore Ruby `.sav`, **stop emulation and boot Channel again** (or reset to title if that is enough). Do **not** kill the Dolphin process every loop.

**Why:** Booting the ISO from a cold process is slower and flakier on macOS. Brute-force SV 0..7 is ~1/8192; loop time dominates.

**Recovery:** If an attempt errors (no GBA window, transfer timeout, bad parse), kill Dolphin and start a fresh process, then continue. Optional: forced process restart every N attempts (e.g. 50) so a stuck GBA window cannot linger.

### 2. “Turn on the GBA”: scripted delays first, RAM later

**Choice for v1:** A **fixed, tunable sequence of waits + button presses** copied from a working manual run (`jirachi-steps.txt`). After “turn on GBA”, **verify** that the GBA window exists (process/window list) before Load ROM. Timeouts fail the attempt, restore save, retry.

**Why:** Stock Dolphin 2606 has no Lua. Channel RAM addresses exist in the RNG community, but wiring a memory reader is extra moving parts. Menus on a completed PAL save are short and repeatable enough for a bot.

**Later:** If delays drift, read GameCube RAM (Dolphin memory socket / mapped file) for the Jirachi-menu / “turn on GBA” flag. Do not switch Dolphin builds just for Lua unless we need RNG hitting.

### 3. Shiny value: parse the `.sav` after an in-game save

**Choice for v1:** After the transfer, **save in Ruby** (Start → Save), wait until `Pokemon - Edicion Rubi (Spain)-2.sav` changes, parse the party, compute SV.

**Why:** We already know the file path and Gen 3 save layout. GBA RAM inside integrated mGBA is not as easy to peek as GameCube RAM. Wrong SV from RAM would corrupt the hunt.

**Cost:** Save animation adds seconds per attempt. Acceptable until the loop is proven. Later optimization: read GBA party RAM and skip the in-game save on fails (still save — or copy the sav aside — on shiny).

### 4. Inputs on macOS: keyboard to the mapped Dolphin keys + focus the right window

**Choice:** Drive the pads with **keyboard events** using the mappings already in `GCPadNew.ini` / `GBA.ini` (A/B/Start, etc.). Before a Channel sequence, focus the **Channel/render** window; before Ruby Continue, focus the **GBA** window. Use a small Python helper (e.g. `pynput` or `pyautogui`) plus Accessibility permission (the same limit we hit with osascript).

**Why:** Stock Dolphin, no TAS movie, no Lua fork. Mouse for “Load ROM” file dialog is OK for v1 (or Dolphin `Rom2` set only at that moment via config + GBA Reset if the file dialog is too brittle).

**Not for v1:** CrossOver/Wine, clicking on pixels of the game image, a custom Dolphin fork.

## Out of scope (this version)

- Discord / push / mail notify (TODO stub only; choose the channel later).
- Copying the shiny `.sav` to another folder, PKHeX, screenshots.
- RNG manipulation (seed hitting, Lua, frame advances). This loop is brute-force receive + SV check.
- Editing Channel GCI.
- UI beyond CLI (terminal + txt logs).

## Done when (later, after implement)

- Unattended loop: restore save → Channel → GBA at the prompt → transfer → SV in the log → repeat until SV 0..7.
- Original `resources` Ruby save is never mutated.
- A shiny attempt stops the loop, keeps the working `.sav`, logs the attempt **and** a summary (`attempts`, `total_s`, `sv`) to terminal + `logs/shiny.txt`.
- Notify (Discord or other) is a TODO, not required to ship v1.
