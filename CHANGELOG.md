# Changelog

Todos los cambios relevantes del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

## [0.4.1] - 2026-04-05

### Added

- **`file_edit` tool** — Search/replace y create con dos estrategias. Backup automático con timestamp antes de cada edición. Diff unificado mostrando cambios. Diagnósticos `_no_match_help` cuando old_text no coincide (whitespace, partial match).
- **Context management con summarización** — Cuando el contexto supera el 75% del límite, el agente pide al propio modelo que resuma los mensajes más antiguos. Fallback a truncación si la summarización falla. Threshold dinámico por `ctx_size` del router.
- **`Agent.estimate_tokens()`** — Método estático como single source of truth para estimación de tokens (chars/3). Usado por agent y TUI.
- **ToolBlock color coding** — Indicador visual: rojo ❌ si la tool retorna error, verde ✅ si éxito. Propagado vía callback `on_tool_done(tool_name, output, error)`.
- **Router polling con alertas progresivas** — Logging de cada fallo de polling. Alerta visual en la TUI tras 3 fallos consecutivos.
- **13 tests de context management** — Cubren `estimate_tokens`, `_manage_context` (threshold, summarización, preservación de mensajes recientes, stop condition), `_summarize_messages` (summary, error fallback, empty response fallback) y `update_context_limit` (valid, zero, negative).
- **14 tests de file_edit** — Cubren replace (single, multiple, all, not found, indented), create (new, existing, force), path traversal, diff output y validación de parámetros.

### Changed

- **`on_tool_done` callback** — Firma actualizada a `fn(tool_name: str, output: str, error: bool)` para soportar color coding.
- **Token estimation unificada** — TUI usa `Agent.estimate_tokens()` en vez de cálculo propio (chars/4 → chars/3).

### Total tests: 27 (14 file_edit + 13 context_management)

- **Router polling en StatusBar** — `ActivityIndicator` consulta `/v1/models` cada 5s. Si el modelo cambia en la WebUI (slot swap), el StatusBar se actualiza automáticamente sin intervención del usuario.
- **ctx-size real desde el router** — `get_router_info()` extrae `--ctx-size` de los args del modelo cargado via `/v1/models`. La capacidad de contexto ya no es un valor hardcodeado, es dinámica por modelo.
- **ToolBlock widget** — Bloque colapsable para ejecución de tools (como ThinkingBlock pero con icono 🔧). Muestra nombre de la tool y su output. Click para expandir/colapsar.
- **Tool execution indicators** — El ActivityIndicator muestra ⚙ durante tool calls y vuelve a ◐ Thinking 500ms después de que la tool termina.
- **Agent callbacks** — `on_tool_call` y `on_tool_done` en `Agent.__init__` para que la TUI reaccione a tool calls en tiempo real.
- **core_identity.yaml runtime section** — Auto-conocimiento del agente: comandos disponibles, capacidades, ubicación del proyecto y motor de inferencia.
- **`get_router_info()` en ProviderClient** — Consulta `/v1/models` (modelo + ctx-size desde args) y `/metrics` (prompt/predicted tokens).
- **WebFetchTool** — Tool nativa para fetch de URLs. HTTP GET via httpx, HTML tag stripping, validación de content-type, truncation a 30k chars, timeout configurable.
- **web-fetch skill** — Skill en `~/.bytia-kode/skills/web-fetch/` con guía de uso de la tool.

### Changed

- **PROVIDER_MODEL default → `auto`** — Coherente con router support. Ya no hardcodea `glm-4.7-flash`.
- **Estimación de ctx usado** — Usa `agent._estimate_tokens()` (chars/3) con prefijo `~` en vez de métricas cumulativas del servidor.

## [0.4.0] - 2026-04-03

### Added

- **Auto-detect modelo del router** — `ProviderClient.detect_loaded_model()` consulta `/v1/models` y filtra `status: loaded`. `ProviderManager.auto_detect_model()` se ejecuta al arrancar y al cambiar provider. Si `PROVIDER_MODEL=auto`, detecta dinámicamente qué modelo hay en VRAM.
- **llama.cpp Router support** — Single port (8080) multi-modelo. B-KODE se conecta al router y usa el modelo que esté cargado, sin hardcodear nombres.
- **Bot Telegram usa router (GPU)** — Cambiado de Ollama (CPU, ~15 t/s) a router (:8080, GPU, ~133 t/s). Lazy init con auto-detect en el primer mensaje.
- **Guard si no hay modelo cargado** — Si el router no tiene ningún modelo, el bot responde con mensaje claro en vez de fallar con 400.

### Removed (cleanup)

