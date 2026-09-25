# AST-5 — Revisión del núcleo de BytIA-KODE (agent, tools, session, guardrail)

**Autor:** BytIA Engineer · **Fecha:** 2026-09-25 · **Base revisada:** commit `768d3ff` (v0.8.0a1), rama `paperclip/review-2026-09-25`
**Método:** lectura íntegra, línea a línea, de `agent.py` (1047 L), `tools/registry.py` (759 L), `session.py` (307 L), `context.py` (152 L), `guardrail.py` (171 L), `herdr.py` (169 L), contrastada con `docs/ARCHITECTURE.md` (466 L) y con los puntos de integración reales (`tui.py`, `telegram/bot.py`, `providers/manager.py`, `prompts/*.yaml`, `CHANGELOG.md`). Todo `ruta:linea` citado fue leído, no supuesto.

**Balance:** 6 HIGH · 11 MED · ~14 LOW. Los tres sistemas más delicados son la cancelación (botón de pánico), la persistencia/rotación de sesiones de Telegram y la compactación de contexto.

---

## HIGH — defectos funcionales con impacto directo en usuario

### H1. El botón de pánico se pierde: `_cancel_event.clear()` al inicio de CADA iteración del bucle agéntico
`agent.py:759-760`:
```python
for _iteration in range(self.max_iterations):
    self._cancel_event.clear()
```
Un `interrupt()` (`agent.py:1026-1028`, Escape en TUI / `/stop` en Telegram) o `kill()` pulsado durante la fase de ejecución de tools — después del último chequeo de la iteración (`agent.py:909`) y antes de la siguiente — es **borrado** por ese `clear()`. La cancelación solo es fiable si se pulsa durante el streaming (chequeo por chunk `agent.py:780` y post-stream `agent.py:836`). Consecuencia visible: el TUI muestra "Interrupting..." pero el agente sigue iterando con nueva llamada al LLM.
**Quick win:** mover el `clear()` fuera del `for` (una vez por `chat()`), 1 línea.

### H2. `kill()` limpia el evento de cancelación al terminar → carrera con el bucle
`agent.py:1030-1044`: `set()` → terminate → `await wait_for(proc.wait(), 2.0)` → `_active_subprocess = None` → **`clear()`** (línea 1044). El `clear()` puede ejecutarse antes de que el bucle observe el `set()` (chequeos `agent.py:780/836/909`): cancelación perdida y el turno continúa como si nada. Es la segunda vía de perder la cancelación (junto a H1).
**Quick win:** eliminar el `clear()` de `kill()`; que lo haga el `clear()` reubicado de H1 al inicio del siguiente turno.

### H3. `/kill` (Telegram) y Ctrl+K (TUI) habilitan un segundo `chat()` concurrente sobre el mismo Agent
- `telegram/bot.py:106-109`: `await agent.kill()` + `self._processing.discard(chat_id)` sin cancelar la corrutina `_chat` (`bot.py:193`) que sigue viva.
- `tui.py:1151-1160`: `action_kill_agent` baja `is_processing = False` sin cancelar el worker `@work` `_process_message` (`tui.py:1083-1090`).
Por H1/H2 el generador casi seguro sigue corriendo → el siguiente mensaje del usuario lanza **otro** `chat()` sobre el mismo `Agent` → `self.messages` intercalado, historial corrupto, callbacks TUI duplicados.
- Además Telegram **no registra `on_subprocess`** (el TUI sí: `tui.py:465,480-481`): `_active_subprocess` siempre es `None` en el bot → `/kill` no mata ningún subproceso. `ARCHITECTURE.md:242-244` documenta Kill funcional para ambas interfaces.

### H4. Telegram nunca resume la conversación tras reinicio del bot
`telegram/bot.py:30-37` busca el id determinista `telegram_{chat_id}`; pero al no existir llama a `set_session(source, source_ref)` (`agent.py:944-955`), que termina en `create_session` → genera **`telegram_{uuid8}`** (`session.py:136`), ignorando `source_ref` para el id. El id determinista nunca llega a existir → la rama `load_session_by_id` (`bot.py:33`) es inalcanzable y cada arranque crea una sesión nueva. El índice `idx_sessions_source_ref` (`session.py:33`) no se usa en ningún lookup. `ARCHITECTURE.md:216-227` documenta exactamente el diseño que el código no cumple.
**Quick win:** en `create_session`, usar `f"{source}_{source_ref}"` como id cuando `source_ref != ''` (2 líneas).

