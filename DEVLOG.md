# BytIA KODE - Development Log

## 2026-04-12 - Sesión 20: Panic Buttons, Seguridad y Auto-Skills (v0.6.0)

### Contexto

Revisión integral del proyecto con auditoría de seguridad (Semgrep), code review (subagent), y análisis estructural (Serena). Se identificaron y corrigieron bugs críticos, se cerró un agujero de seguridad, y se completaron features del roadmap.

### Bugs corregidos

1. **`load_session_by_id` crash (CRÍTICO)** — Asignaba `list[dict]` de SQLite directamente a `self.messages: list[Message]` con `# type: ignore`. En runtime, acceder a `.role`, `.content` causaba `AttributeError`. Fix: usar `_load_messages_from_store()` que convierte dicts → Message.
2. **`_persisted_count` no actualizado** — Al cargar sesión, el contador quedaba en 0 → `save_current_session()` re-insertaba todos los mensajes. Fix: `self._persisted_count = len(self.messages)`.
3. **Regex code blocks** — No capturaba bloques sin language tag ni con guiones. Fix: `[a-zA-Z0-9_+-]*\n?`.

### Seguridad

- **Sandbox bypass cerrado** — `cat`, `head`, `tail` eliminados de `_DEFAULT_BINARIES` (27→24). Permitían leer cualquier archivo del sistema bypassando el sandbox de `file_read`. Ahora `file_read` es la única vía de lectura.
- **Auditoría Semgrep** — No se encontraron: `shell=True`, `eval()`, ni secrets hardcodeados.

### Panic Buttons (#1)

Implementación completa de cancelación de dos niveles:

| Nivel | TUI | Telegram | Mecanismo |
|-------|-----|----------|-----------|
| Interrupt | `Escape` | `/stop` | `threading.Event` → stream loop break |
| Kill | `Ctrl+K` | `/kill` | interrupt + subprocess.terminate/kill + widget cleanup |

**Diseño:**
- `Agent._cancel_event` (threading.Event) — funciona sin event loop (tests síncronos OK)
- `Agent._active_subprocess` — referencia al proceso BashTool activo para kill
- Cancelación checkeada en cada chunk SSE y antes de ejecutar tool calls
- BashTool `on_subprocess` callback — registra/desregistra proceso activo
- Telegram `_processing` set — guard contra mensajes concurrentes

**Elección de threading.Event sobre asyncio.Event:** Los tests crean Agent sin event loop. `asyncio.Event()` requiere loop. `threading.Event` funciona en cualquier contexto y el checkeo `is_set()` es seguro desde corrutinas.

### Auto-selección de Skills

`get_relevant()` existía en `SkillLoader` con scoring (trigger 3pt, description 2pt, content 1pt) pero **nunca se invocaba**. Conectado a `_build_system_prompt()`:
- Usa el último mensaje de usuario como query
- Inyecta hasta 5 skills relevantes con contenido completo
- Antes solo se inyectaba el summary de todas las skills (siempre, sin filtro)

### Archivos modificados

| Archivo | Cambios |
|---------|---------|
| `pyproject.toml` | version 0.5.6 → 0.6.0 |
| `src/bytia_kode/agent.py` | +interrupt(), +kill(), +_cancel_event, +on_subprocess, auto-skills, session fixes |
| `src/bytia_kode/tools/registry.py` | sandbox bypass fix, +on_subprocess param, allowlist 27→24 |
| `src/bytia_kode/tui.py` | +Escape binding, +Ctrl+K binding, +interrupt/kill actions, regex fix |
| `src/bytia_kode/telegram/bot.py` | +/stop, +/kill, +_processing guard |
| `CHANGELOG.md` | entrada [0.6.0] |
| `ROADMAP.md` | v0.6.0 completado, v0.6.1 renumerado |
| `DEVLOG.md` | esta entrada |

### Verificación

- 82 tests pasando (sin cambios — features son de integración)
- Panic Buttons agent-side verificado manualmente
- TUI bindings verificados
- Regex verificado con 5 formatos de code block
- Import OK en todos los módulos

