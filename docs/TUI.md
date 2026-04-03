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

- Tema por defecto: `gruvbox`.
- 9 temas disponibles (6 oscuros + 3 claros). `F2` para cambiar.
- Banner, session info panel y CSS adaptados al tema activo.
- Tema persistido en `~/.bytia-kode/theme.json`.
- Identidad del sistema cargada desde YAML empaquetado.
- Entrada multilinea activa.
- Botón visual de envío activo.

## Limitaciones

- `safe_mode` sigue siendo visual.
- No hay render de streaming en tiempo real.
- La salida detallada de tools no actúa todavía como consola integrada.

## Temas

Pulsa `F2` para cambiar entre temas. La selección se guarda en `~/.bytia-kode/theme.json`.

| Tema | Tipo |
| --- | --- |
| `gruvbox` | Oscuro (por defecto) |
| `monokai` | Oscuro |
| `nord` | Oscuro |
| `dracula` | Oscuro |
| `catppuccin-mocha` | Oscuro |
| `tokyo-night` | Oscuro |
| `catppuccin-latte` | Claro |
| `solarized-light` | Claro |
| `rose-pine-dawn` | Claro |
