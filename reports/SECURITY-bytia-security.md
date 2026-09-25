# Auditoría de seguridad — BytIA-KODE v0.7.8

- **Auditor:** BytIA Security (AST-6) · **Fecha:** 2026-09-25
- **Base auditada:** commit `768d3ff` (rama `paperclip/review-2026-09-25`), historial completo de 218 commits
- **Método:** lectura estática del código real (todas las afirmaciones citan `ruta:linea` verificadas en este árbol); escaneo de `git log --all -p`; inspección de CI y hooks. Sin ejecución de exploits.
- **Corrección al enunciado:** la allowlist de BashTool tiene **34 binarios**, no 31 (contados en `src/bytia_kode/tools/registry.py:43-50`).

## Resumen ejecutivo

El perímetro real del producto es la **allowlist de binarios de BashTool**, y esa allowlist incluye `python`, `pip`, `uv`, `curl`, `wget`, `ssh`, `scp`, `git` y `wsl` (registry.py:43-50). El rechazo de operadores shell (registry.py:152-187) es cosmético frente a eso: no hace falta ni un `;` ni un `|` para obtener ejecución arbitraria de código, exfiltración por red o ejecución remota. Por tanto, el "sandbox de tools" y el guardarraíl JEVAL (apagado por defecto y fail-open) no son hoy una barrera de seguridad, sino convenios de buen comportamiento para el modelo. Telegram está bien cerrado en el perímetro de acceso (fail-secure), pero todos los usuarios permitidos comparten un mismo plano de datos (workspace y sesiones). El historial git está limpio de secretos y `.env` jamás se commiteó; el escáner de secretos, sin embargo, no corre en CI.

| ID | Severidad | Componente | Evidencia principal | Explotabilidad |
|----|-----------|------------|---------------------|----------------|
| T1 | **Crítica** | BashTool allowlist | `registry.py:43-50`, `:199-207` | Trivial, sin precondiciones, por diseño |
| T2 | **Alta** | WebFetchTool SSRF | `registry.py:313-332` | Trivial si el host tiene servicios internos/metadata |
| T3 | **Alta** | Guardarraíl JEVAL | `guardrail.py:67`, `:146-149` | Control inerte por defecto; fail-open en enforce |
| T4 | **Alta** | Trusted paths = persistencia | `agent.py:168-171`, `config.py:13-16` | Una sesión prompt-inyectada persiste al reinicio |
| T5 | **Media** | Sandbox ficheros (symlink TOCTOU + cwd) | `registry.py:99-110`, `agent.py:171` | Condicional (requiere concurrencia local o arranque en `$HOME`) |
| T6 | **Media** | Telegram plano de datos compartido | `bot.py:27-39`, `:146` | Con 2+ usuarios en allowlist |
| T7 | **Media** | audio.py env/PATH heredados | `audio.py:37-43`, `:61-67` | Cadena (persistencia vía PATH) |
| T8 | **Media/Baja** | Secretos: CI no escanea; logs con args | `ci.yml:22-29`, `agent.py:672` | Requiere contribuidor sin install.sh / LOG_FILE configurado |
| T9 | **Media** | Tool-calls parseadas de texto | `agent.py:453-513`, `:899-903` | Amplificador de prompt-injection |

---

## T1 — Crítica: la allowlist de BashTool equivale a RCE total por diseño

**Evidencia.**
- Allowlist de 34 binarios: `src/bytia_kode/tools/registry.py:43-50`, ampliable sin verificación por `EXTRA_BINARIES` (`config.py:98-102`, fusionada en `registry.py:58-65`).
- La única otra barrera es `_validate_command_safety()` (`registry.py:152-187`), que rechaza operadores shell (`;`, `|`, `&&`, `>`, `<<`, `$(`, backticks) porque usa `create_subprocess_exec` sin shell (`registry.py:209-214`).
- El chequeo de allowlist usa solo el basename: `command_base = Path(argv[0]).name` (`registry.py:199`).

