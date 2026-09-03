# 6. Parse shiny value

- **Number:** 06 / 09
- **Status:** done
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

After Ruby saves, read the received Jirachi from the party in `-2.sav` and compute SV. No PKHeX GUI.

## Context

```
SV = (PID_high XOR PID_low XOR TID XOR SID) & 0xFFFF
```

Shiny iff `SV` in **0..7**. Channel OT CHANNEL, TID 40122; still use TID/SID from the Pokémon data. v1: parse `.sav` after in-game save (not GBA RAM).

## Steps

- [x] Gen 3 party parse (valid sections, checksums).
- [x] Find Jirachi (Gen 3 internal species **409**, National Dex 385); error if missing.
- [x] Return `SV` int; caller logs it every attempt.

Implemented in `botjirachi/party.py`. CLI: `--parse-sv [SAV]` (default Dolphin `-2.sav`; no restore / no Dolphin). `--receive` prints SV after the transfer.

Live check (2026-09-02) on the working `-2.sav` from plan 05: Jirachi slot 5, OT CHANNEL, TID 40122, SID 49197, PID `2B69810E`, **SV=63216** (not shiny). Original `resources/*.sav` (5-mon party, no Jirachi) fails loudly.

## Out of scope

Writing the save, notify.

## Done when

A known Ruby save with a Channel Jirachi yields the correct SV; empty/pre-transfer save fails loudly.