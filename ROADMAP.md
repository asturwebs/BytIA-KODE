# Roadmap - BytIA KODE

## Estado actual: v0.7.8 (Alpha estable)

---

## v0.7.7 — Session Audit Fixes (COMPLETADO)

- [x] **Tool Error Memory hash normalization** — `_get_tool_error_key()` hashea solo `command`/`path`, no JSON completo
- [x] **BashTool `df`, `du`, `head`, `tail` en allowlist** — binarios read-only para diagnóstico
- [x] **BashTool error hints** — rechazos incluyen lista de permitidos + hint contextual (`cd` → `workdir`)
- [x] **pytest testpaths** — `uv run pytest -q` recoge 144 tests (antes 116)
- [x] **Flaky test fix** — `test_file_write_tool_handles_relative_path` resetea `_WORKSPACE_ROOT`
- [x] **2 tests nuevos** — hash normalization + security policy blocking. Total: 144.

---

## v0.7.8 — Code Review Fixes (COMPLETADO)

**Fuente:** Code Review triple (2026-04-30) — Hermes + Peke + Claude → `docs/CODE-REVIEW.md`

### P0 — Inmediato

- [x] **Ampliar allowlist bash** — `rg`, `bat`, `eza`, `tokei`, `shellcheck`
  - *No se añaden:* `z` (requiere shell interactivo), `tmux` (requiere TTY), `gh` (superficie de seguridad)
  - *Archivo:* `src/bytia_kode/tools/registry.py`
- [x] **Test: system messages sobreviven compression** — test de regresión (NO es bug, enforcement ya existe en `agent.py:538`)
  - *Archivo:* `tests/test_context_management.py`

### P1 — Alta prioridad

- [x] **Fix race condition interrupt/kill** — capturar `_active_subprocess` en variable local antes del if
  - *Archivo:* `src/bytia_kode/agent.py`

### P2 — Tech debt (no bloqueante)

- [ ] **TUI refactor: extraer widgets a subdir** — `ToolBlock`, `ThinkingBlock`, `StatusBar` → `src/bytia_kode/tui/widgets/`
  - *Archivo:* `src/bytia_kode/tui.py`

### No incluido en v0.7.8 (trade-offs deliberados)

- Summary con modelo separado — requiere redesign del provider manager
- `z` / `tmux` / `gh` en allowlist — sin valor real para el agente
- Symlink attack surface fix — bajo riesgo, alto esfuerzo

---

## v0.7.6 — HOTFIX FIX-3/4 + Skills Polish (COMPLETADO)

- [x] **FIX-3: Tool Error Memory** — hash MD5 de args, `[blocked]` en retry
- [x] **FIX-4: Workspace Context Awareness** — CWD + sandbox + trusted paths en SP
- [x] **YAML multiline parser** — `description: >` folded scalars
- [x] **sync-vendor-skills.sh** — transformación agentskills.io → flat
- [x] **Vendor skills auto-update** — reinstala solo en version change
- [x] **9 tests nuevos** — 3 loader + 3 FIX-3 + 3 FIX-4. Total: 142.

---

## v0.7.5 — Skills System v2.0 (COMPLETADO)

- [x] **Layered skill architecture** — `SkillLoader` con 3 capas: bytia > user > vendor
- [x] **YAML multiline parser** — `_parse_skill()` maneja `description: >` folded scalars
- [x] **sync-vendor-skills.sh** — transforma agentskills.io → flat format durante sync
- [x] **FIX-3: Tool Error Memory** — patrones rechazados no se reintentan (bash, file_write, file_edit)
- [x] **FIX-4: Workspace Context Awareness** — CWD y sandbox inyectados en system prompt dinámico
- [x] **Vendor skills auto-update** — reinstala solo cuando cambia la versión del paquete
- [x] **9 tests nuevos** — 3 loader edge cases + 3 FIX-3 + 3 FIX-4

---

## v0.7.4 — Provider Resilience Hotfixes (COMPLETADO)

- [x] **DeepSeek V4 thinking mode** — `_ensure_deepseek_reasoning()` parchea mensajes con reasoning_content tras tool calls
- [x] **Streaming timeout** — `_stream_with_timeout()` con 60s por chunk, detecta providers zombie
- [x] **Cloud polling fix** — `_poll_router_info()` solo para providers locales (localhost)

---

## HOTFIX v0.7.2 — Agent Reliability (URGENTE)

