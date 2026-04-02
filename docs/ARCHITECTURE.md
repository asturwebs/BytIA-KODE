# Arquitectura técnica

Documento actualizado para la release 0.3.0.

## Entrada principal

- `src/bytia_kode/__main__.py`: selecciona TUI, CLI simple o bot Telegram.

## Interfaces

- `src/bytia_kode/tui.py`
- `src/bytia_kode/cli.py`
- `src/bytia_kode/telegram/bot.py`

## Núcleo del agente

- `src/bytia_kode/agent.py`

Responsabilidades:

- mantener mensajes de conversación
- cargar la identidad constitucional empaquetada
- construir el prompt del sistema
- invocar el provider
- iterar sobre tool calls
- anexar resultados de tools al contexto

## Identidad constitucional

- `src/bytia_kode/prompts/core_identity.yaml` es la fuente central de identidad.
- `agent.py` carga el recurso con `importlib.resources`.
- El recurso se distribuye dentro del wheel.

## Providers

- `providers/client.py`
- `providers/manager.py`

## Tools

- `tools/registry.py`
- tools actuales: `bash`, `file_read`, `file_write`

## Skills

- `skills/loader.py`

## Memoria

- `memory/store.py`

## Limitaciones técnicas

- `safe_mode` no endurece todavía el backend.
- No hay streaming token a token en la TUI principal.
- La memoria semántica avanzada sigue fuera de producción.
