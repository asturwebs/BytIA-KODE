# Roadmap - BytIA KODE

## Estado actual: v0.6.0 (Alpha estable)

### Completado

**v0.1.0 — Fundamentos**
- [x] Arquitectura agéntica con loop think → act → observe
- [x] TUI (Textual) + CLI simple + Bot Telegram
- [x] Identidad constitucional en YAML empaquetado
- [x] Multi-provider OpenAI-compatible (primary, fallback, local)
- [x] Tools: bash (allowlist), file_read, file_write
- [x] Seguridad: command injection mitigado, path traversal bloqueado, fail-secure

**v0.2.0 — Hardening**
- [x] Async I/O: subprocess y disco no bloquean el event loop
- [x] Benchmark: 4.90x speedup concurrente vs secuencial
- [x] 17 tests con pre-commit hook (validación + secret scan + pytest)
- [x] Auditoría profesional completa

**v0.3.0 — UX y build**
- [x] 9 temas con F2 cíclico y persistencia
- [x] Banner "B KODE" con colores dinámicos por tema
- [x] Bordes de chat reactivos al tema activo
- [x] Provider switching con F3 (primary → fallback → local)
- [x] `/models` lista modelos del provider activo
- [x] `/use <model>` selecciona modelo en runtime
- [x] Workflow CI/CD con GitHub Actions
- [x] Scripts de validación y secret scan

**v0.3.1 — Skills System**
- [x] Directorio `~/.bytia-kode/skills/` con auto-creación
- [x] SKILL.md con frontmatter YAML (agentskills.io compatible)
- [x] Comandos: `/skills`, `/skills save`, `/skills show`, `/skills verify`
- [x] Búsqueda por relevance (trigger keywords + description + content scoring)
- [x] Skill `skill-creator` incluida (meta-skill de bootstrap)
- [x] Progressive disclosure: metadata en lista, contenido bajo demanda

**v0.4.0 — Router, Streaming y TUI Avanzada**
- [x] Streaming token a token en la TUI (deltas SSE en tiempo real)
- [x] Reasoning/Thinking con ThinkingBlock colapsable
- [x] B-KODE.md: instrucciones de proyecto por directorio
- [x] Context window management (chars/3, compresión al 75%)
- [x] llama.cpp Router support (single port, multi-modelo, auto-detect)
- [x] Bot Telegram usa router (GPU, ~133 t/s)
- [x] Guard si no hay modelo cargado
- [x] Router polling en StatusBar (cada 5s, detecta swaps)
- [x] ctx-size dinámico desde router API
- [x] ToolBlock widget (ejecución de tools colapsable)
- [x] Agent callbacks (on_tool_call / on_tool_done)
- [x] core_identity runtime section (auto-conocimiento del agente)
- [x] RFC-001: BytIA OS Kernel + Runtime migration (v12.3.0 kernel, v1.0.0 runtime)
- [x] Limpieza de peso muerto (3 deps, cli.py, memory/store.py)
- [x] 15 tests pasando con pre-commit hook

**v0.4.1 — Herramientas y estabilidad**
- [x] `file_edit` tool — search/replace + create con backup automático, diff unificado y diagnósticos (_no_match_help) (BytIA OpenClaw)
- [x] Context management con summarization por modelo (threshold dinámico por ctx_size, fallback a truncación) (BytIA Claude Code)
- [x] Token estimation unificado — `Agent.estimate_tokens()` como single source of truth (chars/3) (BytIA Claude Code)
- [x] ToolBlock color coding — rojo ❌ si error, verde ✅ si ok (BytIA Claude Code)
- [x] Router polling: logging en `_poll_router_info` con alertas progresivas (BytIA Claude Code)
- [x] 27 tests pasando (14 file_edit + 13 context_management)

