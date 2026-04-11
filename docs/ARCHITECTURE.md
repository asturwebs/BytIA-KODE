# Arquitectura técnica

Documento actualizado para la release 0.5.0.

## Entrada principal

- `src/bytia_kode/__main__.py`: TUI por defecto, `--bot` para Telegram.

## Interfaces

- `src/bytia_kode/tui.py` — interfaz Textual TUI (19 temas, streaming, reasoning, sesiones)
- `src/bytia_kode/telegram/bot.py` — bot con fail-secure, aislamiento por chat_id, sesiones
- `src/bytia_kode/audio.py` — TTS con edge-tts + mpv (toggle play/stop, limpieza de Markdown)

## Núcleo del agente

- `src/bytia_kode/agent.py`

Responsabilidades:

- mantener mensajes de conversación
- cargar la identidad constitucional empaquetada
- construir el prompt del sistema (identidad + B-KODE.md + skills + memoria)
- invocar el provider con streaming SSE y manejo de tool calls
- delegar ejecución de tool calls a `_handle_tool_calls()`
- sanitizar input del usuario (no imprimibles filtrados)
- gestionar ventana de contexto (`_manage_context()` comprime mensajes antiguos)
- buscar B-KODE.md con walk-up desde CWD
- **gestionar sesiones persistentes** (auto-save, load, list, context)

### Flujo de `chat()` (streaming)

```
validar input → registrar user msg → iterar:
    llamar provider.chat_stream() → yield chunks:
        ("text", delta)         → yield al TUI para render streaming
        ("reasoning", delta)    → yield al TUI para ThinkingBlock
        ("tool_calls", [TC])    → acumular, ejecutar al final del chunk
    registrar assistant msg con content y/o tool_calls
    AUTO-SAVE: append user msg + assistant msg a sesión activa
    si tool_calls → _handle_tool_calls() → registrar tool results → AUTO-SAVE → continuar
excepciones → yield error (NO se persiste en historial)
```

### Gestión de contexto

- `MAX_CONTEXT_TOKENS = 131072` (128k) — fallback cuando el router no devuelve ctx-size (para modelos GGUF con 256k)
- `_estimate_tokens()`: heurística chars/3 para uso de sesión
- `get_router_info()`: extrae ctx-size real de los args del modelo (`--ctx-size`) vía `/v1/models`
- `_manage_context()`: cuando se supera 75% del límite, comprime los 2 mensajes más antiguos en un resumen de sistema

### B-KODE.md

Fichero de instrucciones a nivel proyecto. Se busca desde CWD hacia arriba hasta la raíz del filesystem. Si existe, se inyecta en el system prompt después de la identidad constitucional y antes del resumen de skills.

## Sesiones Persistentes

- `src/bytia_kode/session.py` — SQLite WAL-backed session store

### Diseño

Las sesiones se almacenan en `~/.bytia-kode/sessions.db` en modo WAL (Write-Ahead Logging). Este diseño fue seleccionado tras revisión de alternativas (JSON + file locking vs SQLite WAL) por:

- **Concurrencia** — WAL permite múltiples lectores y un escritor simultáneo (TUI + N workers Telegram)
- **I/O O(1)** — Solo INSERT por mensaje, nunca reescribe el historial completo
- **Durabilidad** — Transacciones ACID nativas de SQLite
- **Búsqueda** — Índices SQL para list/filter/search sin parsear archivos

### Schema

```sql
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

### Flujo de datos

```
Usuario envía mensaje
  → Agent.chat() añade Message(role="user") a self.messages
  → Provider responde
  → Agent.chat() añade Message(role="assistant") a self.messages
  → AUTO-SAVE: SessionStore.append_message() × 2 (user + assistant)
  → Si primer mensaje: SessionStore.update_title() (auto-título)
  → Si tool_calls: _handle_tool_calls()
    → Tool ejecutada
    → AUTO-SAVE: SessionStore.append_message() (tool result)
