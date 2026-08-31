# 4. Inputs (macOS)

- **Number:** 04 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Drive Dolphin with real keyboard (and mouse only if needed) so Channel and Ruby see the mapped pads.

## Context

- Channel / GCPad1: A=`X`, B=`Z`, Start=`Return` (`GCPadNew.ini`)
- GBA **port 2** today: A=`1`, B=`2`, Start=`6` (`GBA.ini` `[GBA2]`) — bot must use these **or** unify GBA2 to X/Z/Return
- Focus the Channel/render window vs the GBA window before sending keys
- Accessibility permission required; Background Input is off
- Prefer **Rom2 + Reset** over right-click Load ROM (Python *can* right-click; file dialog is brittle)

## Steps

- [ ] Focus helper + key down/up for mapped buttons.
- [ ] Document Accessibility for the terminal/Python app.
- [ ] Load Ruby: set `Rom2` at GBA-on time and Reset, or right-click Load ROM as fallback.
- [ ] Dry-run: Channel accepts X; GBA2 accepts its A key.

## Out of scope

Lua fork, clicking game pixels, Wine.

## Done when

A scripted X (Channel) and GBA A (Ruby) register in-game with the correct window focused.