- `python-docx` — dependencia declarada pero nunca importada. ~2MB eliminados del install.
- `beautifulsoup4` — dependencia declarada pero nunca importada. ~500KB eliminados del install.
- `prompt-toolkit` — solo usada por `cli.py` (REPL simple inalcanzable desde el entry point). ~1MB eliminado.
- `cli.py` — REPL simple eliminada. Entry point `bytia-kode` siempre lanza TUI. `--simple` flag eliminado.
- `memory/store.py` — sistema de memoria persistente eliminado. `add()` nunca se llamaba, `get_context()` siempre devolvía `""`. Agente simplificado.
- 2 tests de memoria eliminados (test_memory_store_raises_on_corrupted_json, test_memory_context_is_bounded).

### Added

- **Streaming real token a token** — `chat_stream()` en `ProviderClient` consume SSE y yield chunks (`("text", str)`, `("reasoning", str)`, `("tool_calls", list)`) en tiempo real.
- **Reasoning/Thinking** — Detección de campos `reasoning_content` (DeepSeek) y `reasoning` (Gemma 4) en SSE. `ThinkingBlock` widget colapsable con click/Ctrl+D.
- **B-KODE.md** — Fichero de instrucciones a nivel proyecto (tipo CLAUDE.md). Búsqueda walk-up desde CWD hasta filesystem root. Inyectado en el system prompt después de la identidad constitucional.
- **Context window management** — `MAX_CONTEXT_TOKENS = 16384`. `_estimate_tokens()` (chars/3). `_manage_context()` comprime mensajes antiguos al superar 75% del límite.
- **ActivityIndicator** — Widget de estado dinámico encima del input. Muestra: `Ready | provider | modelo | ctx Xk/Yk`. Cambia a `Thinking...` o `Running: tool` durante procesamiento.
- **CommandMenuScreen** — Popup modal con Ctrl+P. Lista de comandos seleccionable con ListView (arrows + enter).
- **`COMMAND_PALETTE_BINDING = ""`** — Deshabilita la paleta built-in de Textual para usar la nuestra.
- **Dynamic provider info** — Al cambiar provider con F3, la ActivityIndicator y el Session Info se actualizan inmediatamente.
- **Multi-provider config** — Primary: glm-4.7-flash (llama.cpp), Fallback: glm-5-turbo (Z.AI API), Local: gemma4:26b (Ollama).

### Changed

- **Session Info movida al ActivityIndicator** — Ya no es un panel en el chat area. La info de modelo, provider y contexto se muestra en la barra de estado encima del input.
- **Error handling en agentic loop** — Los errores de provider ya NO se persisten en `self.messages`. Antes causaban cascada de 400 Bad Request en turnos siguientes.
- **Info-panel eliminado del chat area** — Reemplazado por una línea simple (`#info-line`) con B-KODE status y versión.
- **Footer simplificado** — Solo muestra `Menu (Ctrl+P)`. El resto de bindings tienen `show=False`.
- **Config defaults actualizados** — `PROVIDER_BASE_URL` → `http://localhost:8080/v1` (router), `PROVIDER_MODEL` → `auto` (detección dinámica), `FALLBACK_MODEL` → `glm-5-turbo`, `LOCAL_MODEL` → `gemma4:26b`.

### Fixed

- **`COMMAND_PALETTE_BINDING = None`** causaba `NoneType.rpartition()` crash. Fix: `""` (empty string).
- **CommandMenuScreen vacía** — `ListView` dentro de `VerticalScroll` colapsaba height. Fix: yielding ListView directamente.
- **ActivityIndicator no visible** — `dock: bottom` en CSS causaba conflicto con otros widgets docked. Fix: remover dock.
- **ThinkingBlock._render()** — Nombre en conflicto con método interno de Textual. Renombrado a `_update_display()`.
- **Reasoning no streaming** — Se mostraba contador durante streaming. Fix: montar ThinkingBlock al primer chunk y llamar `append()` en cada delta.
- **ThinkingBlock solo toggleable en el último** — Añadido `can_focus = True`, `on_click()`, `BINDINGS` con Enter.
- **`_update_info_panel()` Pyright errors** — Variable `c` no definida en `watch_theme`. Fix: eliminar método duplicado, usar ActivityIndicator.
- **`agent._max_context_tokens`** — Referenciado por ActivityIndicator pero no existía como atributo. Fix: `self._max_context_tokens = MAX_CONTEXT_TOKENS` en `__init__`.

### Removed

- Debug logging temporal (`logger.info("Starting _process_message...")`, `logger.debug("reasoning chunk: ...")`).
- Método `_update_info_panel()` — Funcionalidad absorbida por ActivityIndicator.

### Added

