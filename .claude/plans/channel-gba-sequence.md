# 5. Channel → GBA sequence

- **Number:** 05 / 09
- **Status:** done
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Automate one full receive: Channel Jirachi menu, turn on GBA at the prompt, Continue on Ruby, transfer, in-game save.

## Context

Manual list: `jirachi-steps.txt`. v1 = **tunable delays + buttons**, not GC RAM. After “turn on GBA”, verify the GBA window exists. Timeout → fail attempt, restore save, retry.

Ruby title (verified 2026-08-31): after GBA2 soft-reset (A+B+Select+Start), wait **7 s**, A, wait **7 s**, A. Both registered. Safe delays, not the minimum — tune down later. Constants: `GBA_AFTER_RESET_S` / `GBA_BETWEEN_A_S` in `botjirachi/inputs.py`.

Depends on [dolphin-process.md](dolphin-process.md), [inputs-macos.md](inputs-macos.md), [restore-ruby-save.md](restore-ruby-save.md).

Implemented in `botjirachi/sequence.py` (`receive_jirachi`). CLI: `.venv/bin/python -m botjirachi --receive` (`--pal-hz 50|60`, default **60**). Live receive **works** (2026-09-02): Port 2 GBA is last, no Ruby pad; Jirachi lands in ~**17 s** after GBA on (`TRANSFER_AFTER_GBA_S` cap **18 s**, returns when `-2.sav` mtime changes). No in-game Ruby save. Oak A mash can be tightened later (A during a text crawl only skips the crawl). Title 2×2: Continuar → Right (Extra) → Up (Opciones); Jirachi is the same slot, no stick. Do not pass `SIDevice` on the Dolphin command line. Use the venv Python (`pynput`).

## Steps

- [x] Title → Options → Jirachi → Yes on Oak prompts (timed; not RAM).
- [x] Enable Port 2 GBA + load Ruby ROM only at the prompt.
- [x] Ruby: Rom2 auto-load; no Continue taps. Transfer ~17 s after GBA on (cap 18 s).
- [x] In-game Ruby save skipped for v1 (Channel writes the party during transfer).

Live unattended `--receive` put Jirachi on `-2.sav`.

## Out of scope

SV math ([parse-shiny-value.md](parse-shiny-value.md)), Lua/RNG.

## Done when

One unattended run leaves a Channel Jirachi in the Ruby party on disk.