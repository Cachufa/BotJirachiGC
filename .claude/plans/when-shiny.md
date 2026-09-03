# 8. When shiny

- **Number:** 08 / 09
- **Status:** done
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

- [x] Stop loop; no further restore.
- [x] Dual log attempt + summary.
- [x] `notify_shiny(...)` TODO / `pass` (Discord or other, not v1).

Implemented in `botjirachi/shiny.py` (`handle_shiny`), `botjirachi/huntlog.py` (`logs/shiny.txt`), `botjirachi/notify.py` (stub). `--receive` takes this path when SV is 0..7. `--force-shiny` fakes the hit: skips restore and Dolphin, writes both logs, leaves the working `.sav` as-is, exit `0`. A later default/`--receive` launch also skips restore if the last attempt line is `result=shiny`.

## Out of scope

Copying sav aside, PKHeX, actually sending Discord.

## Done when

A fake/forced shiny path stops, writes both logs, does not overwrite the working `.sav`.