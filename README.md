# BytIA KODE

**BytIA KODE** (B-KODE) es un agente de IA para terminal: identidad configurable en YAML, arquitectura multi-provider con failover automático, skills extensibles y sesiones persistentes. Corre como TUI (Textual) y como bot de Telegram — ambas interfaces comparten la misma base de datos de sesiones en SQLite. Pensado para trabajar sobre tu código: tools nativas con perímetro de seguridad (allowlist de binarios, sandbox de paths) y cero dependencias de servicios en la nube para el núcleo.

[![PyPI](https://img.shields.io/pypi/v/bytia-kode.svg)](https://pypi.org/project/bytia-kode/)
[![Tests](https://github.com/asturwebs/BytIA-KODE/actions/workflows/ci.yml/badge.svg)](https://github.com/asturwebs/BytIA-KODE/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://pypi.org/project/bytia-kode/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![SQLite WAL](https://img.shields.io/badge/SQLite%20WAL-enabled-orange.svg)](docs/ARCHITECTURE.md)
[![Textual](https://img.shields.io/badge/Textual-8.2.1+-blueviolet.svg)](https://textual.textualize.io/)
[![Telegram Bot](https://img.shields.io/badge/Telegram%20Bot-22.0+-26A5E4.svg)](https://docs.python-telegram-bot.org/)

## Instalación

El paquete vive en [PyPI](https://pypi.org/project/bytia-kode/): `pip install bytia-kode` (o `uv tool install bytia-kode`) es el camino canónico. El `git clone` queda **solo para desarrollo** (ver [Desarrollo](#desarrollo)).

### Instalación rápida (recomendada)

```bash
curl -fsSL https://raw.githubusercontent.com/asturwebs/BytIA-KODE/main/install.sh | bash
```

Esto instala todo automáticamente: bootstrap de [uv](https://docs.astral.sh/uv/getting-started/installation/) si falta, instalación de `bytia-kode` **desde PyPI** como tool aislada (`bytia-kode` en `~/.local/bin`), y genera `~/.bytia-kode/.env` con valores por defecto. Solo necesitas editar ese `.env` con tu provider y API key.

### Instalación manual (desde PyPI)

```bash
# con uv (recomendado: entorno aislado, Python gestionado, binario en ~/.local/bin)
uv tool install bytia-kode

# o con pip, dentro de un venv
pip install bytia-kode
```

Luego crea tu configuración global (el instalador rápido lo hace por ti):

```bash
mkdir -p ~/.bytia-kode
cat > ~/.bytia-kode/.env << 'EOF'
PROVIDER_BASE_URL=http://localhost:8080/v1
PROVIDER_API_KEY=not-needed
PROVIDER_MODEL=auto
EOF
# editar con tu provider y API key — todas las variables: .env.example del repo
```

> Un `.env` en el directorio de trabajo (proyecto) tiene precedencia sobre el global `~/.bytia-kode/.env`. Las skills vendor se siembran solas en `~/.bytia-kode/skills/vendor/` en el primer arranque — y se actualizan solas cuando la versión instalada cambia.

## Quickstart

```bash
bytia-kode --version    # versión instalada (+ build id si existe) y sale
bytia-kode              # TUI (por defecto)
bytia-kode --bot        # bot de Telegram
```

La TUI pide lo mínimo: el `.env` con tu provider (ver [Instalación](#instalación)) y, para el bot, `TELEGRAM_BOT_TOKEN`. Dentro de la TUI, `Ctrl+P` abre el menú de comandos y `/help` resume todo.

## Características

- **Multi-provider con failover automático** — cadena local-first (router → Ollama → nube) con circuit breaker (CLOSED → OPEN → HALF_OPEN): si el primario cae, el agente cambia solo y se recupera a los 60 s. Pin manual por teclas F1–F8.
- **Sesiones persistentes** — todo se guarda en SQLite WAL (`~/.bytia-kode/sessions.db`), compartido entre TUI y Telegram: empieza un chat en una interfaz y résumelo en la otra. Auto-save O(1) por mensaje.
- **Sistema de skills por capas** — procedimientos Markdown+YAML en `~/.bytia-kode/skills/` con prioridad bytia > user > vendor; las vendor se siembran y actualizan automáticamente con el paquete.
- **Tools nativas con perímetro de seguridad** — 12 tools (bash, files, grep/glob/tree, web_fetch, sesiones) tras un modelo defense-in-depth: allowlist de binarios, jail de workspace configurable (confined/permissive/open, ver [Política de workspace](#política-de-workspace)), SSRF cerrada, redacción de secretos en logs.
- **Identidad configurable en YAML** — `kernel.default.yaml` (identidad y valores) + `runtime.default.yaml` (adaptación al entorno), empaquetados como recursos; overrides de usuario en `~/.bytia-kode/prompts/`.
- **Bot de Telegram** — mismo cerebro y mismas sesiones, aislamiento por usuario, fail-secure sin allowlist.
- **Motor I/O asíncrono** — benchmark 4.90x frente a ejecución secuencial (medición histórica 2026-04, `docs/devlog/2026-04-02.md`; no hay benchmark reproducible en el repo).

### Modos de ejecución

| Comando | Descripción |
| --- | --- |
| `bytia-kode` | TUI (por defecto) |
| `bytia-kode --bot` | Bot de Telegram |
| `bytia-kode --version` | Imprime `versión (+ build id si existe)` y sale 0 |

En desarrollo: `uv run bytia-kode` y `uv run python -m bytia_kode --bot`.

### Configuración principal

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
| `LOG_LEVEL` | Nivel de logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `LOG_FILE` | Path custom para logs (vacío = `~/.bytia-kode/logs/bytia-kode.log`) | vacío |
| `EXTRA_BINARIES` | Binarios adicionales para BashTool (comma-separated) | vacío |

Además de las variables de entorno, `~/.bytia-kode/config.yaml` configura la política de workspace (ver abajo).

### Política de workspace

El agente corre tras un jail de intención configurable: `~/.bytia-kode/config.yaml` decide qué puede tocar.

```yaml
workspace:
  mode: confined          # confined | permissive | open (default: permissive)
  trusted_paths:          # válvula de precisión: rutas permitidas además del workspace
    - ~/Projects
    - ~/bytia
```

| Modo | File tools (`file_read`/`file_write`/`file_edit`/`grep`/`glob`/`tree`) | `bash` |
| --- | --- | --- |
| `confined` | jailed a workspace + trusted | jailed: `workdir` y todo argumento-que-parece-ruta se valida igual que los file tools |
| `permissive` (default) | jailed a workspace + trusted | libre (el `workdir` sigue validándose) |
| `open` | libre | libre |

- **Es una política de intención, no un sandbox de kernel**: se rechaza lo que el agente pide *por nombre* (rutas absolutas, `~/…`, rutas relativas con `/`; los saltos por symlink se canonicalizan con `Path.resolve()`). Un binario permitido que recorra el árbol por su cuenta (p. ej. git leyendo `~/.gitconfig`) o un fichero dentro del workspace enlazado hacia fuera quedan fuera de lo que esto puede garantizar. Sin namespaces/chroot por diseño.
- **Conmutación en caliente**: `/workspace` en la TUI (o Ctrl+P → *Workspace mode*) muestra el modo activo —también visible en la barra de estado (`ws:confined` en verde, `ws:permissive` en ámbar, `ws:open` en rojo)— y conmuta con confirmación. El cambio aplica a la sesión en curso y **no se persiste**: para hacerlo permanente, edítalo tú en `config.yaml`.
- **Errores accionables**: cada bloqueo nombra el modo activo, los límites del jail y las dos salidas (ampliar `trusted_paths` o conmutar el modo) — el agente no tiene que adivinar.
- **`config.yaml` es del operador**: el agente no puede escribirlo (denylist T4, igual que `.env` o `mcp_servers.json`) — una sesión inyectada no puede silenciosamente pasar el jail a `open` para el siguiente arranque. Ese denylist sigue activo en los tres modos: `open` libera el workspace, nunca la superficie de configuración propia del agente.
- Sin `config.yaml` (o malformado) el arranque es `permissive` — el comportamiento histórico, ahora explícito y documentado.

### Sesiones persistentes

Las sesiones se almacenan en `~/.bytia-kode/sessions.db` (SQLite WAL mode). Tanto la TUI como el bot de Telegram comparten la misma base de datos.

| Comando TUI | Descripción |
| --- | --- |
| `/sessions` | Listar sesiones guardadas (tabla con ID, source, título, msgs, fecha) |
| `/load <session_id>` | Cargar una sesión específica |
| `/new` | Crear nueva sesión (limpia historial, habilita auto-save) |
| `/reset` | Limpiar conversación en memoria (no borra la sesión del disco) |

El modelo también puede acceder a sesiones pasadas durante la conversación: `session_list`, `session_load`, `session_search`.

### Skills System

Las skills son procedimientos reutilizables en formato Markdown+YAML que el agente carga en su system prompt según relevancia (las relevantes al query se inyectan automáticamente).

```
~/.bytia-kode/skills/
├── bytia/      # Ecosistema BytIA (opcional, si ~/bytia existe)
├── user/       # Skills creadas por el usuario (writable)
└── vendor/     # Skills incluidas con KODE (read-only, auto-update)
```

| Capa | Prioridad | Writable | Descripción |
|------|-----------|----------|-------------|
| `bytia/` | 1 (más alta) | No (symlink) | Ecosistema BytIA compartido con otros assistants |
| `user/` | 2 | Sí | Skills propias del usuario |
| `vendor/` | 3 (más baja) | No | Skills core incluidas con KODE |

Capas superiores sobrescriben las inferiores con el mismo nombre. Skills vendor incluidas: **bytia-constitution** (identidad y valores), **bytia-memory** (memoria entre sesiones), **skills-manager** (gestión del sistema), **graphify** (knowledge graphs de código).

### Tools

| Tool | Propósito | Seguridad |
| --- | --- | --- |
| `bash` | Ejecutar comandos shell | Allowlist de binarios, sandbox CWD |
| `file_read` | Leer archivos | Path traversal bloqueado |
| `file_write` | Escribir archivos | Path traversal bloqueado |
| `file_edit` | Editar archivos (search/replace + create) | Backup automático, sandbox CWD |
| `web_fetch` | Fetch URLs (HTTP GET) | Solo http/https, SSRF cerrada, límite 1 MiB |
| `read_context` | Contexto del workspace actual | Solo lectura, auto-genera si no existe |
| `session_list` | Listar sesiones guardadas | Solo lectura |
| `session_load` | Cargar contexto de sesión pasada | Solo lectura |
| `session_search` | Buscar sesiones por título | Solo lectura |
| `grep` | Búsqueda regex en archivos | Python puro, sin bash |
| `glob` | Pattern matching de archivos | Python puro, sin bash |
| `tree` | Jerarquía de directorios | Python puro, sin bash |

### Seguridad

Modelo de seguridad con defense-in-depth:

| Capa | Mitigación |
| --- | --- |
| Command injection | Allowlist de binarios + `shell=False` + `shlex.split()` + guards de argv |
| Path traversal | `_resolve_workspace_path()` con sandbox a CWD + trusted paths |
| Escritura en trusted paths | Denylist sobre `.env`, `mcp_servers.json`, `config.yaml`, `skills/**` |
| SSRF | `web_fetch` rechaza hosts privados/loopback, redirects re-validados |
| Telegram abierto | Fail-secure por defecto (deniega sin allowlist) |
| Sesiones cruzadas | Aislamiento por `chat_id` |
| Secretos en logs | Redacción de claves y valores (hash corto) |

#### Guardarraíl JEVAL (pre-ejecución de tools)

`src/bytia_kode/guardrail.py` clasifica **cada** llamada a tool antes de ejecutarla (TypeSafe System One) y puede bloquear las arriesgadas.

| Modo (`JEVAL_MODE`) | Comportamiento |
| --- | --- |
| `off` | **Default.** Sin clasificación — coste casi nulo (una lectura de env cacheada) |
| `shadow` | Clasifica y loguea en background (*fire-and-forget*, cero latencia añadida) — **nunca bloquea** |
| `enforce` | Bloquea las tools clasificadas como de riesgo con `noul >= JEVAL_THRESHOLD` |

Por defecto `off`; requiere `TYPESAFE_API_KEY` (sin clave, el gate se desactiva aunque `JEVAL_MODE=enforce`); fail-open ante error del clasificador. Otras variables: `JEVAL_THRESHOLD` (`0..1`, default `0.7`), `JEVAL_TIMEOUT` (default `2.0` s). Log de decisiones: `~/.local/state/jev-router/kode-guardrail.jsonl`.

### Limitaciones conocidas

- `safe_mode` sigue siendo principalmente visual y no implementa aislamiento backend completo.
- El cliente MCP es WIP declarado (stubs no-op sin el extra `[mcp]`; `McpTool.execute()` pendiente) — no anunciarlo como capacidad terminada.
- El estimador de tokens es una heurística (chars/3–3.5 según densidad ASCII), no un tokenizer real.
- PromptTextArea no soporta Shift+Enter para newline (limitación de Textual).

## Arquitectura

```text
__main__.py                     ← entry point: --version / --bot / TUI
  ├─ tui.py
  └─ telegram/bot.py

agent.py
  ├─ prompts/kernel.default.yaml + runtime.default.yaml (identidad; overrides de usuario en ~/.bytia-kode/prompts/)
  ├─ session.py                 ← SQLite WAL persistence
  ├─ providers/manager.py
  ├─ providers/circuit.py       ← Circuit breaker (CLOSED/OPEN/HALF_OPEN)
  ├─ providers/client.py
  ├─ tools/registry.py
  ├─ tools/session.py           ← session_list, session_load, session_search
  └─ skills/loader.py

audio.py                        ← TTS: bytia-tts + piper (local)
```

### Stack técnico

| Librería | Rol |
| --- | --- |
| [Textual](https://textual.textualize.io/) | Framework TUI |
| [Rich](https://rich.readthedocs.io/) | Renderizado (Markdown, Panel, Table) |
| [httpx](https://www.python-httpx.org/) | Cliente HTTP async / streaming SSE / web_fetch |
| [Pydantic](https://docs.pydantic.dev/) | Modelos de datos y validación |
| [PyYAML](https://pyyaml.org/) | Parseo de identidad y skills |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Variables de entorno |
| [python-telegram-bot](https://docs.python-telegram-bot.org/) | Bot de Telegram |
| [sqlite3](https://docs.python.org/3/library/sqlite3.html) | Persistencia de sesiones (stdlib) |
| `bytia-tts` | TTS: CLI local que invoca a piper (binario en `~/.local/bin`, **no está en PyPI**) |
| `piper` | Motor TTS local, voz `es_AR-daniela-high` (binario del sistema) |

### Identidad: BytIA OS Kernel + Runtime

El agente carga su identidad desde dos YAML: los defaults empaquetados como recursos del paquete (`kernel.default.yaml` + `runtime.default.yaml` en `src/bytia_kode/prompts/`) y, encima, tus overrides `bytia.kernel.yaml` / `bytia.runtime.kode.yaml` en `~/.bytia-kode/prompts/` — deep-merge sobre los defaults, sin reconstruir nada. Para cambiar los defaults del paquete: edita los YAML en `src/bytia_kode/prompts/` y reconstruye el wheel (`uv build`).

| Sección | Qué contiene | Personalizar |
| --- | --- | --- |
| `identity` | Nombre, versión, naturaleza, creador, **runtime** (capacidades, comandos) | Tu nombre y rol |
| `valores` | Jerarquía de prioridades (seguridad, privacidad, precisión...) | Tus prioridades |
| `protocols` | Comportamiento ante errores, overrides, auto-evaluación | Ajustar a tu flujo |
| `interfaz` | Idioma, estilo de comunicación, formato | Tu idioma y tono |
| `contexto` | Perfil del usuario, ubicación, infraestructura | Tu perfil y entorno |
| `runtime_profile` | Variables del motor (se rellenan en tiempo de ejecución) | No modificar |

## Bot de Telegram

El bot comparte la misma base de datos de sesiones que la TUI (`~/.bytia-kode/sessions.db`):

- **Continuar conversaciones** entre interfaces — empieza un chat en Telegram y résumelo en la TUI (y viceversa).
- **Aislamiento por usuario** — cada `chat_id` tiene su propia sesión e historial privado. No hay filtrado de contenido.
- **Acceso del modelo** — el agente puede usar `session_list(source="telegram")` para acceder a sesiones de Telegram desde la TUI.

### Configuración

| Variable | Descripción |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token del bot (obtener de @BotFather) |
| `TELEGRAM_ALLOWED_USERS` | User IDs permitidos (comma-separated), ej: `123456,789012` |
| `TELEGRAM_API_BASE` | Endpoint alternativo del Bot API (servidor local auto-alojado); vacío = `api.telegram.org` |

Sin `TELEGRAM_ALLOWED_USERS` configurado, el bot deniega todos los mensajes (fail-secure).

Al arrancar, el bot imprime por stdout un banner con el token enmascarado y el número de usuarios permitidos, y queda a la escucha — se detiene limpio con **un** Ctrl+C:

```text
Bot de Telegram activo · token 123456789:AAF…x7Q · usuarios permitidos: 2 · esperando mensajes (Ctrl+C para parar)
```

### Comandos del bot

| Comando | Descripción |
| --- | --- |
| `/start` | Info del bot y modelo activo |
| `/help` | Lista comandos disponibles |
| `/reset` | Limpiar conversación del usuario |
| `/model` | Mostrar provider y modelo activos |
| `/sessions` | Listar sesiones del usuario |
| `/context` | Regenerar contexto del workspace |
| `/stop` | Interrumpir el mensaje en curso |
| `/kill` | Matar el subprocess activo (sesión conservada) |

## TUI

### Comandos

| Comando | Descripción |
| --- | --- |
| `/help` | Ayuda integrada |
| `/quit`, `/exit`, `/q` | Salida |
| `/reset` | Reinicia conversación (en memoria) |
| `/new` | Nueva sesión con auto-save |
| `/sessions` | Listar sesiones guardadas |
| `/load <id>` | Cargar sesión |
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
| `/context` | Regenerar contexto del workspace |
| `/workspace` | Mostrar política de workspace (modo + trusted) |
| `/workspace <modo>` | Conmutar el jail: `confined` \| `permissive` \| `open` (con confirmación, sesión en curso) |

### Atajos

| Atajo | Acción |
| --- | --- |
| `Ctrl+P` | Menú de comandos (incluye *Workspace mode*: cicla confined→permissive→open con confirmación) |
| `Ctrl+Q` | Salir |
| `Ctrl+R` | Reset conversación |
| `Ctrl+L` | Limpiar chat |
| `Ctrl+M` | Mostrar modelo |
| `Ctrl+T` | Mostrar tools |
| `Ctrl+S` | Mostrar skills |
| `Ctrl+D` | Toggle reasoning |
| `Ctrl+E` | Alternar safe mode |
| `Ctrl+X` | Copiar último bloque de código |
| `Ctrl+Shift+C` | Copiar respuesta completa del agente |
| `F1` | Modo AUTO (failover por la cadena completa) |
| `F2` | Cambiar tema cíclicamente |
| `F3` | Cambiar provider (primary/fallback/local) |
| `F4`–`F8` | Pin manual: Studio / Ollama / Z.ai / DeepSeek / Router |
| `↑` / `↓` | Historial de entrada |
| `Enter` | Enviar prompt |

### Temas

Pulsa `F2` para cambiar entre los 19 temas disponibles (12 oscuros + 7 claros, por defecto `gruvbox`). El tema se guarda en `~/.bytia-kode/theme.json`.

## Desarrollo

```bash
git clone https://github.com/asturwebs/BytIA-KODE.git
cd BytIA-KODE
uv sync
uv run bytia-kode
```

### Validación

```bash
uv run python scripts/validate_metadata.py
uv run python scripts/check_readme_claims.py
uv run pytest -q
uv build
uv run python -m twine check dist/*
```

### Publicación

Las versiones se publican automáticamente por [Trusted Publishers (OIDC)](https://docs.pypi.org/trusted-publishers/): push de un tag `v*` → `.github/workflows/release.yml` corre los gates, construye con `uv build`, publica vía `pypa/gh-action-pypi-publish` en el environment `pypi` (aprobación del Socio), y crea la GitHub Release con las notas del CHANGELOG. Cero secretos en el repo. El proceso completo, paso a paso: [RELEASING.md](RELEASING.md).

### Hook local versionado

```bash
git config core.hooksPath .githooks
```

### Contribuir

1. Fork del repositorio
2. Rama para tu feature (`git checkout -b feature/mi-mejora`)
3. Commit con cambios (`git commit -m 'feat: descripción'`)
4. Push a la rama (`git push origin feature/mi-mejora`)
5. Abre un Pull Request

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para los criterios de validación.

## Documentación

- [Manual de la TUI](docs/TUI.md)
- [Arquitectura técnica](docs/ARCHITECTURE.md)
- [Guía de desarrollo](docs/DEVELOPMENT.md)
- [Proceso de release](RELEASING.md)
- [Guía de contribución](CONTRIBUTING.md)
- [Código de conducta](CODE_OF_CONDUCT.md)

Historial completo de versiones: [CHANGELOG.md](CHANGELOG.md).

## Autores

- **Pedro Luis Cuevas Villarrubia** (AsturWebs) `<pedro@asturwebs.es>`
- **BytIA** v12.3.0 — coautoría operativa — BytIA OS RFC-001

## Licencia

Licencia MIT. Consulta [LICENSE](LICENSE).
