# BytIA KODE - Development Log

## 2026-04-01 - Sesión 1: Nacimiento

### Contexto

BytIA KODE nace como un agente de código autónomo con arquitectura agéntica: tools, skills, loop de iteración y memoria persistente. Inspirado en la idea de tener un asistente de código personal con identidad constitucional propia.

### Arquitectura base implementada

```text
src/bytia_kode/
├── config.py
├── agent.py
├── tui.py
├── cli.py
├── providers/
│   ├── client.py
│   └── manager.py
├── tools/
│   └── registry.py
├── skills/
│   └── loader.py
├── memory/
│   └── store.py
└── telegram/
    └── bot.py
```

### Verificación

- Tests unitarios iniciales: 4/4 passing
- Compilación limpia con `compileall`

---

## 2026-04-02 - Sesión 2: Hardening + UX + Documentación

### Fixes técnicos

1. `file_write` soporta rutas relativas sin romper
2. Cliente provider robustecido ante respuestas parciales/malformadas
3. `chat(stream=True)` falla explícitamente con mensaje claro para usar `chat_stream()`
4. Loop del agente tolera tool-calls incompletas
5. Bot de Telegram con guardas defensivas en handlers

### Fix crítico TUI

- Error: `NoMatches: No nodes match '#input-field' on Screen(id='_default')`
- Causa: faltaba `compose()` en `BytIAKODEApp`
- Solución: restaurar `compose()` con la estructura completa de widgets

### Verificación

- `uv run pytest -q` → 6 passed

---

## 2026-04-02 - Sesiones 3-6: Auditoría y Hardening (4 fases)

### Fase 1: Seguridad crítica

- SEC-001: BashTool con allowlist + `shell=False` + `shlex.split()`
- SEC-002/003: Path traversal bloqueado con `_resolve_workspace_path()`
- SEC-005: Telegram fail-secure por defecto
- Resultado: 11 tests passing

### Fase 2: Estabilidad

- Async I/O: `asyncio.create_subprocess_exec` + `asyncio.to_thread`
- Error recovery con excepciones específicas
- Input sanitizado
- Resultado: 14 tests passing

### Fase 3: Producción

- Memory con carga estricta y contexto acotado (20 entries / 2000 chars)
- Telegram oculta errores internos al usuario
- Pre-commit hook con secret scan
- Resultado: 17 tests passing

### Fase 4: Cierre

- Refactor: `_handle_tool_calls()` extraído del agente
- Benchmark: 4.90x speedup secuencial vs concurrente
- Documentación: CHANGELOG, auditoría, history.json

### Verificación final

- `uv run pytest -v` → 17 passed in 0.30s
- Pre-commit hook: metadata OK + secret scan OK + pytest OK
- Repo publicado en GitHub: https://github.com/asturwebs/BytIA-KODE

---

## 2026-04-03 - Sesión 7: UX Avanzada + Skills System

### Temas y provider switching

- Banner ASCII actualizado a "B KODE" con colores dinámicos por tema.
- 3 temas claros añadidos (catppuccin-latte, solarized-light, rose-pine-dawn). Total: 9 temas.
- `F2` cambia tema cíclicamente con persistencia en `~/.bytia-kode/theme.json`.
- Bordes de mensajes de chat reactivos al cambio de tema (on_mount + watch pattern).
- `F3` para switching entre providers (primary → fallback → local).
- `/models` lista modelos del provider activo (Ollama `/api/tags` + `/v1/models` fallback).
- `/use <model>` selecciona modelo en runtime.

### Paper analysis

- Análisis de "Terminal Agents Suffice for Enterprise Automation" (arXiv:2604.00073).
- Hallazgos clave: skills persistentes +5.8pp success rate, -43.7% coste.
- Exploración del sistema de skills de Hermes Agent CLI instalado en WSL2.

### Skills System (v0.3.1)