> **Fuente:** Auditoría sesión `tui_cd8638f8` (2026-04-19) — `docs/SESSION_AUDIT_tui_cd8638f8.md`
> **Problema:** Bucle de 70+ mensajes (~42% de sesión) por desconocimiento de limitaciones del sandbox.
> **Impacto:** Agente no es confiable para proyectos multi-directorio sin estos fixes.

### P0 — Bloqueante (impide uso productivo fuera de CWD)

- [x] **FIX-1: Bash Tool Limitations en System Prompt**
  - Añadir sección `tool_constraints` a `runtime.default.yaml` documentando lo que `bash` NO soporta (pipes, redirects, chains, brace expansion, shell builtins)
  - Incluir patrones permitidos y protocolo de escalación
  - **Archivo:** `src/bytia_kode/prompts/runtime.default.yaml`
  - **Espera reducir:** ~90% de errores de bash por desconocimiento

- [x] **FIX-2: Self-Loop Detection (LoopDetector)**
  - Clase `LoopDetector` en `agent.py`: contador de fallos consecutivos, ventana deslizante de 5 intentos
  - Si 3+ fallos consecutivos → inyectar mensaje de sistema forzando escalación al usuario
  - Mensaje automático: "He intentado esta operación N veces sin éxito. Ejecuta: `comando`"
  - **Archivo:** `src/bytia_kode/agent.py`
  - **Espera reducir:** 100% de bucles >3 iteraciones

### P1 — Alta prioridad (mejora robustez)

- [x] **FIX-3: Tool Error Memory por Sesión**
  - Diccionario en memoria que registra patrones de comandos bloqueados por security policy
  - Antes de ejecutar un tool call, verificar si el patrón ya fue rechazado
  - Evitar reintentar comandos con `|`, `&&`, `>` tras primer rechazo
  - **Archivo:** `src/bytia_kode/agent.py`

- [x] **FIX-4: Workspace Context Awareness**
  - Inyectar en system prompt dinámico: CWD actual, paths escribibles, paths confiados, limitaciones de sandbox
  - El agente debe saber ANTES de intentar escribir que no puede salir del CWD
  - **Archivo:** `src/bytia_kode/agent.py` + `src/bytia_kode/tools/registry.py`

### P2 — Mejora de experiencia

- [ ] **FIX-5: Proactive Escalation Threshold** — Tras 3 fallos consecutivos con el mismo tool, generar mensaje automático con comando manual
  - *Pubsub:* Pendiente desde v0.7.2
- [ ] **FIX-6: Post-Generation Workspace Validation** — Verificar que archivos están dentro del árbol del proyecto actual
  - *Pubsub:* Pendiente desde v0.7.2

### Tests requeridos para cerrar hotfix

- [x] Test: LoopDetector detecta bucle tras 3 fallos consecutivos
- [x] Test: LoopDetector no dispara con fallos intermitentes
- [x] Test: Tool Error Memory bloquea patrón previamente rechazado
- [x] Test: Bash tool limitations presentes en system prompt generado
- [x] Test: Workspace context awareness inyectado en SP dinámico

---

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
- [x] ~~Auto-fallback de providers (circuit breaker)~~ (hecho en v0.7.0)

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

## v0.7.0 — Circuit Breaker y Provider Resilience (COMPLETADO)

### Completado

- [x] **CircuitBreaker class** — CLOSED/OPEN/HALF_OPEN state machine con auto-recuperación
- [x] **ProviderManager.get_healthy()** — routing inteligente por prioridad con health check
- [x] **Agent auto-fallback** — si provider falla, intenta siguiente automáticamente
- [x] **System messages** — aviso al usuario cuando se cambia de provider (TUI + Telegram)
- [x] **report_success / report_failure** — feedback loop del agentic loop al circuit breaker
- [x] **24 tests nuevos** — 8 CircuitBreaker + 7 ProviderManager + 3 Agent fallback + 6 existentes arreglados

## v0.7.3 — Optimizaciones Agente y Pseudo Tool Calls (COMPLETADO)

### Completado

- [x] **Structured CoT Grammar** — GBNF grammars para Chain-of-Thought estructurado (explorado y revertido por incompatibilidad agentic + tools)
- [x] **`supports_grammar` property** — patrón de detección de capacidades del provider, zero overhead
- [x] **llama.cpp b8946** — engine auto-update con weekly cron
- [x] **SP cache** — system prompt cacheado por message count (~500ms/iter ahorrados)
- [x] **Router polling pausado** — sin HTTP requests durante procesamiento agente
- [x] **Placeholder tools** — `[procesando herramientas...]` evita que reasoning se cuele en content
- [x] **Batch compression** — 5 mensajes de golpe (antes 2), preserva últimos 4 non-system
- [x] **LoopDetector** — detecta 3 tool calls idénticos consecutivos e inyecta mensaje de sistema
- [x] **Validación** — 65% menos iteraciones, 73% menos mensajes, 0 leaks de reasoning
- [x] **Pseudo tool calls GGUF** — parseo de tool calls desde texto plano de modelos GGUF
- [x] **FIX-1: tool_constraints** — sección en runtime.default.yaml con limitaciones de bash
- [x] **FIX-2: Self-Loop Detection** — LoopDetector con contador de fallos consecutivos
- [x] **Renumbering devlog** — sesiones S1-S34 con orden cronológico

