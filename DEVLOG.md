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