- `AppConfig.skills_dir` → `~/.bytia-kode/skills/` (auto-creado).
- `SkillLoader`: `save_skill()`, `list_skill_names()`, `get_skill()`, `verify_skill()`.
- `get_relevant()` con scoring (trigger +3, description +2, content +1).
- Campo `verified` parseado del frontmatter YAML.
- Comandos TUI: `/skills save` (multiline capture), `/skills show`, `/skills verify`.
- Skill `skill-creator` creada como meta-skill de bootstrap.
- Formato SKILL.md compatible agentskills.io.

### Verificación

- 17 tests pasando.
- Tool instalado y verificado.

---

## 2026-04-03 - Sesión 8: Streaming, Reasoning, Context Management, TUI v4

### Streaming real

- `ProviderClient.chat_stream()` reescrito para consumir SSE y yield tuples:
  - `("text", delta)` — texto visible
  - `("reasoning", delta)` — razonamiento (DeepSeek `reasoning_content`, Gemma 4 `reasoning`)
  - `("tool_calls", [ToolCall])` — tool calls acumuladas por índice SSE
- Tool calls se acumulan incrementalmente (deltas con `index` en SSE).
- La TUI renderiza con streaming: plain `Static` durante streaming, `ChatMessage` formateado al finalizar.

### Reasoning / Thinking

- `ThinkingBlock(Static)` — widget colapsable con `can_focus = True`.
- Click o Enter para toggle expandir/colapsar.
- Se monta al recibir el primer chunk de reasoning y se actualiza con `append()` en cada delta.
- Soporta múltiples ThinkingBlock en la conversación, cada uno toggleable independientemente.
- Formato: preview de 3000 chars expandido, "N lines of reasoning" colapsado.

### B-KODE.md

- Fichero de instrucciones a nivel proyecto (como CLAUDE.md/HERMES.md).
- Búsqueda walk-up desde CWD hasta filesystem root (`candidate == candidate.parent`).
- Inyectado en system prompt: identidad → B-KODE.md → skills → memoria.
- Status mostrado en info line del chat.

### Context window management

- `MAX_CONTEXT_TOKENS = 16384`.
- `_estimate_tokens()`: heurística chars/3 (incluye system prompt).
- `_manage_context()`: comprime los 2 mensajes más antiguos en resumen cuando se supera 75% del límite.
- `ActivityIndicator` muestra `ctx Xk/Yk` en tiempo real.

### TUI v4 refactor

- **ActivityIndicator** — Nueva barra de estado encima del input. Muestra: estado, provider, modelo, contexto.
- **CommandMenuScreen** — Popup con Ctrl+P. `ListView` con 11 comandos seleccionables.
- **`COMMAND_PALETTE_BINDING = ""`** — Deshabilita paleta built-in de Textual.
- **Session Info movida** — De panel en chat area a ActivityIndicator. Info line simplificada (solo B-KODE status + versión).
- **Footer simplificado** — Solo `Menu (Ctrl+P)` visible. Resto de bindings con `show=False`.

### Config actualizada

- Primary: `glm-4.7-flash` en `localhost:8081/v1` (llama.cpp)
- Fallback: `glm-5-turbo` en `api.z.ai` (Z.AI cloud API)
- Local: `gemma4:26b` en `localhost:11434/v1` (Ollama)

### Bugs fixed

1. `COMMAND_PALETTE_BINDING = None` → `NoneType.rpartition()` crash → Fix: `""`
2. CommandMenuScreen vacía (ListView en VerticalScroll colapsaba) → Fix: ListView directo
3. ActivityIndicator no visible (`dock: bottom` conflicto) → Fix: remover dock
4. ThinkingBlock._render() conflicto con Textual → Fix: renombrar a `_update_display()`
5. Errores de provider persistidos en historial → cascada de 400 Bad Request → Fix: no persistir
6. `watch_theme` con variable `c` no definida → Fix: eliminar código duplicado
7. `agent._max_context_tokens` no existía → Fix: atributo en `__init__`

### Verificación

- 17 tests pasando.
- Tool reinstalada: `bytia-kode==0.3.0`.
- Documentación actualizada: ARCHITECTURE.md, TUI.md, CHANGELOG.md, DEVLOG.md.