### Tests

- [x] 130 tests pasando — sin regresiones

## v0.8.0 — Memoria y Conocimiento

**Objetivo:** Memoria semántica y base de conocimiento.

- [ ] Memoria vectorial con FAISS/ChromaDB (búsqueda semántica)
- [ ] System prompt caching optimizado
- [ ] Memoria entre sesiones (recordar decisiones previas)
- [ ] **Intercom como Skill Package** — sistema genérico de addons:
  - `/setup-intercom` comando TUI que crea `~/.bytia-kode/intercom/` + instala skill
  - Skill package auto-contenido: SKILL.md + scripts + plantillas de directorio
  - Validación de conectividad (local + VPS/remote)
  - Publicar como ejemplo de extensibilidad del sistema de skills
  - Base para futuros addons: Slack bridge, Discord bridge, etc.

## v0.7.2 — Installer Interactivo

**Objetivo:** El instalador `curl | bash` guía al usuario para configurar lo necesario antes de primer uso.

- [ ] Prompt interactivo para provider URL, API key y modelo durante la instalación
- [ ] Validación de conectividad contra el provider antes de continuar
- [ ] Detección automática de modelos disponibles via `/v1/models`
- [ ] Opción de configurar Telegram bot token durante install
- [ ] Generación del override de identidad (`~/.bytia-kode/prompts/bytia.kernel.yaml`) con datos del usuario
- [ ] `--non-interactive` flag para CI/automatización (usa `.env.example` como ahora)
- [ ] Resumen final con config aplicada y siguiente paso claro

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

---

## Inspirado en oh-my-pi / pi-mono (2026-04-18)