**v0.5.0 — Sesiones Persistentes**
- [x] SessionStore con SQLite WAL (create, append, load, list, search, delete, context)
- [x] Auto-save en tiempo real en `Agent.chat()` y `_handle_tool_calls()`
- [x] Session tools para el modelo: `session_list`, `session_load`, `session_search`
- [x] Comandos TUI: `/sessions`, `/load <id>`, `/new`
- [x] Sesión auto-creada al arrancar TUI
- [x] **FIX CRÍTICO Telegram**: aislamiento por chat_id (antes compartía historial entre todos los usuarios)
- [x] Comando `/sessions` en Telegram
- [x] `MAX_CONTEXT_TOKENS` subido a 128k (para modelos GGUF con 256k context)
- [x] 46 tests pasando (19 session + 14 file_edit + 13 context_management)

---

**v0.5.1 — Session Awareness y UX**
- [x] Session tools añadidas a capacidades del prompt (session_list, session_search, session_load)
- [x] Directiva de tools proactivas (reemplaza "solo verificación")
- [x] Directivas conductuales para uso autónomo de session tools
- [x] Auto-resumen de sesión anterior inyectado en system prompt (título, fecha, 3 mensajes)
- [x] Menú Ctrl+P expandido: 11 → 17 items (sessions, model select, history, reasoning)
- [x] InputScreen modal para prompts de texto (session ID, model name)
- [x] 66 tests pasando (24 session + 14 file_edit + 13 context_management + 15 basics)

---

## v0.5.3 — TTS, Debug y Estabilidad

- [x] **TTS (Text-to-Speech)** — edge-tts + mpv, botón 🔊/⏹ en respuestas del asistente, toggle play/stop
- [x] **Logging HTTP en provider** — errores 400/500 loggeados antes de raise_for_status (chat + chat_stream)
- [x] **Voz mexicana** — `es-MX-DaliaNeural` (femenina, friendly)
- [x] **Limpieza TTS** — elimina código, Markdown, URLs, emojis; preserva tildes y puntuación española

---

## v0.5.4 — Memoria Persistente, Trusted Paths y Sandbox Expandida

- [x] **Sistema de memoria persistente** — `~/.bytia-kode/memoria/` con 4 categorías + index.md
- [x] **Skill `memory-manager`** — store, search, index, read procedimientos
- [x] **Trusted paths en sandbox** — `_resolve_workspace_path()` acepta directorios confiados (`data_dir`)
- [x] **Allowlist expandida** — 27 binarios (antes 13): mv, cp, rm, curl, wget, scp, ssh, pip...
- [x] **EXTRA_BINARIES configurable** — `.env` expande allowlist sin modificar código
- [x] **Skill `graphify`** — knowledge graphs de código (tree-sitter)
- [x] **5 tests nuevos** — trusted paths (2), skill load (1), extra binaries (2) — 82 total

---

## v0.5.2 — Botón del Pánico, Context Multi-Workspace y Tests de TUI

**Objetivo:** Cancelación/interrupción del agente, contexto por workspace y tests de integración TUI.

### Logging a archivo

- [x] **RotatingFileHandler** — `~/.bytia-kode/logs/bytia-kode.log` (1MB, 3 backups)
- [x] **LOG_LEVEL** en `.env` (default: INFO)
- [x] **LOG_FILE** en `.env` para custom path
- [x] 8 módulos con logging estructurado

### Multi-Workspace Context

- [x] **`context.py`** — detección automática de workspace (lenguaje, git, estructura, B-KODE.md)
- [x] **`read_context` tool** — lectura bajo demanda del contexto del workspace
- [x] **`/context` command** — regeneración forzada (TUI + Telegram)
- [x] **Storage** — `~/.bytia-kode/contexts/<sha256[:8]>.md` (hash determinista del path)
- [x] **CONTEXT.md** — eliminado del tracking git, ahora local-only
- [x] **B-KODE.md nudge** — instrucción para usar `read_context`

### Panic Buttons (Interrupt + Kill)

- [x] **Interrupt** — Para generación/tool actual, agente sigue vivo
  - TUI: `Escape` (estándar: Claude Code, VS Code)
  - Telegram: `/stop`
  - Implementado: `threading.Event` en Agent, cancelación en stream loop y pre-tool
- [x] **Kill** — Nuclear: cancela procesamiento + kill subprocess + cleanup widgets
  - TUI: `Ctrl+K`
  - Telegram: `/kill`
  - Implementado: `Agent.kill()` con terminate/kill del subprocess activo