---

## 2026-04-03 - Sesión 9: Limpieza de peso muerto

### Depuración de dependencias

Auditoría completa del codebase para identificar código/peso muerto:

| Item | Estado | Acción |
| --- | --- | --- |
| `python-docx` | Declarado, nunca importado | Eliminado (~2MB) |
| `beautifulsoup4` | Declarado, nunca importado | Eliminado (~500KB) |
| `prompt-toolkit` | Solo usado por `cli.py` (REPL inalcanzable) | Eliminado (~1MB) |
| `cli.py` | REPL simple, nunca accesible desde entry point | Eliminado |
| `memory/store.py` | `add()` nunca se llama → `get_context()` siempre vacío | Eliminado |
| 2 tests de memoria | Testean módulo eliminado | Eliminados |
| `__main__.py` | `--simple` flag ya no tiene destino | Simplificado |

### Resultado

- Dependencias: 9 → 6 (eliminadas 3)
- Tests: 17 → 15
- Archivos fuente: -2 (cli.py, memory/store.py)
- Install size reducido ~3.5MB

### Verificación

- 15 tests pasando.
- Tool reinstalada: `bytia-kode==0.4.0`.

---

## 2026-04-03 - Sesión 10: Consolidación Router + Gemma 4 + Cleanup

### Consolidación llama.cpp a router single-port

6 servicios individuales (puertos 8080-8085) consolidados en un solo router:
- `bytia-router.service` (systemd) — `llama-server --models-dir ... --models-max 1 --models-autoload`
- Un solo puerto `:8080`, un modelo en VRAM a la vez, carga/descarga via API
- 7 modelos disponibles (141GB total): GLM-4.7 Flash, GLM-4.7 Distill, Gemma 4 26B, Hermes 4.3 36B, Nemotron Cascade 30B (Q5+Q8), Qwen 3.5 27B

### llama.cpp rebuild v417

- Build anterior (v330) no soportaba arquitectura Gemma 4 (`unknown model architecture: 'gemma4'`)
- Rebuild desde source: `cmake -B build -DLLAMA_CUDA=ON -DCMAKE_BUILD_TYPE=Release` → ggml v0.9.11, versión 417
- Gemma 4 26B-A4B-it (Q4_K_M, 15.6GB) cargado OK: 23.6GB/24.5GB VRAM

### B-KODE adaptado al paradigma router

- `PROVIDER_BASE_URL` → `http://localhost:8080/v1` (router, antes :8081 individual)
- `PROVIDER_MODEL` → `auto` (detección dinámica del modelo cargado)
- `ProviderClient.detect_loaded_model()` — consulta `/v1/models`, filtra `status: loaded`
- `ProviderManager.auto_detect_model()` — se ejecuta al montar TUI y al cambiar provider
- `_auto_detect_model()` worker en TUI — async, exclusive, con fallback silencioso
- Bug fix: `@work(exclusive=True)` + `run_worker(exclusive=True)` = doble decoración → crash. Fix: solo `run_worker` con `async def` sin decorador

### Infra cleanup

- `.zshrc`: eliminadas 5 funciones `claude-*` (qwopus, hermes, nemotron, etc.), 6 aliases `llama-*` individuales, 12 aliases de servicios systemd, sección AgentZero Docker. Añadidos `routeron/off/status/logs/ui/slots`
- `~/.bytia-banner`: simplificado a Router:8080 con modelo activo detectado via API (solo si `status: loaded`). Sin `sudo` (no pide password)
- `~/.bytia-kode/.env`: puerto actualizado, modelo auto

### Verificación

- 15 tests pasando.
- TUI funcional: auto-detect Gemma 4, reasoning OK, tildes OK.
- 133 t/s generación Gemma 4 (MoE: 26B total, 4B activos).

---

## 2026-04-03 - Sesión 10b: Bot Telegram → Router + Guard sin modelo

### Bot migra de Ollama a router