### Commits

- `9e6cc4b` fix: session persistence bugs + code block extraction regex
- `2b63ec8` fix: remove auto-cleanup of empty sessions
- `462d9b1` feat: Panic Buttons (Escape + Ctrl+K) + sandbox bypass fix

---

## 2026-04-12 - Sesión 19: file_read Sandbox Fix + Legacy Cleanup

### Contexto

Pedro encontró que Kode (TUI) no podía leer los YAML del Kernel/Runtime con `file_read`. El error era "Security violation: path escapes workspace" a pesar de que los archivos están dentro del workspace.

### Root Cause

Doble causa:
1. **Symlinks:** `bytia.kernel.yaml` y `bytia.runtime.kode.yaml` son symlinks a `~/bytia/`. `Path.resolve()` sigue el symlink y el path resultante queda fuera del workspace de Kode (`~/bytia/proyectos/BytIA-KODE/`).
2. **CWD dependency:** `_resolve_workspace_path()` usaba `Path.cwd()` para resolver paths relativos y como boundary del workspace. Si CWD cambiaba durante la sesión, paths legítimos fallaban.

### Fix

- `registry.py`: `_WORKSPACE_ROOT` + `set_workspace_root()` — workspace fijo al inicio, invariante a cambios de CWD. Paths relativos se resuelven contra este root.
- `agent.py`: `~/bytia/` añadido como trusted path — permite a `file_read` seguir symlinks legítimos al repo padre.
- Sandbox sigue protegiendo contra escapes reales (`/etc/passwd`, `../../../../`).

### Legacy Cleanup

- `core_identity.yaml` (v12.1.0) seguía presente en `prompts/` pero **no se usaba** desde RFC-001 — `load_identity()` solo carga kernel + runtime.
- Contradecía al Kernel: 7 anclas (C01-C07) vs 4 consolidadas (C01-C04), protocolos con naming diferente.
- Archivado a `prompts/legacy/core_identity.yaml.v12.1.0.yaml`.

### Archivos modificados

- `src/bytia_kode/tools/registry.py` — `_WORKSPACE_ROOT`, `set_workspace_root()`, path resolution mejorado
- `src/bytia_kode/agent.py` — trusted path `~/bytia/`, `set_workspace_root()` call, docstring
- `src/bytia_kode/prompts/core_identity.yaml` → `prompts/legacy/core_identity.yaml.v12.1.0.yaml`
- `CHANGELOG.md` — entrada [0.5.6]
- `CONTEXT.md` — referencia SP actualizada
- `docs/DEVELOPMENT.md` — estructura de prompts actualizada

### Lección: uv tool install vs editable venv (CAUSA RAÍZ REAL)

**Síntoma recurrente:** Cada vez que se edita el código fuente de Kode, los cambios NO se reflejan al arrancar `bytia-kode`. El modelo carga el SP viejo, las tools tienen bugs corregidos.

**Diagnóstico inicial (incorrecto):** Se asumió que era `__pycache__` stale. Limpiar cache NO solucionó el problema.

**Causa raíz real:** `bytia-kode` estaba instalado via `uv tool install`, que crea un entorno AISLADO en `~/.local/share/uv/tools/bytia-kode/` con una COPIA del código (no editable). Los edits en `src/` van al `.venv` del proyecto, que es una instalación completamente separada.

```
bytia-kode (binario) → ~/.local/share/uv/tools/bytia-kode/ → v0.5.3 COPIA
nuestros edits        → ~/bytia/proyectos/BytIA-KODE/.venv/  → v0.5.4 EDITABLE
```

**Solución definitiva:** Wrapper `~/.local/bin/bytia-kode` reescrito para ejecutar desde el `.venv` editable:

```bash
#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$HOME/bytia/proyectos/BytIA-KODE"
cd "$PROJECT_DIR"
exec uv run python -m bytia_kode.tui "$@"
```

Resultado: `bytia-kode` siempre usa el código fuente actual. Sin reinstalar, sin cache, sin sorpresas.