- Skills System persistente: directorio `~/.bytia-kode/skills/` con auto-creación vía `AppConfig`.
- `SkillLoader.save_skill()` — crea SKILL.md con frontmatter YAML (agentskills.io compatible).
- `SkillLoader.list_skill_names()`, `get_skill()`, `verify_skill()` — gestión CRUD de skills.
- `SkillLoader.get_relevant()` mejorado con scoring (trigger +3, description +2, content +1).
- Campo `verified` en `Skill` dataclass, parseado del frontmatter en `_parse_skill()`.
- Comando `/skills save <name> [desc]` — captura multiline de contenido de skill.
- Comando `/skills show <name>` — muestra contenido en panel con borde.
- Comando `/skills verify <name>` — marca skill como verificada.
- Skill `skill-creator` incluida: meta-skill que guía al agente para crear nuevas skills.
- `AppConfig.skills_dir` — campo derivado que apunta a `~/.bytia-kode/skills/`.

### Changed

- `_show_skills()` usa `list_skill_names()` en vez de `load_all()`, muestra estado verified.

- Banner ASCII actualizado a "B KODE" con crédito "by AsturWebs & BytIA".
- Colores del banner y session info panel ahora son dinámicos, adaptándose al tema activo.
- Borde del banner dinámico (cambia con el tema).
- Añadidos 3 temas claros: `catppuccin-latte`, `solarized-light`, `rose-pine-dawn` (total: 9 temas).
- Tema por defecto cambiado de `monokai` a `gruvbox`.

### Added

- Atajo `F2` para cambiar de tema cíclicamente (con `priority=True` para WSL).
- Método `_get_theme_colors()` para extraer colores del tema activo.
- Método `_render_banner()` para inyección dinámica de color en el banner.
- `watch_theme()` actualiza banner e info panel en tiempo real al cambiar tema.
- Persistencia del tema seleccionado en `~/.bytia-kode/theme.json`.
- Bordes de mensajes de chat (user, assistant, tool, error) reaccionan en tiempo real al cambiar tema.

### Added

- `F3` para cambiar entre providers configurados (primary → fallback → local → primary).
- Comando `/models` para listar modelos disponibles del provider activo (Ollama/llama.cpp).
- Comando `/use <model>` para seleccionar un modelo del provider activo.
- `ProviderClient.list_models()` — consulta Ollama `/api/tags` y fallback a `/v1/models`.
- `ProviderManager.list_available()` y `set_model()` para switching en runtime.
- TUI usa `active_provider` para routing de chat (antes hardcodeado a "primary").

## [0.3.0] - 2026-04-02

### Added

- Directorio `src/bytia_kode/prompts/` con la identidad constitucional `core_identity.yaml`.
- Subpaquete `bytia_kode.prompts` para distribuir recursos internos del proyecto.
- Script `scripts/validate_metadata.py` para validar versión, autoría, documentación y limpieza mínima.
- Script `scripts/check_secrets.py` para escaneo de secrets en pre-commit.
- Script `scripts/benchmark_io.py` para benchmark comparativo secuencial vs concurrente.
- Hook versionado en `.githooks/pre-commit` con validación, secret scan y tests.
- Workflow de GitHub Actions para validación, tests, build y verificación del wheel.
- Sección de seguridad y rendimiento en auditoría profesional.

### Changed

- Refactor completo de `agent.py` para cargar la identidad con `importlib.resources`.
- Extracción de `_handle_tool_calls()` desde `chat()` para mejorar legibilidad.
- BashTool migrado a `asyncio.create_subprocess_exec` (I/O no bloqueante).
- FileReadTool y FileWriteTool migrados a `asyncio.to_thread` para I/O de disco.
- Input sanitizado: `_sanitize_user_message()` filtra caracteres no imprimibles.
- Error recovery: `chat()` captura `TimeoutError`, `ConnectionError`, `RuntimeError`, `httpx.HTTPError` y preserva historial.
- Memoria con carga estricta (error en JSON corrupto) y contexto acotado (20 entries / 2000 chars).
- Telegram en modo fail-secure (denegar por defecto sin allowlist).
- Errores internos ocultos al usuario de Telegram (solo en logs).
- Metadatos del paquete alineados en `pyproject.toml` con versión `0.3.0`.

### Security

- **SEC-001**: Mitigado — BashTool con allowlist de binarios, `shell=False`, `shlex.split()`.
- **SEC-002/003**: Mitigado — `_resolve_workspace_path()` impide path traversal.
- **SEC-005**: Mitigado — Telegram fail-secure por defecto.

### Performance

- Motor I/O asíncrono validado con benchmark: **4.90x speedup** (79.6% mejora) en ejecución concurrente vs secuencial.

### Fixed

- Eliminación de advertencias `Duplicate name` durante la construcción del wheel.
- Corrección de errores en el manejo del prompt multilinea de la TUI.
- Corrección de la carga del system prompt para editable y wheel instalado.
- `python3` añadido al allowlist de BashTool (`sys.executable` resuelve a `python3`).
- Eliminación de imports y logger duplicados en `registry.py`.

### Validation

- 17 tests pasando.
- Pre-commit hook: validación de metadatos + secret scan + pytest.
- `uv build` completado sin warnings.
