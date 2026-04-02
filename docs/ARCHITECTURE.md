# Arquitectura técnica

Documento actualizado para la release 0.3.0.

## Entrada principal

- `src/bytia_kode/__main__.py`: selecciona TUI, CLI simple o bot Telegram.

## Interfaces

- `src/bytia_kode/tui.py` — interfaz Textual con tema monokai
- `src/bytia_kode/cli.py` — REPL simple
- `src/bytia_kode/telegram/bot.py` — bot con fail-secure por defecto

## Núcleo del agente

- `src/bytia_kode/agent.py`

Responsabilidades:

- mantener mensajes de conversación
- cargar la identidad constitucional empaquetada
- construir el prompt del sistema (cacheado en `__init__`)
- invocar el provider con manejo de errores específico
- delegar ejecución de tool calls a `_handle_tool_calls()`
- sanitizar input del usuario (no imprimibles filtrados)
- preservar historial ante fallos del provider

### Flujo de `chat()`

```
validar input → registrar user msg → iterar:
    llamar provider → registrar assistant msg → yield contenido
    si tool_calls → _handle_tool_calls() → continuar iteración
excepciones → registrar error en historial → yield mensaje controlado
```

### Manejo de errores

`chat()` captura excepciones específicas (`TimeoutError`, `ConnectionError`, `RuntimeError`, `httpx.HTTPError`) y las transforma en mensajes claros vía `_format_chat_error()`. El historial se preserva incluso ante fallo del provider.

## Identidad constitucional

- `src/bytia_kode/prompts/core_identity.yaml` es la fuente central de identidad.
- `agent.py` carga el recurso con `importlib.resources`.
- El recurso se distribuye dentro del wheel.

## Providers

- `providers/client.py` — cliente HTTP async (httpx)
- `providers/manager.py` — gestión de provider primario, fallback y local

## Tools

- `tools/registry.py` — registro y ejecución de tools
- Tools actuales: `bash`, `file_read`, `file_write`

### Seguridad de tools

- **BashTool**: allowlist de binarios (`ls`, `pwd`, `cat`, `echo`, `git`, `grep`, `find`, `mkdir`, `touch`, `uv`, `python`, `wsl`). Ejecuta con `asyncio.create_subprocess_exec` (sin `shell=True`). Directorio de trabajo confinado al workspace.
- **FileReadTool / FileWriteTool**: `_resolve_workspace_path()` impide path traversal. I/O delegado a `asyncio.to_thread` para no bloquear el event loop.

## Skills

- `skills/loader.py` — carga de skills desde directorios configurables

## Memoria

- `memory/store.py` — almacenamiento JSON persistente

### Comportamiento

- Carga estricta: `store.json` corrupto genera `RuntimeError` (no degradación silenciosa).
- Contexto acotado: `get_context()` limita a las 20 entradas más recientes y máximo 2000 caracteres.
- Búsqueda por keywords (futura integración con FAISS para búsqueda semántica).

## Limitaciones técnicas

- `safe_mode` no endurece todavía el backend.
- No hay streaming token a token en la TUI principal.
- La memoria semántica avanzada sigue fuera de producción.
- No hay auto-fallback de providers (circuit breaker pendiente).
- Telegram comparte un solo Agent entre todos los usuarios.
