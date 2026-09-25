# RESEARCHER — Matriz de verdad: estado documentado vs estado real de BytIA-KODE

**Issue:** AST-9 · **Agente:** BytIA Researcher (`d284fe7c`) · **Fecha:** 2026-09-25
**Revisión padre:** AST-4 — Planificar la revisión de BytIA-KODE
**HEAD verificado:** `768d3ff` (rama `paperclip/review-2026-09-25`)

---

## 0. Método y límites

- **Fuentes leídas (no supuestas):** `README.md` (531 L), `ROADMAP.md` (598 L), `HANDOFF.md` (86 L),
  `CHANGELOG.md` (317 L), `DEVLOG.md` (74 L) + `docs/devlog/` (20 ficheros, 39 sesiones),
  `B-KODE.md` (239 L), `docs/CODE-REVIEW.md` (186 L), `docs/INTERCOM-REFACTOR.md` (220 L),
  `docs/PLAN-memory-manager-B-KODE.md` (112 L), `docs/ARCHITECTURE.md` (466 L),
  `.github/workflows/ci.yml` (51 L), `pyproject.toml` (78 L) y todo el código Python
  (`src/bytia_kode/`, 28 ficheros).
- **Verificación ejecutada:** suite de tests completa en un venv desechable del scratch de Paperclip,
  con `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1` y `-p no:cacheprovider` (el workspace del
  proyecto se dejó sin ficheros `.pyc` ni `.pytest_cache`).
  Reproducción:
  ```bash
  python3 -m venv "$SCRATCH/venv" && "$SCRATCH/venv/bin/python" "$SCRATCH/get-pip.py"
  "$SCRATCH/venv/bin/python" -m pip install pytest pytest-asyncio httpx python-dotenv \
      pydantic rich pyyaml textual python-telegram-bot edge-tts
  cd /paperclip/instances/default/workspaces/bytia-kode
  PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 TYPESAFE_API_KEY=dummy \
      "$SCRATCH/venv/bin/python" -m pytest -p no:cacheprovider -q
  ```
  (`uv` no está instalado en este runner y `/src/BytIA-KODE` no existe aquí: el checkout es el
  workspace compartido del proyecto.)
- **Límite:** afirmaciones de runtime en el host del Socio (servicios systemd, tokens, puertos,
  alertas de GitHub, sesiones de herdr) **no son verificables desde el repo**; se marcan como tales
  y no se dan por ciertas ni por falsas.
- Cada fila de la matriz cita `ruta:línea` de la fuente **y** de la verificación.

---

## 1. Veredicto ejecutivo

El repo está **más avanzado de lo que la documentación central dice en código** (el extra `[mcp]`
de pyproject ya existe aunque sigue listado como pendiente) y **más atrasado de lo que dice en
estado** (MCP está a medio construir). La documentación se desincronizó a partir del
**2026-09-21**: `HANDOFF.md` no se tocó desde el commit `5fe9c1f` (16-sep) y desde entonces han
entrado 4 commits sustantivos (`cf66bec`, `ab6554b`, `4b12ca7`, `768d3ff`).

Tres hechos duros, todos reproducidos aquí:

1. **La suite no recoge 174 tests: recoge 184.** Y **no es hermética**: sin `TYPESAFE_API_KEY`
   4 tests fallan (`4 failed, 180 passed`); con una clave dummy, `184 passed`.
2. **La allowlist de bash tiene 34 binarios**, no los 26 de `B-KODE.md` ni los 31 que reza
   `docs/ARCHITECTURE.md:254` (y que arrastran las descripciones de AST-5 y AST-6).
3. **El extra `[mcp]` ya está en `pyproject.toml:46`**, mientras que `HANDOFF.md:62` y
   `ROADMAP.md:368` lo siguen listando como pendiente.

---

## 2. Matriz claim → verificado

Leyenda de **Veredicto**: ✅ confirmado · ⚠️ desactualizado · ❌ falso · 🚫 no verificable en repo
· 🔎 parcial.