- `bot.py`: `provider="local"` (Ollama, CPU, ~15 t/s) → `provider="primary"` (router, GPU, ~133 t/s)
- Motivo: Ollama en CPU puro = 9x más lento que llama.cpp en GPU
- Lazy init: `auto_detect_model()` se ejecuta en el primer mensaje (no en `__init__`)
- `_initialized` flag en Agent para ejecutar auto-detect una sola vez

### Guard: sin modelo cargado

- `auto_detect_model()` devuelve `bool` (True si detectó, False si no)
- Si no hay modelo en VRAM, el agente yield mensaje claro: *"No hay ningún modelo cargado en el router"* en vez de fallar con 400

### Bug fix

- `@work(exclusive=True)` + `run_worker(exclusive=True)` = doble decoración → WorkerError. Fix: async def sin `@work`, solo `run_worker(exclusive=True)`

### Verificación

- 15 tests pasando.
- Bot Telegram respondiendo vía router GPU (~133 t/s).

---

## 2026-04-04 - Sesión 11: Router Polling, ToolBlock, Auto-conocimiento

### Router polling en StatusBar

- `ActivityIndicator` consulta `/v1/models` cada 5s vía `set_interval`.
- `_poll_router_info()` ejecutado inmediatamente en `on_mount` + polling recurrente.
- Si el modelo cambia en la WebUI (slot swap), nombre y ctx-size se actualizan automáticamente.

### ctx-size dinámico desde API

- `get_router_info()` en `ProviderClient`: consulta `/v1/models` para modelo + ctx-size desde args (`--ctx-size`), y `/metrics` para tokens.
- `set_router_info()` en ActivityIndicator: actualiza modelo, ctx capacity y uso estimado.
- Uso de sesión: `agent._estimate_tokens()` (chars/3) con prefijo `~`. Ya no métricas cumulativas del servidor.

### ToolBlock widget

- Widget colapsable para ejecución de tools (similar a ThinkingBlock pero con icono 🔧).
- Muestra nombre de la tool y su output. Click para expandir/colapsar.
- Se monta en el chat area cuando una tool termina de ejecutarse.

### Tool execution indicators

- ActivityIndicator cambia a `⚙ tool:<name>` durante tool calls.
- 500ms delay antes de volver a `◐ Thinking...` para que el usuario vea el indicador.

### Agent callbacks

- `on_tool_call: list` y `on_tool_done: list` en `Agent.__init__`.
- Callbacks se disparan en `_handle_tool_calls()`: antes y después de ejecutar la tool.
- La TUI registra callbacks en `on_mount` para reaccionar en tiempo real.

### core_identity runtime section

- Añadida sección `runtime` bajo `identity` en `core_identity.yaml`.
- Contiene: interfaz, proyecto, motor, capacidades, comandos.
- El agente ahora tiene auto-conocimiento de sus propias capacidades.

### Config fix

- `PROVIDER_MODEL` default cambiado de `"glm-4.7-flash"` a `"auto"` (coherente con router support).

### Documentación

- CHANGELOG: sección `[Unreleased]` con 7 additions + 2 changed.
- README: Skills vision (tools dinámicas, sub-agentes), fix duplicados, PROVIDER_MODEL → auto.
- ROADMAP: v0.4.0 completado, items pendientes movidos a v0.4.1.
- ARCHITECTURE: ToolBlock, polling, get_router_info, Skills evolución, fix carácter raro.
- TUI.md: ToolBlock section, polling router, estados actualizados.

### Verificación

- 15 tests pasando.
- Pre-commit hook: metadata OK + secret scan OK + pytest OK.
- Commit `c361f1c` push a GitHub.

---

## 2026-04-06 - Sesión 12: Sesiones Persistentes (SQLite WAL)

### Objetivo

Implementar persistencia de sesiones en tiempo real para BytIA-KODE:
1. Las sesiones se guardan automáticamente (no se pierden al reiniciar)
2. TUI y Telegram pueden acceder a las sesiones entre sí
3. El modelo puede acceder a sesiones pasadas cuando se le indica

