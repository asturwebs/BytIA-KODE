# Guía de Desarrollo

## Estructura del proyecto

```text
src/bytia_kode/
├── __main__.py              # Entry point: TUI (default) / --bot (Telegram)
├── agent.py                 # Núcleo agéntico: loop, tools, contexto, system prompt, sesiones
├── session.py               # Persistencia de sesiones: SQLite WAL
├── tui.py                   # Interfaz Textual: widgets, bindings, streaming, sesiones
├── config.py                # Config desde .env + dataclasses
├── providers/
│   ├── client.py            # Cliente HTTP async (httpx), streaming SSE, get_router_info
│   └── manager.py           # Multi-provider: primary, fallback, local
├── tools/
│   ├── registry.py          # Tool base class + registry (bash, file_read, file_write, file_edit, web_fetch)
│   └── session.py          # Session tools (session_list, session_load, session_search)
├── skills/
│   └── loader.py            # Carga, búsqueda, scoring y persistencia de skills
├── prompts/
│   ├── bytia.kernel.yaml          # Kernel v12.3.0 (symlink → ~/bytia/)
│   ├── bytia.runtime.kode.yaml    # Runtime KODE v1.0.0 (symlink → ~/bytia/)
│   └── legacy/                    # Archived SPs
│       └── core_identity.yaml.v12.1.0.yaml
└── telegram/
    └── bot.py               # Bot Telegram con fail-secure, aislamiento por chat_id

tests/
├── test_session.py          # 19 tests de SessionStore
├── test_file_edit.py        # 14 tests de FileEditTool
└── test_context_management.py  # 13 tests de context management

scripts/                      # Utilidades de validación
├── validate_metadata.py      # Check de versión, autoría, docs
├── check_secrets.py          # Scan de secrets en pre-commit
└── benchmark_io.py           # Benchmark secuencial vs concurrente
```

## Flujo de desarrollo

```bash
# 1. Activar entorno
cd ~/bytia/proyectos/BytIA-KODE
source .venv/bin/activate

# 2. Hacer cambios...

# 3. Validar
uv run pytest -q
uv run python scripts/validate_metadata.py
uv run python scripts/check_secrets.py

# 4. Build
uv build

# 5. Reinstalar (comando ÚNICO — bkode usa uv tool, NO uv pip)
uv tool install --force --reinstall .

# 6. Probar
bytia-kode
```

## Hook de pre-commit

```bash
git config core.hooksPath .githooks
```

Ejecuta automáticamente: validación de metadata + secret scan + pytest. Un test fail bloquea el commit.

## Crear una Tool

Las tools son la forma en que el agente interactúa con el sistema. Cada tool hereda de `Tool` en `tools/registry.py`.

### Patrón estándar (stateless)

```python
class MiTool(Tool):
    name = "mi_tool"
    description = "Qué hace esta tool"
    parameters = {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Descripción del parámetro"},
            "param2": {"type": "integer", "description": "Otro parámetro", "default": 42},
        },
        "required": ["param1"],
    }

    async def execute(self, param1: str, param2: int = 42, **_) -> ToolResult:
        try:
            # Lógica aquí
            return ToolResult(output="resultado")
        except Exception as exc:
            logger.error("mi_tool error: %s", exc)
            return ToolResult(output=str(exc), error=True)
```

### Patrón con dependencias (stateful)

Las tools que necesitan acceso al store o al agent reciben la dependencia vía constructor:

```python
class SessionListTool(Tool):
    name = "session_list"
    description = "List saved sessions"
    parameters = { "type": "object", "properties": { ... } }

    def __init__(self, session_store: SessionStore):
        self._store = session_store

    async def execute(self, source: str | None = None, limit: int = 15, **_) -> ToolResult:
        sessions = self._store.list_sessions(source=source, limit=limit)
        # ...
```

### Registrar la tool

**Stateless** — en `ToolRegistry._register_defaults()`:

```python
for tool_cls in [BashTool, FileReadTool, FileWriteTool, WebFetchTool, MiTool]:
    self.register(tool_cls())
```

**Stateful** — en `Agent.__init__()` (después de crear la dependencia):

```python
self.tools.register(MiTool(dependencia))
```

### Convenciones

- `execute()` siempre es `async` — usa `asyncio.to_thread()` para I/O bloqueante
- Usa `**_` para kwargs no esperados (Pyright compatibility)
- Devuelve `ToolResult(output=str, error=bool)` — nunca lances excepciones
- El output se trunca si es muy largo (ver `BashTool`: 50k chars)
- Las tools que tocan el filesystem deben usar `_resolve_workspace_path()` para sandbox
- Las tools que ejecutan comandos deben usar allowlist (ver `BashTool`)
- Las tools de solo lectura (como las session tools) no necesitan sanitización adicional

### Tools existentes

| Tool | Propósito | Seguridad | Tipo |
|------|-----------|-----------|------|
| `bash` | Ejecutar comandos shell | Allowlist de binarios, `shell=False`, sandbox CWD | Stateless |
| `file_read` | Leer archivos | Path traversal bloqueado, sandbox CWD | Stateless |
| `file_write` | Escribir archivos | Path traversal bloqueado, sandbox CWD | Stateless |
| `file_edit` | Editar archivos (search/replace + create) | Backup automático, sandbox CWD | Stateless |
| `web_fetch` | Fetch URLs (HTTP GET) | Solo http/https, content type validation, truncation | Stateless |
| `session_list` | Listar sesiones guardadas | Solo lectura | Stateful (SessionStore) |
| `session_load` | Cargar contexto de sesión pasada | Solo lectura | Stateful (SessionStore) |
| `session_search` | Buscar sesiones por título | Solo lectura | Stateful (SessionStore) |

