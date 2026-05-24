# Session 39 — MCP Client Support (2026-05-24)

**Objetivo:** Añadir soporte MCP client a B-KODE para tools dinámicas desde servidores externos.

## Contexto

BytIA-KODE tenía 12 tools fijas harcodeadas en `ToolRegistry`. No podía conectarse a servidores MCP externos. Esto limitaba su extensibilidad frente a Claude Code, que ya consume CodeGraph, Graphify, Serena, QMD, Playwright, etc. vía MCP.

## Análisis previo

- Evaluación comparativa de **CodeGraph vs Graphify** — herramientas complementarias, no competidoras. CodeGraph para navegación en tiempo real (AST puro), Graphify para descubrimiento de conocimiento (AST + semántica + visualización).
- Verificación de que el tool dispatch chain es 100% async (`Tool.execute()`, `ToolRegistry.execute()`, `Agent._handle_tool_calls()`).

## Revisión de diseño con segunda opinión (Gemini)

Se solicitó feedback externo al plan original. De 6 puntos sugeridos:

| Punto | Decisión | Razón |
|-------|----------|-------|
| AsyncExitStack | Aceptado | Crítico — SDK MCP usa async context managers |
| Lazy init race condition | UX aceptado, diagnóstico rechazado | `await` es secuencial, pero mejor UX en bootstrap |
| Zombis / SPOF | Diferido a v2 | AsyncExitStack + close() suficiente para v1 |
| JSON Schema strict mode | Descartado | No aplica a nuestros providers (llama.cpp, Z.ai, Ollama) |
| Impedancia sync/async | Descartado | Ya es async — no verificaron el código |
| Entorno restrictivo | Aceptado | Heredar parent env + overrides (necesario para WSL2) |

## Progreso

### Completado

1. **`mcp/config.py`** — `McpServerConfig` dataclass + `load_mcp_config()` desde `~/.bytia-kode/mcp_servers.json`
2. **`mcp/__init__.py`** — Public API + soft-import guard (stub sin SDK)
3. **`mcp/client.py`** — `McpClient`: stdio transport + `AsyncExitStack` + handshake + `tools/list` + `tools/call`
4. **`mcp/tool.py`** — `McpTool` skeleton con `TODO(human)` para `execute()`
5. **`pyproject.toml`** — versión bump a `0.8.0a1` + `[mcp]` optional dependency
6. **Documentación** — CLAUDE.md, ROADMAP.md, CHANGELOG.md actualizados

### Pendiente (próxima sesión)

7. **`mcp/manager.py`** — `McpManager`: lifecycle (`start_all`, `stop_all`, `restart_server`), registry integration
8. **`agent.py` wiring** — `McpManager` en `__init__`, `mcp_start()` desde bootstrap, `stop_all()` en `close()`
9. **`tui.py` wiring** — Llamar `agent.mcp_start()` en `on_mount()`, status en banner
10. **`McpTool.execute()`** — implementación del puente (reservado para contribución del usuario)
11. **Tests** — `test_mcp_config.py`, `test_mcp_tool.py`

## Decisiones de arquitectura

- **Adapter Pattern**: MCP tools extienden `Tool`, se registran en `ToolRegistry`. Zero cambios en dispatch.
- **AsyncExitStack**: Los context managers del SDK MCP se mantienen vivos durante toda la sesión.
- **Entorno heredado + overrides**: Child processes heredan `os.environ` completo + config overrides.
- **Soft dependency**: `mcp` SDK como `[mcp]` optional. Sin él, B-KODE funciona con solo tools nativas.
- **Tool naming**: `mcp__{server}__{tool}` — evita colisiones, sigue convención de Claude Code.

## Lecciones aprendidas

- Siempre verificar claims de reviews externos contra el código real. 2 de 6 puntos de Gemini eran incorrectos (no leyeron el código).
- `AsyncExitStack` es esencial para cualquier integración con async context managers de larga duración.
- El sandbox de BashTool puede bloquear comandos que parecen inocentes (`stat`, `ls` en ciertos paths). No confiar en Bash para exploración de filesystem.

## Archivos modificados

- `src/bytia_kode/mcp/config.py` (nuevo)
- `src/bytia_kode/mcp/__init__.py` (nuevo)
- `src/bytia_kode/mcp/client.py` (nuevo)
- `src/bytia_kode/mcp/tool.py` (nuevo, con TODO(human))
- `pyproject.toml` (versión + optional dep)
- `CLAUDE.md` (arquitectura + versión)
- `ROADMAP.md` (v0.8.0 MCP section)
- `CHANGELOG.md` (v0.8.0a entry)