### H5. `_manage_context` rompe los pares assistant(tool_calls)↔tool al compactar
`agent.py:530-543` selecciona los lotes **por posición** (`non_system[:-4][:5]`, donde `non_system` incluye mensajes `role="tool"`) sin respetar la pareja assistant(tool_calls)/tool-responses. El `pop` (`agent.py:556-557`) puede eliminar el assistant con tool_calls dejando mensajes `tool` huérfanos (o viceversa) → las APIs OpenAI-compatibles estrictas (DeepSeek, Z.ai) devuelven 400 ("tool message without preceding tool_calls") en cuanto la sesión supera el 75% y se compacta. Además: inserta resúmenes `system` en la posición 0 (`agent.py:559`) acumulándose, y la BD conserva el historial completo (la recarga restaura el contexto sin compactar, rompiendo la contabilidad `_persisted_count`).

### H6. BashTool: el timeout NO mata el proceso hijo
`registry.py:217-228`: `asyncio.wait_for(process.communicate(), timeout)` cancela el `communicate` pero deja el hijo vivo (huérfano) escribiendo a pipes sin lector; y `on_subprocess(None)` (`registry.py:226-227`) elimina la referencia, con lo que un `kill()` posterior ya no puede alcanzarlo.
**Quick win:** en la rama `TimeoutError`, `process.kill()` + `await process.wait()` (3 líneas).

---

## MED — defectos funcionales o de robustez

### M1. Guardrail enforce puede reventar el turno con respuestas malformadas (viola su propio contrato fail-open)
El módulo promete "Never raises" (`guardrail.py:107`) y "Fail-open: any Jev error → allow" (`guardrail.py:10`), pero el parseo de la respuesta (`guardrail.py:119-122`: `j.get(...)`, `float(a.get("noul", 0.0))`) está **fuera** del `try` (que solo cubre la llamada, `guardrail.py:109-115`). Un JSON válido pero no-dict, o `noul: null` → `AttributeError`/`TypeError` que sube por `jeval_check` (`guardrail.py:166-171`) → `_handle_tool_calls` (`agent.py:659`, sin try) → `chat()` revienta. Solo afecta modo `enforce` (off por defecto, `guardrail.py:67`).

### M2. Shadow mode: task sin referencia fuerte → veredictos silenciosamente perdidos
`guardrail.py:147-149` devuelve el `asyncio.Task` dentro del dict, pero el caller (`agent.py:659-669`) solo lee `blocked` y descarta el dict. El event loop solo mantiene weak-refs a tasks (pie documentado de `create_task`): el task puede ser recolectado antes de ejecutarse/completar → el log JSONL pierde entradas shadow sin avisar. Commit `ab6554b` ("fire-and-forget, cero latencia") implementado sin el `set` de referencias.
**Quick win:** set module-level con `add_done_callback(set.discard)` (3 líneas).

### M3. FIX-3 (tool error memory): bloqueo permanente, cruzado entre tools y sin expiración — deuda confirmada
`agent.py:646-657` (bloqueo), `agent.py:682-684` (memorización de **cualquier** error, incluidos transitorios: timeout de bash `registry.py:228`, errores de red), `agent.py:709-713` (`_is_tool_pattern_blocked` busca la key md5 en **todas** las herramientas: md5(command de bash) == md5(path de file_write) colisionan). Sin expiración ni reset por turno: un solo timeout deja ese comando/ruta bloqueado el resto de la sesión con mensaje "Previously rejected". CHANGELOG.md:124 lo declaró feature; en la práctica castiga reintentos legítimos.

### M4. Auto-título de sesión muerto: condición imposible
`agent.py:885`: `if msg_count_before == 0` — pero `msg_count_before` (`agent.py:850`) siempre es ≥1 porque el mensaje de usuario ya se añadió (`agent.py:745`). `update_title` (`session.py:284-293`) nunca se invoca → todas las sesiones quedan "(untitled)". `ARCHITECTURE.md:108` documenta este comportamiento como vigente.
**Quick win:** `== 1`.