**NUNCA hacer:** `uv tool install bytia-kode` o `uv tool upgrade bytia-kode` — sobreescribe el wrapper y crea copia aislada de nuevo.

### Fixes adicionales (misma sesión)

- **Timer.interval AttributeError:** Textual 8.x `Timer` no tiene propiedad `interval` mutable. Fix: stop + recreate timer con nuevo intervalo.
- **Alias `~/.zshrc`:** `bkode-update` hacía `uv tool install --force` que sobreescribía el wrapper. Actualizado a `git pull` solo.
- **`bkode-dev` alias eliminado:** `uv tool install --editable .` también sobreescribe el wrapper.
- **Version bump:** 0.5.4 → 0.5.6 (pyproject.toml)

### Nota: modelo no puede inspeccionar su propio SP

El system prompt se inyecta como `role="system"` en la llamada al provider — NO se almacena en la tabla `messages`. El modelo dentro de Kode no puede "verse a sí mismo". La verificación del SP correcto se hace programáticamente (`load_system_prompt()`), no preguntando al modelo.

### Fix: Kernel/Runtime separados en system prompt

**Problema:** `load_identity()` hacía `{**kernel, **runtime}` — merge destructivo donde Runtime sobreescribía keys del Kernel (version, component, etc.). El modelo veía `version: 1.0.0` (Runtime) en vez de `version: 12.3.0` (Kernel). Las anclas se mezclaban con valores.

**Fix:** `load_identity()` ahora devuelve `(kernel, runtime)` como tupla. `_build_system_prompt()` renderiza ambos como secciones separadas con etiquetas claras:

```
BytIA OS — Kernel v12.3.0 + Runtime v1.0.0
# KERNEL (inmutable — identity, values, protocols)
# RUNTIME KODE (adaptación al entorno)
```

---

## 2026-04-11 - Sesión 18: BashTool Shell Operator Validation (Hotfix)

### Contexto

El 10 Abr 2026 a las 22:48, BytIA-KODE ejecutó un comando `mkdir -p path && cat << 'EOF' > archivo` con contenido markdown embebido. `shlex.split()` rompió el heredoc y `create_subprocess_exec` ejecutó `mkdir` con todos los tokens del markdown como argumentos literales, creando 48 directorios basura en `~/`. La limpieza requirió investigación forense (log de KODE línea 2531), verificación de contenido, y eliminación.

### Causa raíz

`BashTool.execute()` usa `shlex.split(command)` + `asyncio.create_subprocess_exec(*argv)`. Este pipeline NO usa shell — los operadores shell (`|`, `&&`, `>`, `<<`, `;`) se pasan como argumentos literales al binary. Un heredoc roto convierte cada token del contenido en un directorio.

### Fix implementado

