# 5. Channel → GBA sequence

- **Number:** 05 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Automate one full receive: Channel Jirachi menu, turn on GBA at the prompt, Continue on Ruby, transfer, in-game save.

## Context

Manual list: `jirachi-steps.txt`. v1 = **tunable delays + buttons**, not GC RAM. After “turn on GBA”, verify the GBA window exists. Timeout → fail attempt, restore save, retry.

Ruby title (verified 2026-08-31): after GBA2 soft-reset (A+B+Select+Start), wait **7 s**, A, wait **7 s**, A. Both registered. Safe delays, not the minimum — tune down later. Constants: `GBA_AFTER_RESET_S` / `GBA_BETWEEN_A_S` in `botjirachi/inputs.py`.

Depends on [dolphin-process.md](dolphin-process.md), [inputs-macos.md](inputs-macos.md), [restore-ruby-save.md](restore-ruby-save.md).

## Steps

- [ ] Title → Options → Jirachi → Yes on Oak prompts.
- [ ] Enable Port 2 GBA + load Ruby ROM only at the prompt.
- [ ] Ruby: Continue (not New Game); finish transfer.
- [ ] Ruby: Start → Save; wait for `-2.sav` to update.

## Out of scope

SV math ([parse-shiny-value.md](parse-shiny-value.md)), Lua/RNG.

## Done when

One unattended run leaves a Channel Jirachi in the Ruby party on disk.