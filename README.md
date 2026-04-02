# BytIA KODE v0.3.0

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Release](https://img.shields.io/badge/release-0.3.0-success.svg)

BytIA KODE es una TUI agéntica para desarrollo asistido con terminal avanzada, CLI simple y bot de Telegram. La versión 0.3.0 consolida una arquitectura constitucional modular basada en YAML, carga de identidad mediante recursos empaquetados y validación reproducible de build.

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
  <em>Comandos integrados · Benchmark: 5.01x speedup async</em>
</p>

> Release actual: `0.3.0`
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
uv run bytia-kode
uv run python -m bytia_kode
uv run python -m bytia_kode --simple
uv run python -m bytia_kode --bot
```

## Arquitectura resumida

```text
__main__.py
  ├─ tui.py
  ├─ cli.py
  └─ telegram/bot.py

agent.py
  ├─ prompts/core_identity.yaml
  ├─ providers/manager.py
  ├─ providers/client.py
  ├─ tools/registry.py
  ├─ skills/loader.py
  └─ memory/store.py
```

Documentación adicional:

- [Manual de la TUI](docs/TUI.md)
- [Arquitectura técnica](docs/ARCHITECTURE.md)
- [Guía de contribución](CONTRIBUTING.md)
- [Código de conducta](CODE_OF_CONDUCT.md)
- [Historial de cambios](CHANGELOG.md)

## Configuración principal

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| `PROVIDER_BASE_URL` | Endpoint principal compatible con OpenAI | `https://api.z.ai/api/coding/paas/v4` |
| `PROVIDER_MODEL` | Modelo principal | `glm-5.1` |
| `LOCAL_BASE_URL` | Endpoint local compatible | `http://localhost:8080` |
| `LOCAL_MODEL` | Modelo local | vacío (configurar) |
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
| `/skills` | Skills detectadas |
| `/history` | Historial reciente |
| `/cwd` | Directorio actual |
| `/safe` | Estado visual de safe mode |

### Atajos

| Atajo | Acción |
| --- | --- |
| `Ctrl+Q` | Salir |
| `Ctrl+R` | Reset conversación |
| `Ctrl+L` | Limpiar chat |
| `Ctrl+M` | Mostrar modelo |
| `Ctrl+T` | Mostrar tools |
| `Ctrl+S` | Mostrar skills |
| `Ctrl+E` | Alternar safe mode |
| `Ctrl+X` | Copiar último bloque de código |
| `↑` / `↓` | Historial de entrada |
| `Enter` | Enviar prompt |

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
| `identity` | Nombre, versión, naturaleza, creador | Tu nombre y rol |
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
uv run python -m build --wheel
```

## Seguridad

v0.3.0 incluye hardening de seguridad verificado con auditoría profesional:

| Issue | Mitigación |
| --- | --- |
| SEC-001 — Command injection | Allowlist de binarios + `shell=False` + `shlex.split()` |
| SEC-002/003 — Path traversal | `_resolve_workspace_path()` con sandbox a `cwd` |
| SEC-005 — Telegram abierto | Fail-secure por defecto (denegar sin allowlist) |

Motor I/O asíncrono validado con benchmark: **5.01x speedup** (80% mejora) frente a ejecución secuencial.

## Limitaciones conocidas

- `safe_mode` sigue siendo principalmente visual y no implementa aislamiento backend completo.
- La TUI no muestra todavía streaming token a token real del proveedor.
- La memoria persistente es local con contexto acotado (20 entries / 2000 chars). Sin búsqueda semántica todavía.

## Autores

- **Pedro Luis Cuevas Villarrubia** (AsturWebs) `<pedro@asturwebs.es>`
- **BytIA** v12.1.0 — coautoría operativa y constitucional

## Licencia

Licencia MIT. Consulta [LICENSE](LICENSE).
