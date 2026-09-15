# HANDOFF — BytIA-KODE (B-KODE)

> Memoria transferible del repo. Leer ANTES de asumir contexto. Actualizar al cerrar sesión significativa.
> Última actualización: 2026-09-15 (sesión puente herdr)

## Qué es

Agente CLI propio (Python 3.11+ / Textual): agente + skills + terminal.
"Efectividad > Coste. Zero Hype. Truth > Comfort."

## Estado

- **Versión**: `0.8.0a1` (EN PROGRESO — ver CHANGELOG.md para el detalle por feature)
- **Tests**: 167/167 ✅ (`uv run pytest -q`)
- **CI**: `.github/workflows/ci.yml` — solo validación (metadata + tests + wheel + twine). Push a main NO deploya.
- **Lanzador**: `~/.local/bin/bytia-kode` (wrapper bash → `.venv/bin/bytia-kode`)
- **Cerebro**: `~/.bytia-kode/` (config, sesiones SQLite, temas, `mcp_servers.json`)

## Arquitectura en 30 segundos

```
src/bytia_kode/
├── tui.py        # BytIAKODEApp (Textual). ActivityIndicator.set_status = choke point de estados
├── agent.py      # loop agéntico
├── providers/    # multi-provider + failover local-first + circuit breaker
├── mcp/          # cliente MCP (Adapter sobre Tool registry)
├── herdr.py      # puente herdr: auto-reporte al panel de agentes del multiplexor
├── session.py    # persistencia SQLite de sesiones
├── skills/       # loader de skills
└── telegram/     # bot (--bot)
```

## Integración herdr (2026-09-15, commit bc24e04)

Si corre en un pane de herdr (`HERDR_PANE_ID`), el TUI se auto-reporta al panel
de agentes del multiplexor (label `bytia-kode`, estados working/idle/blocked).
Kill-switch: `BYTIA_KODE_HERDR=0`. Detalles y gotcha del parser CLI 0.8.2
(positional antes que opciones): docstring de `src/bytia_kode/herdr.py`.

## Decisiones vivas

- **Failover local-first (2026-09-15 tarde, `27934dc`)**: 5 slots — `primary(router
  :8080) → unsloth(Studio :8888) → local(ollama) → fallback(z.ai) → deepseek`.
  Locales ANTES que nube (petición del Socio). El sondeo de arranque abre circuito
  de los locales muertos (reviven solos a los 60 s, half-open); solo si NO hay
  ningún local se tira del fallback. Router vivo-dormido (sleep-idle) NO se salta:
  auto → primer preset, la 1ª petición lo despierta.
- **Estados → herdr**: `ready→idle`, `thinking/tool/skill→working`. Aún no hay
  prompt de aprobación nativo → `blocked` soportado en el mapa pero sin emisor.
- **CLI de herdr, no socket**: interfaz pública estable > protocolo interno.
- venv con `uv`; tests con pytest; estilo: docstrings/comentarios en español.

## Pendiente (próxima sesión)

- MCP (v0.8.0a1): `mcp/manager.py` lifecycle, wiring bootstrap en agent+tui,
  `McpTool.execute()` (TODO(human)), optional dep `[mcp]` en pyproject
- Dependabot: 36 vulns acumuladas en deps (`uv lock --upgrade` + suite)
- Emisor de estado `blocked` cuando exista flujo de aprobación de tools
- Sesión `--agent-session-id` en el puente herdr (hoy best-effort sin id)
- Telegram: sin activar (decisión del Socio)

## Gotchas

- `git pull` antes de trabajar: otras sesiones de Claude pueden commitear en paralelo (ha pasado).
- El parser del CLI `herdr` 0.8.2 exige `<PANE_ID>` antes que las `--opciones`.