```

### Almacenamiento

```
~/.bytia-kode/
├── sessions.db           # SQLite database
├── sessions.db-wal       # Write-Ahead Log (auto, gestiona concurrencia)
├── sessions.db-shm       # Shared memory (auto, para lectores concurrentes)
└── skills/
```

### Conexiones

`SessionStore` usa una conexión por método (no thread sharing). Cada operación abre y cierra su propia conexión SQLite. Esto elimina problemas de concurrencia sin necesidad de locks a nivel de aplicación.

## Providers

- `providers/client.py` — cliente HTTP async (httpx) con streaming SSE, `list_models()` y `get_router_info()`
- `providers/manager.py` — gestión de provider primario, fallback y local con `list_available()` y `set_model()`

### Streaming SSE

`chat_stream()` consume el endpoint `/v1/chat/completions` con `stream=True`. Yield tuples:

| Tipo | Contenido | Origen |
| --- | --- | --- |
| `("text", str)` | Delta de texto visible | `choices[0].delta.content` |
| `("reasoning", str)` | Delta de razonamiento | `choices[0].delta.reasoning_content` (DeepSeek) o `.reasoning` (Gemma 4) |
| `("tool_calls", [ToolCall])` | Tool calls completadas | Acumuladas por índice SSE |

### Switching

`F3` en la TUI alterna entre providers configurados. El provider activo determina a qué endpoint se envían los mensajes. Al cambiar, la ActivityIndicator se actualiza dinámicamente.

## TUI (Textual)

### Composición de widgets

```text
compose():
  Header (show_clock=True)
  VerticalScroll (#chat-area)
    → Banner (Panel ASCII)
    → Info line (B-KODE status, versión)
    → ChatMessage widgets (user/assistant/tool/error)
    → ThinkingBlock widgets (razonamiento colapsable)
    → ToolBlock widgets (ejecución de tools colapsable)
    → System messages
  ActivityIndicator (estado + modelo + contexto)
  Horizontal (#input-area)
    → PromptTextArea (#input-field)
    → Button (#send-button)
  Footer (solo "Menu (Ctrl+P)")
```

### Widgets custom

| Widget | Función |
| --- | --- |
| `ChatMessage` | Mensaje con Panel temático (user=secondary, assistant=accent, tool=warning, error=error) |
| `ThinkingBlock` | Razonamiento colapsable. Click o Ctrl+D para toggle. `can_focus = True`. |
| `ToolBlock` | Ejecución de tools colapsable. Muestra nombre y output. Click para toggle. Color coding: ✅ verde / ❌ rojo. |
| `ActivityIndicator` | Barra de estado: `● Ready | provider | model | ctx ~Xk/Yk`. Polling cada 5s. Estados: Thinking (◐), Tool (⚙), Ready (●). |
| `CommandMenuScreen` | Modal con ListView de comandos. Se abre con Ctrl+P. |
| `PromptTextArea` | TextArea con `Submitted` message en Enter. |

### Sesiones en la TUI

- Al montar (`on_mount`), la TUI crea automáticamente una sesión TUI con auto-save.
- `/sessions` muestra tabla con ID, source, título, mensajes y fecha de las sesiones guardadas.
- `/load <id>` reemplaza el historial actual con los mensajes de la sesión seleccionada.
- `/new` limpia la conversación y crea una sesión nueva.
- `/reset` limpia la conversación en memoria pero no borra la sesión del disco.

## Telegram Bot

### Arquitectura

El bot mantiene un diccionario `_agents: dict[str, Agent]` donde la clave es el `chat_id` (string del user ID de Telegram). Cada usuario tiene su propia instancia de `Agent` con su propia sesión persistente.

```python
class TelegramBot:
    def __init__(self, config):
        self.session_store = SessionStore(config.data_dir / "sessions.db")
        self._agents: dict[str, Agent] = {}

    def _get_agent(self, chat_id: str) -> Agent:
        if chat_id not in self._agents:
            session_id = f"telegram_{chat_id}"
            if self.session_store.get_metadata(session_id):
                agent = Agent(self.config)
                agent.load_session_by_id(session_id)  # Resume sesión existente
            else:
                agent = Agent(self.config)
                agent.set_session(source="telegram", source_ref=chat_id)  # Nueva sesión
            self._agents[chat_id] = agent
        return self._agents[chat_id]
```

### Seguridad

- **Fail-secure**: sin `allowed_users` configurado, todo se deniega.
- **Aislamiento**: cada `chat_id` tiene su propia sesión e historial.
- **Acceso cruzado**: el modelo puede usar `session_list(source="telegram")` para acceder a sesiones de Telegram desde la TUI.

## Tools

- `tools/registry.py` — registro y ejecución de tools
- `tools/session.py` — tools de sesión (session_list, session_load, session_search)
- Tools actuales: `bash`, `file_read`, `file_write`, `file_edit`, `web_fetch`, `session_list`, `session_load`, `session_search`

### Seguridad de tools

- **BashTool**: allowlist de binarios (`ls`, `pwd`, `cat`, `echo`, `git`, `grep`, `find`, `mkdir`, `touch`, `uv`, `python`, `python3`, `wsl`). Ejecuta con `asyncio.create_subprocess_exec` (sin `shell=True`). Directorio de trabajo confinado al workspace. **Validación de operadores shell**: `_validate_command_safety()` rechaza `|`, `&&`, `||`, `>`, `>>`, `<<`, `;`, `$()`, backticks antes de la ejecución. Estos operadores no se interpretan por `subprocess.exec` y se pasan como argumentos literales al binary, causando resultados catastróficos (ej: heredoc roto → decenas de directorios basura). El LLM recibe mensaje de error con guidance para usar `file_write`/`file_edit` y llamar a `bash` múltiples veces.
- **FileReadTool / FileWriteTool**: `_resolve_workspace_path()` impide path traversal. I/O delegado a `asyncio.to_thread` para no bloquear el event loop.
- **FileEditTool**: search/replace + create. Backup automático con timestamp. Diff unificado. `_no_match_help` con diagnósticos de partial match.
- **WebFetchTool**: HTTP GET via httpx. Solo URLs http/https. Validación de content-type (text/*, json, xml). HTML se convierte a texto plano (tag stripping). Truncation a 30k chars. Timeout configurable (15s default).
- **Session tools**: Solo lectura. Listan, buscan y cargan contexto de sesiones almacenadas.

### Tools con dependencias

Las session tools (`session_list`, `session_load`, `session_search`) necesitan acceso al `SessionStore`. Se inyectan vía constructor:

```python
class SessionListTool(Tool):
    def __init__(self, session_store: SessionStore):
        self._store = session_store
```

El `Agent` registra estas tools automáticamente en `__init__` después de crear el store.

## Skills

- `skills/loader.py` — carga, búsqueda y gestión de skills persistentes

Skills son procedimientos reutilizables almacenados como archivos SKILL.md con frontmatter YAML (compatible agentskills.io).

**Directorio:** `~/.bytia-kode/skills/<skill-name>/SKILL.md`

**Capacidades actuales:**

- `load_all()`: escanea directorios y parsea SKILL.md files
- `save_skill()`: crea nueva skill con frontmatter auto-generado
- `get_relevant(query)`: búsqueda por scoring (trigger +3, description +2, content +1)
- `verify_skill()`: marca como verificada tras validación del usuario
- `skill_summary()`: genera resumen para inyección en system prompt

**Evolución prevista (v0.6.0):**

Las skills pasarán de instrucciones estáticas a unidades autónomas:
- **Tools dinámicas**: scripts en `skills/<name>/scripts/` auto-registrados como tools
- **Sub-agentes**: skill con SP propio que se ejecuta como agente dedicado
- **Skills Hub**: distribución desde repos GitHub
- **`write_skill` tool**: el agente crea skills programáticamente

---

## Stack Técnico (dependencias externas)

Librerías y frameworks que usamos, no creamos. Versión mínima según `pyproject.toml`.

### Core runtime

| Paquete | Versión | Uso en BytIA KODE |
| --- | --- | --- |
| [Python](https://python.org) | >=3.11 | Runtime principal |
| [uv](https://docs.astral.sh/uv/) | latest | Gestión de env, deps, build y tool install |
| [Hatchling](https://hatch.pypa.io/latest/) | latest | Build backend (`pyproject.toml`) |

### HTTP / Async

| Paquete | Versión | Uso |
| --- | --- | --- |
| [httpx](https://www.python-httpx.org/) | >=0.28 | Cliente HTTP async para providers OpenAI-compatible. Streaming SSE. |
| [anyio](https://anyio.readthedocs.io/) | >=4.13 | Backend async (dependencia de httpx). |

### TUI / Terminal

| Paquete | Versión | Uso |
| --- | --- | --- |
| [Textual](https://textual.textualize.io/) | >=8.2.1 | Framework TUI. App, Screens, Widgets, CSS, reactive, bindings. |
| [Rich](https://rich.readthedocs.io/) | >=14.0 | Renderizado: Markdown, Panel, Table, Syntax, Text, Box. Usado por Textual internamente. |

### Data / Config

| Paquete | Versión | Uso |
| --- | --- | --- |
| [Pydantic](https://docs.pydantic.dev/) | >=2.11 | Validación y serialización. `Message`, `ToolDef`, `ToolCall`, `ToolResult`. |
| [PyYAML](https://pyyaml.org/) | >=6.0 | Parseo de `core_identity.yaml` y frontmatter de skills. |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | >=1.1 | Carga de `.env` (CWD + `~/.bytia-kode/.env`). |

### Telegram

| Paquete | Versión | Uso |
| --- | --- | --- |
| [python-telegram-bot](https://docs.python-telegram-bot.org/) | >=22.0 | Bot de Telegram. API async v20+. |

### Dev dependencies

| Paquete | Versión | Uso |
| --- | --- | --- |
| [pytest](https://docs.pytest.org/) | >=9.0.2 | Tests unitarios. |
| [textual-dev](https://textual.textualize.io/dev/) | >=1.8.0 | Dev tools para Textual (CSS inspector, etc.). |
| [build](https://pypa-build.readthedocs.io/) | >=1.4.2 | Build del wheel. |
| [twine](https://twine.readthedocs.io/) | >=6.2.0 | Verificación del paquete antes de publish. |

### Optional dependencies

| Grupo | Paquetes | Uso |
| --- | --- | --- |
| `local` | llama-cpp-python>=0.3 | Inferencia local con GGUF |
| `memory` | sentence-transformers>=4.0, faiss-cpu>=1.11 | Búsqueda semántica en memoria |

### External CLI tools

| Herramienta | Instalación | Uso |
| --- | --- | --- |
| `edge-tts` | `uv tool install edge-tts` | TTS: generación de voz neuronal |
| `mpv` | `sudo apt install mpv` | Reproductor de audio para TTS |

---

## Limitaciones técnicas

- `safe_mode` no endurece todavía el backend.
- La memoria semántica avanzada sigue fuera de producción (requiere grupo `memory`).
- No hay auto-fallback de providers (circuit breaker pendiente).
- El estimador de tokens es una heurística (chars/3), no un tokenizer real.
- PromptTextArea no soporta Shift+Enter para newline (limitación de Textual).