### Diseño

Revisión de alternativas (JSON + file locking vs SQLite WAL) por BytIA Gemini (Socia) y Gemma 4B:

| Criterio | JSON + File Locking | SQLite WAL |
|----------|---------------------|------------|
| Concurrencia | ❌ Bloqueante | ✅ Múltiples lectores + 1 escritor |
| I/O por mensaje | ❌ O(N) - reescribe todo | ✅ O(1) - solo INSERT |
| Durabilidad | ⚠️ Requiere fsync manual | ✅ ACID nativo |
| Búsqueda | ❌ Parsear archivos | ✅ Índices SQL |
| Complejidad | ❌ Alta (locks, retries) | ✅ Baja (sqlite3 nativo) |

**Veredicto:** SQLite WAL — sin race conditions, I/O O(1), transacciones ACID, código simple.

### Implementación

**`session.py` (nuevo)** — SessionStore con SQLite WAL:
- `SessionMetadata` dataclass con `__slots__` para metadata ligera
- `SessionStore` con connection-per-method (no thread sharing)
- `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON`
- Append-only INSERT para O(1) por mensaje
- Atomic INSERT + UPDATE metadata en transacción
- Safe JSON parse para tool_calls con try/except
- Índices: `idx_sessions_source`, `idx_sessions_updated`, `idx_sessions_source_ref`, `idx_messages_session`

**`agent.py` (modificado)**:
- `__init__` acepta `session_store: SessionStore | None`
- Auto-save en `chat()`: append user + assistant después de cada intercambio
- Auto-save en `_handle_tool_calls()`: append tool results
- Auto-title: `update_title()` desde primer mensaje del usuario (truncado a 80 chars)
- Session tools registradas automáticamente: `session_list`, `session_load`, `session_search`
- `MAX_CONTEXT_TOKENS` subido de 16k a 128k (para modelos GGUF con 256k)
- Métodos: `set_session()`, `load_session_by_id()`, `save_current_session()`, `list_sessions()`, `get_session_context()`, `_load_messages_from_store()`

**`telegram/bot.py` (reescrito)**:
- **FIX CRÍTICO:** `_agents: dict[str, Agent]` — antes compartía un solo Agent entre todos los usuarios (violación de privacidad)
- `session_store = SessionStore(config.data_dir / "sessions.db")` compartido entre todos los agentes
- `_get_agent(chat_id)` crea o recupera sesión por chat_id
- Comando `/sessions` para listar sesiones del usuario
- Bug fix: `config` → `self.config` en `_get_agent()` (líneas 30, 34)

**`tui.py` (modificado)**:
- `on_mount`: sesión auto-creada con `agent.set_session(source="tui")`
- `/sessions` — tabla con ID, source, título, msgs, fecha
- `/load <id>` — cargar sesión por ID
- `/new` — nueva sesión con auto-save
- Tabla de ayuda actualizada con los 3 comandos nuevos

**`tools/session.py` (nuevo)** — 3 tools para el modelo:
- `SessionListTool` — listar sesiones (filtro source opcional)
- `SessionLoadTool` — cargar contexto de sesión pasada
- `SessionSearchTool` — buscar sesiones por título

**`tests/test_session.py` (nuevo)** — 19 tests:
- TestSessionLifecycle: create, create with ref, metadata not found
- TestMessageOperations: append/load, message count, tool_calls JSON, tool result, seq_num ordering
- TestListAndSearch: list all, list by source, search by title, limit
- TestDelete: delete session, delete nonexistent
- TestTitle: update, truncate to 80 chars, no overwrite existing
- TestGetContext: formatted context, not found

### Bugs encontrados y corregidos

1. **SQLite INSERT** — `create_session()` tenía 4 columnas pero solo 3 placeholders. `OperationalError: 3 values for 4 columns`.
2. **Telegram NameError** — `config` usado en vez de `self.config` en `_get_agent()` (líneas 30, 34 de bot.py).