Nuevo método `_validate_command_safety()` en `BashTool`:
- 9 patrones peligrosos bloqueados: `<<`, `>>`, `>`, `|`, `&&`, `||`, `;`, `$()`, backticks
- Mensaje de error con guidance: "usa file_write o file_edit, llama a bash múltiples veces"
- Descripción de tool actualizada para que el LLM sepa la restricción

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/bytia_kode/tools/registry.py` | +_validate_command_safety(), BashTool.description actualizada |
| `CHANGELOG.md` | Entrada [0.5.6] |
| `DEVLOG.md` | Esta entrada |

---

## 2026-04-10 - Sesión 5: Constitución, Comunicación y Optimización

### Contexto

B-KODE.md fue eliminado con `git-filter-repo` por contener un token de Telegram expuesto. Kode operaba sin instrucciones de proyecto, causando problemas recurrentes: no encontraba skills, memoria ni intercom. Además, la capa de comunicación con llama.cpp tenía bugs y hardcodes que afectaban la operatividad.

### Cambios realizados

**B-KODE.md (nuevo, 70 líneas):**
- Rutas absolutas a skills, memoria, intercom, logs y sesiones
- Protocolo de intercom con inbox isolation
- Sistema de memoria con categorías y formato YAML frontmatter
- Constraints de runtime y reglas de seguridad (repo público)
- Se carga automáticamente via `_load_bkode()` en `agent.py`

**Template variable interpolation:**
- `core_identity.yaml` tenía `{{environment}}`, `{{engine_id}}`, etc. que NUNCA se interpolaban
- El modelo recibía literales como `{{engine_id}}` desde que Kode existe
- Fix: `_apply_template_vars()` resuelve variables en runtime con lazy evaluation
- Se ejecuta después de `auto_detect_model()`, dentro de `_build_system_prompt()`
- Dirty flag para re-interpolar cuando cambia el context window

**Provider client optimizations:**
- Retry con backoff para 5xx/timeout (no-streaming only)
- `list_models()` invertido: OpenAI primero, Ollama fallback
- Error handling diferenciado en `detect_loaded_model()`
- Connection pool limits en httpx
- Temperature y max_tokens configurables via `.env`

**Token estimation:**
- Heurística ASCII-aware (3.5x para código, 3.0x para español)
- Tool calls cuentan arguments, no el Pydantic model dump

**Router polling:**
- Exponential backoff: 5s→60s cap tras fallos consecutivos

### Lecciones aprendidas

- Kode reportó éxito en `file_write` pero el archivo no se creó — diferencia entre "la tool dijo OK" y "el archivo está en disco". Kode se impuso un protocolo de verificación post-escritura.
- Los tests expusieron que `_apply_template_vars()` recibía MagicMock objects en `pc.model` y `pc.base_url` — añadido `isinstance()` guards.
- El retry para streaming es problemático porque `client.stream()` retorna un context manager y el error de conexión ocurre al entrar, no al llamar. Solo se aplica retry a `chat()` no-streaming.

### Archivos modificados

| Archivo | Líneas |
|---------|--------|
| `B-KODE.md` | +70 (nuevo) |
| `src/bytia_kode/agent.py` | +99, -23 |
| `src/bytia_kode/config.py` | +3 |
| `src/bytia_kode/providers/client.py` | +59, -16 |
| `src/bytia_kode/tui.py` | +13, -7 |
| `tests/test_context_management.py` | +1, -1 |
| `CHANGELOG.md` | +42 |

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

---

## 2026-04-07 - Sesión 16: TTS (Text-to-Speech) + Infra

### Contexto

Sesión de implementación de TTS en la TUI, debugging de errores Textual y arreglos de infraestructura (claude-mem, router 400).

### TTS — Audio en respuestas del asistente

**Diseño:** Botón 🔊 Escuchar montado como widget sibling debajo de cada respuesta del asistente. Toggle play/stop con label dinámico.

**Stack:** edge-tts (generación) + mpv (reproducción). Zero VRAM, zero API keys.

**Módulo:** `src/bytia_kode/audio.py`
- `TextCleaner.clean()` — elimina bloques de código, Markdown, URLs y emojis
- `play_speech(text)` — genera MP3 en `/tmp/bytia_audio/` y reproduce con mpv
- `stop()` / `is_playing()` — control del proceso mpv (terminate → kill con timeout)
- Voz: `es-MX-DaliaNeural` (femenina, mexicana)
- mpv con `--af=adelay=0.3` para compensar latencia de inicialización de PulseAudio

**Integración TUI (`tui.py`):**
- `_add_message()` monta un `Button` como sibling del `ChatMessage` en el chat area
- `_audio_content: dict[str, str]` mapea button_id → texto de la respuesta
- `on_button_pressed()` único handler que dispatcha por `event.button.id` (send-button vs audio_btn_*)
- `_play_and_update()` async: await play_speech + actualiza label

**Problemas resueltos durante implementación:**
1. `Vertical(Markdown, Button)` dentro de Rich `Panel` — Rich renderables y Textual widgets no se mezclan. Fix: botón como widget sibling
2. `rich.markdown.Markdown` vs `textual.widgets.Markdown` — la primera es renderable, la segunda es Widget. Fix: importar ambos con alias `RichMarkdown`
3. `Button.on("click", ...)` — Textual no tiene ese método. Fix: `on_button_pressed()` handler en la App
4. Dos `on_button_pressed` en la misma clase — Python conserva solo el último, el primero era invisible. Fix: mergear en un solo handler
5. `asyncio` no importado — Kode lo borró en una edición. Fix: re-añadir import
6. `encode('ascii', 'ignore')` eliminaba tildes — "dirección" → "direccin". Fix: regex que preserva Unicode español
7. Directorio `temp_audio` relativo — cwd diferente al correr como uv tool. Fix: `/tmp/bytia_audio/` absoluto

### Infra: claude-mem plugin

- Plugin restaurado desde `plugins.bak/` a `marketplaces/thedotmack/plugin/`
- Limpiadas versiones viejas del cache (10.6.3, 11.0.0, 11.0.1)

### Infra: Router 400 error

- Root cause: `"Assistant message must contain either 'content' or 'tool_calls'"` — gemma-4-26b devuelve `reasoning_content` sin `content`, llama.cpp lo rechaza
- Fix: logging HTTP 400 en `client.py` (chat y chat_stream) antes de `raise_for_status()`

### Infra: Sandbox bypass (documentado)

- `file_read` de Kode bloquea paths fuera del workspace, pero `cat` en bash allowlist lo salta
- Documentado en memory: `project_bkode_sandbox_bypass.md`
- Pendiente de fix

### Documentación actualizada

- CHANGELOG.md: entrada [0.5.3]
- docs/TUI.md: sección Audio TTS
- docs/ARCHITECTURE.md: audio.py en interfaces, edge-tts/mpv en dependencias externas
- DEVLOG.md: esta entrada

---

## 2026-04-10 - Sesión 17: Memoria Persistente, Trusted Paths y Sandbox Expandida

### Contexto

Kode propuso crear un sistema de memoria persistente para almacenar conocimiento entre sesiones. La propuesta conceptual era sólida pero había problemas de implementación: la sandbox bloqueaba escritura fuera del CWD, y Kode tenía un bug de respuesta duplicada en streaming. Claude tomó la implementación.

### Cambios principales

**1. Trusted Paths (registry.py + agent.py)**

`_resolve_workspace_path()` sandboxea contra `Path.cwd()`. Si Kode ejecuta desde `/home/asturwebs/proyectos/mi-proyecto/`, escribir en `~/.bytia-kode/` fallaba con `PermissionError`.

Solución: añadir `_TRUSTED_PATHS` como lista de directorios confiados. `Agent.__init__()` registra `config.data_dir` como trusted path. El workspace sigue siendo la primera comprobación; trusted paths es fallback controlado.

```python
_TRUSTED_PATHS: list[Path] = []

