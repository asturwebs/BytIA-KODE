# Manual de la TUI

> **B-KODE: Agente + Skills + Terminal. La automatización empresarial cabe en tu CLI.**

Documento actualizado para la versión 0.4.0 (unreleased).

## Componentes

| Componente | Descripción |
| --- | --- |
| `Header` | Barra superior con reloj |
| `VerticalScroll (#chat-area)` | Área de chat con scroll. Banner, info, mensajes, reasoning |
| `ActivityIndicator` | Barra de estado encima del input: modelo, provider, contexto |
| `Horizontal (#input-area)` | Input multilínea + botón de envío |
| `Footer` | Solo muestra `Menu (Ctrl+P)` |

## Flujo

1. Inicia con `bytia-kode`.
2. Escribe el prompt en la caja inferior.
3. Pulsa `Enter` o el botón de envío.
4. El ActivityIndicator cambia a `◐ Thinking...`.
5. Si el modelo razona, aparece un bloque `ThinkingBlock` colapsable.
6. La respuesta se muestra con streaming token a token.
7. Si hay tool calls, el indicador muestra `● Running: bash`.
8. Al terminar, vuelve a `● Ready | provider | model | ctx Xk/Yk`.

## Barra de estado (ActivityIndicator)

Muestra información contextual en tiempo real:

```
  ● Ready | Local | glm-4.7-flash | ctx 2k/16k
```

Estados:

| Estado | Aspecto | Cuándo |
| --- | --- | --- |
| Ready | `● Ready | ...` | Idle |
| Thinking | `◐ Thinking... | ...` | Procesando |
| Running | `● Running: bash | ...` | Tool call activa |
| Error | `✗ Error` | Fallo del provider |

La info de modelo y provider se actualiza al cambiar con F3.

## B-KODE.md

Si existe un fichero `B-KODE.md` en el CWD o cualquier directorio padre, se carga y muestra en la info line del chat. El contenido se inyecta en el system prompt del agente.

## Razonamiento (ThinkingBlock)

Los modelos que generan razonamiento (DeepSeek, Gemma 4) muestran un bloque colapsable antes de la respuesta:

- **Colapsado**: `💭 Reasoning — N lines of reasoning` (click para expandir)
- **Expandido**: Contenido completo del razonamiento (click para colapsar)

Interacción:
- **Click** en cualquier ThinkingBlock para toggle
- **Enter** cuando el ThinkingBlock tiene foco
- **Ctrl+D** togglea el último ThinkingBlock

## Command Menu (Ctrl+P)

Popup modal con lista de comandos seleccionable:

| Comando | Acción |
| --- | --- |
| Quit | Salir |
| Reset conversation | Reiniciar chat |
| Clear screen | Limpiar pantalla |
| List tools | Mostrar tools |
| List skills | Mostrar skills |
| Toggle safe mode | Safe mode on/off |
| Change theme | Ciclar temas |
| Switch provider | Cambiar provider |
| Copy last code | Copiar último bloque de código |
| Show model info | Info del modelo |
| List available models | Listar modelos del provider |

Navegación: `↑`/`↓` para mover, `Enter` para seleccionar, `Escape` para cerrar.

## Comandos

| Comando | Descripción |
| --- | --- |
| `/help` | Ayuda integrada |
| `/quit`, `/exit`, `/q` | Cerrar aplicación |
| `/reset` | Reset conversación |
| `/clear` | Limpiar chat |
| `/model`, `/provider` | Mostrar proveedor y modelo |
| `/tools` | Listar tools |
| `/skills` | Listar skills guardadas |
| `/skills save <name>` | Crear skill (multiline, línea vacía para terminar) |
| `/skills show <name>` | Mostrar contenido de skill |
| `/skills verify <name>` | Marcar skill como verificada |
| `/models` | Listar modelos del provider activo |
| `/use <model>` | Seleccionar modelo del provider activo |
| `/history` | Mostrar prompts recientes |
| `/cwd` | Mostrar directorio actual |
| `/safe` | Alternar estado visual de safe mode |

## Atajos de teclado

| Atajo | Acción |
| --- | --- |
| `Ctrl+P` | Abrir menú de comandos |
| `Ctrl+Q` | Salir |
| `Ctrl+R` | Reset conversación |
| `Ctrl+L` | Limpiar chat |
| `Ctrl+M` | Mostrar modelo |
| `Ctrl+T` | Mostrar tools |
| `Ctrl+S` | Mostrar skills |
| `Ctrl+D` | Toggle reasoning (último bloque) |
| `Ctrl+E` | Alternar safe mode |
| `Ctrl+X` | Copiar último bloque de código |
| `F2` | Cambiar tema cíclicamente |
| `F3` | Cambiar provider (primary/fallback/local) |
| `↑` / `↓` | Historial de entrada |
| `Enter` | Enviar prompt |

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

Todos los colores (banner, mensajes, ActivityIndicator, ThinkingBlock) se adaptan al tema activo.
