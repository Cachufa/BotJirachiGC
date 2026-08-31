# 2. Restore Ruby save

- **Number:** 02 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Before each failed-attempt retry, copy the original Ruby save into Dolphin’s GBA save slots. Never mutate `resources/`.

## Context

- Source (read-only): `resources/Pokemon - Edicion Rubi (Spain).sav`
- Destinations: `~/Library/Application Support/Dolphin/GBA/Saves/Pokemon - Edicion Rubi (Spain).sav` and `…-2.sav` (port 2 uses `-2`)
- One Jirachi per Ruby save; restore is what allows the loop
- On **shiny**, do **not** restore (see [when-shiny.md](when-shiny.md))

## Steps

- [ ] Copy source → both dest names.
- [ ] Refuse to write into `resources/`.
- [ ] Error if source missing.

## Out of scope

Parsing the save, Channel GCI.

## Done when

A failed attempt can be retried on a clean Hall of Fame save; `resources/*.sav` unchanged.