### Verificación

- 46 tests pasando (19 session + 14 file_edit + 13 context_management).
- Pre-commit hook: metadata OK + secret scan OK + pytest OK.
- Documentación actualizada: CHANGELOG, README, ROADMAP, ARCHITECTURE, TUI, DEVELOPMENT, CONTEXT, DEVLOG.

---

## 2026-04-06 - Sesión 13: Session Awareness + Prompt Enhancement

### Problema detectado

El agente (ejecutándose sobre Gemma 4 26B) declaró que NO tenía acceso autónomo a las sesiones guardadas. Las session tools (`session_list`, `session_load`, `session_search`) estaban registradas en el código y enviadas al LLM, pero el modelo no las usaba por:

1. **El system prompt no mencionaba las session tools** en su lista de capacidades
2. **La directiva "Usar herramientas solo cuando sean verificación"** inhibía el uso proactivo
3. **No había instrucción conductual** sobre cuándo usar session tools
4. **No se inyectaba contexto de sesiones anteriores** al arrancar

### Cambios implementados

**`core_identity.yaml`:**
- Session tools añadidas a `runtime.capacidades`: `session_list`, `session_search`, `session_load`
- Comandos `/sessions`, `/load <id>`, `/new` añadidos a `runtime.comandos`
- Directiva de tools reemplazada: de "solo verificación" a "proactivamente cuando aporten valor"
- Nuevas directivas: usar `session_search` cuando el usuario pregunte sobre trabajo anterior, revisar resumen de sesión anterior inyectado

**`agent.py` — `_get_previous_session_summary()`:**
- Método nuevo que obtiene la última sesión del mismo source (TUI o Telegram)
- Genera resumen compacto: título, fecha, nº mensajes, últimos 3 mensajes truncados
- Se inyecta automáticamente en `_build_system_prompt()` si hay sesión anterior
- Diseño determinista (sin llamada al LLM) — el modelo decide si necesita más contexto vía `session_load`

### Tests

5 nuevos tests en `TestPreviousSessionSummary`:
- Sin sesiones previas → empty string
- Con sesión anterior → resumen con título, ID, mensajes
- Exclusión de sesión actual
- Filtro por source (TUI vs Telegram)
- Límite de 3 mensajes (no muestra más)

### Verificación

- 66 tests pasando (24 session + 14 file_edit + 13 context_management + 15 basics).
- Versión: 0.5.0 → 0.5.1.
- SP identity: v12.0.0 → v12.1.0.

---

## 2026-04-07 - Sesión 14: Infraestructura de Debug, Bugs y Multi-Workspace Context

### Logging a archivo

B-KODE tenía `logging.getLogger(__name__)` en 8 módulos pero **sin configuración de output** — los logs iban a stderr, que Textual tragaba. Sin archivo de log, imposible debug a posteriori.

- `__main__.py`: configuración de logging con `RotatingFileHandler`
  - Ubicación: `~/.bytia-kode/logs/bytia-kode.log`
  - Rotación: 1MB por archivo, 3 backups
  - Formato: `14:23:05 ERROR  [bytia_kode.agent] mensaje`
  - Nivel: `LOG_LEVEL` en `.env` (default: `INFO`)
  - Custom path: `LOG_FILE` en `.env`
- `config.py`: añadido campo `log_file` a `AppConfig`
- `.env.example`: añadido `LOG_FILE=`

### Bug: Provider errors no mostrados al usuario

**Issue:** asturwebs/BytIA-KODE#2

Cuando el LLM devuelve un error (400 Bad Request) durante o después de reasoning, el usuario no recibe feedback. El error se yield como string plano, se renderiza como texto del asistente, y en algunos casos no se muestra en absoluto.

**Root cause doble:**
1. `agent.py:370-373` — errores yield como string, no como tipo diferenciado
2. `agent.py:341-345` — tras un error, el mensaje del asistente nunca se append a `self.messages`, dejando la conversación en estado roto. Los mensajes siguientes fallan con el mismo 400 en loop hasta `/reset`

