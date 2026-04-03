# Arquitectura técnica

Documento actualizado para la release 0.4.0 (unreleased).

## Entrada principal

- `src/bytia_kode/__main__.py`: TUI por defecto, `--bot` para Telegram.

## Interfaces

- `src/bytia_kode/tui.py` — interfaz Textual TUI (9 temas, streaming, reasoning)
- `src/bytia_kode/telegram/bot.py` — bot con fail-secure por defecto

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

### Flujo de `chat()` (streaming)

```
validar input → registrar user msg → iterar:
    llamar provider.chat_stream() → yield chunks:
        ("text", delta)         → yield al TUI para render streaming
        ("reasoning", delta)    → yield al TUI para ThinkingBlock
        ("tool_calls", [TC])    → acumular, ejecutar al final del chunk
    registrar assistant msg con content y/o tool_calls
    si tool_calls → _handle_tool_calls() → registrar tool results → continuar
excepciones → yield error (NO se persiste en historial)
```

### Gestión de contexto

- `MAX_CONTEXT_TOKENS = 16384` (configurable)
- `_estimate_tokens()`: heurística chars/3
- `_manage_context()`: cuando se supera 75% del límite, comprime los 2 mensajes más antiguos en un resumen de sistema

### B-KODE.md

Fichero de instrucciones a nivel proyecto. Se busca desde CWD hacia arriba hasta la raíz del filesystem. Si existe, se inyecta en el system prompt después de la identidad constitucional y antes del resumen de skills.

## Providers

- `providers/client.py` — cliente HTTP async (httpx) con streaming SSE y `list_models()`
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
| `ActivityIndicator` | Barra de estado: `● Ready | provider | model | ctx Xk/Yk`. Cambia a `◐ Thinking...` o `● Running: tool`. |
| `CommandMenuScreen` | Modal con ListView de comandos. Se abre con Ctrl+P. |
| `PromptTextArea` | TextArea con `Submitted` message en Enter. |

### ActivityIndicator estados

| Estado | Icono | Cuándo |
| --- | --- | --- |
| `ready` | `●` (green) | Idle, esperando input |
| `thinking` | `◐` (warning) | Provider procesando |
| `tool` | `●` (accent) | Ejecutando tool: nombre |
| `error` | `✗` (red) | Error del provider |
| `skill` | `✎` (warning) | Procesando skill |

## Tools

- `tools/registry.py` — registro y ejecución de tools
- Tools actuales: `bash`, `file_read`, `file_write`

### Seguridad de tools

- **BashTool**: allowlist de binarios (`ls`, `pwd`, `cat`, `echo`, `git`, `grep`, `find`, `mkdir`, `touch`, `uv`, `python`, `wsl`). Ejecuta con `asyncio.create_subprocess_exec` (sin `shell=True`). Directorio de trabajo confinado al workspace.
- **FileReadTool / FileWriteTool**: `_resolve_workspace_path()` impide path traversal. I/O delegado a `asyncio.to_thread` para no bloquear el event loop.

## Skills

- `skills/loader.py` — carga, búsqueda y gestión de skills persistentes

Skills son procedimientos reutilizables almacenados como archivos SKILL.md con frontmatter YAML (compatible agentskills.io).

**Directorio:** `~/.bytia-kode/skills/<skill-name>/SKILL.md`

**Capacidades:**

- `load_all()`: escanea directorios y parsea SKILL.md files
- `save_skill()`: crea nueva skill con frontmatter auto-generado
- `get_relevant(query)`: búsqueda por scoring (trigger +3, description +2, content +1)
- `verify_skill()`: marca como verificada tras validación del usuario
- `skill_summary()`: genera resumen para inyección en system prompt

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

---

## Limitaciones técnicas

- `safe_mode` no endurece todavía el backend.
- La memoria semántica avanzada sigue fuera de producción (requiere grupo `memory`).
- No hay auto-fallback de providers (circuit breaker pendiente).
- Telegram comparte un solo Agent entre todos los usuarios.
- El估算 de tokens es una heurística (chars/3), no un tokenizer real.
