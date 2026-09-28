# Changelog

## [0.8.2] - 2026-09-28

Blindaje de cancelación (AST-24, commit `13ccac7`, de GitHub issue #3): los
botones del pánico se comportan como se espera incluso en los casos que daban
miedo. Interrumpir o matar al agente a mitad de tarea no deja subprocess vivos
ni estado sucio: lo que ya se generó se conserva, lo que no llegó a correr no
corre, y el turno siguiente nace limpio.

### Fixed — interrumpir en mitad de la generación conserva lo parcial

- **Escape (`/stop` en Telegram) ya no pierde el turno**: la parte de la respuesta que ya llegó al cortar se conserva en la conversación y queda persistida en la sesión en disco — al recargar la sesión, el turno cancelado sigue ahí. Un turno cortado antes de llegar el primer texto ahora deja `(respuesta cancelada)` en la transcripción; antes no dejaba nada.

### Fixed — un kill durante un lote de herramientas aborta el resto

- **Ctrl+K (`/kill`) mientras corre la herramienta 1 de N ya no ejecuta las herramientas 2..N** sobre un agente que el usuario mató: el lote restante se aborta y cada herramienta que no llegó a correr queda respondida `[cancelled by user]`, en memoria y en sesión — sin tool calls colgados en la transcripción.

### Fixed — el kill termina el comando de bash en curso, con escalado

- **Matar durante un comando largo de bash termina el subprocess**: primero `terminate`, y si el proceso ignora la señal, **escalado a SIGKILL**. El registro del subprocess vivo ya no depende de que cada interfaz (TUI, Telegram) lo conecte a mano — vive en el propio Agent y funciona en cualquier embedding.

### Changed — cleanup estructurado de la cancelación

- **`AgentCancelledError`** (`bytia_kode.errors`): excepción propia que señala "el usuario canceló aquí". El cleanup vive en un solo sitio: persistir la respuesta parcial y responder los tool calls pendientes. Detalle deliberado: NO hereda de `RuntimeError` — `chat()` trata esa familia como fallo de provider con failover, y una cancelación no es un fallo.
- **El turno siguiente nace limpio**: el estado de cancelación se limpia al entrar en cada turno; las invariantes del agente (limpieza una vez por turno; `kill()` no limpia el evento, porque puede retornar antes de que el loop lo observe) quedan blindadas por tests.

### Added — primeros tests de la TUI

- **Tests de interrupción de la TUI** con el Pilot integrado de Textual (`App.run_test()`, sin dependencia nueva): Escape llama a interrupt, Ctrl+K a kill, sin widgets de streaming colgados y con el flujo de mensaje cortado a mitad. El 100% de cobertura de `tui.py` sigue siendo deuda declarada.

## [0.8.1] - 2026-09-27

Cierre de la 0.8.x: **estreno real del flujo OIDC de publicación** y saneado de la documentación. Publica el fix `--bot` que quedó en main tras v0.8.0 (AST-22) y añade `--version`, el auto-reseed real de skills vendor y la GitHub Release automática.

### Fixed — el console script despacha `--bot` (AST-22, publicado aquí)

- **`bytia-kode --bot` arranca el bot**: `bytia-kode = bytia_kode.__main__:main` (antes `tui:run_tui`). En 0.8.0, `bytia-kode --bot` arrancaba la TUI en silencio — el flag sólo funcionaba vía `python -m bytia_kode`. El fix estaba en main desde AST-22; esta release lo publica.

### Fixed — skills vendor se actualizan en instalaciones de PyPI (AST-23)

- **`.vendor-version` con la versión real**: `_get_package_version()` lee `importlib.metadata` (dist-info) antes que el `pyproject.toml` del checkout. En site-packages no hay pyproject: el sello decía `"unknown"` en TODA instalación de PyPI, así que `installed_version == current_version` se cumplía siempre y el auto-reseed por upgrade nunca disparaba — las skills vendor actualizadas no llegaban al usuario. Orden: dist-info → pyproject del checkout → `"unknown"`.

### Added — `--version` (AST-23)

- **Cortesía para usuarios de pip**: `bytia-kode --version` imprime `versión (+ build id si existe)` y sale 0 — nunca arranca la TUI ni el bot. Gana el primer flag (`--version --bot` imprime la versión igual).

### Added — GitHub Release automática con notas del CHANGELOG (AST-23)

- **Job `github-release`** en `release.yml` (`needs: build + publish`): tras publicar en PyPI crea la GitHub Release del tag con las notas **extraídas de `CHANGELOG.md`** — fuente única de verdad, nada de notas a mano ni PR-lists de GitHub. Fail-closed: tag sin entrada en el CHANGELOG → job rojo, nunca una Release vacía. Contexto: v0.7.8 siguió de "Latest" cinco horas después de publicar 0.8.0 porque la Release se creaba a mano. Permiso `contents: write` sólo en ese job.

### Added — RELEASING.md: el proceso real (AST-23)

- **El flujo de publicación vive en el repo**: preparación (CHANGELOG + pyproject + `uv.lock` bumpados juntos), tag `v*`, gates CI, PROD GATE (environment `pypi`, aprobación del Socio por UI), intercambio OIDC → PyPI, verificación post-publish (wheel en venv limpio, `--version`, `.vendor-version`, ficha de PyPI), camino manual de emergencia (el de v0.8.0, con rotación de token) y las reglas (publish aprobado por el Socio, CHANGELOG como única fuente de notas, un tag se publica una vez).

### Changed — README profesional (AST-23)

- **Fuera las 16 secciones "Novedades en vX.Y.Z"** (v0.5.0→v0.7.8, ~110 líneas) que duplicaban el CHANGELOG (= drift) — sustituidas por una línea: "Historial completo: CHANGELOG.md". También fuera el disclaimer ⚠️ sobre ellas.
- **Reestructura**: qué es/para qué → badges → instalación (canónica PyPI) → quickstart → características → arquitectura → bot Telegram → desarrollo → docs.
- **Badges dinámicos** (PyPI, CI) en vez del conteo de tests hardcodeado; **capturas con URL absoluta** (PyPI no resuelve rutas relativas del long_description); `--version`/`--bot` documentados como modos; fix de un fence huérfano que se tragaba la sección Validación.
- **Guard tests**: cero secciones novedades, línea de historial al CHANGELOG, ninguna imagen con ruta relativa.

### Changed — instalación canónica desde PyPI (AST-22)

- **`install.sh` reescrito**: bootstrap de uv → `uv tool install bytia-kode` (PyPI) → configuración de `~/.bytia-kode/.env` (preservado si existe) + skills dirs. **Ya no clona el repo** ni genera wrapper: el binario `bytia-kode` es el console script del paquete. El clone queda solo para desarrollo (`docs/DEVELOPMENT.md`).
- **README/docs alineados**: sección Instalación = PyPI (`pip install bytia-kode` / `uv tool install bytia-kode`), badge PyPI, clone marcado como camino de desarrollo. `scripts/validate_metadata.py` ahora exige el camino PyPI como reflejo de la instalación oficial (antes exigía `uv run bytia-kode`).

### Added — release por Trusted Publishers, el workflow (AST-22)

- **`.github/workflows/release.yml`**: push de tag `v*` → gates (secret scan + metadata + suite) → `uv build` → `twine check` → `pypa/gh-action-pypi-publish` **por OIDC** (`permissions: id-token: write`), **cero secretos en el repo**.
- **PROD GATE en forma GitHub**: el job publish corre en el environment `pypi` con required reviewer — cada release la aprueba el Socio con un clic en la UI. **Fail-closed por diseño**: sin el Trusted Publisher registrado en PyPI, el publish falla en el intercambio OIDC y no publica nada.
- **Tests de guarda**: `tests/test_canonical_install.py` (install.sh sin git, README refleja PyPI, entry point + despacho `--bot`) y `tests/test_release_workflow.py` (trigger solo tags `v*`, environment `pypi`, OIDC sin secretos, gates antes de build, GitHub Release tras publish con notas del CHANGELOG).

## [0.8.0] - 2026-09-27

Release centrada en **seguridad y verdad del repo** (revisión AST: oleadas O0–O2 + ronda F de endurecimiento). Lo que contiene de verdad:

### Security — perímetro de ejecución (T1/T2/T4/T8)

- **T1 — allowlist de bash recortada a 24 binarios** (`src/bytia_kode/tools/registry.py`): fuera `python`/`pip`/`uv`/`ssh`/`scp`/`curl`/`wget` y familia (RCE/exfiltración por diseño). `EXTRA_BINARIES` sigue siendo la válvula manual del operador. Guards de argv sobre shlex.split: `-c`/`-m` en intérpretes (aunque el operador los re-habilite), `git -c alias.*`, `--exec` genérico. Resolución `shutil.which()` + exigencia de `/usr/bin` o `/usr/local/bin` (mata el vector `./git` commiteado). (AST-14)
- **T1 capa 2 — programas inline y posicionales**: rechazo de flags de ejecución de código en intérpretes reintroducidos (`-e`/`-E`/bundles con `e`, `-r` de php, `-p` de node, `--eval`, `--source` — F1/AST-18) y de programas posicionales de `awk`/`gawk` (`-f fichero` obligatorio — F2/AST-19). Fail-closed deliberado en bundles (`sh -e` se rechaza igual).
- **T2 — SSRF cerrada en `web_fetch`** (AST-15): `_assert_public_host` resuelve el host y rechaza privados/loopback/link-local/reserved para **todas** las IPs antes de conectar; redirects manuales máx. 3 saltos re-validando cada destino; límite de descarga 1 MiB en streaming.
- **T4 — denylist de escritura en trusted paths** (AST-15): `file_write`/`file_edit` rechazan escribir sobre `~/.bytia-kode/.env`, `mcp_servers.json` y `skills/**` (reads permitidos, decisión documentada). El `.env` global se carga con `override=False` y el del proyecto tiene precedencia.
- **T8 — secretos**: redacción de argumentos en logs de tool calls (claves + valores hasheados, `sha256:` de prefijo corto) y **scan de secretos full-tree en CI** (`scripts/check_secrets.py --all`), además del hook pre-commit staged. (AST-16)

### Suite — hermética, 331 tests

- Gate JEVAL sin `TYPESAFE_API_KEY`, fin de la basura `MagicMock/` (O0-A/AST-11): la suite corre hermética en CI y en venv limpio.
- +147 tests de regresión sobre los 184 herméticos: perímetro T1/T2/T4 (incl. F1/F2), redacción T8, escáner de secretos, extras `[mcp]` y build id (AST-20). Total: **331 passed** (`pytest -q`).

### Docs — una sola verdad (D1–D22)

- README/ROADMAP/CHANGELOG/HANDOFF/ARCHITECTURE sincronizados con `pyproject.toml` (parche documental D1–D22): versión, conteo de tests, allowlist, estado real de MCP. `scripts/validate_metadata.py` hace fail en CI si CHANGELOG y versión divergan.

### Added — build id en el header: `v0.8.0+<commit>` (2026-09-27, AST-20)

- **Header y arranque**: la barra de estado de la TUI y el log de arranque muestran `v0.8.0+<hash>` (`src/bytia_kode/_build_info.py`); el banner `/start` de Telegram igual. Residuo del hallazgo C6: dos builds eran indistinguibles entre bumps de versión.
- **Tres modos**: editable lee `git rev-parse --short HEAD` en runtime; wheel/sdist estampan `_commit.txt` en build time (hook `hatch_build.py`); sin estampa ni git (p.ej. PyPI) degrada a `v0.8.0` a secas — nunca falla. En site-packages jamás se consulta git (un venv dentro de un repo ajeno no hereda su hash).
- **Coste**: resolución única por proceso (`lru_cache`), ni git ni disco en cada render.

### MCP Client — WIP declarado, NO feature de esta release

> **⚠️ Experimental (WIP), no anunciar como capacidad terminada.** El cliente MCP está a medio construir: **`McpTool.execute()` sigue siendo `NotImplementedError`** (`src/bytia_kode/mcp/tool.py`), no existe `mcp/manager.py` (lifecycle) ni wiring en `agent.py`/`tui.py`. El extra `[mcp]` (`pyproject.toml`) es **experimental**: instalarlo habilita el paquete `bytia_kode.mcp`, que degrada a stubs no-op (soft-import guard en `mcp/__init__.py` — verificado en CI y en venv limpio). Sin el extra, B-KODE funciona igual con solo tools nativas.

Código base presente (sin ejecución real todavía):

- **`src/bytia_kode/mcp/config.py`**: `McpServerConfig` dataclass + `load_mcp_config()` desde `~/.bytia-kode/mcp_servers.json`. Formato compatible con Claude Code.
- **`src/bytia_kode/mcp/__init__.py`**: Public API + soft-import guard. Si el SDK `mcp` no está instalado (o `manager.py` sigue en WIP), exporta stub no-op.
- **`src/bytia_kode/mcp/client.py`**: `McpClient` con transporte stdio + `AsyncExitStack` para lifecycle de context managers del SDK. Handshake (`initialize`), descubrimiento (`tools/list`), ejecución (`tools/call`) con timeouts.
- **`src/bytia_kode/mcp/tool.py`**: `McpTool` (subclase de `Tool`) — puente Adapter Pattern. Naming: `mcp__{server}__{tool}`. **`execute()` pendiente** (`NotImplementedError`).

#### Architecture Decisions (MCP)

- **Adapter Pattern**: MCP tools extienden `Tool`, se registran en `ToolRegistry` existente. Zero cambios en dispatch.
- **AsyncExitStack**: Los context managers del SDK MCP (`stdio_client`, `ClientSession`) se mantienen vivos durante toda la sesión.
- **Entorno heredado + overrides**: Child processes heredan el entorno completo del padre (necesario para WSL2/venvs/CUDA), con overrides desde config.
- **Soft dependency**: `mcp` SDK como `[mcp]` optional. Sin él, B-KODE funciona con solo tools nativas.

### Added — selección directa de providers (2026-09-16)

- **F1 = modo AUTO** (`pin(None)`): failover Studio→Ollama→nube; reversible desde cualquier pin.
- **F4 Studio · F5 Ollama · F6 Z.ai · F7 DeepSeek · F8 Router**: pin manual directo con aviso de circuito abierto. F3 sigue ciclando.
- Fix: el fire inmediato de `watch()` en el mount pineaba `primary` al arranque (regresión del hotfix anterior) — el watcher ignora `old == new`.

### Fixed — failover vivo (2026-09-16)

Dos bugs HIGH detectados por OpenCodeReview (`ocr` · deepseek-flash) revisando la cadena auto v3 (`ae97b37`):

- **Pin implícito mataba el failover**: reasignar `active_provider` (reactivo) en `_auto_detect_model` y en el handler `provider_used` disparaba `_on_provider_changed` → `pin()` implícito → `agent.chat` cortaba por `pinned`. El walk Studio→Ollama→nube quedaba desactivado de facto (en el arranque y en cada failover). Fix: guard `_provider_sync` — el reactive se sincroniza display-only; el pin solo cambia con acción manual (F3).
- **Router no pineable**: `primary` fuera de `_priority_order` → `list_available()` nunca lo devolvía → F3 no ofrecía el router. Fix: `ProviderManager.list_pinnable()` (cadena auto + primary); seleccionar `primary` en F3 ahora **pina el router** (demanda manual real: `get_healthy` lo sirve por pin, error honesto si está caído).

Re-review con `ocr` del propio fix: 0 HIGH; hardening aplicado (sync con `try/finally`, `active_provider` sigue al motor efectivo, rename `list_pinnable`). La vía de vuelta a modo AUTO llegó con F1 (selección directa, mismo día).

Tests: 173 passed (2 nuevos). Auditoría posterior (mismo día): la "limitación conocida" del failover era fantasma — el auto-sanado vía half-open está verificado con `test_self_heal_returns_to_chain_head_after_recovery` (174 passed).

### Pending — MCP (siguiente release; nada de esto bloquea v0.8.0)

- `mcp/manager.py` — lifecycle manager
- `agent.py` + `tui.py` wiring — bootstrap integration
- Tests — `test_mcp_config.py`, `test_mcp_tool.py`
- `McpTool.execute()` — implementación del puente (TODO(human))

### Added — Puente herdr (integración con multiplexor)

Cuando B-KODE corre dentro de un pane de herdr (env `HERDR_PANE_ID`), se
reporta al panel de agentes del multiplexor con su nombre y ciclo de vida
(working/idle/blocked), igual que los agentes nativos soportados (claude,
codex, opencode…).

- **`src/bytia_kode/herdr.py`**: `HerdrBridge` — thread daemon con cola
  (fire-and-forget, nunca bloquea la TUI), de-dup de estados repetidos,
  `--seq` monotónico y kill-switch `BYTIA_KODE_HERDR=0`. Fuera de herdr:
  inactivo (cero overhead).
- **`src/bytia_kode/tui.py`**: `ActivityIndicator.set_status` notifica el
  bridge — choke point único: `ready→idle`, `thinking/tool/skill→working`.
  Además pasa un `session_id_fn` (lee `agent._current_session_id`) y notifica
  cambios de sesión en `/load` y `/new`.
- **Sesión activa**: el bridge ancla el id de sesión (`--agent-session-id`)
  al identificarse y lo re-ancla cuando cambia (inmediato en /load //new,
  lag de un ciclo de estado en el resto).
- **`tests/test_herdr.py`**: 21 tests (activación, mapeo, dedup, seq,
  sintaxis CLI, robustez, sesión).

### Architecture Decisions (herdr)

- **CLI sobre socket**: el bridge invoca `herdr pane report-agent*` (interfaz
  pública estable) en vez del protocolo interno del socket.
- **Orden de args canónico**: `<PANE_ID>` antes que las opciones — el parser
  del CLI 0.8.2 rechaza valores espaciados si las opciones van primero
  (verificado empíricamente 2026-09-15 contra herdr real).
- **Degradación silenciosa**: fallos del CLI (herdr cerrado, timeout) → log
  debug; jamás afectan al funcionamiento del agente.
- **Sesión forward-compatible**: herdr 0.8.2 acepta `report-agent-session` de
  agentes self-reported (exit 0) pero aún no expone ni persiste visiblemente
  la sesión (verificado: agent get/list, api snapshot, estado en disco). Se
  envía igualmente — el día que herdr lo consuma, B-KODE ya lo reporta.

## [0.7.8] - 2026-04-30

### Fixed

- **BashTool allowlist incompleta**: Añadidos `rg` (ripgrep), `bat`, `eza`, `tokei`, `shellcheck` a `_DEFAULT_BINARIES`. Antes, el agente recurría a `python -c` como workaround. Binarios `z`, `tmux`, `gh` excluidos deliberadamente (sin valor para agente no-interactivo o superficie de seguridad excesiva).
- **Race condition en kill()**: `_active_subprocess` capturado en variable local antes del check de `returncode`. Elimina ventana teórica donde el callback `on_subprocess` podría sobrescribir la referencia durante terminate/kill.

### Added

- **Test: system message preservation**: Verifica que mensajes `role="system"` en cualquier posición de `self.messages` sobreviven a `_manage_context()`. El enforcement ya existía (filtro `non_system` en `agent.py:538`), pero el test protege contra regresiones futuras. 145 tests total.
- **Session metadata persistence**: `update_metadata()` en `SessionStore` persiste `model` y `token_count` por sesión. Hook en `Agent.chat()` actualiza ambos campos tras cada turno. SQL parametrizado con allowlist de campos.
- **Code review document**: `docs/CODE-REVIEW.md` con análisis triple (Hermes + Peke + Claude). 11 patrones buenos, 5 flags analizados, priorización para v0.7.8.

### Changed

- **ROADMAP.md**: Corregido allowlist marcada como completada cuando no lo estaba, binarios sin valor eliminados, threshold arbitrario TUI eliminado, cabecera actualizada.
- **CODE-REVIEW.md**: Flag #5 corregido (no era bug, enforcement existía), idiomas mezclados corregidos, tamaño TUI precisado.

## [0.7.7] - 2026-04-29

### Fixed

- **Tool Error Memory hash normalization**: `_get_tool_error_key()` now hashes only the `command` field (bash) or `path` field (file_write/file_edit) instead of the full JSON arguments. Previously, same command with different `workdir`/`timeout` produced different hashes, bypassing the error memory and allowing repeated blocked commands.
- **BashTool allowlist missing `df`**: Added `df` to `_DEFAULT_BINARIES` for disk diagnostics. Previously required `python -c` workarounds.
- **BashTool allowlist missing `du`, `head`, `tail`**: Added read-only diagnostic/filtering binaries. `du` for disk usage, `head`/`tail` for file inspection.
- **BashTool error messages lack hints**: Binary rejection messages now include the list of allowed commands and contextual hints (e.g., `cd` → "use workdir parameter"). Reduces agent retry loops from 7+ to 1.
- **Flaky test `test_file_write_tool_handles_relative_path`**: Test now calls `set_workspace_root()` to reset the global `_WORKSPACE_ROOT`, preventing contamination from earlier tests.
- **pytest `testpaths` missing**: Added `[tool.pytest.ini_options]` with `testpaths = ["tests", "src/tests"]`. Previously `uv run pytest -q` collected only 116 of 142 tests.

### Added

- **2 tests**: `test_error_memory_hashes_command_only` (hash stability with different workdir), `test_error_memory_blocks_security_policy_rejections` (pipe/chain commands remembered). Total: 144.

## [0.7.6] - 2026-04-29

### Fixed

- **YAML multiline description parser**: `_parse_skill()` now correctly handles `description: >` folded scalars by accumulating indented continuation lines. Previously, descriptions using agentskills.io format resulted in literal `>` string.
- **sync-vendor-skills.sh Python heredoc**: Script passed arguments via `python3 - "$args" << 'PYEOF'` instead of bare heredoc without sys.argv.
- **Secret scanner false positive**: Added `src/bytia_kode/vendor/skills/` to skip dirs (MCP tool names trigger 30-char entropy check).

### Added

- **FIX-3: Tool Error Memory** — `_tool_error_memory` dict (previously declared but unused) now stores MD5 hashes of rejected bash/file_write/file_edit arguments. Same command is skipped with `[blocked]` message on retry. Safe tools (file_read, grep) are not tracked.
- **FIX-4: Workspace Context Awareness** — `_workspace_context_block()` injects CWD, sandbox constraints, and trusted paths into the dynamic system prompt so the agent knows its boundaries before attempting operations.
- **sync-vendor-skills.sh** — New script that syncs skills from `~/bytia/skills/` to vendor/ with automatic agentskills.io → flat format transformation. Supports `--list`, `--sync`, and per-skill sync.
- **Vendor skills auto-update**: `_ensure_vendor_skills()` checks `.vendor-version` file and only reinstalls when package version changes.
- **9 tests**: 3 loader YAML multiline edge cases, 3 FIX-3 tool error memory, 3 FIX-4 workspace context.

### Changed

- **Vendor skills format**: Restored to flat format after agentskills.io sync corruption. All 4 vendor skills (bytia-constitution, bytia-memory, graphify, skills-manager) now use flat frontmatter compatible with KODE parser.

## [0.7.5] - 2026-04-29

### Changed

- **Skills System Architecture**: Migrated from flat `~/.bytia-kode/skills/` to layered structure with vendor/user/bytia priorities. Skills are now organized in layers: `bytia/` (ecosystem, highest priority) → `user/` (custom, writable) → `vendor/` (bundled, lowest priority).

### Added

- **Vendor Skills**: Core skills (bytia-constitution, bytia-memory, skills-manager, graphify) are now bundled in `src/bytia_kode/vendor/skills/` and installed automatically.
- **SkillLoader Layer Support**: `SkillLoader` now supports layered directory scanning with priority-based override (bytia > user > vendor).
- **Auto-installation of Vendor Skills**: `AppConfig._ensure_vendor_skills()` copies vendor skills on first run or update.
- **install.sh BytIA Integration**: Installer detects `~/bytia/` ecosystem and offers to create symlink for shared skills.
- **`get_skill_info()`**: New method to inspect loaded skills and layers.

### Fixed

- **SKILL.md Constant**: Corrected typo `SKILL_FILE = "SKILL_FILE"` → `SKILL_FILE = "SKILL.md"`.

### Security

- **Vendor skills are read-only**: User cannot modify vendor skills directly. Verification copies to user layer first.

## [0.7.4] - 2026-04-28

### Fixed

- **DeepSeek V4 error 400**: `reasoning_content` ahora se incluye en todos los mensajes `assistant` posteriores a un tool call cuando se usa DeepSeek en thinking mode. El flag `_has_had_tool_calls` (antes muerto) se activa correctamente y `_ensure_deepseek_reasoning()` parchea los mensajes antes de enviarlos a la API.
- **Streaming timeout (silent hang)**: `_stream_with_timeout()` envuelve el iterador SSE con `asyncio.wait_for()` por chunk (60s). Si el provider deja de emitir datos sin cerrar la conexión, se lanza `TimeoutError` en lugar de colgarse indefinidamente.
- **Cloud API polling storm**: `_poll_router_info()` ahora verifica `client.is_local` antes de llamar a `get_router_info()`. Solo el router local (localhost) recibe polling cada 5s. APIs cloud (DeepSeek, MiniMax, Z.ai) se saltan — su endpoint `/v1/models` no expone métricas de llama.cpp.

### Added

- `ProviderClient.is_local`: nueva propiedad que detecta si el provider es un servidor local (localhost/127.0.0.1).
- `Agent._stream_with_timeout()`: wrapper de iterador async con timeout por chunk.
- `Agent._ensure_deepseek_reasoning()`: parchea mensajes para cumplir requisitos de DeepSeek thinking mode.

## [0.7.3] - 2026-04-27

### Changed

- **SP cache**: system prompt cached per message count, avoids double rebuild per iteration (~500ms/iter saved).
- **Router polling**: paused during agent processing to eliminate unnecessary HTTP requests.
- **Placeholder**: reasoning text used as fallback instead of literal `(sin respuesta de texto)`, reducing history pollution.
- **Batch compression**: 5 messages at once (was 2), last 4 non-system messages always preserved, truncation for very old history.

### Tests

- 130 passed — no regressions

---


## [0.7.2] - 2026-04-26

### Added

- **DeepSeek V4 provider**: 5th provider slot with OpenAI-compatible endpoint (`api.deepseek.com`). Models: `deepseek-v4-flash` (default, fast MoE) and `deepseek-v4-pro` (thinking/reasoning). Configurable context limit via `DEEPSEEK_MAX_CONTEXT` env var (default 1M tokens). Priority 4 in chain: primary → fallback → minimax → deepseek → local.
- **Provider pinning (sticky)**: F3 manual provider selection now pins to the chosen provider. Agent uses pinned provider exclusively — no auto-fallback on failure. Unpin by switching back to Primary with F3. Auto-fallback (circuit breaker + priority walk) still works when no pin is set.
- **Context-aware provider switching**: Context limit updates on every F3 provider switch. DeepSeek gets configured limit (1M), others get agent default (262k), primary delegates to router polling.

### Fixed

- **`/model` table missing providers**: Hardcoded provider list in `_show_model_info()` now includes DeepSeek.
- **`_provider_display_name` missing**: Added "deepseek" → "DeepSeek" mapping.
- **Stale context on provider switch**: Switching from DeepSeek (1M ctx) to another provider no longer keeps the 1M limit. Each provider properly resets ctx.
- **Claude Code settings.json model override conflict**: `ANTHROPIC_DEFAULT_{SONNET,OPUS,HAIKU}_MODEL` GLM overrides in settings.json were overriding process env vars from provider aliases. Moved GLM model vars to `claude-zai` and `claude-zai-yolo` aliases explicitly. Each alias now controls its own models.
- **DeepSeek 400 Bad Request after tool calls**: `reasoning_content` from DeepSeek responses is now stored in `Message` and passed back in subsequent requests. Without this, DeepSeek rejects requests where the previous assistant turn included tool calls but `reasoning_content` was missing. Affects `ProviderResponse`, `Message`, `SessionStore` schema, and agent message persistence.

### Changed

- **Agent error handling**: Pinned provider failures now yield error and stop (user switches manually). Non-pinned failures still auto-fallback via circuit breaker (unchanged behavior).
- **`get_healthy()`**: Returns pinned provider unconditionally when set. Priority walk only used when no pin.
- **`.zshrc` aliases**: `claude-ds` added (DeepSeek Anthropic-compatible endpoint). `claude-zai` and `claude-zai-yolo` now carry explicit GLM model vars. `~/.bytia-banner` updated with new provider.

### Tests

- 130 passed — no regressions.

---

## [0.7.1] - 2026-04-15

### Fixed

- **Reasoning tag leak**: `<reasoning>` tags no longer stored in message history. Prevents tag pollution in subsequent model turns. Reasoning is still displayed in TUI ThinkingBlock but not persisted.
- **Fallback notification missing**: `provider_used` chunk now emitted in exception handler path, not just initial provider selection. User sees "Switched to: Fallback" on within-request provider changes.
- **Circuit breaker recovery**: `get_healthy()` always walks full priority order. Primary circuit naturally retried after HALF_OPEN recovery (60s), regardless of previously active provider.
- **Security bypass**: Added `rmdir` to BashTool allowlist. Model no longer needs `file_write` + `python script.py` workaround for removing empty directories.
- **Duplicate system messages**: Removed `_add_system_message()` from reactive watcher `_on_provider_changed`. Notification now comes exclusively from chunk handler — no duplicates.
- **Stale venv**: Removed orphaned `uv tool install` (v0.5.3) from `~/.local/share/uv/tools/`. Single installation via project's editable `.venv`.

### Changed

- `(sin respuesta de texto)` replaces `[razonamiento sin respuesta de texto]` as empty response fallback.
- `get_healthy()` refactored: always evaluates from top of priority order, `preferred` parameter only used as last resort when all circuits are OPEN.

### Tests

- 110 passed — assertions updated for new reasoning storage behavior.

---

## [0.7.0] - 2026-04-15

### Added

- **Circuit Breaker**: CLOSED/OPEN/HALF_OPEN state machine for provider resilience. 3-failure threshold, 60s recovery timeout. `force_open()` for immediate circuit breaking on startup.
- **Auto-fallback**: Provider chain (primary → fallback → local) with automatic switching on failure. Loop-internal `continue` for seamless retry.
- **Provider signaling**: `("provider_used", name)` chunk type for agent→TUI provider communication.
- **Status line updates**: ActivityIndicator reflects active provider and model on switch.

---

## [0.6.1] - 2026-04-12

### Fixed

- Agentic loop infinite restart after tool execution.
- ToolRegistry.execute() accepts `on_subprocess` callback from Agent.

---

## [0.6.0] - 2026-04-11

### Added

- **Panic Buttons**: Escape (interrupt stream) + Ctrl+K (kill agent + subprocess).
- **Native exploration tools**: GrepTool, GlobTool, TreeTool.
- **Sandbox**: `_validate_command_safety()` blocks shell operators (pipes, redirects, heredocs, subshells).
- **Reasoning persistence**: Assistant messages store reasoning alongside text.
- **106 tests** passing.

---

## [0.5.0] - 2026-04-10

### Added

- 19 TUI themes with CSS.
- Streaming rendering with RichMarkdown.
- ThinkingBlock (collapsible reasoning).
- ToolBlock (color-coded execution output).
- Session management: /sessions, /load, /new, /reset.

---

## [0.4.0] - 2026-04-09

### Added

- Telegram bot with fail-secure authentication.
- Skills system (load, save, search, verify).
- Memory directories (contexto, decisiones, procedimientos, tecnologia).

---

## [0.3.0] - 2026-04-08

### Added

- BashTool, FileReadTool, FileWriteTool, FileEditTool, WebFetchTool.
- SQLite WAL session store.
- Session tools (list, load, search).

---

## [0.2.0] - 2026-04-07

### Added

- Multi-provider support (primary/fallback/local).
- httpx SSE streaming.
- OpenAI-compatible endpoint integration.

---

## [0.1.0] - 2026-04-06

### Added

- Basic Textual TUI.
- Agent with agentic loop.
- Tool call handling.
- B-KODE.md project instructions.
