# 8. When shiny

- **Number:** 08 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

On SV 0..7: stop, keep the save, log the attempt plus a hunt summary. Leave a notify stub for later (Discord or other).

## Context

Do not restore the original `.sav`. Leave Dolphin running. Exit code 0.

Per-attempt line still goes to terminal + `logs/attempts.txt` (`result=shiny`).

Summary → terminal **and** `logs/shiny.txt`:

```
SHINY  …  attempts=812  total_s=28940.2  sv=4  save=…-2.sav
```

`attempts` = cumulative attempt number. `total_s` = wall clock from hunt start (all sessions).

## Steps

- [ ] Stop loop; no further restore.
- [ ] Dual log attempt + summary.
- [ ] `notify_shiny(...)` TODO / `pass` (Discord or other, not v1).

## Out of scope

Copying sav aside, PKHeX, actually sending Discord.

## Done when

A fake/forced shiny path stops, writes both logs, does not overwrite the working `.sav`.