### M5. Límite de contexto: código 262144 vs docs 131072, y default inflado para providers sin límite configurado
- `agent.py:34`: `MAX_CONTEXT_TOKENS = 262144` (el comentario "~200k" es además incoherente con el valor); `ARCHITECTURE.md:48` dice `131072`.
- `tui.py:564-568` y `tui.py:1026`: al pinear cualquier provider sin `get_context_limit` (solo deepseek lo define, `providers/manager.py:230-236`) se fuerza 262144 → para fallback (z.ai) o GGUF con ctx pequeño, la compresión dispara a 75% de 262144 = 196.608 tokens → overflow real de contexto. El poll solo corrige providers locales (`tui.py:613-618`).

### M6. Template vars del system prompt: maquinaria inerte
`agent.py:301-317` solo sustituye `{{var}}` dentro de `payload["runtime_profile"]`; el `runtime.default.yaml` shipped no tiene esa clave **ni ningún placeholder** (grep `{{` en `src/bytia_kode/prompts/*.yaml`: 0 resultados). Resultado: `engine.context_limit: "model-dependent"` (`prompts/runtime.default.yaml:18-22`) nunca se rellena con el límite/modelo real pese a que el código calcula ambas cosas. Feature declarada, no cableada.

### M7. SQLite síncrono en el event loop + conexiones que nunca se cierran
- Todas las llamadas al store son síncronas desde el loop asíncrono (`agent.py:695-701`, `agent.py:876-897`): con `busy_timeout=5000` (`session.py:117`), contención TUI+Telegram puede congelar el streaming hasta 5 s por llamada.
- `with self._connect() as conn` (`session.py:122-123,156-173,...`) — el context manager de sqlite3 hace commit/rollback pero **no** `close()`; el cierre queda al GC. `ARCHITECTURE.md:126` afirma "abre y cierra su propia conexión".
**Quick win:** `asyncio.to_thread` en los puntos calientes + cierre explícito (try/finally o `contextlib.closing`).

### M8. `append_message` traga todas las excepciones
`session.py:174-175`: `except Exception → log`. Un fallo de INSERT (FK violada porque la sesión no existe, disco lleno) pierde el mensaje en silencio; el agente sigue como si estuviera persistido y nadie puede detectarlo.

### M9. GrepTool: case-insensitive incondicional, regex inválida silenciosa, y glob con braces documentado pero imposible
- `registry.py:628`: `_re.compile(pattern, _re.IGNORECASE)` siempre — buscar "Foo" casa "foo"; no hay forma de búsqueda case-sensitive.
- `registry.py:633-634`: `except Exception: pass` → un patrón regex inválido devuelve "No matches found." engañoso.
- `registry.py:592`: la doc del parámetro `include` documenta `'*.{ts,tsx}'`, pero `pathlib.glob` no expande `{}` → cero resultados garantizados.
- `sorted(resolved.rglob(...))` (`registry.py:607`) y `resolved.glob(...)` (`registry.py:656`) corren en el event loop (solo el grep por fichero va a `to_thread`, `registry.py:611`): árboles grandes bloquean el streaming. `ARCHITECTURE.md:340` ("Todas usan asyncio.to_thread") solo es parcialmente cierto.

### M10. ReadContextTool: bloquea el event loop y sirve contexto congelado
`registry.py:573-574` llama `ensure_context(Path.cwd())` síncronamente dentro de `execute` (2× `subprocess.run` con timeout 5 s, `context.py:55-64`). Y `ensure_context` (`context.py:148`) solo genera si el fichero no existe → rama git/estructura/commits congelados desde la primera invocación, sin invalidación por TTL ni por cambio: la tool "git info" sirve datos podridos para siempre.

### M11. Estimador heurístico de tokens (reconocido) — agrava M5
`agent.py:431-438`: chars/3.5 (>85% ASCII) o chars/3. `ARCHITECTURE.md:465` lo admite como limitación. El riesgo real aparece combinado con M5: umbral calculado sobre un límite inflado con un estimador que subestima español (~1 token/3.5-4 chars reales).

