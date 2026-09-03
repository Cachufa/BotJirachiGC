# 4. Inputs (macOS)

- **Number:** 04 / 09
- **Status:** done
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Drive Dolphin with real keyboard (and mouse only if needed) so Channel and Ruby see the mapped pads.

## Context

- Channel / GCPad1: A=`X`, B=`Z`, Start=`Return` (`GCPadNew.ini`)
- GBA **port 2** today: A=`1`, B=`2`, Start=`6` (`GBA.ini` `[GBA2]`) — bot must use these **or** unify GBA2 to X/Z/Return
- Focus the Channel/render window vs the GBA window before sending keys
- Accessibility required. **Background Input on** (Mandos → Común → Funcionar en segundo plano) or GBA2 never sees keys (only the Channel render window does).
- Prefer **Rom2 + Reset** over right-click Load ROM (Python *can* right-click; file dialog is brittle)

Implemented in `botjirachi/inputs.py` (`PadDriver`) and `botjirachi/dolphin.py`. Channel A=`X`; GBA2 A=`1` (number-row vk 18, not numpad 83). HID keys while osascript keeps Dolphin frontmost. Ruby title: soft-reset (A+B+Select+Start), wait **7 s**, A, wait **7 s**, A — both registered. `Rom2` auto-loads. Do **not** pass `SIDevice` via `--config`. Background Input must be on.

## Steps

- [x] Focus helper + key down/up for mapped buttons.
- [x] Document Accessibility for the terminal/Python app.
- [x] Load Ruby: set `Rom2` at GBA-on time and Reset, or right-click Load ROM as fallback.
- [x] Dry-run: Channel accepts X; GBA2 accepts its A key (`--probe-inputs`).

## Out of scope

Lua fork, clicking game pixels, Wine.

## Done when

A scripted X (Channel) and GBA A (Ruby) register in-game with the correct window focused.