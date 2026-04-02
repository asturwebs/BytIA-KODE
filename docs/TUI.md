# Manual de la TUI

Documento actualizado para la versión 0.3.0.

## Componentes

- `Header`
- área de chat con scroll
- barra de estado
- entrada multilínea
- botón visual de envío
- `Footer`

## Flujo

1. Inicia con `bytia-kode`.
2. Escribe el prompt en la caja inferior.
3. Pulsa `Enter` o el botón de envío.
4. Consulta la respuesta en el panel de chat.

## Comandos

| Comando | Descripción |
| --- | --- |
| `/help` | Ayuda integrada |
| `/quit`, `/exit`, `/q` | Cerrar aplicación |
| `/reset` | Reset conversación |
| `/clear` | Limpiar chat |
| `/model`, `/provider` | Mostrar proveedor y modelo |
| `/tools` | Listar tools |
| `/skills` | Listar skills |
| `/history` | Mostrar prompts recientes |
| `/cwd` | Mostrar directorio actual |
| `/safe` | Alternar estado visual de safe mode |

## Estado actual

- Tema por defecto documentado: `monokai`.
- Identidad del sistema cargada desde YAML empaquetado.
- Entrada multilinea activa.
- Botón visual de envío activo.

## Limitaciones

- `safe_mode` sigue siendo visual.
- No hay render de streaming en tiempo real.
- La salida detallada de tools no actúa todavía como consola integrada.