| # | Afirmación de estado | Fuente (`ruta:línea`) | Verificable en repo | Verificación (`ruta:línea` / resultado) | Veredicto | Revisor |
|---|---|---|---|---|---|---|
| 1 | "Tests: **174/174** ✅ (`uv run pytest -q`)" | `HANDOFF.md:14`; `CHANGELOG.md:36` | Sí | `pytest --collect-only -q` → **184 tests collected**. Con `TYPESAFE_API_KEY` → `184 passed in 2.08s`. Sin ella → `4 failed, 180 passed`. Los 10 tests de JEVAL se añadieron en `cf66bec` (2026-09-21), posterior al último cambio de `HANDOFF.md` (`5fe9c1f`, 16-sep): 174+10=184. | ⚠️ número caducado + 🔎 no hermético | **AST-7** |
| 2 | "Failover **auto-sanado** verificado (16-sep)" | `HANDOFF.md:16`; `CHANGELOG.md:36` | Sí | Existe `tests/test_provider_health.py:43` `test_self_heal_returns_to_chain_head_after_recovery`; cuerpo en `tests/test_provider_health.py:43-56` (3 failures → open → `get_healthy` cae a `local` → `_last_failure_time -= 61` → vuelve a `unsloth` → closed). Pasa en la ejecución de esta revisión. | ✅ | **AST-7** (regresión) / **AST-5** (mecanismo) |
| 3 | "**CI solo valida** (metadata + tests + wheel + twine). Push a main NO deploya" | `HANDOFF.md:18` | Sí | `.github/workflows/ci.yml:10-51` — único job `validate`; pasos `validate_metadata.py` (L23), `pytest -q` (L25), `python -m build --wheel` (L27), `twine check` (L29), verificación de recurso empaquetado (L30-51). Sin `deploy`, `permissions: contents: read` (L7-8). | ✅ | **AST-8** |
| 4 | *(implícito)* CI es un gate fiable del repo | — | Sí | `ci.yml` no declara ningún `env:`/`secrets.`; los 4 tests de JEVAL dependen de `TYPESAFE_API_KEY` (`guardrail.py:51,74-76`; el helper `_gate()` de `tests/test_jeval_guardrail.py:19-21` solo fija `JEVAL_MODE`). Reproducido: sin la clave, `tests/test_jeval_guardrail.py::TestJevalModes::test_shadow_never_blocks_and_is_fire_and_forget`, `::test_enforce_blocks_risky`, `::test_fail_open_on_error` y `::TestAgentIntegration::test_enforce_mode_blocks_risky_tool` fallan. | ❌ **CI debe estar rojo desde `cf66bec`** (2026-09-21) salvo secreto no visible en el repo | **AST-8** (confirmar en Actions) |
| 5 | "**36 vulns Dependabot cerradas** (2026-09-15, upgrade quirúrgico de 12 paquetes)" | `HANDOFF.md:66-68` | Parcial | El commit existe: `16407a0` "fix(deps): cierra las 36 alertas de Dependabot" toca `pyproject.toml`, `uv.lock` (678 líneas) y `HANDOFF.md`. Pero `HANDOFF.md:68` **él mismo** pide "verificar que GitHub cierra las alerts tras el re-escaneo" → sigue sin cerrar. No existe `.github/dependabot.yml` en el árbol **ni en el historial** (`git log --all -- .github/dependabot.yml` = vacío). | 🔎 parche aplicado, cierre de alerts sin verificar | **AST-8** |
| 6 | "**Bot Telegram activo** — servicio systemd user, enabled, Linger, 0 restarts" | `HANDOFF.md:72-75` | **No** | No hay ningún `.service` en el repo (`grep -rn "bytia-kode-telegram"` solo hit en `HANDOFF.md:74`). Es estado de runtime del host. Lo único verificable es el código: `src/bytia_kode/telegram/bot.py` existe y el entrypoint funciona (`__main__.py:4-6`). | 🚫 runtime | **AST-8** (instalación) / externo |
| 7 | Invocación correcta `python -m bytia_kode --bot`; el binario `bytia-kode` ignora argv | `HANDOFF.md:76-78` | Sí | `src/bytia_kode/__main__.py:4-9` (ramas `--bot` → `telegram.bot.main`, resto → `run_tui`); `pyproject.toml:50` `bytia-kode = "bytia_kode.tui:run_tui"`; `tui.py:1275-1277` `run_tui()` no lee argv. | ✅ | **AST-8** |
| 8 | "**MCP (v0.8.0a1): `mcp/manager.py` lifecycle** … wiring … tests" pendiente | `HANDOFF.md:61-62`; `CHANGELOG.md:40-44`; `ROADMAP.md:365-369` | Sí | `ls src/bytia_kode/mcp/` → solo `__init__.py`, `client.py`, `config.py`, `tool.py` (**sin `manager.py`**). `grep -rn mcp src/bytia_kode/agent.py src/bytia_kode/tui.py` → 0 hits (sin wiring). No hay `tests/test_mcp_*.py`. | ✅ pendiente real | **AST-5** / **AST-8** |
| 9 | "**Latente**: `mcp/__init__.py` ya importa `manager.py` → con el extra `[mcp]` instalado … cualquier `import bytia_kode.mcp` explota" | `HANDOFF.md:63-65` | Sí | `src/bytia_kode/mcp/__init__.py:15-16` — `if _MCP_AVAILABLE: from bytia_kode.mcp.manager import McpManager`. El stub del `else` (L19-38) solo aplica **sin** SDK. | ✅ (bug latente real) | **AST-8** (reproduce el traceback) |
| 10 | "`McpTool.execute()` — implementación del puente (TODO(human))" | `HANDOFF.md:62`; `CHANGELOG.md:44`; `ROADMAP.md:364` | Sí | `src/bytia_kode/mcp/tool.py:27-29` — `# TODO(human): Implement the MCP tool execution bridge` + `raise NotImplementedError`. | ✅ | **AST-5** |
| 11 | "`pyproject.toml` — optional dependency `[mcp]`" **pendiente** | `HANDOFF.md:62`; `ROADMAP.md:368` (`mcp>=1.6.0`) | Sí | **Ya hecho**: `pyproject.toml:46` `mcp = ["mcp>=1.28.1,<2"]` (bajo `[project.optional-dependencies]`, L39). Y la versión real es `>=1.28.1,<2`, no `>=1.6.0`. | ⚠️ pendiente caducado (hecho) | **AST-8** |
| 12 | "**Estados → herdr**: … `blocked` soportado en el mapa pero **sin emisor**" | `HANDOFF.md:54-55`; `HANDOFF.md:69` | Sí | `src/bytia_kode/herdr.py:39-44` — `"blocked": "blocked"` está en `_STATE_MAP`. En `tui.py` solo existen `set_status("ready"/"thinking"/"tool"/"error")` (`tui.py:472,478,525,644,719,726`), **ninguna llamada a `blocked`**. `grep -rn -i "approv\|aprobaci" src/` → 0 hits: no existe flujo de aprobación de tools. | ✅ abierto | **AST-5** (mapa) / autor del flujo de aprobación |
| 13 | "**Upstream herdr**: que exponga/persista sesiones self-reported" | `HANDOFF.md:70` | **No** | Depende del repo/CLI de `herdr` (externo). En repo solo se documenta que `herdr 0.8.2` acepta el flag (`HANDOFF.md:40-41`, `CHANGELOG.md:76-79`). | 🚫 externo | fuera de los 5 (上游) |
| 14 | P2 "**TUI refactor: extraer widgets a subdir**" | `ROADMAP.md:37-38`; `docs/CODE-REVIEW.md:71-79` | Sí | `ls src/bytia_kode/tui` → **no existe**. `src/bytia_kode/tui.py` = **52.683 bytes / 1.281 líneas** (frente a los "47.8 KB" que ya eran flag en `docs/CODE-REVIEW.md:73`): ha crecido ~10% desde el review. | ✅ abierto y crecido | **AST-5** |
| 15 | "**Memoria semántica** con FAISS/ChromaDB" pendiente | `ROADMAP.md:379`; `docs/ARCHITECTURE.md:464` | Sí | `pyproject.toml:47` declara el extra `memory = ["sentence-transformers>=4.0", "faiss-cpu>=1.11"]` pero **no está en deps base** (`pyproject.toml:23-32`) y no hay código FAISS en `src/`. `docs/ARCHITECTURE.md:464`: "fuera de producción (requiere grupo `memory`)". | ✅ abierto | **AST-5** (diseño) / roadmap |
| 16 | Versión **`0.7.8`** ("Estado actual") | `ROADMAP.md:3`; `README.md:10` (badge), `README.md:42` | Sí | `pyproject.toml:3` → `version = "0.8.0a1"`. `src/bytia_kode/__init__.py:10-24` lee la versión **del pyproject** → la app se reporta `0.8.0a1`. | ⚠️ caducado | **AST-8** |
| 17 | Versión **`0.8.0a1`** | `HANDOFF.md:13`; `CHANGELOG.md:3` | Sí | Coincide con `pyproject.toml:3`. | ✅ | **AST-8** |
| 18 | Badge "**tests-145 passing**" y "Total: 145" | `README.md:11`; `README.md:50` | Sí | 184 recogidos / 184 pasan (con clave). También `CHANGELOG.md:90` "145 tests total" (histórico de v0.7.8, correcto *entonces*). | ⚠️ caducado | **AST-7** |
| 19 | "`audio.py` — TTS con **edge-tts** + mpv" | `docs/ARCHITECTURE.md:13`, `docs/ARCHITECTURE.md:456-457`; `B-KODE.md:195`; `README.md:237`, `README.md:489`; `docs/TUI.md:115`; `ROADMAP.md:215` | Sí | `src/bytia_kode/audio.py:3-5` ("la era WSL usaba `edge-tts` … Ahora usa `bytia-tts`"), `audio.py:63` `subprocess` con `"bytia-tts", "--", clean_text`, `audio.py:71,89,94,112`. Commit `4b12ca7` (2026-09-21). **Nota AST-8:** `pyproject.toml:31` sigue declarando `edge-tts>=7.2.8` → dependencia muerta. | ⚠️ caducado en 6 sitios | **AST-8** (deps) + **AST-9** (docs) |
| 20 | Bash allowlist de **26 binarios** | `B-KODE.md:33`, `B-KODE.md:46-53` | Sí | `src/bytia_kode/tools/registry.py:43-50` → **34** binarios (`rg,bat,eza,tokei,shellcheck` añadidos en v0.7.8). | ❌ falso/caducado | **AST-6** (seguridad) / **AST-5** |
| 21 | Bash allowlist de **31 binarios** | `docs/ARCHITECTURE.md:254` | Sí | La **propia lista** de `ARCHITECTURE.md:254` contiene 34 entraciones; el código tiene 34 (`registry.py:43-50`, contado programáticamente). El "31" es un recuento erróneo que se filtró a las descripciones de AST-5 y AST-6. | ❌ falso | **AST-5** / **AST-6** |
| 22 | "**Tools Registradas (11)**" | `B-KODE.md:29` | Sí | La tabla de `B-KODE.md:33-44` lista **12** filas. `registry.py:736` registra 9 por defecto + `agent.py:207-209` añade 3 session = **12**. `ARCHITECTURE.md:250` dice correctamente "12 nativas". `Session-39-MCP-Client.md:7` también dice 12. | ❌ inconsistente internamente | **AST-5** |
| 23 | Guardarraíl JEVAL modos `off/shadow/enforce` | `CHANGELOG.md:3`, commits `cf66bec`/`ab6554b` | Sí | `src/bytia_kode/guardrail.py:5-8,13` (default **`off`**), `:67-77` (fallback a `off` sin clave), `:122` (`blocked` solo en `enforce`), `:146-148` (shadow = fire-and-forget). **No documentado** en `B-KODE.md` ni `README.md` → hueco doc. | ✅ en código, 🔎 sin documentar | **AST-6** (default/off) / **AST-5** |
| 24 | "**39 sesiones**" de devlog | `DEVLOG.md:3-27`; objetivo de la issue | Sí | `grep -h "^# Session" docs/devlog/*.md \| sort -u` → **39** (S1..S39). | ✅ | AST-9 |
| 25 | Índice `DEVLOG.md` completo | `DEVLOG.md:5-27` | Sí | El índice **no** contiene ninguna fila para `docs/devlog/Session-39-MCP-Client.md:1` ("Session 39 — 2026-05-24"): `grep -n "Session 39\|2026-05-24\|MCP" DEVLOG.md` → vacío. Tampoco hay entrada de devlog para los 4 commits del **2026-09-21** (JEVAL, shadow, bytia-tts, botón de audio): `ls docs/devlog` no incluye `2026-09-21.md`. | ⚠️ índice caducado | AST-9 |
| 26 | "`HANDOFF.md` — memoria transferible, **última actualización 2026-09-16**" | `HANDOFF.md:4` | Sí | Último commit que lo toca: `5fe9c1f` (16-sep). Posteriores: `cf66bec`, `ab6554b`, `4b12ca7`, `768d3ff` (todos 2026-09-21) → ni el guardarraíl JEVAL ni el cambio de TTS a `bytia-tts` están en el HANDOFF. | ⚠️ caducado | AST-9 |
| 27 | "Safe mode (`Ctrl+E`) es **visual solamente**" | `B-KODE.md:239`; `README.md:507`; `docs/ARCHITECTURE.md:463`; `ROADMAP.md:296` | Sí | Los cuatro documentos coinciden y `ROADMAP.md:296` lo mantiene como pendiente ("Safe mode backend real"). | ✅ consistente | **AST-6** |
| 28 | `docs/CODE-REVIEW.md` como revisión vigente | `docs/CODE-REVIEW.md:1-6` | Sí | Congelado a **2026-04-30**, `v0.7.7-2-g3576cb4`, **144 tests**. Sigue citándose como fuente en `ROADMAP.md:20`. Es histórico, no vigente; debería etiquetarse como tal. | 🔎 histórico | AST-9 |
| 29 | `docs/INTERCOM-REFACTOR.md` | `docs/INTERCOM-REFACTOR.md:5` ("**Estado: Borrador**") | Parcial | El plan es sobre infraestructura fuera del repo (`~/.bytia/intercom/`, `docs/INTERCOM-REFACTOR.md:53-80`) y tiene **4 decisiones abiertas que requieren al Socio** (`docs/INTERCOM-REFACTOR.md:203-208`). Nada de esto aparece en los "Pendiente" de `HANDOFF.md:59-70`. | 🔎 borrador con bloqueo humano | AST-9 → Socio |