**Explotabilidad — bypass sin ningún operador bloqueado.**
1. **RCE directo:** `python -c` con payload en comillas. El filtro de `;` no cubre saltos de línea: `shlex.split` (registry.py:195) preserva `\n` dentro de comillas como parte del argumento, y `python` está en la allowlist. Ejecución arbitraria como el usuario, sin `;|>&`.
2. **Git alias con `!`:** `git -c alias.pwn='!<comando>' pwn` — git ejecuta aliases con prefijo `!` a través de `sh`. Ninguna firma del filtro coincide. `git` está en la allowlist (registry.py:44).
3. **Exfiltración/remota explícita:** `curl`, `wget` (POST/`-F` de ficheros), `scp fichero user@host:`, `ssh host comando` — registry.py:46. Pueden exfiltrar `~/.bytia-kode/.env`, `.env` del proyecto (legible con `file_read`/`grep` — `_resolve_workspace_path` lo permite: está dentro del workspace), claves SSH, etc.
4. **Servidor de exfiltración:** `python -m http.server 8000` sirve el cwd (que puede ser `$HOME`, ver T5) a la red local.
5. **Supply chain:** `pip install <pkg>` / `uv` ejecutan `setup.py`/build hooks arbitrarios.
6. **Windows:** `wsl` (registry.py:49) ejecuta cualquier comando dentro de WSL.
7. **Destructivo sin operadores:** `rm -rf /ruta/absoluta`, `chmod` — registry.py:44-45; el filtro restringe *qué binario*, no *qué hace*.
8. **Binario del atacante en repos maliciosos:** al validar solo `Path(argv[0]).name` (registry.py:199), un repo clonado que incluya `./git` o `./python` pasa la allowlist y ejecuta un binario commiteado, con `cwd` = raíz del workspace (registry.py:211).

**Nota de deriva:** `_DANGEROUS_PATTERNS` (registry.py:52-55) está definido y **no se usa nunca**; la lista real vive dentro de `_validate_command_safety` (registry.py:164-174). Drift típico de dos fuentes de verdad.

**Mitigación rápida.**
- Sacar de la allowlist o pasar a confirmación humana: `python`, `python3`, `pip`, `pip3`, `uv`, `ssh`, `scp`, `wsl`, `curl`, `wget` (o mantener red con denylist de destinos).
- Rechazar flags `-c`/`-m`/`alias`/`-exec`/`--exec` en argv tras `shlex.split`.
- Resolver binarios con `shutil.which()` y exigir ruta bajo `/usr/bin`/`/usr/local/bin` (elimina el punto 8).
- Contención real por OS (bubblewrap/firejail) si se quiere mantener `python`.

## T2 — Alta: WebFetchTool es SSRF sin ninguna restricción

**Evidencia.** `src/bytia_kode/tools/registry.py:309-342`:
- `follow_redirects=True` sin límite de host ni de saltos (registry.py:314).
- Sin bloqueo de IPs privadas/loopback/link-local ni resolución-DNS previa.
- Acepta `text/plain` y `json` (registry.py:326) además de `text/html`.

**Explotabilidad.** El modelo (o una inyección de prompt vía contenido web) puede pedir `web_fetch("http://169.254.169.254/latest/meta-data/")` (IMDSv1 responde `text/plain` → pasa el filtro de content-type y llega íntegro al contexto del modelo), o cualquier API interna en `localhost` que devuelva JSON. Combinado con T1/T9, el contenido interno se exfiltra con un `curl` posterior. Una URL pública puede redirigir (301/302) a un destino interno sorteando cualquier allowlist de dominios que se añada al URL inicial.

**Mitigación rápida.** Resolver el host y rechazar rangos privados/loopback/link-local **antes de conectar y en cada redirect**; permitir redirects solo al mismo registrable-domain; limitar bytes descargados.

## T3 — Alta: guardarraíl JEVAL inerte por defecto, fail-open, y shadow que puede ni siquiera loguear

