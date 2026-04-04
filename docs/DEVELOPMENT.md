# Guía de Desarrollo

## Estructura del proyecto

```text
src/bytia_kode/
├── __main__.py              # Entry point: TUI (default) / --bot (Telegram)
├── agent.py                 # Núcleo agéntico: loop, tools, contexto, system prompt
├── tui.py                   # Interfaz Textual: widgets, bindings, streaming
├── config.py                # Config desde .env + dataclasses
├── providers/
│   ├── client.py            # Cliente HTTP async (httpx), streaming SSE, get_router_info
│   └── manager.py           # Multi-provider: primary, fallback, local
├── tools/
│   └── registry.py          # Tool base class + registry (bash, file_read, file_write, web_fetch)
├── skills/
│   └── loader.py            # Carga, búsqueda, scoring y persistencia de skills
├── prompts/
│   └── core_identity.yaml   # Identidad constitucional (empaquetada en el wheel)
└── telegram/
    └── bot.py               # Bot Telegram con fail-secure

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

### Patrón

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

### Registrar la tool

En `ToolRegistry._register_defaults()`:

```python
for tool_cls in [BashTool, FileReadTool, FileWriteTool, WebFetchTool, MiTool]:
```

### Convenciones

- `execute()` siempre es `async` — usa `asyncio.to_thread()` para I/O bloqueante
- Usa `**_` para kwargs no esperados (Pyright compatibility)
- Devuelve `ToolResult(output=str, error=bool)` — nunca lances excepciones
- El output se trunca si es muy largo (ver `BashTool`: 50k chars)
- Las tools que tocan el filesystem deben usar `_resolve_workspace_path()` para sandbox
- Las tools que ejecutan comandos deben usar allowlist (ver `BashTool`)

### Tools existentes

| Tool | Propósito | Seguridad |
|------|-----------|-----------|
| `bash` | Ejecutar comandos shell | Allowlist de binarios, `shell=False`, sandbox CWD |
| `file_read` | Leer archivos | Path traversal bloqueado, sandbox CWD |
| `file_write` | Escribir archivos | Path traversal bloqueado, sandbox CWD |
| `web_fetch` | Fetch URLs (HTTP GET) | Solo http/https, content type validation, truncation |

## Crear una Skill

Las skills son procedimientos reutilizables que el agente carga en su system prompt. Se almacenan en `~/.bytia-kode/skills/` (user-space, no se commitean al repo).

### Estructura

```
~/.bytia-kode/skills/
├── mi-skill/
│   ├── SKILL.md          # Instrucciones (requerido)
│   ├── references/       # Docs adicionales (opcional)
│   └── scripts/          # Scripts ejecutables (opcional, v0.5.0)
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

### Visión v0.5.0

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

## System Prompt

El agente construye el system prompt en este orden:

1. `core_identity.yaml` — identidad constitucional (empaquetada en el wheel)
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

## Build y Release

```bash
uv build                                    # Genera .tar.gz + .whl
uv run python -m twine check dist/*        # Verificar paquete
uv pip install ./dist/*.whl --force-reinstall  # Instalar localmente
```

La versión se gestiona en `pyproject.toml` (campo `version`).
