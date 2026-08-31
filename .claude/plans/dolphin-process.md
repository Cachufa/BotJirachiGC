# 3. Dolphin process

- **Number:** 03 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Run Dolphin for Channel without booting the GBA until the prompt. Keep the process alive between attempts.

## Context

- ISO: `resources/Pokemon Channel (Europe) (En,Fr,De,Es,It) (v1.00).iso`
- Channel GCI already in `GC/EUR/Card A/`
- `SIDevice0 = 6` (GC pad), Port 2 **empty** at Channel boot (`SIDevice1 = 0`)
- When Channel asks: Port 2 = GBA integrated (`SIDevice1 = 13`)
- Prefer not killing Dolphin every loop; restart process on error or every N attempts

## Steps

- [ ] Start Dolphin once; boot Channel.
- [ ] Each attempt: Port 2 None, restore save, stop emulation, boot Channel again.
- [ ] On timeout/error (or every N): kill Dolphin, start fresh, continue attempt counter via [logging.md](logging.md).

## Out of scope

Button presses ([inputs-macos.md](inputs-macos.md)), menu sequence ([channel-gba-sequence.md](channel-gba-sequence.md)).

## Done when

Channel boots with no GBA window; GBA can be enabled later without a full app relaunch unless recovering.