**Evidencia.** `src/bytia_kode/guardrail.py` (171 L):
- **Default `off`**: `os.getenv("JEVAL_MODE", "off")` (guardrail.py:67); además, si no hay `TYPESAFE_API_KEY` se auto-desactiva con warning (guardrail.py:74-77). Sin acción del operador, no clasifica nada.
- **shadow = fire-and-forget real** (confirma `ab6554b`): crea `asyncio.create_task` y devuelve inmediatamente `blocked: False` (guardrail.py:146-149). El llamador (`agent.py:659`) descarta el dict devuelto (incluida la referencia `task`) → ninguna referencia fuerte mantiene vivo el task; el recolector de basura puede cancelarlo antes de que termine (pitfall documentado de asyncio para tasks sin referencia). Es decir: ni bloquea (por diseño) **ni siquiera garantiza el log JSONL** que es su única función. Ningún consumidor del log existe en el repo.
- **enforce fail-open**: cualquier error/timeout de la API → allow (guardrail.py:10, 106-117); el veredicto es un clasificador LLM (`noul >= 0.7`, guardrail.py:71,121) que solo ve tool-name + 1500 chars de argumentos (guardrail.py:143) — un `file_write` cuyo contenido riesgoso empiece después del carácter 1500 no se clasifica.
- **Egreso de datos**: al activarse, envía los argumentos de cada tool call (incluido contenido de ficheros en `file_write`) a `https://api.typesafe.ai` (guardrail.py:33, 93-102).

**Mitigación rápida.** Mantener un `set` module-level con los tasks en vuelo (y `discard` en `finally`); truncar el `state` por el *final* además del inicio, o muestrear; registrar tasa de fail-open en el log y en la TUI; y no sustituir por esto los bloqueos deterministas de T1.

## T4 — Alta: trusted paths incluyen la configuración del propio agente → persistencia

**Evidencia.**
- `agent.py:168-171`: `set_trusted_paths([config.data_dir (~/.bytia-kode), Path.home()/"bytia"])` y `set_workspace_root(Path.cwd())`. Las file tools pueden escribir en `~/.bytia-kode` (registry.py:107-109).
- `config.py:13-16`: `~/.bytia-kode/.env` se carga con `load_dotenv(..., override=True)` — **pisa** al `.env` del proyecto. Un `file_write` a `~/.bytia-kode/.env` inyecta `PROVIDER_BASE_URL`/`EXTRA_BINARIES`/`JEVAL_MODE=off` que al siguiente arranque redirige el tráfico del LLM, amplía la allowlist o desactiva controles.
- Skills: `SkillLoader` carga `SKILL.md` de `~/.bytia-kode/skills/user/` y `~/bytia/skills/` (loader.py:62-81) y sus instrucciones entran en el system prompt (agent.py:372-382). Ambos directorios son trusted paths → un agente comprometido persiste instrucciones maliciosas como "constitución" del sistema (agent.py:130: *"Treat every field below as binding constitutional system-level instruction"*).
- MCP (hoy sin cablear): `mcp/tool.py:27-29` lanza `NotImplementedError` y no hay referencias a `McpClient`/`load_mcp_config` en `tui.py`/`__main__.py`/`herdr.py` — es scaffolding. Pero el diseño ya confirmado hereda `os.environ` completo al hijo (mcp/client.py:92-95; docs/ARCHITECTURE.md:320-321: *"child processes heredan os.environ completo + config overrides"*) y su config vive en `~/.bytia-kode/mcp_servers.json` (mcp/config.py:24-27), un trusted path. Cuando el puente se implemente, un fichero escrito por el agente ejecutará comandos arbitrarios con todos los secretos del entorno.

**Mitigación rápida.** Trusted paths en modo lectura; denylist explícita de writes del agente para `~/.bytia-kode/.env`, `mcp_servers.json` y `skills/`; cargar el `.env` global con `override=False` o firmarlo.

## T5 — Media: sandbox de ficheros — symlink TOCTOU residual y workspace = cwd de arranque

