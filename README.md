# BotJirachiGC

Bot for shiny hunting Jirachi (Pokémon Channel + Pokémon Ruby).

Game dumps (ISO, GBA, SAV, GCI) belong in `resources/` and are gitignored. Do not commit them.

Save editor (web, no install): [PKMDS](https://pkmds.app/) — PKHeX.Core in the browser. Alternative: [PKHeX.Everywhere](https://pkhex-web.github.io/). Use these for the Ruby `.sav`; Pokémon Channel `.gci` is not a main-series save.

GBA timing: Port 2 starts empty so the GBA window does not open with Channel. When Channel asks to turn the GBA on, Controllers → Port 2 → GBA (Integrated), then in the GBA window Load ROM → `resources/Pokemon - Edicion Rubi (Spain).gba`.

## Run

From the repo root:

```bash
python3 -m botjirachi
```

Requires the Channel ISO, Ruby GBA and original Ruby `.sav` under `resources/`, GBA BIOS at `~/Library/Application Support/Dolphin/GBA/gba_bios.bin`, and Dolphin at `/Applications/Dolphin.app`. Missing paths are listed on stderr (exit `1`). The hunt loop itself is later plans; this command is the single entry point.

See `CLAUDE.md` for project conventions.
