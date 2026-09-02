# BotJirachiGC

Bot para shiny hunting de Jirachi (Pokémon Channel + Ruby).

Este archivo es la memoria de proyecto. Lo leen Claude Code y Grok (compatibilidad Claude: `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/`).

## Qué es este repo

Automatización para cazar Jirachi shiny usando recursos de GameCube / GBA. Los dumps (ISO, GBA, SAV, GCI) viven en `resources/` y **no son código**.

## Dónde está qué

| Ruta | Uso |
|------|-----|
| `CLAUDE.md` | Normas y contexto del proyecto (este archivo) |
| `.claude/rules/` | Normas modulares (se cargan todas) |
| `.claude/plans/` | Planes de trabajo, specs, checklists |
| `resources/` | ROMs, saves, dumps — no commitear dumps nuevos si pesan o son ilegales de redistribuir |
| `README.md` | Descripción corta para humanos |

## Cómo trabajar aquí

- **No hay commit ni push sin permiso expreso del usuario.** Ni `git commit`, ni `git push`, ni `--amend`, ni staging “por si acaso”. Esperar una frase clara del tipo “haz commit” / “commitea esto”.
- Todo **código, identificadores, comentarios, docstrings, mensajes de commit y texto en el repo** van en **inglés**. El chat con el usuario puede ir en español.
- Antes de implementar, lee las reglas en `.claude/rules/` y el plan activo en `.claude/plans/` si existe.
- Plans live in `.claude/plans/<name>.md`, in English. One active plan at a time unless stated otherwise.
- No inventes arquitectura: el repo está empezando. Propón y documenta en un plan antes de crear un árbol grande de carpetas.
- No toques dumps en `resources/` salvo que el usuario lo pida. No copies ROMs a otros sitios.
- Código nuevo: claro, acotado al pedido, sin refactors de relleno.

## Idioma

- Chat: español (salvo que el usuario pida otra cosa).
- Repo: inglés — código, comentarios, docs en el árbol de código, nombres de archivos de implementación.

## Comandos

- Hunt (desde la raíz del repo): `python3 -m botjirachi`
- Si faltan ISO, GBA, `.sav` original, BIOS GBA o el binario de Dolphin: error en stderr y exit `1`
- Tras el check: copia el `.sav` original a las dos ranuras GBA de Dolphin; no escribe en `resources/`
- Arranca Channel en Dolphin con el puerto 2 vacío; Ctrl+C no mata Dolphin. Accessibility de macOS para menús y teclado (`pynput`). `--probe-inputs` prueba Channel A y GBA2 A. `--parse-sv` lee el SV de Jirachi en un `.sav` (sin restore ni Dolphin). Default `python3 -m botjirachi` repite el receive hasta SV 0..7. Tras un fail: Port 2 None, A ×3, 1 s, restore; los reintentos no eligen 50/60 Hz. Cinco `sv=-1` seguidos: mata Dolphin, restaura el `.sav`, arranca Channel y vuelve a elegir PAL Hz. `--receive` es un solo transfer (reset + Hz) y registra el intento en stdout y `logs/attempts.txt`; el número continúa al reiniciar. Si SV 0..7: no restaura el `.sav`, escribe resumen en `logs/shiny.txt`, `notify_shiny` (stub), exit `0`. `--force-shiny` finge ese hit sin restore ni Dolphin.
- Detalle: `.claude/rules/toolchain.md`
