# 1. Python project

- **Number:** 01 / 09
- **Status:** requirements — not started
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Scaffold the hunt as a **Python 3** program: runnable entry point, English code, stdlib first.

## Context

Umbrella language/layout. Repo files in English. No dumps in git. One active hunt command.

## Steps

- [ ] Pick entry point (`python -m …` or `hunt.py`).
- [ ] Extra deps only if needed to drive Dolphin (`pynput` / `pyautogui`); record them.
- [ ] Fail loudly if ISO, GBA, original `.sav`, BIOS, or Dolphin paths are missing.
- [ ] `.gitignore` for `logs/` and venv if added.

## Out of scope

Emulator driving, save parse, Discord.

## Done when

`python …` starts the hunt (or prints a clear missing-path error) without placeholders.