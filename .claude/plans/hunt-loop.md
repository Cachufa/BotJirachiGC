# 9. Hunt loop

- **Number:** 09 / 09
- **Status:** done
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Wire the other plans into the repeat loop until SV is 0..7.

## Context

Default CLI (`python3 -m botjirachi`) is the loop. `--receive` stays one shot (Channel reset + PAL Hz).

**First boot** (Dolphin down, or Channel not running): restore `.sav` → boot Channel → PAL 50/60 Hz → title → Options → Jirachi → GBA on → transfer → parse SV → log.

**Fail path** (Channel leftover is “turn off the GBA”): Port 2 None → Channel A ×3 → wait **1 s** (placeholder) → restore original Ruby `.sav` (GBA must already be off). Do **not** reset Channel and do **not** pick PAL Hz again. Live leftover (2026-09-02): after this, GBA window is gone and Channel is on the Nintendo / Pokémon Company / Ambrella splash (not Pokémon Home). Retry then uses the title 2×2 without Hz.

**Retry receive:** skip PAL Hz. Same menus as boot; before Jirachi A, a tiny stick Up so the cursor hits the button.

**Five consecutive misses (`sv=-1`):** stop the in-game fail path, kill Dolphin, restore the original Ruby `.sav`, boot Channel with Port 2 empty, pick PAL Hz again. A logged fail or shiny, or a Dolphin reboot, resets the streak (five more misses before the next kill). Seeded from the trailing `sv=-1` lines in `logs/attempts.txt`.

**Shiny:** [when-shiny.md](when-shiny.md) — no restore, no fail path.

Ctrl+C: leave emu/saves; do not wipe logs.

## Steps

- [x] Implement the loop using the sibling plans (do not duplicate their rules).
- [x] Time each attempt for `duration_s`.
- [x] Fail path: Port 2 None, A ×3, 1 s, then restore; shiny path never restores.
- [x] Five consecutive `sv=-1`: kill Dolphin, restore, boot Channel, pick PAL Hz.

## Out of scope

RNG hitting, Channel GCI edits, UI.

## Done when

Verified 2026-09-02: five unattended cycles (boot + four retries) each landed Jirachi, logged SV, restored on fail. `resources` Ruby save not mutated. Loop default has no attempt cap; `--max-attempts` is test-only.