# HANDOFF — BytIA-KODE (B-KODE)

> Memoria transferible del repo. Leer ANTES de asumir contexto. Actualizar al cerrar sesión significativa.
> Última actualización: 2026-09-16 (hotfix failover — bugs hallados por OpenCodeReview)

## Qué es

Agente CLI propio (Python 3.11+ / Textual): agente + skills + terminal.
"Efectividad > Coste. Zero Hype. Truth > Comfort."

## Estado

- **Versión**: `0.8.0a1` (EN PROGRESO — ver CHANGELOG.md para el detalle por feature)
- **Tests**: 173/173 ✅ (`uv run pytest -q`)
- **Hotfix 2026-09-16** (`a010780`): failover vivo — pin solo en F3 (guard `_provider_sync`), router pineable de nuevo (`list_pinnable()`; F3→primary pina el router). 2 bugs HIGH hallados por OpenCodeReview revisando `ae97b37`. Detalle: `docs/devlog/2026-09-16.md`
- **Limitación conocida**: tras un failover el `preferred` queda en el motor usado — el Studio recuperado no se reintenta hasta F3 o reinicio (mejora candidata de `get_healthy`, pendiente de decisión)
- **Pendiente de decisión (UX)**: no hay vía de volver a modo AUTO desde F3 (primary ahora pina el router). Candidato: slot "Auto" en F3 con `pin(None)`. Detectado en re-review ocr
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
También ancla el id de sesión activa (`--agent-session-id`, re-ancla en /load
y /new) — herdr 0.8.2 lo acepta pero aún no lo expone (forward-compatible).
Kill-switch: `BYTIA_KODE_HERDR=0`. Detalles y gotcha del parser CLI 0.8.2
(positional antes que opciones): docstring de `src/bytia_kode/herdr.py`.

## Decisiones vivas

- **Cadena auto v3 (2026-09-15 noche, `ae97b37`)**: `unsloth(Studio bandeja) →
  local(ollama) → fallback(z.ai) → deepseek`. El ROUTER (:8080) es **BAJO DEMANDA**:
  fuera del walk de failover — no se auto-despierta nunca; solo pin manual (F3) o
  último recurso si TODO caído. El sondeo lee su catálogo (GET /v1/models no carga
  modelo) para tener el preset listo en la demanda. Evolución: v2 (`27934dc`) puso
  primary primero; el Socio migró a Studio-en-bandeja (autostart + idle-unload 300s)
  y pidió que el router no cargue solo. `active_provider` inicial = 1º de la cadena.
- **Estados → herdr**: `ready→idle`, `thinking/tool/skill→working`. Aún no hay
  prompt de aprobación nativo → `blocked` soportado en el mapa pero sin emisor.
- **CLI de herdr, no socket**: interfaz pública estable > protocolo interno.
- venv con `uv`; tests con pytest; estilo: docstrings/comentarios en español.

## Pendiente (próxima sesión)

- MCP (v0.8.0a1): `mcp/manager.py` lifecycle, wiring bootstrap en agent+tui,
  `McpTool.execute()` (TODO(human)), optional dep `[mcp]` en pyproject.
  ⚠️ **Latente**: `mcp/__init__.py` ya importa `manager.py` → con el extra
  `[mcp]` instalado, cualquier `import bytia_kode.mcp` explota (sin extra, el
  soft-guard lo esconde). La TUI no depende del paquete mcp.
- Dependabot: ✅ **36 vulns cerradas (2026-09-15, `uv lock` quirúrgico de 12
  paquetes; `mcp` pineado `>=1.28.1,<2` para evitar major 2.x sin tests)** —
  verificar que GitHub cierra las alerts tras el re-escaneo
- Emisor de estado `blocked` cuando exista flujo de aprobación de tools
- Upstream herdr: que exponga/persista sesiones self-reported (hoy las traga)

## Telegram bot (2026-09-15, servicio activado por el Socio)

- **Servicio**: `bytia-kode-telegram.service` (systemd USER, enabled — arranca al
  boot vía Linger). Activo y polleando (`api.telegram.org` ESTABLISHED, 0 restarts).
- **Invocación correcta**: `.venv/bin/python -m bytia_kode --bot` — el binario del
  venv (`bytia-kode`) apunta a `tui:run_tui` e IGNORA argv (por eso `--help` lanza
  la TUI). Un solo poller: lanzar `--bot` a mano en otra máquina/proceso da 409.
- Token + allowed_users en `~/.bytia-kode/.env` (600). PATH del unit incluye shims
  mise + `~/.local/bin` (tools del agente).

## Gotchas

- `git pull` antes de trabajar: otras sesiones de Claude pueden commitear en paralelo (ha pasado).
- El parser del CLI `herdr` 0.8.2 exige `<PANE_ID>` antes que las `--opciones`.
