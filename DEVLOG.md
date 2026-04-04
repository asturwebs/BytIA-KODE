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