### Resumen de veredictos

| Veredicto | Nº de claims |
|---|---|
| ✅ confirmado en el repo | 12 |
| ⚠️ desactualizado (documento caducado) | 7 |
| ❌ falso / inconsistente | 3 |
| 🔎 parcial o histórico | 4 |
| 🚫 no verificable desde el repo (runtime/externo) | 3 |

---

## 3. Docs caducados — lista accionable

Cada línea: **dónde está mal → qué dice el código → esfuerzo**.

| # | Fichero:línea | Dice | Debería decir | Esfuerzo |
|---|---|---|---|---|
| D1 | `ROADMAP.md:3` | "Estado actual: v0.7.8 (Alpha estable)" | `0.8.0a1` (consistente con `pyproject.toml:3` y con su propia sección `ROADMAP.md:351` "v0.8.0 … EN PROGRESO") — el fichero **se contradice a sí mismo** | 1 línea |
| D2 | `README.md:10` | badge `release-0.7.8` | `release-0.8.0a1` | 1 línea |
| D3 | `README.md:11` | badge `tests-145 passing` | `tests-184 passing` | 1 línea |
| D4 | `README.md:42` | "Release actual: `0.7.8`" | `0.8.0a1` | 1 línea |
| D5 | `README.md:50` | "Total: 145" | histórico v0.7.8 → marcarlo como histórico o recalcular | 1 línea |
| D6 | `HANDOFF.md:14` | "Tests: 174/174 ✅" | 184/184 **con `TYPESAFE_API_KEY`**; 180/184 sin ella (ver F1) | 2 líneas |
| D7 | `HANDOFF.md:4` | "Última actualización: 2026-09-16" | añadir los cambios del 2026-09-21 (JEVAL, shadow, bytia-tts, botón de audio) | párrafo |
| D8 | `HANDOFF.md:62` | "optional dep `[mcp]` en pyproject" como pendiente | ya está: `pyproject.toml:46` | 1 línea |
| D9 | `ROADMAP.md:368` | "`pyproject.toml` — `[mcp]` … `mcp>=1.6.0`" [ ] | ya está, y con `>=1.28.1,<2` | marcar [x] + corregir versión |
| D10 | `docs/ARCHITECTURE.md:13` | "TTS con edge-tts + mpv" | `bytia-tts` (piper local) — `audio.py:3-5,63` | 1 línea |
| D11 | `docs/ARCHITECTURE.md:456-457` | tools externas `edge-tts` / `mpv` | `bytia-tts` / `piper` | 2 líneas |
| D12 | `B-KODE.md:195` | "Voz … vía `edge-tts` … y `mpv`" | `bytia-tts` (piper Daniela) | párrafo |
| D13 | `README.md:237`, `README.md:489` | "TTS: edge-tts + mpv" / tabla de stack `edge-tts` | `bytia-tts`; retirar `edge-tts` de la tabla | 2 líneas |
| D14 | `docs/TUI.md:115` | tool externa `edge-tts` | `bytia-tts` | 1 línea |
| D15 | `B-KODE.md:33,46` | "Allowlist **26** binarios" | **34** (`registry.py:43-50`) | 2 líneas |
| D16 | `docs/ARCHITECTURE.md:254` | "allowlist de **31** binarios" (y lista de 34) | **34** — este número erróneo está copiado en las descripciones de **AST-5** y **AST-6** | 1 línea + avisar |
| D17 | `B-KODE.md:29` | "Tools Registradas (**11**)" con tabla de 12 | **12** | 1 línea |
| D18 | `DEVLOG.md:5-27` | índice sin `Session-39` ni sesiones del 2026-09-21 | añadir fila `Session 39 — MCP (2026-05-24)` y crear devlog del 2026-09-21 | 2 filas + 1 fichero |
| D19 | `docs/ARCHITECTURE.md:449` | `mcp>=1.6.0` | `mcp>=1.28.1,<2` (`pyproject.toml:46`) | 1 línea |
| D20 | `docs/ARCHITECTURE.md:328` | describe solo la rama "sin SDK → stub" | añadir que **con** SDK el import revienta (`mcp/__init__.py:16`) | 1 línea |
| D21 | *(hueco)* `B-KODE.md` / `README.md` | no documentan el guardarraíl JEVAL (`guardrail.py:5-15`) ni su default `off` | añadir sección | párrafo |
| D22 | `docs/CODE-REVIEW.md:1-6` | se cita como revisión vigente (`ROADMAP.md:20`) | etiquetar "histórico (v0.7.7, 2026-04-30)" | 1 línea |

