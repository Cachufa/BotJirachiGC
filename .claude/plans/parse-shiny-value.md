# 6. Parse shiny value

- **Number:** 06 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

After Ruby saves, read the received Jirachi from the party in `-2.sav` and compute SV. No PKHeX GUI.

## Context

```
SV = (PID_high XOR PID_low XOR TID XOR SID) & 0xFFFF
```

Shiny iff `SV` in **0..7**. Channel OT CHANNEL, TID 40122; still use TID/SID from the Pokémon data. v1: parse `.sav` after in-game save (not GBA RAM).

## Steps

- [ ] Gen 3 party parse (valid sections, checksums).
- [ ] Find Jirachi (species 385); error if missing.
- [ ] Return `SV` int; caller logs it every attempt.

## Out of scope

Writing the save, notify.

## Done when

A known Ruby save with a Channel Jirachi yields the correct SV; empty/pre-transfer save fails loudly.