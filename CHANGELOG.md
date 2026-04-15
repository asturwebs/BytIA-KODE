# Changelog

Todos los cambios relevantes del proyecto se documentan en este archivo.

## [Unreleased]

### Added
- _No hay cambios aún._

## [0.7.0] - 2026-04-15

### Added
- Circuit Breaker pattern for provider auto-fallback (CLOSED → OPEN → HALF_OPEN)
- `providers/circuit.py` — new `CircuitBreaker` class with configurable threshold and recovery
- `ProviderManager.get_healthy()` — returns first available provider by priority
- `ProviderManager.report_success/failure()` — feedback loop for circuit state
- `ProviderManager.get_status()` — circuit state for debugging/UI
- `Agent.chat()` automatic fallback to next provider on failure
- System messages in TUI and Telegram when provider switches
- 24 new tests (8 CircuitBreaker + 7 ProviderManager + 3 Agent fallback + 6 existing fixed)

## [0.6.1] - 2026-04-13

### Fixed

- **Agentic loop infinite restart (CRÍTICO)** — El patrón `for...else: continue` en `Agent.chat()` causaba que la respuesta del asistente nunca se guardara al completarse el stream. El modelo recibía los mismos mensajes otra vez y generaba otra respuesta, repitiendo hasta 50 iteraciones. Afectaba tanto TUI como Telegram. Fix: eliminar `else: continue`, añadir guard de cancelación explícito tras el stream.
- **Cancelación con respuesta parcial** — Al cancelar (Escape/Ctrl+K) durante el stream, la respuesta parcial ahora se guarda en `self.messages` y se persiste en la sesión. Antes se perdía.
- **ToolRegistry.execute() rechazaba `on_subprocess`** — El commit de Panic Buttons (v0.6.0) añadió `on_subprocess` a la llamada de `Agent._handle_tool_calls()` pero nunca actualizó `ToolRegistry.execute()` para aceptarlo. Toda tool call fallaba con `TypeError: got an unexpected keyword argument 'on_subprocess'`. Estaba enmascarado por el bug del bucle infinito (las tools nunca llegaban a ejecutarse). Fix: añadir `on_subprocess` como keyword-only param al registry y reenviarlo al tool.

### Tests

