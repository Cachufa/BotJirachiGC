# BotJirachiGC

Bot for shiny hunting Jirachi (Pokémon Channel + Pokémon Ruby).

Game dumps (ISO, GBA, SAV, GCI) belong in `resources/` and are gitignored. Do not commit them.

Save editor (web, no install): [PKMDS](https://pkmds.app/) — PKHeX.Core in the browser. Alternative: [PKHeX.Everywhere](https://pkhex-web.github.io/). Use these for the Ruby `.sav`; Pokémon Channel `.gci` is not a main-series save.

GBA timing: Port 2 starts empty so the GBA window does not open with Channel. When Channel asks to turn the GBA on, Controllers → Port 2 → GBA (Integrated), then in the GBA window Load ROM → `resources/Pokemon - Edicion Rubi (Spain).gba`.

See `CLAUDE.md` for project conventions.