def set_trusted_paths(paths: list[Path]) -> None:
    _TRUSTED_PATHS.extend(p.resolve() for p in paths)

def _resolve_workspace_path(path: str) -> Path:
    # ... workspace check primero ...
    for trusted in _TRUSTED_PATHS:
        if trusted in resolved.parents:
            return resolved
    raise PermissionError(...)
```

Verificación: `/etc/` bloqueado, `/var/` bloqueado, `~/.bytia-kode/memoria/` permitido — desde cualquier CWD.

**2. Sistema de Memoria (`~/.bytia-kode/memoria/`)**

Estructura de 4 categorías + index:
```
memoria/
├── procedimientos/     # How-tos, workflows
├── contexto/           # Decisiones, hitos
├── tecnologia/         # Stacks, arquitecturas
├── decisiones/         # ADRs
└── index.md            # Auto-generado
```

Formato estándar con frontmatter YAML (created, category, tags).

**3. Skill `memory-manager`**

Procedimientos concretos usando las tools existentes (file_write, grep, find):
- `memory_store` — escribir archivo con frontmatter
- `memory_search` — grep recursivo en memoria/
- `memory_index` — regenerar index.md
- `memory_read` — file_read de archivo específico

Trigger: memory, recordar, guardar conocimiento, memoria, aprendido, lección.

**4. Allowlist expandida (registry.py)**

De 13 a 27 binarios. Nuevos: mv, cp, rm, head, tail, wc, date, chmod, curl, wget, scp, ssh, pip, pip3.

Patrón `_DEFAULT_BINARIES` (inmutable) + `EXTRA_BINARIES` (.env, configurable). Set union: solo puede expandir, nunca reducir.

**5. Skill graphify**

Instalación: `uv tool install graphifyy` (doble y). Requiere `EXTRA_BINARIES=graphify` en `.env`.

### Problemas resueltos

1. **Sandbox bloqueaba memoria** — `_resolve_workspace_path()` solo chequeaba CWD. Fix: trusted paths.
2. **Trusted paths podían abrir la sandbox** — Si se añade `/` como trusted, se bypassa todo. Mitigación: solo `data_dir` se registra, no paths arbitrarios.
3. **Tests de trusted paths** — Primer test falló porque `mkdir` iba después de `chdir`. Fix: crear directorio antes de cambiar.
4. **Assertion mal escrito** — `"memoria" in result.output` pero output era `"Wrote 7 chars to..."`. Fix: `"Wrote" in result.output`.
5. **`_TRUSTED_PATHS` es estado global** — Tests pueden contaminarse. Mitigación: cada test usa `tmp_path` aislado, las rutas no colisionan. No es ideal pero funcional.
6. **DEVLOG.md no estaba en local** — Solo existía en el remote. Fix: `git checkout origin/main -- DEVLOG.md`.

### Observaciones sobre Kode

- Kode propuso la memoria con buena estructura conceptual (4 categorías + protocolo de uso)
- Bug activo: respuesta duplicada en streaming (dos bloques de reasoning colados en output)
- Kode propuso "tools internas" con firmas de función, pero las skills son markdown, no código
- Propuso emojis en nombres de directorio (mala práctica para scripts y filesystems)
- Aceptó el feedback con madurez y se puso en modo evaluadora

### Tests

5 nuevos (82 total):
- `test_trusted_paths_allow_write_outside_workspace`
- `test_trusted_paths_do_not_bypass_arbitrary_paths`
- `test_memory_manager_skill_loads`
- `test_extra_binaries_merged_from_env`
- `test_extra_binaries_empty_env_uses_defaults`

### Documentación actualizada

- CHANGELOG.md: entrada [0.5.4]
- README.md: versión 0.5.4, novedades, badge 82 tests, estructura de directorios, EXTRA_BINARIES
- ROADMAP.md: sección v0.5.4 completada
- B-KODE.md: Memory System, trusted paths, skills actualizadas, versión 0.5.4
- CONTEXT.md: allowlist 27 binarios, trusted paths, versión 0.5.4
- DEVLOG.md: esta entrada

---

## Session 6 — 2026-04-11: RFC-001 BytIA OS Migration

### Context
Pedro + BytIA (Claude Code) + Grok collaborated on a constitutional audit that identified naming incoherence, verbosity, and missing directives in the v12.1.0 SP. Pedro authored RFC-001 defining the Kernel/Runtime architecture.

### Changes
- Created `bytia.kernel.yaml` (v12.3.0) — 4 anchors, Truth-First with per-type thresholds, O16 anti-sycophancy, O17 anti-bureaucracy
- Created `bytia.runtime.kode.yaml` (v1.0.0) — TUI capabilities, tools, commands, model config
- Migrated `agent.py`: `load_identity()` now merges kernel + runtime via `_load_yaml_resource()`
- Fixed P25 jailbreak patterns: `/` separators → `|` for YAML `safe_load` compatibility
- Archived legacy `core_identity.yaml` (v12.0.0 concisa)
- Main repo: ~40 files, ~300 references updated from old naming

### Key Insight
The Kernel is like `vmlinux` — portable, hardware-agnostic. The Runtime is like a device driver — adapts to the specific environment. `compatible_kernel: ">=12.3.0"` is the `vermagic` equivalent.

### Commits
- `1df5552` — Main repo: full RFC-001 migration
- `6409b8d` — KODE: agent.py + symlinks
- `1f46990` — Kernel YAML fix + legacy archive
