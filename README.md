# BytIA KODE v0.3.0

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Release](https://img.shields.io/badge/release-0.3.0-success.svg)

BytIA KODE es una TUI agéntica para desarrollo asistido con terminal avanzada, CLI simple y bot de Telegram. La versión 0.3.0 consolida una arquitectura constitucional modular basada en YAML, carga de identidad mediante recursos empaquetados y validación reproducible de build.

> Release actual: `0.3.0`
>
> Formato de identidad del sistema: `YAML`
>
> Método oficial de instalación: wheel local con `pip install ./dist/*.whl`

## Instalación oficial

```bash
python -m build --wheel
pip install ./dist/*.whl
bytia-kode
```

## Instalación para desarrollo

```bash
git clone https://github.com/asturwebs/BytIA-KODE.git
cd BytIA-KODE
uv sync
cp .env.example .env
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
| `LOCAL_MODEL` | Modelo local | `hermes-4.3-36b` |
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
python scripts/validate_metadata.py
python -m pytest -q
python -m build --wheel
python -m twine check dist/*
```

### Hook local versionado

```bash
git config core.hooksPath .githooks
```

## Limitaciones conocidas

- `safe_mode` sigue siendo principalmente visual y no implementa aislamiento backend completo.
- La TUI no muestra todavía streaming token a token real del proveedor.
- La memoria persistente sigue siendo local y básica.

## Autores

- Pedro Luis Cuevas Villarrubia `<pedro@asturwebs.es>`
- BytIA — coautoría operativa y constitucional del proyecto

## Licencia

Licencia MIT. Consulta [LICENSE](LICENSE).