---

## 4. Pendientes abiertos consolidados

Los 5 pedidos en la issue, con estado real y evidencia:

| # | Pendiente | Estado real | Evidencia (`ruta:línea`) | Tamaño |
|---|---|---|---|---|
| P1 | **MCP lifecycle — `mcp/manager.py`** | **ABIERTO** y es el cuello de botella de v0.8.0a1 | falta el fichero (`ls src/bytia_kode/mcp/`); sin wiring en `agent.py`/`tui.py` (0 hits); `mcp/tool.py:27-29` `NotImplementedError`; sin `tests/test_mcp_*.py`; **pero** el extra ya existe (`pyproject.toml:46`) y el import latente revienta (`mcp/__init__.py:15-16`) | **1-2 días** (manager + `execute()` + wiring + tests + repro) |
| P2 | **Emisor de estado `blocked`** | **ABIERTO** — no hay ni emisor ni flujo de aprobación que lo dispare | mapa en `herdr.py:43`; cero emisiones en `tui.py`; `grep -i approv` = 0 hits en `src/` | **Medio** (diseño de approval flow primero; el emisor es 1 línea) |
| P3 | **Upstream herdr** (que persista sesiones self-reported) | **ABIERTO, externo** — fuera del repo | `HANDOFF.md:70`, `CHANGELOG.md:76-79` | Fuera del repo |
| P4 | **P2 refactor TUI widgets** | **ABIERTO** y empeorando | `ROADMAP.md:37-38` sin marcar; `src/bytia_kode/tui/` no existe; `tui.py` = 1.281 L / 52,7 KB (era 47,8 KB en `CODE-REVIEW.md:73`) | **Medio-alto** (refactor mecánico de 1.281 líneas) |
| P5 | **Memoria semántica** | **ABIERTO** — solo el extra declarado | `ROADMAP.md:379-381`; `pyproject.toml:47`; `ARCHITECTURE.md:464` | **Alto** (FAISS/ChromaDB + integración) |