**Fix pendiente (issue #2):**
- Yield errores como `("error", str)` en vez de string plano
- Appendear error como mensaje del asistente en `self.messages` para mantener historial balanceado
- TUI/Telegram: manejar `("error", ...)` con estilo diferenciado

### Feature: Panic Buttons (diseño)

**Issue:** asturwebs/BytIA-KODE#1

Diseño de dos niveles de cancelación para el agente:

| Nivel | TUI | Telegram | Comportamiento |
|-------|-----|----------|----------------|
| Interrupt | `Escape` | `/stop` | Para generación/tool actual |
| Kill | `Ctrl+K` | `/kill` | Cancela + reset + cleanup |

Añadido al ROADMAP v0.5.2. Implementación pendiente.

### Feature: Multi-Workspace CONTEXT.md

**Problema:** CONTEXT.md solo existía en el repo de B-KODE, trackeado en git con datos locales del usuario. Si B-KODE se ejecuta en otro proyecto, no tiene contexto operativo de ese workspace.

**Solución:** Sistema de CONTEXT.md auto-generado por workspace:

- `src/bytia_kode/context.py` (nuevo) — detección de workspace:
  - Lenguaje (pyproject.toml, package.json, Cargo.toml, go.mod)
  - Estructura (directorio top-level)
  - Git (branch, últimos 3 commits)
  - B-KODE.md (búsqueda walk-up)
- Storage: `~/.bytia-kode/contexts/<sha256[:8]>.md` (hash determinista del path)
- `read_context` tool — el agente lee contexto bajo demanda (no auto-inyectado)
- `/context` command — regeneración forzada (TUI + Telegram)
- B-KODE.md nudge: "usa la tool `read_context`"
- CONTEXT.md eliminado del tracking git, añadido a `.gitignore`

**Design spec:** `docs/superpowers/specs/2026-04-07-multi-workspace-context-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-07-multi-workspace-context.md`

### Documentación actualizada

- ROADMAP.md: v0.5.2 reestructurada (Panic Buttons + Tests TUI)
- B-KODE.md: sección Logging, sección Context
- CONTEXT.md: sección Logging
- `.env.example`: `LOG_FILE=`
- `.gitignore`: `CONTEXT.md`

## 2026-04-07 - Sesión 15: Debug, fixes y copiado

### Contexto

Sesión de validación y corrección post-v0.5.2. Verificación de todas las features implementadas, corrección de bugs encontrados durante testing, y mejora de UX (copiado de respuestas).

### Issues resueltos

- **CI failure** — Tests que mockean el provider fallaban porque `auto_detect_model()` se ejecutaba antes y cortaba con "No hay ningún modelo". Fix: `agent._initialized = True` en tests para saltar la detección.
- **Logging no se creaba** — `_setup_logging()` estaba en `__main__.py` pero el entry point de `uv tool` (`bytia_kode.tui:run_tui`) lo saltaba. Movido a `__init__.py` (se ejecuta en cualquier punto de entrada).
- **Versión desincronizada** — `pyproject.toml` decía `0.5.1`, `B-KODE.md` decía `0.5.2-dev`. Sincronizado a `0.5.2`.

### Nuevas features

- **Copy last response (`Ctrl+Shift+C`)** — Copia la respuesta completa del último mensaje del agente al portapapeles del sistema.
- **Banner actualizado** — Muestra comandos disponibles en el inicio.
- **Modo editable** — `uv tool install --editable .` para desarrollo: cambios se reflejan sin reinstalar.

### Commits

- `fix: move logging setup to __init__.py so all entry points get logs`
- `fix: skip auto_detect_model in tests that mock the provider`
- `feat: update banner with available commands reference`
- `feat: add copy last full response (Ctrl+Shift+C)`

### Documentación actualizada

- CHANGELOG.md: sección [0.5.2] completa
- README.md: versión 0.5.2, Ctrl+Shift+C en atajos, copiar respuestas en novedades
- DEVLOG.md: esta entrada