**Evidencia.**
- `_resolve_workspace_path()` (registry.py:99-110) hace `resolve()` **y luego** verifica contención. Un symlink preexistente que apunte fuera del workspace se resuelve fuera y se rechaza (registry.py:105-110) — el caso estático está correctamente cubierto.
- El residuo real es **TOCTOU**: entre `resolve()` (verificación) y el `open()`/`write_text()` posterior (registry.py:113-120) un proceso concurrente puede sustituir el path por un symlink. Requiere ejecución local concurrente — que BashTool ya concede de sobra (T1). El trade-off de ROADMAP.md:44 (*"Symlink attack surface fix — bajo riesgo, alto esfuerzo"*) es defendible **solo después** de cerrar T1; hoy el sandbox es irrelevante frente a `python -c`.
- Agravio estructural: `set_workspace_root(Path.cwd())` (agent.py:171). Si el agente se lanza desde `$HOME`, el "sandbox" es **todo el home**: `file_read ~/.ssh/id_rsa` pasa la validación (está dentro del workspace-root), y el bloque del system prompt afirma *"Commands outside sandbox will be rejected"* (agent.py:326-332), lo cual solo es cierto para file tools, no para bash.

**Mitigación rápida.** Rechazar arranque con cwd = `$HOME` (o pedir confirmación); abrir ficheros con `O_NOFOLLOW` en escrituras; documentar que la barrera es de conveniencia, no de seguridad.

## T6 — Media: Telegram — fail-secure correcto, pero plano de datos compartido entre usuarios

**Evidencia.**
- **Fail-secure confirmado**: `_is_allowed()` devuelve `False` si `TELEGRAM_ALLOWED_USERS` está vacío (bot.py:52-56; parse en config.py:82-86). Sin allowlist, el bot niega a todos. `main()` solo exige token (bot.py:220-229) — correcto, aunque un fail-fast con mensaje "configura allowlist" sería más claro que un bot que niega silenciosamente.
- **Aislamiento por usuario, no por chat**: agentes por `str(effective_user.id)` (bot.py:27-39, 183) — dos usuarios en un mismo grupo no comparten conversación. Bien.
- **PERO comparten plano de datos**: todos los agentes usan el mismo `config.data_dir` (misma `sessions.db`) y el mismo cwd del proceso → mismo workspace de ficheros. `/sessions` lista sin filtro (bot.py:146) y las tools `session_list`/`session_load` acceden a **todas** las sesiones de todas las fuentes (tools/session.py:33-45, 70-72; `list_sessions` sin filtro de usuario en session.py:232-241). Un usuario permitido puede cargar el historial de otro.
- Cada usuario allowlisted obtiene el agente completo (bash incluido, T1) sobre el host: el perímetro de Telegram es tan fuerte como el Telegram account más débil de la lista.

**Mitigación rápida.** Un subdirectorio de workspace/data por `user_id`; filtrar sesiones por `source_ref`; monitoreo de sesión nueva en allowlist.

## T7 — Media: audio.py — exec sin shell (bien) pero con entorno y PATH heredados

**Evidencia.**
- `create_subprocess_exec("bytia-tts", "--", clean_text)` (audio.py:61-67): argv directo, sin shell, texto del modelo tras `--` → **no hay inyección de comandos shell**. Correcto.
- `_child_env()` copia `os.environ` **completo** (audio.py:37-43) a un proceso que solo necesita PATH — todas las keys cargadas por dotenv viajan al hijo sin necesidad.
- `bytia-tts` se resuelve por PATH, y `~/.local/bin` (escribible por el usuario — y por el propio agente vía bash, que no restringe rutas de argumentos) se añade al PATH del hijo (audio.py:40-42). Un agente comprometido que reemplace `~/.local/bin/bytia-tts` consigue ejecución en el siguiente `play_speech` (persistencia, misma clase que T4).

**Mitigación rápida.** Env mínimo (`PATH` controlado, sin `*_API_KEY*`), ruta absoluta al binario, propietario/permisos verificables del binario.