**Otros abiertos que la issue no lista** (todos verificados en la misma pasada):

- `ROADMAP.md:115-117` — FIX-5 (umbral de escalación proactiva) y FIX-6 (validación post-generación).
- `ROADMAP.md:265-266` — `AgentCancelledError` con cleanup + tests de cancelación.
- `ROADMAP.md:270-277` — toda la batería de tests de TUI (`pytest-textual`) sigue vacía; de ahí que
  `tui.py` (1.281 L) no tenga ni un test.
- `ROADMAP.md:294-296` — PromptTextArea Shift+Enter y safe-mode backend real.
- `ROADMAP.md:384-394` — instalador interactivo (v0.7.2, fuera de orden en el documento).
- `docs/INTERCOM-REFACTOR.md:203-208` — 4 decisiones que **requieren al Socio**.
- `HANDOFF.md:68` — verificar en GitHub el cierre de las 36 alertas de Dependabot.
- `docs/CODE-REVIEW.md:144-151` — el "symlink attack surface" sigue como *observation* (lo evalúa
  **AST-6**) y los *panic buttons* incompletos.

---

## 5. Hallazgos nuevos (no están en la issue)

| # | Hallazgo | Evidencia | Severidad |
|---|---|---|---|
| F1 | **La suite no es hermética: 4 tests exigen `TYPESAFE_API_KEY`.** Sin la clave, `JevalGate.__init__` degrada a `off` y los tests de shadow/enforce fallan. Cualquier entorno sin la clave (incluido el runner de GitHub, que no inyecta nada) ve la suite roja. | `guardrail.py:51,73-77`; `tests/test_jeval_guardrail.py:19-21`; reproducido: `4 failed, 180 passed` / con clave `184 passed` | **HIGH** |
| F2 | **`ci.yml` no inyecta `TYPESAFE_API_KEY`** → F1 significa que **CI debe estar rojo en `main` desde `cf66bec`** (2026-09-21), salvo que exista un secreto no visible en el repo. | `.github/workflows/ci.yml` sin `env:`/`secrets.`; `git log -1 --format=%h` de `cf66bec` | **HIGH** (confirmar en Actions → **AST-8**) |
| F3 | **Ejecutar la suite ensucia la raíz del repo**: se crea `MagicMock/mock.data_dir.__truediv__()/…`. Culpable: el fixture `_agent()` hace `cfg = MagicMock()` y `session.py:109` hace `data_dir.parent.mkdir(parents=True)` sobre el path generado por el MagicMock. | `tests/test_jeval_guardrail.py:94-98`; `src/bytia_kode/session.py:109`; reproducido en esta revisión | **MED** (→ **AST-7**, punto 3 de su issue) |
| F4 | **174 era correcto hasta el 2026-09-21**: `HANDOFF.md` no se tocó tras `5fe9c1f` y luego entraron 10 tests de JEVAL (`cf66bec`). El desfase no es un error de recount, es **docs que no se actualizaron tras 4 commits**. | `git log -3 -- HANDOFF.md` → `5fe9c1f`; `git log --diff-filter=A -- tests/test_jeval_guardrail.py` → `cf66bec` | **MED** |
| F5 | **Tres números distintos de allowlist conviven** (26 en `B-KODE.md`, 31 en `ARCHITECTURE.md`, 34 reales) y **el 31 ya se copió en las descripciones de AST-5 y AST-6**, así que dos revisores están auditando contra un número inventado. | `B-KODE.md:33,46`; `ARCHITECTURE.md:254`; `registry.py:43-50` (contado: 34) | **MED** |
| F6 | **El guardarraíl JEVAL es el cambio de seguridad más reciente y no está documentado en ningún doc de cara al usuario** (`B-KODE.md`, `README.md` ni lo mencionan), pese a que `enforce` puede bloquear tools. | `guardrail.py:5-15,122`; ausente en `B-KODE.md`/`README.md` | **MED** |
| F7 | `tui.py` creció de 47,8 KB (30-abr) a 52,7 KB sin tests — el P2 lleva 5 meses sin tocarse y el coste de refactor crece. | `CODE-REVIEW.md:73`; `wc -c src/bytia_kode/tui.py` = 52.683; `ROADMAP.md:37` | **BAJO** (deuda) |

