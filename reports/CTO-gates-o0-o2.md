# AST-4 — Verificación de gates O0/O1/O2 y cierre (CTO)

**Fecha:** 2026-09-27 · **Wake:** `issue_children_completed` (las 7 issues de implementación AST-11…AST-17 en estado terminal `done`)
**HEAD verificado:** `2341a78` + commit de re-sincronización documental de este cierre (ver §4) sobre rama `paperclip/review-2026-09-25`.
**Entorno:** sandbox venv propio (`python3 -m venv --without-pip` + get-pip), suite ejecutada fuera del repo; `TYPESAFE_API_KEY` **ausente** del entorno en todas las ejecuciones.

## 1. Matriz de verificación por gate

| Gate | Criterio de salida (plan §9) | Verificación ejecutada | Resultado |
|---|---|---|---|
| **O0** | Suite verde SIN `TYPESAFE_API_KEY` | `env -u TYPESAFE_API_KEY … pytest -q` → `261 passed in 2.99s` | ✅ |
| **O0** | Árbol limpio tras la suite (fin de la basura SQLite/`MagicMock/`) | `git status --short` inmediatamente después de la suite → vacío | ✅ |
| **O0** | Wheel + `import bytia_kode.mcp` OK en sandbox | `pip wheel` → `bytia_kode-0.8.0a1-py3-none-any.whl`; instalado en venv limpio; `import bytia_kode.mcp` → stub `McpManager` exportado sin crash | ✅ |
| **O0** | MCP reclasificado WIP + smoke extras en CI | `CHANGELOG.md:5-15` cabecera WIP con warning explícito; `mcp/__init__.py:15-29` soft-import guard; con SDK `mcp` instalado: warning único + stub (verificado en venv) | ✅ |
| **O0** | Parche documental D1-D22 aplicado | Commits `6541aba` (D1-D22) + `5537803` (D2 vía WIP); spot-check: ROADMAP `0.8.0a1` ✅, badge README ✅, HANDOFF hermeticidad ✅ | ✅ |
| **O1** | 8 vectores RCE de T1 rechazados por tests | `tests/test_bash_allowlist.py` → **39/39 PASSED**, incluye `TestT1Vectors` v1 (`python -c` en comillas), v2 (alias `!` de git ×3), v3 (exfiltración curl/wget/scp/ssh ×4), v4 (`python -m http.server`), v5 (pip/uv install ×3), v6 (wsl), v8 (binario relativo/absoluto atacante ×3) | ✅ |
| **O1** | Tests T2/T4/T8 en verde | `test_web_fetch_ssrf.py` (10 tests: literales privados, resolución DNS→privada, mixta, redirects 302→interna, cadena redirects, límite redirects, tamaño descarga), `test_trusted_write_denylist.py`, `test_log_redaction.py` — todos dentro de los 261 | ✅ |
| **O1** | Suite sigue verde tras O1 | 261 passed (243 tras O1 + 18 tras O2) | ✅ |
| **O2** | Suite completa verde con regresiones de los 7 fixes | `261 passed in 2.99s` = 184 herméticos (O0) + 59 regresión seguridad (O1) + 18 quick wins (O2, commit `2341a78`); `TestBashTimeoutKillsChild` incluido | ✅ |

**Los tres gates se superan.** Conteo de allowlist verificado contra código vivo (`registry.py:54-58`): **24 binarios** (34 − 10 eliminados: `python`, `python3`, `pip`, `pip3`, `uv`, `curl`, `wget`, `scp`, `ssh`, `wsl`), con `_INTERPRETER_BINARIES` (`:62-66`) bloqueando `-c`/`-m` incluso si un operador re-habilita vía `EXTRA_BINARIES`, y `_SYSTEM_BIN_DIRS` (`:70`) forzando resolución a `/usr/bin`|`/usr/local/bin`.

## 2. Commits por oleada (trazabilidad)

| Oleada | Issue | Commit | Contenido |
|---|---|---|---|
| O0 | AST-11 | `38f2053` | Gate JEVAL hermético + fin basura `MagicMock/` |
| O0 | AST-12 | `5537803` | `[mcp]` degrada a stub + smoke extras CI + CHANGELOG WIP |
| O0 | AST-13 | `6541aba` | Parche documental D1-D22 |
| O1 | AST-14 | `a2cb332` | T1 recorte allowlist + argv guards + resolución sistema |
| O1 | AST-15 | `a4f9da1` | T2 SSRF web_fetch + T4 denylist escritura trusted paths |
| O1 | AST-16 | `f6143f9` | T8 scan full-tree CI + redacción args en logs |
| O2 | AST-17 | `2341a78` | 7 quick wins núcleo + wiring + 18 tests regresión |

## 3. Hallazgo del cierre: re-sincronización documental (4ª pasada de verdad)

La propia ejecución invalidó dos verdades que O0 había dejado correctas:

1. **Conteo de tests**: badge y HANDOFF decían **184** (cierto al cierre de O0); O1 añadió 59 y O2 otros 18 → **261**. Sin parche, el repo volvería a infravalorar su estado — el mismo defecto de señal que motivó todo esto.
2. **Allowlist en `docs/ARCHITECTURE.md:254`**: seguía documentando los **34 binarios con `python`/`curl`/`ssh`/`wsl`** (verdad al cierre de O0, pre-recorte). AST-14 fue deliberadamente de scope mínimo (solo `registry.py` + tests, con hermanos editando el mismo fichero en paralelo) — la actualización documental del recorte quedaba para el cierre.

**Parche aplicado en este cierre** (commit de este informe): `README.md:11` (badge 261), `README.md:52` (nota 261), `HANDOFF.md:16` (261/261 + trazabilidad de commits por oleada), `docs/ARCHITECTURE.md:254` (allowlist 24 + capas `_INTERPRETER_BINARIES`/`_SYSTEM_BIN_DIRS` + nota histórica del recorte T1).

## 4. Pendiente que NO es de esta ejecución

- **Push/merge de `paperclip/review-2026-09-25`**: el runner no tiene remote git ni `gh` autenticado. La verificación en GitHub Actions (incluido el smoke de extras de AST-12) se activará cuando el Socio push/merges la rama. Todos los gates quedan verificados localmente (suite en venv sandbox + build/import del wheel).

## 5. Balance final de la operación aprobada

De los hallazgos auditados (AST-5…AST-9): **O0** restauró la señal de calidad (suite hermética verde, CI creíble, docs sincronizadas), **O1** cerró el perímetro (RCE por diseño eliminado y con regresión, SSRF y persistencia mitigadas, secretos y logs bajo control), **O2** cerró los 7 defectos de núcleo de mayor ratio impacto/líneas. Quedan fuera por decisión del Socio: MCP como WIP (no se implementa `manager.py`) e INTERCOM-REFACTOR aparcado.