> Análisis comparativo: [oh-my-pi](https://github.com/can1357/oh-my-pi) v14.1.2 (3.1k estrellas, fork de [pi-mono](https://github.com/badlogic/pi-mono) por Mario Zechner)

### v0.8.0 — Hashline Edits + LSP básico

**Hashline Edits** (inspirado en oh-my-pi)
- [ ] Anchors por hash de contenido en vez de `str_replace`
- [ ] Hash corto (4-6 chars) generado desde contenido de línea
- [ ] Rechazar ediciones si hash no coincide (archivo cambió desde última lectura)
- [ ] Benchmark: medir tasa de éxito antes/después
- **Por qué:** x10 mejora en modelos débiles, +5pp en modelos fuertes. `str_replace` es la fuente #1 de fallos.
- **Ref:** [oh-my-pi — Hashline Edits](https://github.com/can1357/oh-my-pi#-hashline-edits)

**LSP Integration básico** (inspirado en oh-my-pi)
- [ ] Protocolo LSP client sobre stdio (Python, TypeScript, Rust mínimo)
- [ ] Operaciones: `diagnostics`, `definition`, `references`, `hover`
- [ ] Integración como tool en el registry (`lsp` tool)
- [ ] Diagnósticos automáticos post-escritura
- **Por qué:** Retroalimentación inmediata sobre errores sin compilar. oh-my-pi tiene 11 operaciones y 40+ lenguajes.
- **Ref:** [oh-my-pi — LSP Integration](https://github.com/can1357/oh-my-pi#-lsp-integration-language-server-protocol)

### v0.9.0 — Model Roles + Subagentes

**Model Roles** (inspirado en oh-my-pi)
- [ ] Roles configurables: `default`, `fast` (smol), `deep` (slow), `plan`, `commit`
- [ ] Config en `.env`: `MODEL_DEFAULT`, `MODEL_FAST`, `MODEL_DEEP`, etc.
- [ ] Ciclado de roles con keybinding en TUI (Ctrl+P / Alt+P)
- [ ] Auto-selección de rol según tarea
- **Por qué:** Separar modelos por rol optimiza coste y calidad. B-KODE ya tiene circuit breaker, faltan roles.
- **Ref:** [oh-my-pi — Model Roles](https://github.com/can1357/oh-my-pi#-model-roles)

**Subagentes / Task Tool** (inspirado en oh-my-pi)
- [ ] Framework de subagentes con ejecución paralela
- [ ] Agentes base: `explore`, `plan`, `review`
- [ ] Comunicación vía cola de resultados, streaming al TUI
- [ ] Aislamiento opcional con git worktrees
- [ ] Tool `task` en el registry
- **Por qué:** Paralelizar exploración de codebase = respuestas más rápidas. oh-my-pi tiene 6 agentes.
- **Ref:** [oh-my-pi — Task Tool](https://github.com/can1357/oh-my-pi#-task-tool-subagent-system)

### v0.10.0 — TTSR + Contexto inteligente

**TTSR — Time Traveling Streamed Rules** (inspirado en oh-my-pi)
- [ ] Reglas con patrón regex que vigilan el stream de output
- [ ] Inyección just-in-time: patrón match → abort → inyectar regla → reintentar
- [ ] Zero upfront cost: 0 tokens hasta que son relevantes
- [ ] One-shot por sesión: cada regla solo dispara una vez
- [ ] Definición en YAML: `ttsr_trigger: "patrón_regex"`
- **Por qué:** Las reglas de estilo/corrección queman tokens siempre. TTSR las hace gratuitas hasta necesidad real.
- **Ref:** [oh-my-pi — TTSR](https://github.com/can1357/oh-my-pi#-time-traveling-streamed-rules-ttsr)

**Universal Config Discovery** (inspirado en oh-my-pi)
- [ ] Detectar config de múltiples tools: `.claude/`, `.cursor/`, `.gemini/`, `.codex/`
- [ ] Merge de CLAUDE.md, AGENTS.md, .cursorrules en contexto unificado
- [ ] Atribución: mostrar origen de cada config
- **Por qué:** Aprovechar configs que el usuario ya tenga. oh-my-pi detecta 8 tools.
- **Ref:** [oh-my-pi — Universal Config Discovery](https://github.com/can1357/oh-my-pi#-universal-config-discovery)

### v0.11.0 — Experiencia de desarrollo

**Commit Tool** (inspirado en oh-my-pi)
- [ ] Commits convencionales con análisis de cambios
- [ ] `git diff` + `git log` como tools del registry
- [ ] Detección de cambios multi-concern y split en commits atómicos
- [ ] Validación: sin filler words, formato convencional
- [ ] Comando `/commit` en TUI
- **Ref:** [oh-my-pi — Commit Tool](https://github.com/can1357/oh-my-pi#-commit-tool-ai-powered-git-commits)

**Python REPL Tool** (inspirado en oh-my-pi)
- [ ] Kernel IPython persistente con output streaming
- [ ] Prelude helpers: file I/O, search, line operations
- [ ] Tool `python` en el registry
- **Por qué:** El tool `bash` ejecuta Python como subproceso. Kernel persistente = más rápido + mantiene estado.
- **Ref:** [oh-my-pi — Python Tool](https://github.com/can1357/oh-my-pi#-python-tool-ipython-kernel)

**Interactive Code Review** (inspirado en oh-my-pi)
- [ ] Comando `/review` (branch diff, uncommitted, commit específico)
- [ ] Findings estructurados con prioridad (P0-P3)
- [ ] Veredicto: approve / request-changes / comment
- **Ref:** [oh-my-pi — Interactive Code Review](https://github.com/can1357/oh-my-pi#-interactive-code-review)

### v0.12.0 — Infraestructura y extensibilidad

**SDK / Programmatic API** (inspirado en pi-mono + oh-my-pi)
- [ ] API Python para embeber B-KODE en otras aplicaciones
- [ ] `create_agent_session()`, suscripción a eventos, control de modelo/tools
- [ ] Modo RPC sobre stdin/stdout para integración multi-lenguaje
- **Por qué:** pi-mono expone SDK nativo. oh-my-pi tiene RPC mode. Abre puerta a web UI, integraciones.

**Hooks System** (inspirado en oh-my-pi)
- [ ] Lifecycle hooks: `pre_tool_call`, `post_tool_call`, `pre_response`, `post_response`
- [ ] Definición en Python: `~/.bytia-kode/hooks/`
- [ ] Capacidad de bloquear/modificar tool calls y responses

**MCP Client nativo** (inspirado en oh-my-pi)
- [ ] Conexión a MCP servers vía stdio/HTTP como client
- [ ] Auto-descubrimiento de tools MCP y registro en tool registry
- [ ] Configuración en `.bytia-kode/mcp.json`

### v0.13.0 — TUI avanzado

**Session Branching** (inspirado en oh-my-pi)
- [ ] Árbol de sesión con branching desde cualquier mensaje
- [ ] Navegación tipo `/tree` con búsqueda
- [ ] Labels/bookmarks en puntos clave

**Persistent Prompt History** (inspirado en oh-my-pi)
- [ ] Historial de prompts en SQLite (cross-sesión)
- [ ] Búsqueda con Ctrl+R estilo reverse-i-search

**Session Export** (inspirado en oh-my-pi)
- [ ] Export a HTML con syntax highlighting
- [ ] Comando `/export [path]`
- [ ] Compartir sesiones como gists

**`@file` References** (inspirado en oh-my-pi)
- [ ] Type `@` para fuzzy-search archivos del proyecto
- [ ] Respects `.gitignore`
- [ ] Contenido del archivo inyectado inline en el prompt
- **Por qué:** Productividad enorme. No más copy-paste de archivos. oh-my-pi y Claude Code lo tienen.
- **Complejidad:** Baja — fuzzy search + file read + inyección en prompt

**Path Completion con Tab** (inspirado en oh-my-pi)
- [ ] Autocompletar rutas relativas, `../`, `~/` con Tab
- [ ] Integración con `PromptTextArea`
- **Por qué:** QoL básico que todo coding agent tiene. B-KODE no lo tiene.
- **Complejidad:** Media — requiere interceptar Tab en PromptTextArea y resolver paths

**Powerline Footer** (inspirado en oh-my-pi)
- [ ] Footer informativo: modelo activo + cwd + git branch/status + tokens + context %
- [ ] Actualización en tiempo real durante streaming
- **Por qué:** oh-my-pi muestra todo esto en una línea. Nuestro StatusBar actual es mínimo.
- **Complejidad:** Media — reemplazar Footer estático con widget reactivo

**Auto Session Titles** (inspirado en oh-my-pi)
- [ ] Título automático basado en primer mensaje del usuario
- [ ] Mostrar en `/sessions` list y welcome screen
- **Por qué:** Sesiones sin título son inútiles para buscar. oh-my-pi usa el commit model para generar títulos.
- **Complejidad:** Baja — tomar primeras N palabras del primer mensaje, o pedir al modelo que genere un título

**Welcome Screen** (inspirado en oh-my-pi)
- [ ] Pantalla de bienvenida: logo + tips + sesiones recientes seleccionables
- [ ] Reemplazar el banner estático actual
- **Por qué:** Primera impresión. oh-my-pi muestra sesiones recientes y tips. Nosotros solo un banner.
- **Complejidad:** Media — nuevo screen con lista navegable

**Grouped Tool Display** (inspirado en oh-my-pi)
- [ ] Tool calls consecutivos del mismo tipo (ej: 5 reads) mostrados como compact tree
- [ ] Expand/collapse individual o global
- **Por qué:** Un agente explorando un codebase genera 10-20 reads seguidos. Ahora ocupa toda la pantalla. oh-my-pi los agrupa en un árbol compacto.
- **Complejidad:** Media — detectar secuencias en mount() y reemplazar por widget compacto

### v0.14.0 — Multi-canal y observabilidad

**Stats Dashboard** (inspirado en oh-my-pi)
- [ ] Dashboard local de uso: requests, coste, cache rate, tokens/s
- [ ] Datos por provider, modelo, sesión
- [ ] Comando `/stats` en TUI

**Multi-Credential Support** (inspirado en oh-my-pi)
- [ ] Round-robin de API keys para distribuir carga
- [ ] Fallback automático entre credenciales al hitting rate limits
- [ ] Hashing consistente (FNV-1a) para asignación estable por sesión

### Ideas futuras sin versión (oh-my-pi / pi-mono)

| Idea | Origen | Complejidad |
|------|--------|-------------|
| Browser tool con stealth (Puppeteer) | oh-my-pi | Alta |
| SSH tool con conexiones persistentes | oh-my-pi | Media |
| Image generation (Gemini/OpenRouter) | oh-my-pi | Baja |
| Web UI components | pi-mono | Alta |
| Slack bot (pi-mom equivalente) | pi-mono | Media |
| vLLM pod manager | pi-mono | Alta |
| AST tools (ast-grep integration) | oh-my-pi | Media |
| Sampling controls (topP, topK, minP) | oh-my-pi | Baja |
| File reference con `@path` | oh-my-pi | Baja |
| Todo tool integrado | oh-my-pi | Media |
| Ask tool (preguntas estructuradas al usuario) | oh-my-pi | Baja |