## Sesiones

### SessionStore API

```python
from bytia_kode.session import SessionStore

store = SessionStore(Path("~/.bytia-kode/sessions.db"))

# Crear sesión
sid = store.create_session(source="tui", source_ref="", title="Mi sesión")

# Añadir mensajes (O(1), append-only)
store.append_message(sid, role="user", content="Hola")
store.append_message(sid, role="assistant", content="¿Qué tal?")
store.append_message(sid, role="tool", content="ls output", tool_call_id="call_1", name="bash")

# Cargar mensajes
messages = store.load_messages(sid)  # list[dict]

# Metadata
meta = store.get_metadata(sid)  # SessionMetadata | None
store.update_title(sid, "Título nuevo")

# Listar y buscar
sessions = store.list_sessions(source="tui", limit=15)
sessions = store.list_sessions()  # Todas las fuentes
results = store.search_sessions("python", limit=10)

# Contexto para el modelo
context = store.get_session_context(sid, max_messages=20)

# Eliminar
store.delete_session(sid)
```

### SessionMetadata

```python
@dataclass(slots=True)
class SessionMetadata:
    session_id: str
    source: str          # "tui" | "telegram"
    source_ref: str     # chat_id para telegram
    title: str
    created_at: str
    updated_at: str
    message_count: int
    token_count: int
    model: str
    is_active: bool
```

## Crear una Skill

Las skills son procedimientos reutilizables que el agente carga en su system prompt. Se almacenan en `~/.bytia-kode/skills/` (user-space, no se commitean al repo).

### Estructura

```
~/.bytia-kode/skills/
├── mi-skill/
│   ├── SKILL.md          # Instrucciones (requerido)
│   ├── references/       # Docs adicionales (opcional)
│   └── scripts/          # Scripts ejecutables (opcional, v0.6.0)
```

### Formato SKILL.md

```yaml
---
name: mi-skill                    # Requerido, kebab-case
description: Brief description   # Requerido
trigger: keywords, for, search   # Opcional, para scoring de relevancia
verified: false                  # Opcional, marca de validación
---

## Purpose
Qué hace esta skill y por qué existe.

## How to Use
Instrucciones paso a paso.

## When to Use / When NOT to Use
Contexto de activación y limitaciones.

## Best Practices
Consejos para el agente.
```

### Convenciones

- Frontmatter YAML obligatorio (`---` delimitado)
- `trigger` es una lista de keywords — scoring: trigger +3, description +2, content +1
- `verified: true` solo después de validar que la skill funciona correctamente
- Las skills se buscan con `get_relevant(query)` usando el mensaje del usuario
- Comandos TUI: `/skills`, `/skills save <name>`, `/skills show <name>`, `/skills verify <name>`

### Visión v0.6.0

Las skills evolucionarán a unidades autónomas:
- **Tools dinámicas**: scripts en `scripts/` auto-registrados como tools del agente
- **Sub-agentes**: skill con SP propio que se ejecuta como agente dedicado
- **Skills Hub**: distribución desde repos GitHub

## Crear un Provider

B-KODE soporta cualquier endpoint OpenAI-compatible. Los providers se configuran vía `.env`:

| Variable | Para qué |
|----------|----------|
| `PROVIDER_BASE_URL` + `PROVIDER_MODEL` | Provider principal (router llama.cpp) |
| `FALLBACK_BASE_URL` + `FALLBACK_MODEL` | Fallback cloud |
| `LOCAL_BASE_URL` + `LOCAL_MODEL` | Local (Ollama) |

`F3` en la TUI alterna entre los tres providers.

## BytIA OS (Kernel + Runtime)

El agente construye el system prompt en este orden:

1. `bytia.kernel.yaml + bytia.runtime.kode.yaml — BytIA OS (empaquetada en el wheel)
2. `B-KODE.md` — instrucciones de proyecto (walk-up desde CWD)
3. Skills relevantes — inyectadas según scoring del mensaje del usuario
4. Resumen de contexto — si el historial supera 75% del límite

## Testing

```bash
uv run pytest -q          # Ejecutar tests
uv run pytest -v          # Verboso
uv run pytest tests/ -k "test_name"  # Test específico
```

Los tests están en `tests/`. El pre-commit hook los ejecuta automáticamente.

### Tests por módulo

| Archivo | Tests | Qué cubre |
|---------|-------|-----------|
| `test_session.py` | 19 | SessionStore: lifecycle, messages, list/search, delete, title, context |
| `test_file_edit.py` | 14 | FileEditTool: replace, create, path traversal, diff, params |
| `test_context_management.py` | 13 | Context: estimate_tokens, manage_context, summarize, update_limit |
| **Total** | **46** | |

## Build y Release

```bash
uv build                                    # Genera .tar.gz + .whl
uv run python -m twine check dist/*        # Verificar paquete
uv pip install ./dist/*.whl --force-reinstall  # Instalar localmente
```

La versión se gestiona en `pyproject.toml` (campo `version`).
