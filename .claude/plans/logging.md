# 7. Logging

- **Number:** 07 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Every attempt is logged to **stdout and** `logs/attempts.txt`. Restarting the program continues `attempt` from the file. Hunt start time is kept for total duration.

## Context

Append-only UTF-8. Gitignore `logs/`. Same line in both sinks. Never truncate on startup.

```
2026-08-31T18:00:00Z  attempt=1  duration_s=42.1  sv=1842  result=fail
```

Resume: last `attempt=N` → next is `N+1`; missing file → 1. Resume does **not** continue an in-game attempt. Persist hunt start (`logs/hunt_started.txt` or first log line); do not reset on resume.

Shiny extra file: [when-shiny.md](when-shiny.md).

## Steps

- [ ] Dual write (print + append).
- [ ] Parse last attempt on startup.
- [ ] Persist hunt start timestamp.
- [ ] Run header optional; no secrets.

## Out of scope

Discord.

## Done when

Kill and rerun: next line is `attempt=N+1`; old lines still in the file; stdout shows the same lines.