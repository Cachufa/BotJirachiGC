# 9. Hunt loop

- **Number:** 09 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Wire the other plans into the repeat loop until SV is 0..7.

## Context

Order per attempt: restore save → boot Channel (no GBA) → Channel menus → GBA on + ROM → Continue → transfer → Ruby save → parse SV → log → fail: repeat / shiny: [when-shiny.md](when-shiny.md).

Ctrl+C: leave emu/saves; do not wipe logs.

## Steps

- [ ] Implement the loop using the sibling plans (do not duplicate their rules).
- [ ] Time each attempt for `duration_s`.
- [ ] Fail path always restores save; shiny path never does.

## Out of scope

RNG hitting, Channel GCI edits, UI.

## Done when

Unattended: restore → Channel → GBA at prompt → transfer → SV in log → repeat until 0..7; `resources` Ruby save never mutated.