---

## 6. Top-3 «por dónde atacar» — recomendación para el Socio

> Criterio: (impacto × probabilidad) / esfuerzo. El objetivo del Socio es decidir prioridades;
> esto es el insumo principal.

### 🥇 1. Hacer hermética y verde la suite + el gate de CI — **esfuerzo bajo (~2 h), impacto desproporcionado**

**Qué:** (a) que los 4 tests de JEVAL se inyecten su propia clave
(`monkeypatch.setenv("TYPESAFE_API_KEY", "test")` en `_gate()`, `tests/test_jeval_guardrail.py:19-21`),
o que `JevalGate` acepte la clave por constructor en vez de solo por env; (b) confirmar el estado
real de Actions y, si está rojo, cerrarlo; (c) blindar el fixture de `tests/test_jeval_guardrail.py:94`
para que no escupa el directorio `MagicMock/` en la raíz.

**Por qué primero:** es la **señal de calidad de todo el repo**. Hoy esa señal es falsa en las dos
direcciones: mide rojo en entornos sin secreto (F1/F2) y, cuando mide verde, no protege contra
regresiones de un código (JEVAL) que nadie más está revisando. Sin un gate verde no se puede
validar ningún otro ataque de esta lista. **Cero riesgo funcional.**
**Dueños:** **AST-7** (tests) + **AST-8** (CI).