---

## LOW — dead code, cosmética, deuda menor

1. **Dead code verificado:**
   - `_DANGEROUS_PATTERNS` (`registry.py:52-55`): nunca usado; la lista vigente es la inline de `_validate_command_safety` (`registry.py:164-174`), que además es más completa.
   - `tool_names = "|".join(known)` (`agent.py:464`): asignado y nunca usado (el patrón se reconstruye en la 467).
   - `return` inalcanzable tras el `except` (`registry.py:581`).
   - Rama `chunk[0] == "system"` del bot (`bot.py:194`): `chat()` nunca emite ese tipo (solo `str`, `reasoning`, `provider_used`, `error` — `agent.py:755,781,785,788,810,822,833`).
   - `save_current_session` (`agent.py:973-993`): sin llamadores en todo el árbol. Landmine: si algún día se llama tras el auto-save de `chat()`, duplicará todo el historial (`_persisted_count` jamás se actualiza en `chat()`).
2. `_parse_text_tool_calls` (`agent.py:453-513`): cualquier mención literal `tool(...)` en prosa del modelo ejecuta la tool; solo parsea kwargs con comillas dobles (`agent.py:499`); nombres de tools inyectados al regex sin escapar (`agent.py:467`).
3. `set_trusted_paths` (`registry.py:25-31`) usa `.extend` sobre un global: cada `Agent.__init__` (`agent.py:170`) acumula duplicados — N chats Telegram = N copias de los trusted paths.
4. `_create_backup` (`registry.py:123-132`): docstring "atomic copy" falso (copy2 directo, sin temp+rename); backups junto al original contaminan glob/tree del workspace; sin limpieza ni rotación; colisión si se edita dos veces en el mismo segundo.
5. FileWriteTool sobrescribe sin backup (`registry.py:279-288`) — asimetría con FileEditTool (que sí respalda, `registry.py:490`).
6. Falsos positivos del safety validator (`registry.py:164-174`): bloquea `;`, `|`, `&&`, `>` también **dentro de comillas** donde son literales inofensivos — `grep -E "a|b" f` se rechaza.
7. TreeTool: conectores └──/├── incorrectos cuando hay dotfiles al final (`registry.py:700-712`: `is_last` se calcula sobre `entries` sin filtrar los ocultos que se saltan en 705-706).
8. `context.py:86-87`: al alcanzar justo el cap imprime `+0 more`.
9. `session.py`: LIKE sin escapar `%`/`_` en `search_sessions` (`session.py:250-253`); `update_title` devuelve `True` aunque no actualice nada (`session.py:288-293`); `get_session_context` devuelve "Session not found" como string de éxito (`session.py:269-270`).
10. `herdr.py`: carrera menor sobre `_last_session` entre el hilo llamador (`herdr.py:108`) y el worker (`herdr.py:135-138`); el `detail` se dropea para estados ≠ working, incluido `blocked` (`herdr.py:94`); el hilo no tiene shutdown (`herdr.py:83`).
11. `_ensure_deepseek_reasoning` acoplado al **nombre del slot** provider (`agent.py:764`): solo cubre el slot "deepseek". Hoy es correcto (solo la API de DeepSeek exige el eco de reasoning), pero es frágil si se sirve un DeepSeek por otro slot.
12. `estimate_tokens` no cuenta `reasoning_content` ni los ToolDefs (solo contenido y argumentos, `agent.py:440-451`).
13. Seguridad (nota de diseño, no bug puntual): la allowlist valida **binarios, no argumentos** — `python -c`, `wsl <cmd>`, `ssh host cmd`, `pip` (ejecuta setup.py arbitrario) escapan del sandbox pretendido desde `registry.py:199-207`; `curl`/`wget`/`scp` en la allowlist (`registry.py:46`) habilitan exfiltración; `web_fetch` sin mitigación SSRF (`registry.py:309-335`, `follow_redirects=True`, sin blocklist de red interna) ni límite de tamaño de descarga antes de `.text`. Con JEVAL off por defecto (`guardrail.py:67`) no hay guardarraíl efectivo salvo opt-in.
14. Telegram `_chat` hace `return` ante `("error", ...)` (`bot.py:198-200`) sin pasar por el `finally` de limpieza… sí pasa (el `finally` está en `bot.py:212-213`), pero el texto parcial acumulado se descarta silenciosamente.

