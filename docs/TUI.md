# Manual de la TUI

> **B-KODE: Agente + Skills + Terminal. La automatización empresarial cabe en tu CLI.**

Documento actualizado para la versión 0.7.0.

## Componentes

| Componente | Descripción |
| --- | --- |
| `Header` | Barra superior con reloj |
| `VerticalScroll (#chat-area)` | Área de chat con scroll. Banner, info, mensajes, reasoning, tools |
| `ActivityIndicator` | Barra de estado encima del input: modelo, provider, contexto |
| `Horizontal (#input-area)` | Input multilínea + botón de envío |
| `Footer` | Solo muestra `Menu (Ctrl+P)` |

## Flujo

1. Inicia con `bytia-kode`.
2. Se crea automáticamente una sesión con auto-save habilitado.
3. Escribe el prompt en la caja inferior.
4. Pulsa `Enter` o el botón de envío.
5. El ActivityIndicator cambia a `◐ Thinking...`.
6. Si el modelo razona, aparece un bloque `ThinkingBlock` colapsable.
7. La respuesta se muestra con streaming token a token.
8. Si hay tool calls, el indicador cambia a `⚙ tool:bash`. Al terminar, aparece un `ToolBlock` colapsable con el output.
9. El mensaje y la respuesta se guardan automáticamente en la sesión.
10. Al terminar, vuelve a `● Ready | provider | model | ctx ~Xk/Yk`.

## Sesiones

Todas las conversaciones se guardan automáticamente en `~/.bytia-kode/sessions.db` (SQLite WAL). No se pierde nada al cerrar la TUI.

### Comandos de sesión

| Comando | Descripción |
| --- | --- |
| `/sessions` | Listar sesiones guardadas en tabla |
| `/load <session_id>` | Cargar una sesión específica (reemplaza historial actual) |
| `/new` | Crear sesión nueva (limpia historial, habilita auto-save) |
| `/reset` | Limpiar conversación en memoria (no borra la sesión del disco) |

### Tabla de sesiones

Al ejecutar `/sessions`, se muestra una tabla con:

| Columna | Contenido |
| --- | --- |
| ID | Identificador único (ej: `tui_a1b2c3d4`) |
| Source | `tui` o `telegram` |
| Title | Título auto-generado del primer mensaje (o "Untitled") |
| Msgs | Número de mensajes en la sesión |
| Updated | Fecha y hora de última actividad |

### Acceso cruzado

Las sesiones de TUI y Telegram se almacenan en la misma base de datos. Desde la TUI puedes cargar sesiones de Telegram con `/load <id>` (y viceversa). El modelo también puede acceder a sesiones pasadas usando las session tools (`session_list`, `session_load`, `session_search`).

#### Panic buttons (Telegram)

| Comando | Acción |
| --- | --- |
| `/stop` | Interrupt (para generación actual) |
| `/kill` | Kill (cancelación nuclear + kill subprocess) |

## Barra de estado (ActivityIndicator)

Muestra información contextual en tiempo real:

```
  ● Ready | Local | gemma-4-26b | ctx ~2k/262k
```

La capacidad de contexto (`262k`) se obtiene dinámicamente del router (`--ctx-size` en los args del modelo). El uso (`~2k`) es una estimación heurística (chars/3) de la sesión actual.

### Polling del router

Cada 5 segundos, la StatusBar consulta `/v1/models` del router. Si el modelo activo cambia en la WebUI (slot swap), el nombre y ctx-size se actualizan automáticamente — no hay que hacer nada.

### Estados

| Estado | Aspecto | Cuándo |
| --- | --- | --- |
| Ready | `● Ready | ...` | Idle |
| Thinking | `◐ Thinking... | ...` | Procesando respuesta |
| Tool | `⚙ tool:bash | ...` | Tool call en ejecución |
| Error | `✗ Error` | Fallo del provider |

La info de modelo y provider se actualiza al cambiar con F3 y por polling automático.

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

## Audio TTS

Cada respuesta del asistente incluye un botón **🔊 Escuchar** que convierte el texto a voz.

### Requisitos

| Herramienta | Instalación | Propósito |
| --- | --- | --- |
| `edge-tts` | `uv tool install edge-tts` | Generación de voz neuronal (Microsoft Edge) |
| `mpv` | `sudo apt install mpv` | Reproductor de audio CLI |

### Uso

- **Click en 🔊 Escuchar** — Genera audio y lo reproduce. El botón cambia a ⏹ Parar.
- **Click en ⏹ Parar** — Detiene la reproducción. El botón vuelve a 🔊 Escuchar.
- Solo un audio a la vez. Al reproducir uno nuevo, el anterior se detiene automáticamente.

### Detalles técnicos

- Voz: `es-MX-DaliaNeural` (femenina, mexicana).
- Limpieza: se eliminan bloques de código, links Markdown, formatting y emojis antes de generar audio.
- Archivos temporales: `/tmp/bytia_audio/` (auto-limpieza por el SO).
- Módulo: `src/bytia_kode/audio.py`.

## Tool Execution (ToolBlock)

Cuando el agente ejecuta una tool (bash, file_read, file_write, session_*), se muestra un bloque colapsable con el resultado:

- **Colapsado**: `✅ bash — N chars` o `❌ bash — error` (click para expandir)
- **Expandido**: Output completo de la tool (click para colapsar)

El ActivityIndicator cambia a `⚙ tool:bash` durante la ejecución y vuelve a `◐ Thinking...` 500ms después. El ToolBlock aparece en el chat cuando la tool termina.

## Command Menu (Ctrl+P)

Popup modal con lista de comandos seleccionable:

| Comando | Acción |
| --- | --- |
| Quit | Salir |
| Reset conversation | Reiniciar chat (en memoria) |
| Clear screen | Limpiar pantalla |
| List tools | Mostrar tools |
| List skills | Mostrar skills |
| Toggle safe mode | Safe mode on/off |
| Change theme | Ciclar temas |
| Switch provider | Cambiar provider |
| Copy last code | Copiar último bloque de código |
| Show model info | Info del modelo |
| List available models | Listar modelos del provider |
| Session info | Ver información de la sesión activa |
| Interrupt | Para generación actual (Escape) |
| Kill | Cancelación nuclear + kill subprocess (Ctrl+K) |

Navegación: `↑`/`↓` para mover, `Enter` para seleccionar, `Escape` para cerrar.

## Comandos

| Comando | Descripción |
| --- | --- |
| `/help` | Ayuda integrada |
| `/quit`, `/exit`, `/q` | Cerrar aplicación |
| `/reset` | Reset conversación (en memoria, no borra sesión) |
| `/new` | Nueva sesión con auto-save |
| `/sessions` | Listar sesiones guardadas |
| `/load <id>` | Cargar sesión por ID |
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
| `/session` | Ver información de la sesión activa |

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
| `Escape` | Para generación actual |
| `Ctrl+K` | Cancelación nuclear + kill subprocess |
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
| `atom-one-dark` | Oscuro |
| `catppuccin-frappe` | Oscuro |
| `catppuccin-macchiato` | Oscuro |
| `rose-pine` | Oscuro |
| `rose-pine-moon` | Oscuro |
| `solarized-dark` | Oscuro |
| `textual-dark` | Oscuro |
| `catppuccin-latte` | Claro |
| `solarized-light` | Claro |
| `rose-pine-dawn` | Claro |
| `atom-one-light` | Claro |
| `flexoki` | Claro |
| `textual-light` | Claro |

Todos los colores (banner, mensajes, ActivityIndicator, ThinkingBlock, ToolBlock) se adaptan al tema activo.