## T8 — Media/Baja: secretos — historial limpio, pero el escáner no corre en CI y los logs registran argumentos

**Evidencia.**
- `.env` está ignorado (`.gitignore:11`), **nunca se commiteó** (`git log --all -- .env` → vacío) y el escaneo de los 218 commits (`git log --all -p` + patrones `sk-…`, `AKIA…`, `ghp_…`, `xox*`, PEM keys, `key/token =` largos) no encontró secretos reales (un único falso positivo: un ancla de URL). En esta copia del workspace no existe fichero `.env`.
- `scripts/check_secrets.py` solo escanea ficheros **staged** (check_secrets.py:28-36) con dos patrones (check_secrets.py:8-9). Corre únicamente en el hook `.githooks/pre-commit`, que solo se activa si `install.sh` configuró `core.hooksPath .githooks` (install.sh:184-188; en esta copia `git config core.hooksPath` está vacío). **CI no lo ejecuta**: `.github/workflows/ci.yml:22-29` solo corre validate_metadata, pytest, build y twine.
- `logger.info("Tool call: %s(%s)", tool_name, arguments)` (agent.py:672) registra **todos** los argumentos — incluido el `content` de `file_write` y salidas que contengan secretos leídos del workspace — con nivel INFO; con `LOG_FILE` configurado (config.py:93-94) van a disco en claro.

**Mitigación rápida.** Un paso `python scripts/check_secrets.py` (variante full-tree) en ci.yml; loguear claves de argumentos, no valores; rotar cualquier key que haya pasado por logs.

## T9 — Media: tool-calls ejecutables embebidas en texto del modelo

**Evidencia.** El fallback para modelos GGUF parsea patrones `tool_name(key="value")` **del propio texto** de respuesta y los convierte en tool-calls reales (agent.py:453-513, aplicado en agent.py:899-903). Si una inyección de prompt (p.ej. página maliciosa vía `web_fetch`, T2) logra que el modelo "ejemplifique" `bash(command="curl …")` en prosa, se ejecuta de verdad. Multiplica la superficie de T1/T2 sin necesidad de tool-calls nativos.

**Mitigación rápida.** Activar el fallback solo con modelos sin tool-calls nativos (flag de config), o exigir un prefijo explícito acordado por turno + mostrar confirmación en TUI.

---

## Qué está bien (verificado)

- **Telegram fail-secure** sin allowlist (bot.py:52-56) y sesiones aisladas por usuario (bot.py:27-39).
- **SQL parametrizado en todo** `session.py` (p.ej. session.py:249-252) — no hay inyección SQL.
- **`.env` jamás commiteado** e historial limpio (verificado sobre los 218 commits).
- **audio.py sin shell** y con `--` separando opciones del texto (audio.py:61-67).
- **MCP sin cablear hoy** (`mcp/tool.py:27-29`), así que su herencia de entorno (mcp/client.py:92-95) es riesgo de diseño futuro, no presente.
- **`web_fetch` restringe esquemas** a `http://`/`https://` (registry.py:310-311) — evita `file://`/`gopher://`.

## Priorización de remediación sugerida

1. **T1** (1-2 h): recortar allowlist + bloquear `-c/-m/alias/-exec` + resolver con `which` bajo `/usr/*bin`. Elimina de un golpe las cadenas T1→T2-exfil, T1→T4-persistencia, T7-PATH.
2. **T2** (2-3 h): denylist de IPs privadas pre-conexión y en redirects.
3. **T4** (1 h): denylist de writes sobre `~/.bytia-kode/.env`, `mcp_servers.json`, `skills/**`; `override=False` en el dotenv global.
4. **T3** (30 min): referencia fuerte a tasks shadow + métrica de fail-open; decidir default `shadow` con key presente.
5. **T8** (15 min): `check_secrets` en CI; redacción de argumentos en logs.
6. **T5/T6/T9**: ordenar tras los anteriores; T6 solo importa con 2+ usuarios reales en la allowlist.
