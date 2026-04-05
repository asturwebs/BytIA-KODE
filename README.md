# BytIA KODE v0.4.1

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Release](https://img.shields.io/badge/release-0.4.1-success.svg)

BytIA KODE es una TUI agéntica para desarrollo asistido con terminal y bot de Telegram. La versión 0.4.1 añade `file_edit` tool con backup, context management con summarización, ToolBlock color coding y 27 tests.

> **B-KODE: Agente + Skills + Terminal. La automatización empresarial cabe en tu CLI.**

<p align="center">
  <img src="docs/img/bytia-kode-1-TUI-inicio.png" width="700"><br>
  <em>TUI con identidad constitucional cargada</em>
</p>

<p align="center">
  <img src="docs/img/bytia-kode-2-TUI-chat.png" width="350">
  <img src="docs/img/bytia-kode-4-TUI-temas.png" width="350"><br>
  <em>Chat con el agente · Temas disponibles</em>
</p>

<p align="center">
  <img src="docs/img/bytia-kode-3-TUI-comandos.png" width="350">
  <img src="docs/img/bytia-kode-5-benchmark.png" width="350"><br>
  <em>Comandos integrados · Benchmark: 4.90x speedup async</em>
</p>

> Release actual: `0.4.1`
>
> Formato de identidad del sistema: `YAML`
>
> Método recomendado de instalación: `uv` (ver [uv installation](https://docs.astral.sh/uv/getting-started/installation/))

## Instalación

Requiere [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/asturwebs/BytIA-KODE.git
cd BytIA-KODE
uv sync
cp .env.example .env   # editar con tu provider y API key
uv run bytia-kode
```

## Build como paquete

```bash
uv build
uv pip install ./dist/*.whl
bytia-kode
```

## Modos de ejecución

```bash
uv run bytia-kode          # TUI (por defecto)
uv run python -m bytia_kode --bot  # Telegram bot
```

## Arquitectura resumida

```text
__main__.py
  ├─ tui.py
  └─ telegram/bot.py

agent.py
  ├─ prompts/core_identity.yaml
  ├─ providers/manager.py
  ├─ providers/client.py
  ├─ tools/registry.py
  └─ skills/loader.py
```

Documentación adicional:

- [Manual de la TUI](docs/TUI.md)
- [Arquitectura técnica](docs/ARCHITECTURE.md)
- [Guía de desarrollo](docs/DEVELOPMENT.md)
- [Guía de contribución](CONTRIBUTING.md)
- [Código de conducta](CODE_OF_CONDUCT.md)
- [Historial de cambios](CHANGELOG.md)

## Configuración principal

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| `PROVIDER_BASE_URL` | Endpoint principal (router llama.cpp) | `http://localhost:8080/v1` |
| `PROVIDER_API_KEY` | API key del provider principal | vacío |
| `PROVIDER_MODEL` | Modelo principal (`auto` = auto-detect del router) | `auto` |
| `FALLBACK_BASE_URL` | Endpoint fallback (nube) | `https://api.z.ai/api/coding/paas/v4` |
| `FALLBACK_API_KEY` | API key del fallback | vacío |
| `FALLBACK_MODEL` | Modelo fallback | `glm-5-turbo` |
| `LOCAL_BASE_URL` | Endpoint local (Ollama) | `http://localhost:11434/v1` |
| `LOCAL_MODEL` | Modelo local | `gemma4:26b` |
| `TELEGRAM_BOT_TOKEN` | Token del bot | vacío |
| `DATA_DIR` | Directorio persistente | `~/.bytia-kode` |

## TUI

### Comandos

| Comando | Descripción |
| --- | --- |
| `/help` | Ayuda integrada |
| `/quit`, `/exit`, `/q` | Salida |
| `/reset` | Reinicia conversación |
| `/clear` | Limpia chat |
| `/model`, `/provider` | Proveedor y modelo activos |
| `/tools` | Tools registradas |
| `/skills` | Listar skills guardadas |
| `/skills save <name>` | Crear skill nueva (contenido multiline) |
| `/skills show <name>` | Mostrar contenido de skill |
| `/skills verify <name>` | Marcar skill como verificada |
| `/models` | Listar modelos del provider activo |
| `/use <model>` | Seleccionar modelo del provider activo |
| `/history` | Historial reciente |
| `/cwd` | Directorio actual |
| `/safe` | Estado visual de safe mode |

### Atajos

| Atajo | Acción |
| --- | --- |
| `Ctrl+P` | Menú de comandos |
| `Ctrl+Q` | Salir |
| `Ctrl+R` | Reset conversación |
| `Ctrl+L` | Limpiar chat |
| `Ctrl+M` | Mostrar modelo |
| `Ctrl+T` | Mostrar tools |
| `Ctrl+S` | Mostrar skills |
| `Ctrl+D` | Toggle reasoning |
| `Ctrl+E` | Alternar safe mode |
| `Ctrl+X` | Copiar último bloque de código |
| `F2` | Cambiar tema cíclicamente |
| `F3` | Cambiar provider (primary/fallback/local) |
| `↑` / `↓` | Historial de entrada |
| `Enter` | Enviar prompt |

### Temas

Pulsa `F2` para cambiar entre los 9 temas disponibles. El tema seleccionado se guarda automáticamente en `~/.bytia-kode/theme.json`.

| Tema | Tipo |
| --- | --- |
| `gruvbox` (por defecto) | Oscuro |
| `monokai` | Oscuro |
| `nord` | Oscuro |
| `dracula` | Oscuro |
| `catppuccin-mocha` | Oscuro |
| `tokyo-night` | Oscuro |
| `catppuccin-latte` | Claro |
| `solarized-light` | Claro |
| `rose-pine-dawn` | Claro |

El banner, ActivityIndicator, ThinkingBlock, ToolBlock y todos los colores CSS se adaptan al tema activo.

## Tools

| Tool | Propósito | Seguridad |
| --- | --- | --- |
| `bash` | Ejecutar comandos shell | Allowlist de binarios, sandbox CWD |
| `file_read` | Leer archivos | Path traversal bloqueado |
| `file_write` | Escribir archivos | Path traversal bloqueado |
| `file_edit` | Editar archivos (search/replace + create) | Backup automático, sandbox CWD |
| `web_fetch` | Fetch URLs (HTTP GET) | Solo http/https, content type validation |

Consulta [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) para crear nuevas tools.

## Skills System

BytIA KODE incluye un sistema de skills persistente inspirado en [Hermes Agent](https://github.com/hermes-agent/hermes) y el paper [_Terminal Agents Suffice for Enterprise Automation_](https://arxiv.org/abs/2604.00073). Las skills son procedimientos reutilizables que el agente carga en su system prompt.

### Visión (v0.5.0)

Las skills evolucionarán de instrucciones estáticas a **unidades autónomas** con capacidad de ejecutar tools y scripts propios, e incluso actuar como sub-agentes con system prompt independiente:

- **Tools dinámicas** — scripts en `skills/<name>/scripts/` auto-registrados como tools del agente
- **Sub-agentes** — una skill puede definir su propio SP (identidad + instrucciones especializadas) y ejecutarse como agente dedicado
- **Skills Hub** — instalar skills desde repos GitHub, compartir entre usuarios
- **`write_skill` tool** — el agente crea skills programáticamente durante la ejecución

### Estructura

```
~/.bytia-kode/skills/
├── skill-creator/
│   └── SKILL.md          # Instrucciones principales (requerido)
├── my-procedure/
│   ├── SKILL.md
│   ├── references/       # Docs adicionales (opcional)
│   └── scripts/          # Scripts ejecutables (opcional)
└── ...
```

### Formato SKILL.md

```yaml
---
name: my-skill               # Requerido, kebab-case
description: Brief desc      # Requerido
trigger: keywords, for, search  # Opcional, búsqueda por relevance
verified: false              # Opcional, marca de validación
---

## Procedure
[Instrucciones paso a paso]

## Pitfalls
[Errores comunes y soluciones]
```

### Comandos

| Comando | Descripción |
| --- | --- |
| `/skills` | Listar skills con estado |
| `/skills save <name>` | Crear skill (escribir contenido, línea vacía para terminar) |
| `/skills show <name>` | Mostrar contenido completo |
| `/skills verify <name>` | Marcar como verificada |

### Skill incluida

- **skill-creator** — Guía para crear nuevas skills (meta-skill de bootstrap)

## Validación y release

```bash
uv run python scripts/validate_metadata.py
uv run pytest -q
uv build
uv run python -m twine check dist/*
```

### Hook local versionado

```bash
git config core.hooksPath .githooks
```

## Identidad constitucional (System Prompt)

El agente carga su identidad desde `src/bytia_kode/prompts/core_identity.yaml`, un archivo YAML que define la personalidad, valores, protocolos y reglas del sistema. Este archivo se empaqueta dentro del wheel como recurso del paquete.

### Personalizar la identidad

Para adaptar BytIA KODE a tu propio contexto, edita `src/bytia_kode/prompts/core_identity.yaml`:

| Sección | Qué contiene | Personalizar |
| --- | --- | --- |
| `identity` | Nombre, versión, naturaleza, creador, **runtime** (capacidades, comandos) | Tu nombre y rol |
| `valores` | Jerarquía de prioridades (seguridad, privacidad, precisión...) | Tus prioridades |
| `protocols` | Comportamiento ante errores, overrides, auto-evaluación | Ajustar a tu flujo |
| `interfaz` | Idioma, estilo de comunicación, formato | Tu idioma y tono |
| `contexto` | Perfil del usuario, ubicación, infraestructura | Tu perfil y entorno |
| `runtime_profile` | Variables del motor (se rellenan en tiempo de ejecución) | No modificar |

Ejemplo mínimo:

```yaml
identity:
  nombre: "Mi Asistente"
  version: "1.0.0"
  naturaleza: "asistente de código"
  creador_socio: "Tu Nombre"
```

Después de editar, reconstruye el wheel para que los cambios se empaqueten:

```bash
uv build
```

## Stack técnico

BytIA KODE se construye sobre librerías open-source de terceros. Consulta [ARCHITECTURE.md](docs/ARCHITECTURE.md) para el detalle completo con versiones y uso específico.

| Librería | Rol |
| --- | --- |
| [Textual](https://textual.textualize.io/) | Framework TUI |
| [Rich](https://rich.readthedocs.io/) | Renderizado (Markdown, Panel, Table) |
| [httpx](https://www.python-httpx.org/) | Cliente HTTP async / streaming SSE / web_fetch |
| [Pydantic](https://docs.pydantic.dev/) | Modelos de datos y validación |
| [PyYAML](https://pyyaml.org/) | Parseo de identidad y skills |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Variables de entorno |
| [python-telegram-bot](https://docs.python-telegram-bot.org/) | Bot de Telegram |

## Seguridad

Hardening de seguridad verificado con auditoría profesional:

| Issue | Mitigación |
| --- | --- |
| SEC-001 — Command injection | Allowlist de binarios + `shell=False` + `shlex.split()` |
| SEC-002/003 — Path traversal | `_resolve_workspace_path()` con sandbox a `cwd` |
| SEC-005 — Telegram abierto | Fail-secure por defecto (denegar sin allowlist) |

Motor I/O asíncrono validado con benchmark: **4.90x speedup** (80% mejora) frente a ejecución secuencial.

## Limitaciones conocidas

- `safe_mode` sigue siendo principalmente visual y no implementa aislamiento backend completo.
- Las skills no registran tools dinámicas todavía (previsto para v0.5.0).
- El estimador de tokens es una heurística (chars/3), no un tokenizer real.
- No hay auto-fallback de providers (circuit breaker pendiente).

## Contribuir

Contribuciones, issues y sugerencias son bienvenidas.

1. Fork del repositorio
2. Rama para tu feature (`git checkout -b feature/mi-mejora`)
3. Commit con cambios (`git commit -m 'feat: descripción'`)
4. Push a la rama (`git push origin feature/mi-mejora`)
5. Abre un Pull Request

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para los criterios de validación.

## Autores

- **Pedro Luis Cuevas Villarrubia** (AsturWebs) `<pedro@asturwebs.es>`
- **BytIA** v12.1.0 — coautoría operativa y constitucional

## Licencia

Licencia MIT. Consulta [LICENSE](LICENSE).