---

## Contraste `docs/ARCHITECTURE.md` ↔ código

| Docs (línea) | Afirmación | Realidad en código |
|---|---|---|
| :48 | `MAX_CONTEXT_TOKENS = 131072` (128k) | `agent.py:34` = **262144** (M5) |
| :51 | "comprime los **2 mensajes más antiguos**" | lotes de 5 dejando intactos los últimos 4 (`agent.py:538`) |
| :37, :39 | reasoning "NO se almacena en historial" | se persiste como `reasoning_content` (`agent.py:871,883`; columna `session.py:44`) |
| :43 | error sin fallback "NO se persiste en historial" | se persiste como assistant (`agent.py:824-832`) |
| :108 | auto-título del primer mensaje | condición muerta, nunca ocurre (M4) |
| :126 | cada operación "abre **y cierra**" su conexión | nunca se hace `close()` (M7) |
| :254 | "allowlist de **31** binarios" | lista 34 en la propia docs y el código tiene 34 (`registry.py:43-50`) |
| :13, :456-457 | audio con `edge-tts` + `mpv` | `bytia-tts` (piper local) desde commit `4b12ca7` (`audio.py:63`) |
| :242-244 | Panic Buttons (Interrupt/Kill) en TUI y Telegram | Telegram sin wiring `on_subprocess` → kill inoperante (H3) |
| :340 | tools de exploración "todas" con `asyncio.to_thread` | `rglob`/`glob` en el event loop (M9) |
| :46-52 | compresión al 75%, heurística chars/3.5-3, `get_router_info` | ✔ correcto (`agent.py:523`, `agent.py:436-438`, `providers/client.py:314` + `tui.py:614-618`) |
| :250 | 12 tools nativas | ✔ 9 en registry (`registry.py:736`) + 3 session (`agent.py:207-209`) |

## Deuda conocida — veredicto

- **FIX-3 tool error memory** (CHANGELOG.md:124): implementada, pero con los defectos de M3 (permanente, cruzada, sin distinción error-transitorio vs rechazo de seguridad).
- **Race P1 v0.7.8 sobre `_active_subprocess`** (CHANGELOG.md:86): el fix (captura en variable local antes del check de returncode, `agent.py:1033-1034`) es correcto para el TOCTOU concreto que describía. Quedan fuera: H2 (clear del evento), H3 (Telegram sin wiring + doble chat) y la ventana `_active_subprocess = None` (`agent.py:1043`) contra un nuevo `on_subprocess(process)` concurrente (`tui.py:481`).

## Quick wins priorizados (relación impacto/esfuerzo)

1. **H1** — mover `self._cancel_event.clear()` fuera del `for` (`agent.py:759-760`). 1 línea.
2. **H2** — eliminar el `clear()` final de `kill()` (`agent.py:1044`). 1 línea.
3. **H6** — `process.kill()` + `await process.wait()` en el `TimeoutError` de BashTool (`registry.py:225-228`). 3 líneas.
4. **M4** — `msg_count_before == 1` (`agent.py:885`). 1 línea.
5. **M1** — envolver el parseo de respuesta en try/fail-open (`guardrail.py:119-122`). 4 líneas.
6. **M2** — set de referencias fuertes para los tasks shadow (`guardrail.py:147`). 3 líneas.
7. **H4** — id determinista `f"{source}_{source_ref}"` en `create_session` cuando hay `source_ref` (`session.py:136`). 2 líneas.
8. **L1** — barrido de dead code (`_DANGEROUS_PATTERNS`, `tool_names`, return `registry.py:581`, rama system del bot).
9. **M9** — parámetro `case_sensitive` + error explícito de regex en GrepTool.
10. **M7** — `asyncio.to_thread` en `append_message`/puntos calientes del store.

Items 1-6 son <20 líneas en total y eliminan las tres clases de fallo más visibles para el usuario (pánico no fiable, títulos vacíos, guardarraíl que revienta).
