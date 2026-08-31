# 1. Python project

- **Number:** 01 / 09
- **Status:** done
- **Parent:** [jirachi-shiny-loop.md](jirachi-shiny-loop.md)

## Goal

Scaffold the hunt as a **Python 3** program: runnable entry point, English code, stdlib first.

## Context

Umbrella language/layout. Repo files in English. No dumps in git. One active hunt command.

**Chosen entry point:** `python3 -m botjirachi` (package `botjirachi/`). Path checks live in `botjirachi/paths.py`. No extra PyPI deps yet.

## Steps

- [x] Pick entry point (`python -m …` or `hunt.py`).
- [x] Extra deps only if needed to drive Dolphin (`pynput` / `pyautogui`); record them.
- [x] Fail loudly if ISO, GBA, original `.sav`, BIOS, or Dolphin paths are missing.
- [x] `.gitignore` for `logs/` and venv if added.

## Out of scope

Emulator driving, save parse, Discord.

## Done when

`python …` starts the hunt (or prints a clear missing-path error) without placeholders.