### 🥈 2. Parche de verdad documental — **esfuerzo bajo (~2 h), multiplicador para los 5 revisores y todas las sesiones futuras**

**Qué:** aplicar la tabla D1–D22 de la sección 3, con **una única fuente de verdad**:
`pyproject.toml:3` para la versión, el conteo real de `pytest --collect-only` para los tests, y
`registry.py:43-50` para la allowlist. Avisar a **AST-5** y **AST-6** de que su "31 binarios" es 34
(F5).

**Por qué segundo:** `HANDOFF.md:3` dice literalmente *"Leer ANTES de asumir contexto"*. Estos
ficheros **son** la memoria del equipo de agentes: hoy 6 de ellos mienten (versión, tests, TTS,
allowlist, nº de tools, `[mcp]` pendiente). Cada hora que pasa, los 4 revisores restantes leen
números falsos y los reproducen en sus informes (ya ha pasado con el "31"). Es el mejor ratio
esfuerzo/impacto del proyecto y no toca código.
**Dueño:** **AST-9** (yo) puede hacerlo en una issue dedicada si el Socio lo aprueba.

### 🥉 3. Decidir MCP: **cerrarlo** o **bajarlo de "Added" a "WIP"** — **esfuerzo medio (2 h vs 1-2 días), impacto en el release v0.8.0**