- 6 tests nuevos (`test_agentic_loop.py`): verificación de terminación del loop, persistencia, cancelación, y que el provider se llama exactamente 1 vez (no en bucle).
- **112 tests** total (6 nuevos para agentic loop).
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y [Semantic Versioning](https://semver.org/lang/es/).

## [0.6.0] - 2026-04-12

### Added

- **Panic Buttons (#1)** — Cancelación de dos niveles para el agente:
  - **Interrupt** — `Escape` (TUI) / `/stop` (Telegram): para generación/tool actual, agente sigue vivo
  - **Kill** — `Ctrl+K` (TUI) / `/kill` (Telegram): cancelación nuclear + kill subprocess + cleanup de widgets
  - `Agent.interrupt()` / `Agent.kill()` — mecanismo basado en `threading.Event` + subprocess tracking
  - Cancelación checkeada en cada chunk del stream SSE y antes de ejecutar tool calls
- **Telegram guard** — No apila mensajes mientras procesa (race condition previa). Responde con aviso de usar `/stop`.
- **Auto-selección de skills** — `get_relevant()` conectado al system prompt. Skills relevantes al query del usuario se inyectan automáticamente con su contenido completo. Antes solo se inyectaba el summary de todas las skills.
- **BashTool subprocess tracking** — `on_subprocess` callback registra el proceso activo, permitiendo kill desde Panic Buttons.
- **Native exploration tools** — `GrepTool`, `GlobTool`, `TreeTool` implementadas en Python puro, sin depender de bash allowlist. GrepTool busca regex en archivos con filtro include. GlobTool encuentra archivos por patrón. TreeTool muestra estructura de directorios con tamaños y control de profundidad.
- **Panic Buttons en menú Ctrl+P** — Interrupt y Kill añadidos al menú de comandos (22 items).
- **Banner actualizado** — Muestra atajos de Panic Buttons: `Esc stop | Ctrl+K kill`.
- **`/session` command** — Muestra sesión activa (ID + nº de mensajes). Disponible como comando y en Ctrl+P.
- **Reasoning persistence** — El razonamiento/thinking del modelo se guarda en la sesión con tags `<reasoning>`. Al cargar una sesión anterior, el modelo ve su propio razonamiento previo, mejorando coherencia.
- **106 tests** — 5 tests nuevos de persistencia de respuesta (user+assistant siempre guardados, reasoning preservado, roundtrip completo).

### Fixed

- **`load_session_by_id` crash** — Asignaba `list[dict]` a `list[Message]` (type mismatch). Ahora usa `_load_messages_from_store()` que convierte dicts a objetos Message.
- **`_persisted_count` no actualizado al cargar sesión** — Causaba re-inserción masiva de mensajes en SQLite. Ahora se actualiza en `load_session_by_id()`.
- **Regex code blocks** — `action_copy_last_code` no capturaba bloques sin language tag ni con guiones (`c++`, `objective-c`). Fix: `[a-zA-Z0-9_+-]*\n?`.
- **Sandbox bypass** — `cat`, `head`, `tail` eliminados de bash allowlist. Permitían leer cualquier archivo saltándose el sandbox de `file_read`. Ahora `file_read` es la única vía de lectura.
- **Session auto-cleanup removido** — Las sesiones persisten indefinidamente hasta borrado manual. El método `cleanup_empty_sessions()` queda disponible para uso manual.

### Changed

- `_build_system_prompt()` — Inyecta skills relevantes al query (hasta 5) con contenido completo, no solo summary.
- BashTool `execute()` — Nuevo parámetro `on_subprocess` para tracking del proceso activo.
- `_DEFAULT_BINARIES` — 27 → 24 binarios (eliminados `cat`, `head`, `tail`).
- `_handle_tool_calls()` — Pasa callback `on_subprocess` a `execute()`.
- Telegram `Bot._chat()` — Guard con `_processing` set para evitar mensajes concurrentes.
- Agent `__init__` — `_cancel_event` (threading.Event), `_active_subprocess`, `on_subprocess` callback list.

### Tests

- 101 passed (19 nuevos: GrepTool 5, GlobTool 5, TreeTool 6, PanicButtons 3).

## [0.5.6] - 2026-04-12

### Fixed

- **file_read sandbox bug** — Symlinked kernel/runtime YAML files resolved outside workspace via `.resolve()`, triggering "path escapes workspace" error. Fix: added `~/bytia/` as trusted path + `_WORKSPACE_ROOT` for stable path resolution regardless of CWD changes.
- **`core_identity.yaml` removed** — Legacy v12.1.0 monolithic SP was still present but unused since RFC-001. Contradicted Kernel v12.3.0 (7 anchors vs 4, different protocol naming). Archived to `prompts/legacy/`.

### Changed

- `registry.py`: `_resolve_workspace_path()` uses `_WORKSPACE_ROOT` (set at startup) instead of `Path.cwd()` for relative path resolution. New `set_workspace_root()` function.
- `agent.py`: Added `~/bytia/` as trusted path + calls `set_workspace_root()` at init. Updated docstring.

## [0.5.5] - 2026-04-10

### Added

- **B-KODE.md** — Instrucciones de proyecto con rutas a skills, memoria, intercom, logs y sesiones. Protocolo de comunicación inter-agente, sistema de memoria y reglas de seguridad (sin secrets). Se carga automáticamente al iniciar.
- **Template variable interpolation** — `{{engine_id}}`, `{{context_limit}}`, `{{max_output}}`, `{{environment}}`, `{{engine_family}}` en `core_identity.yaml` se resuelven en runtime con info del provider (lazy, después de auto-detect model).
- **`_FAMILY_MAP`** — Mapeo de prefijos de modelo a fabricante (gemma→Google, glm→Zhipu AI, llama→Meta, etc.) para el Hard Identity Override.
- **Configurable LLM params** — `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT` en `.env`.
- **Retry con backoff** — `_request_with_retry()` reintenta 5xx y timeout/connection errors hasta 2 veces con exponential backoff (1s, 2s). Solo en `chat()` no-streaming.
- **Connection pool limits** — httpx client con `max_connections=10`, `max_keepalive_connections=5`.

### Changed

- **`list_models()`** — Invertido el orden: `/v1/models` (OpenAI/llama.cpp) primero, `/api/tags` (Ollama) como fallback. Early return si el primer intento tiene resultados.
- **`detect_loaded_model()`** — Error handling diferenciado: `ConnectError` (warning) vs otros (error). Antes silenciaba todas las excepciones.
- **Tool call argument parsing** — Cuando JSON decode falla, se envía error al modelo con los primeros 500 chars del raw input. Antes se silently fallback a `{}`.
- **Token estimation** — Heurística ASCII-aware: `chars/3.5` para texto mayoritariamente ASCII (código), `chars/3.0` para texto mixto (español). Reemplaza `chars/3` fijo.
- **`_estimate_tokens()`** — Cuenta argumentos de tool calls en vez de `str(tc)` del modelo Pydantic completo.
- **Router polling** — Exponential backoff en `_poll_router_info()`: 5s→10s→20s→40s→60s (cap) tras fallos consecutivos. Reset a 5s en éxito.
- **`update_context_limit()`** — Marca `_identity_dirty=True` para re-interpolar template vars cuando cambia el context window.
- **Test actualizado** — `test_static_method_unicode` usa rango en vez de valor exacto para la nueva heurística.

### Security

- **`~/.bytia-kode/skills/agent-intercom/SKILL.md`** — Token de Telegram hardcoded reemplazado por `$TELEGRAM_BOT_TOKEN` env var. Añadido `TELEGRAM_CHAT_ID` a `.env`.

### Tests

- 82 passed (1 actualizado por nueva heurística de tokens).

## [0.5.4] - 2026-04-10

### Added

- **Sistema de memoria persistente** — Directorio `~/.bytia-kode/memoria/` con 4 categorías (`procedimientos/`, `contexto/`, `tecnologia/`, `decisiones/`) + `index.md` auto-generable. Permite al agente almacenar conocimiento entre sesiones.
- **Skill `memory-manager`** — Procedimientos para almacenar (`memory_store`), buscar (`memory_search`), indexar (`memory_index`) y leer (`memory_read`) memoria. Trigger: memory, recordar, guardar conocimiento, memoria, aprendido, lección.
- **Trusted paths en sandbox** — `_resolve_workspace_path()` acepta directorios confiados además del workspace. `set_trusted_paths(paths)` en `registry.py`. `Agent.__init__()` registra `data_dir` como trusted path. Permite al agente escribir en `~/.bytia-kode/` desde cualquier proyecto.
- **Allowlist expandida** — BashTool: 27 binarios permitidos (antes 13). Nuevos: `mv`, `cp`, `rm`, `head`, `tail`, `wc`, `date`, `chmod`, `curl`, `wget`, `scp`, `ssh`, `pip`, `pip3`.
- **`EXTRA_BINARIES` configurable** — Campo `extra_binaries` en `AppConfig` (`.env`). Merge con `_DEFAULT_BINARIES` vía set union. Solo puede expandir, nunca reducir la sandbox.
- **Skill `graphify`** — Análisis de código con knowledge graphs via tree-sitter. Instalación: `uv tool install graphifyy`. Requiere `EXTRA_BINARIES=graphify` en `.env`.

### Changed

- **`_resolve_workspace_path()`** — Añadido fallback a trusted paths cuando el path no está dentro del workspace.
- **`Agent.__init__()`** — Registra `config.data_dir` como trusted path al inicializar.
- **B-KODE.md** — Sección Memory System, trusted paths en Security, tabla de skills actualizada, versión 0.5.3→0.5.4.
- **CONTEXT.md** — Allowlist actualizada a 27 binarios, trusted paths documentados.

### Tests

- 5 nuevos tests (82 total):
  - `test_trusted_paths_allow_write_outside_workspace` — Verifica escritura en trusted path desde workspace remoto.
  - `test_trusted_paths_do_not_bypass_arbitrary_paths` — Verifica que paths arbitrarios siguen bloqueados.
  - `test_memory_manager_skill_loads` — Verifica carga de la skill memory-manager.
  - `test_extra_binaries_merged_from_env` — Verifica merge de EXTRA_BINARIES con defaults.
  - `test_extra_binaries_empty_env_uses_defaults` — Verifica defaults sin EXTRA_BINARIES.

### Architecture

- **RFC-001**: Migrated from monolithic `core_identity.yaml` to BytIA OS Kernel + Runtime
- Kernel `bytia.kernel.yaml` v12.3.0: 4 anchors, Truth-First thresholds, O16/O17 directives
- Runtime `bytia.runtime.kode.yaml` v1.0.0: TUI-specific capabilities, tools, session system
- `agent.py`: new `_load_yaml_resource()` + dual-file merge via `importlib.resources`
- Legacy `core_identity.yaml` archived

### Changed

- **Naming**: `core_identity.yaml` → `bytia.kernel.yaml` + `bytia.runtime.kode.yaml` (symlinks)

### Security

- **BashTool: shell operator validation** — `create_subprocess_exec` no interpreta operadores shell (`|`, `&&`, `>`, `<<`, `;`, `$()`, backticks). Nuevo método `_validate_command_safety()` rechaza operadores shell con mensaje claro.
- **Tool description updated** — `BashTool.description` indica "SINGLE shell command, no pipes/chains/redirects/heredocs".

### Fixed

- **BUG CRÍTICO: BashTool heredoc explosion** — `shlex.split()` rompía heredocs y `create_subprocess_exec` ejecutaba `mkdir` con contenido markdown como argumentos, creando 48 directorios basura. Fix: validación pre-ejecución que bloquea operadores shell.

## [0.5.3] - 2026-04-07

### Added

- **TTS (Text-to-Speech)** — Botón 🔊 Escuchar en cada respuesta del asistente. Genera audio con edge-tts (voz `es-MX-DaliaNeural`) y lo reproduce con mpv.
  - Toggle play/stop: click para reproducir, click de nuevo para parar.
  - Limpieza automática de Markdown, código, URLs y emojis antes de TTS.
  - Audio temporal en `/tmp/bytia_audio/`.
  - Módulo: `src/bytia_kode/audio.py`.

### Dependencies

- **edge-tts** (CLI) — Generación de voz neuronal (Microsoft Edge). Instalar: `uv tool install edge-tts`
- **mpv** — Reproductor de audio CLI. Instalar: `sudo apt install mpv`

## [0.5.2] - 2026-04-07

### Added

- **Logging a archivo** — Sistema de logging con `RotatingFileHandler` en `~/.bytia-kode/logs/bytia-kode.log`. Rotación 1MB, 3 backups. Nivel configurable vía `LOG_LEVEL` en `.env`. Custom path vía `LOG_FILE`.
- **`read_context` tool** — Tool que lee el contexto del workspace actual (lenguaje, estructura, git, B-KODE.md). Auto-genera el archivo si no existe. Storage: `~/.bytia-kode/contexts/<hash>.md`.
- **`/context` command** — Regenera el CONTEXT.md del workspace actual (TUI + Telegram).
- **`context.py` module** — Detección automática de workspace: lenguaje, framework, estructura de directorios, git info, B-KODE.md.
- **B-KODE.md: Context nudge** — Instruye al agente a usar `read_context` para estado operativo del workspace.
- **Copy last response (`Ctrl+Shift+C`)** — Copia la respuesta completa del último mensaje del agente al portapapeles.
- **Banner actualizado** — Muestra comandos disponibles: `/reset · /model · /context · /help | Ctrl+P menu`.
- **Info-line con `/context`** — Referencia visual al comando de contexto en la barra de estado.

### Fixed

- **Logging no se activaba** — `_setup_logging()` estaba en `__main__.py` pero el entry point de `uv tool` (`bytia_kode.tui:run_tui`) lo saltaba. Movido a `__init__.py` para ejecutarse en cualquier punto de entrada.
- **Provider errors no visibles (Issue #2)** — Errores del proveedor ahora se muestran inmediatamente en la TUI con estilo de error, y el historial se mantiene balanceado.
- **CI test compatibility** — Tests adaptados para funcionar sin modelo cargado en el router (`_initialized = True` para saltar `auto_detect_model`).

### Changed

- **CONTEXT.md** — Eliminado del tracking git. Ahora es local-only (`.gitignore`). Auto-generado por workspace.
- **`.gitignore`** — Añadido `CONTEXT.md`.
- **`.env.example`** — Añadido `LOG_FILE=`.
- **`config.py`** — Nuevo campo `log_file` en `AppConfig`.
- **Versión** — `0.5.1` → `0.5.2`.

### Issues

- **#1** — feat: Panic Buttons — Interrupt (Escape) + Kill (Ctrl+K) — Roadmap v0.5.2
- **#2** — bug: Provider errors not shown to user after reasoning + stuck conversation state

## [0.5.1] - 2026-04-06

### Added

- **Auto-resumen de sesión anterior** — Al iniciar una conversación, el system prompt incluye automáticamente un resumen compacto de la última sesión del mismo source (TUI o Telegram): título, fecha, nº mensajes y los últimos 3 mensajes truncados. El modelo puede usar `session_load` para obtener contexto completo si lo necesita.

### Changed

- **core_identity.yaml: capacidades actualizadas** — Añadidas session tools (`session_list`, `session_search`, `session_load`) a la lista de capacidades del runtime. Añadidos comandos `/sessions`, `/load <id>`, `/new` a la lista de comandos disponibles.
- **core_identity.yaml: directiva de tools proactivas** — Reemplazada "Usar herramientas solo cuando sean verificación" por directiva expandida que permite uso proactivo de tools (verificación, contexto histórico, archivos).
- **core_identity.yaml: directivas de session tools** — Nuevas directivas que instruyen al modelo a usar `session_search` cuando el usuario pregunte sobre trabajo anterior, y a revisar el resumen de sesión anterior inyectado automáticamente.

### Tests

- 5 nuevos tests en `TestPreviousSessionSummary`: sin sesiones previas, resumen con sesión anterior, exclusión de sesión actual, filtro por source, y límite de 3 mensajes.

## [0.5.0] - 2026-04-06

### Added

- **Persistencia de sesiones (SQLite WAL)** — Sistema completo de sesiones persistentes con almacenamiento SQLite en modo WAL (Write-Ahead Logging). Todas las conversaciones se guardan automáticamente en tiempo real. O(1) por mensaje (append-only INSERT). Transacciones ACID. Concurrencia segura entre TUI y Telegram.
- **`session.py`** — `SessionStore` con métodos: `create_session()`, `append_message()`, `load_messages()`, `get_metadata()`, `list_sessions()`, `search_sessions()`, `delete_session()`, `get_session_context()`, `update_title()`. `SessionMetadata` dataclass con slots para metadata ligera.
- **Auto-save en `Agent.chat()`** — Después de cada intercambio user→assistant, los mensajes se persisten automáticamente. Tool results también se auto-guardan. Título auto-generado desde el primer mensaje del usuario.
- **Auto-save en `Agent._handle_tool_calls()`** — Resultados de tools persistidos automáticamente con tool_call_id y nombre.
- **Session tools para el modelo** — Tres nuevas tools que permiten al agente acceder a sesiones pasadas:
  - `session_list` — listar sesiones (filtro por source opcional)
  - `session_load` — cargar contexto de una sesión pasada
  - `session_search` — buscar sesiones por título
- **Comandos de sesión en TUI** — `/sessions` (lista sesiones en tabla), `/load <id>` (cambia a otra sesión), `/new` (crea sesión nueva con auto-save)
- **Sesión auto-creada en TUI** — Al arrancar, la TUI crea automáticamente una sesión TUI con auto-save habilitado.
- **Aislamiento por usuario en Telegram** — Cada `chat_id` tiene su propia instancia de `Agent` con su propia sesión. Antes, todos los usuarios compartían el mismo historial (bug crítico de privacidad).
- **Comando `/sessions` en Telegram** — Lista las sesiones del usuario.
- **19 tests de SessionStore** — Cubren lifecycle, messages, list/search, delete, title, context y edge cases.

### Changed

- **`MAX_CONTEXT_TOKENS`** — Subido de 16k a 128k. Los modelos GGUF locales como Gemma 4 26B soportan 256k tokens. El valor se sobreescribe dinámicamente vía router info si está disponible.
- **Telegram bot** — Reescrito con `_agents: dict[str, Agent]` para aislamiento por `chat_id`. `_get_agent()` crea o recupera la sesión del usuario.
- **`Agent.__init__`** — Acepta `session_store: SessionStore | None`. Registra session tools automáticamente.
- **Tabla de ayuda TUI** — Añadidos `/sessions`, `/load`, `/new` con descripciones.

### Fixed

- **BUG CRÍTICO Telegram** — `config` usado en vez de `self.config` en `_get_agent()` (líneas 30, 34). Causaba `NameError` al crear agentes para usuarios de Telegram.
- **BUG SQLite** — `create_session()` tenía 4 columnas pero solo 3 placeholders en INSERT. Causaba `OperationalError: 3 values for 4 columns`.

### Security

- **Telegram: aislamiento por chat_id** — Antes del fix, todos los usuarios de Telegram compartían un solo Agent y un solo historial. Violación de privacidad corregida con instancias separadas por chat_id.

### Schema de base de datos

```sql
-- Sesiones: metadata con índices por source y fecha
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,           -- 'tui' | 'telegram'
    source_ref TEXT,                -- chat_id para telegram
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    model TEXT,
    is_active INTEGER DEFAULT 1
);

-- Mensajes: append-only, O(1) por INSERT
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    seq_num INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,                -- JSON serializado
    tool_call_id TEXT,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

### Almacenamiento

```
~/.bytia-kode/
├── sessions.db           # SQLite con WAL mode
├── sessions.db-wal       # Write-Ahead Log (auto)
├── sessions.db-shm       # Shared memory (auto)
└── skills/               # Skills existentes
```

### Total tests: 46 (19 session + 14 file_edit + 13 context_management)

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
- `SkillLoader.list_skill_names()`, `get()`, `verify_skill()` — gestión CRUD de skills.
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