- [x] Guard de Telegram: no apilar mensajes mientras se procesa (`_processing` set)
- [ ] `AgentCancelledError` con cleanup parcial (respuestas streaming, ToolBlock state)
- [ ] Tests de cancelación: interrupt mid-stream, interrupt mid-tool, kill durante bash

### Tests de TUI

- [ ] Tests de TUI con `pytest-textual` o `app_test` (pilot, screen mounting, key simulation)
- [ ] Test: CommandMenuScreen muestra 17 items y dispara acciones correctas
- [ ] Test: InputScreen acepta texto, cancela con Escape
- [ ] Test: _handle_command() enruta todos los comandos (/help, /sessions, /new, /reset, etc.)
- [ ] Test: ActivityIndicator muestra modelo y contexto
- [ ] Test: ThinkingBlock toggle expand/collapse
- [ ] Test: ToolBlock muestra output de tools
- [ ] Test: on_mount crea sesión y detecta modelo

## v0.6.0 — Skills Inteligentes, Panic Buttons y Seguridad (COMPLETADO)

### Completado en v0.6.0

- [x] **Panic Buttons** — Interrupt (Escape/`/stop`) + Kill (Ctrl+K/`/kill`)
- [x] **Telegram guard** — No apila mensajes mientras procesa
- [x] **Auto-selección de skills** — `get_relevant()` conectado a `_build_system_prompt()`
- [x] **Sandbox bypass fix** — `cat`, `head`, `tail` eliminados de bash allowlist
- [x] **Session persistence fixes** — `load_session_by_id` type mismatch + `_persisted_count`
- [x] **Native exploration tools** — GrepTool, GlobTool, TreeTool en Python puro (no dependen de bash)
- [x] **Panic Buttons en Ctrl+P** — Interrupt + Kill en menú (21 items)
- [x] **19 tests nuevos** — 101 total

### Pendiente

- [ ] PromptTextArea: Shift+Enter/Ctrl+Enter = newline (Textual Key no expone modifiers de forma fiable)
- [ ] Bash allowlist diferenciada por safe_mode
- [ ] Safe mode backend real (confirmación de comandos destructivos)
- [x] ~~Tools de exploración: `grep`, `tree`, `glob` nativos en Python~~ (hecho en v0.6.0 — GrepTool, GlobTool, TreeTool)
- [ ] Auto-fallback de providers (circuit breaker)

## v0.6.1 — Skills Avanzadas y Multi-agente

**Objetivo:** Skills autónomas y equipo de desarrollo virtual.

### Skills avanzadas
- [x] ~~Auto-selección de skills~~ (hecho en v0.6.0 — `get_relevant()` conectado al SP)
- [ ] Tools dinámicas en skills (scripts en `skills/<name>/scripts/` auto-registrados)
- [ ] `write_skill` tool para que el agente cree skills programáticamente
- [ ] Skill como sub-agente (SP propio dentro de la skill)
- [ ] Skills Hub: instalar skills desde GitHub repos

### Multi-agente
- [ ] Architect Agent → desglosa tareas complejas
- [ ] Coder Agent → implementa archivo por archivo
- [ ] Reviewer Agent → revisa calidad y seguridad
- [ ] Ejecución asíncrona de tareas largas
- [ ] Generación automática de Pull Requests

## v0.7.0 — Memoria y Conocimiento

**Objetivo:** Memoria semántica y base de conocimiento.

- [ ] Memoria vectorial con FAISS/ChromaDB (búsqueda semántica)
- [ ] System prompt caching optimizado
- [ ] Memoria entre sesiones (recordar decisiones previas)

## v1.0.0 — Producción

**Objetivo:** Release estable para uso diario.

- [ ] CI/CD con Docker para validación aislada
- [ ] Auto-corrección con linters (ruff, mypy)
- [ ] Web search tool integrada
- [ ] Documentación completa con ejemplos
- [ ] Cobertura de tests >= 80%
- [ ] MCP server mode (exponer KODE como tool server)

---

## Dependencias opcionales futuras

```toml
[project.optional-dependencies]
local = ["llama-cpp-python>=0.3"]
memory = ["sentence-transformers>=4.0", "faiss-cpu>=1.11"]
```