**Qué:** dos caminos mutuamente excluyentes, decisión del Socio:

- **Rápido (~2 h):** `CHANGELOG.md:5-12` presenta MCP como *"Added — MCP Client Support"* cuando
  `manager.py`, el wiring y `McpTool.execute()` no existen, y con el extra instalado el import
  revienta (`mcp/__init__.py:16`). Bajarlo a WIP + ocultar/quitar el extra `[mcp]` de la instalación
  deja el repo **honesto** y elimina un bug latente de packaging de un plumazo.
- **Completo (~1-2 días):** `manager.py` (lifecycle) + `execute()` real + wiring `agent`/`tui` +
  `tests/test_mcp_config.py`/`test_mcp_tool.py` + repro del traceback. Esto **desbloquea el release
  0.8.0**, que según `CHANGELOG.md:3` está "EN PROGRESO" desde hace 4 meses.

**Por qué tercero:** es la única feature anunciada públicamente que no funciona, pero **no bloquea
nada mientras no se instale el extra**, así que su urgencia es de producto, no de estabilidad.
**Dueños:** **AST-5** (núcleo) + **AST-8** (packaging) + decisión del Socio.

**Descartado deliberadamente como top-3:** el refactor de widgets TUI (P4) y la memoria semántica
(P5) — ambos son deuda real pero de esfuerzo alto y bajo efecto inmediato; y el "symlink attack
surface" (`ROADMAP.md:44`), que el propio roadmap marca como trade-off deliberado y que evalúa
**AST-6**.

---

## 7. Mapa de quién comprueba qué (para AST-4)

| Revisor | Claims de esta matriz que le corresponden |
|---|---|
| **AST-5** — núcleo | #2 mecanismo de auto-sanado, #10 `McpTool.execute`, #12 mapa `blocked`, #14 refactor TUI, #15 memoria semántica, #21/#22 allowlist y tools; **corregir su "31 binarios"** |
| **AST-6** — seguridad | #20 allowlist real (34), #23 default `off` de JEVAL, #27 safe mode; **corregir su "31 binarios"** |
| **AST-7** — tests | #1 conteo 184 vs 174 + hermeticidad (F1), #2 contrato de regresión del failover, #18 badge 145, **F3 directorio `MagicMock/`** (culpable localizado: `test_jeval_guardrail.py:94`) |
| **AST-8** — packaging/CI | #3 CI solo valida, **#4/F2 CI rojo**, #5 Dependabot, #6/#7 bot Telegram, #9 repro del crash MCP, #11 `[mcp]` ya hecho, #16/#17 versión, #19 `edge-tts` muerto en `pyproject.toml:31` |
| **AST-9** — docs (esta issue) | matriz completa, docs caducados D1–D22, pendientes P1–P5, top-3 |
