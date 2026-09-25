# AST-4 — Informe de estado real de BytIA-KODE y recomendación de ataque

**Emite:** BytIA CTO · **Fecha:** 2026-09-25 · **Base:** commit `768d3ff` (v0.8.0a1), rama `paperclip/review-2026-09-25`
**Input:** los 5 informes de las subtareas AST-5…AST-9 (todas `done`), cada hallazgo con cita `ruta:línea` leída por su autor. Este documento no re-audita: consolida, cruza y decide.

| Informe | Issue | Fichero | Commit |
|---|---|---|---|
| AST-5 · Núcleo | AST-5 | `reports/ENGINEER-bytia-engineer.md` | `edff66d` |
| AST-6 · Seguridad | AST-6 | `reports/SECURITY-bytia-security.md` | `28d89e6` |
| AST-7 · Tests | AST-7 | `reports/QA-qa.md` | `594098d` |
| AST-8 · Packaging/CI | AST-8 | `reports/DEVOPS-devops.md` | `3505b7b` |
| AST-9 · Docs vs real | AST-9 | `reports/RESEARCHER-researcher.md` | `68cf37a` |

---

## 1. Resumen ejecutivo (una página)

**BytIA-KODE es un agente CLI funcional y bien testeado en su núcleo, cuyo problema no es lo que no funciona, sino que nadie puede fiarse de lo que dice de sí mismo.** La suite mide rojo donde debería medir verde (y verde donde el entorno del autor lo maquilla), la documentación central —que es la memoria del equipo— lleva 4 commits sin actualizarse y miente en 22 puntos, el paquete publica un extra que revienta al importarlo, y el perímetro de seguridad real es inexistente por diseño (34 binarios con `python`/`curl`/`ssh` = RCE).

**Balance agregado de las 5 auditorías:**

| Dimensión | Balance |
|---|---|
| Núcleo (AST-5) | **6 HIGH · 11 MED · ~14 LOW** — cancelación poco fiable (H1-H3), Telegram sin resume de sesión (H4), compactación que corrompe pares tool (H5), timeout de bash que no mata el hijo (H6) |
| Seguridad (AST-6) | **1 Crítica · 3 Altas · 5 Medias** (T1-T9) — T1: allowlist ≡ RCE por diseño; guardarraíl JEVAL `off` por defecto y fail-open |
| Tests (AST-7) | Claim "174/174" **obsoleto y no hermético**: hoy 184 tests, **4 fallan sin `TYPESAFE_API_KEY`**; `tui.py` (1281 L), `audio.py`, `mcp/*`, `tools/session.py` con **0 tests** |
| Packaging/CI (AST-8) | **12 defectos** (2 P0) — `[mcp]` publicable y roto, `edge-tts` muerto, binario que ignora `--bot`, CI roja desde el 21-sep, instalador que aborta sin TTY |
| Documentación (AST-9) | 29 claims auditados: **12 confirmados · 7 caducados · 3 falsos · 4 parciales · 3 no verificables**; 22 parches documentales identificados (D1-D22) |

**Los tres hechos que cambian la lectura del proyecto** (todos reproducidos, no inferidos):

1. **La señal de calidad está rota.** `ci.yml` no inyecta `TYPESAFE_API_KEY` y 4 tests de JEVAL la exigen → **CI roja en cada push desde `cf66bec` (2026-09-21)**, salvo secreto no visible en el repo. El "174/174 ✅" de `HANDOFF.md:14` era cierto en `5fe9c1f` y quedó caducado tras añadir 10 tests de JEVAL. Triple verificación independiente (AST-7 §5.1, AST-8 §3, AST-9 F1/F2).
2. **El perímetro de seguridad es la allowlist de bash, y la allowlist concede RCE.** 34 binarios (`registry.py:43-50`) con `python`, `pip`, `uv`, `curl`, `wget`, `ssh`, `scp`, `git`, `wsl`; `python -c` en comillas o un git alias `!` son ejecución arbitraria sin usar ningún operador bloqueado (AST-6 T1). JEVAL —la única contramedida— está `off` por defecto (`guardrail.py:67`), es fail-open y su modo shadow ni siquiera garantiza el log (AST-5 M2). Si el bot de Telegram sigue corriendo en el host del Socio como documenta `HANDOFF.md:72-75` (runtime no verificable desde el repo, AST-9 #6), esto es **riesgo vivo, no teórico**.
3. **La documentación es la fuente de los errores del propio equipo.** El "31 binarios" de `ARCHITECTURE.md:254` es falso (son 34) y se propagó **al plan de este mismo AST-4 y a los enunciados de AST-5/AST-6** (AST-9 F5). `HANDOFF.md:3` dice "Leer ANTES de asumir contexto" — y miente en versión, tests, TTS, allowlist, nº de tools y estado de `[mcp]`.

---

## 2. Convergencia cross-audit — hallazgos confirmados por ≥2 auditores independientes

Estos son los datos con máxima confianza (cada autor leyó el código por su cuenta):

| # | Hallazgo | Confirmado por | Evidencia clave |
|---|---|---|---|
| C1 | Suite no hermética: 4 tests fallan sin `TYPESAFE_API_KEY`; CI roja desde `cf66bec` | **AST-7 + AST-8 + AST-9** (3 ejecuciones independientes) | `guardrail.py:73-77`, `tests/test_jeval_guardrail.py:19-21`, `ci.yml` sin `env:` |
| C2 | Directorio basura `MagicMock/mock.data_dir.__truediv__()/` en la raíz del repo | **AST-7 (§3, repro byte a byte) + AST-8 (§11, bisect) + AST-9 (F3)** | `tests/test_jeval_guardrail.py:93-98` → `session.py:108-109` |
| C3 | `pip install bytia-kode[mcp]` → `ModuleNotFoundError: bytia_kode.mcp.manager`; el wheel lo publica | **CTO (planificación) + AST-8 (§2, traceback reproducido) + AST-9 (#9)** | `mcp/__init__.py:15-16`; `manager.py` no existe |
| C4 | Allowlist = **34** binarios (no 26 ni 31) | **AST-6 (contado) + AST-9 F5 (contado programáticamente)** | `registry.py:43-50` |
| C5 | `edge-tts` dependencia muerta; `bytia-tts`/`piper` sin declarar (bytia-tts ni está en PyPI) | **AST-8 §4 + AST-9 (#19)** | `pyproject.toml:31` vs `audio.py:63` |
| C6 | Deriva de versión: docs dicen 0.7.8, el paquete es 0.8.0a1; última tag v0.7.8 | **AST-8 §9 + AST-9 (D1-D4)** | `ROADMAP.md:3`, `README.md:10,42` vs `pyproject.toml:3` |
| C7 | Guardarraíl JEVAL `off` por defecto, fail-open en enforce, shadow sin garantía de log | **AST-5 (M1, M2) + AST-6 (T3) + AST-9 (#23)** | `guardrail.py:67, 106-117, 146-149` |
| C8 | Entrypoint roto para `--bot`: el binario ignora argv (y `install.sh` instala un wrapper igual de roto mientras anuncia `--bot`) | **AST-8 (D4, D5) + AST-9 (#7)** + documentado por el propio `HANDOFF.md:76-78` | `pyproject.toml:50`, `tui.py:1275-1277`, `install.sh:168,200` |
| C9 | `tui.py` (1281 L, mayor módulo del repo) con **cero** tests; el fix HIGH #1 de `3a1b9ee` (`_provider_sync`) sin red de regresión | **AST-7 (§2, §4) + AST-9 (P4, F7)** | 0 referencias a `bytia_kode.tui` en la suite; `tui.py:456` |

Discrepancias entre auditores: **ninguna sustantiva.** AST-6 abre su informe corrigiendo el "31 binarios" del enunciado (son 34) y AST-9 detecta la misma corrección — convergencia en la corrección, no conflicto.

---

## 3. Estado real por dimensión

### 3.1 Núcleo (AST-5) — funciona, pero las tres funciones más delicadas están rotas
- **Cancelación (botón de pánico):** el `clear()` por iteración borra interrupts fuera de streaming (`agent.py:759-760`), `kill()` re-limpia el evento en carrera (`agent.py:1044`), y ni Telegram registra `on_subprocess` ni nadie cancela la corrutina viva → doble `chat()` concurrente con historial corrupto (`bot.py:106-109`, `tui.py:1151-1160`). El fix P1 de v0.7.8 (`3a1b9ee`) cerró el TOCTOU puntual, no la clase.
- **Persistencia Telegram:** el id determinista `telegram_{chat_id}` nunca llega a existir (`session.py:136` ignora `source_ref`) → cada arranque del bot crea sesión nueva; el índice `idx_sessions_source_ref` (`session.py:33`) no se usa nunca.
- **Contexto:** `_manage_context` compacta por posición y rompe pares assistant↔tool (`agent.py:530-559`) → 400 en APIs estrictas (DeepSeek/Z.ai) al superar el 75% de sesiones largas; el límite de contexto efectivo es 262144 contra 131072 documentado, y se aplica inflado a providers que no lo declaran (`agent.py:34`, `tui.py:564-568`).
- **Lo positivo:** failover con circuit breaker bien testeado (`tests/test_provider_health.py:43-56` es un contrato real), SQL parametrizado en todo `session.py`, dead code identificado y acotado, y 6 quick wins de <20 líneas que eliminan las 3 clases de fallo más visibles (AST-5 §Quick wins 1-7).

### 3.2 Seguridad (AST-6) — no hay perímetro; hay convenios
- **T1 (Crítica):** allowlist de 34 binarios = RCE trivial sin precondiciones (`registry.py:43-50, 199-207`). Ocho vías de bypass documentadas sin usar un solo operador bloqueado (`python -c`, git alias `!`, `curl`/`scp` exfiltración, `python -m http.server`, `pip install`, `wsl`, `rm -rf`, binario malicioso commiteado en un repo porque se valida solo el basename).
- **T2:** `web_fetch` sin mitigación SSRF: `follow_redirects=True`, sin denylist de IPs privadas, acepta `text/plain` → IMDS/localhost al contexto del modelo (`registry.py:309-342`).
- **T4:** trusted paths incluyen `~/.bytia-kode` → un `file_write` a `.env`/`skills/` persiste configuración e instrucciones al reinicio (`agent.py:168-171`, `config.py:13-16` con `override=True`).
- **T9:** `_parse_text_tool_calls` ejecuta `tool(...)` escrita en prosa del modelo (`agent.py:453-513`) — amplificador de prompt-injection sobre T1/T2.
- **Lo positivo verificado:** historial git limpio de secretos (218 commits escaneados), `.env` jamás commiteado, Telegram fail-secure sin allowlist (`bot.py:52-56`), SQL parametrizado, `audio.py` sin shell y con `--`.

### 3.3 Calidad de tests (AST-7) — el núcleo cubierto, la superficie sin red
- 184 tests, ~2 s, núcleo (`session.py`, `circuit.py`, `herdr.py`, `manager.py`) bien cubierto. Pero: `tui.py`/`audio.py`/`mcp/*`/`tools/session.py` sin un solo test; `telegram/bot.py` con 2; la suite no es hermética (C1) y además escribe en `$HOME` real (`~/.bytia-kode`, `~/.local/state/jev-router/`) al correr (AST-7 §5.2).
- La causa raíz del "174/174 ✅" publicado: el autor tenía `~/.config/typesafe/env` en su máquina (`guardrail.py:54-59`) — el verde era ambiental, no verificado.

### 3.4 Packaging/CI (AST-8) — publica cosas rotas y no publica lo que promete
- 2 P0: C1 (CI roja) y C3 (`[mcp]` roto y publicado). P1: `edge-tts` muerto + binarias reales sin declarar ni documentar (con fallo **silencioso** del botón 🔊 en instalación limpia, `audio.py:82-86`), entrypoint que ignora argv, wrapper de `install.sh` igual, instalador que aborta con stdin cerrado (`install.sh:147` bajo `set -e`).
- CI: un solo job, Python 3.11 fijo (declara 3.11-3.13), sin lint, sin coverage, sin sdist, sin smoke de extras, sin `check_secrets.py` (existe, solo corre en pre-commit local). `uv.lock` coherente con `pyproject` pero ambos obsoletos vs código; `dev` duplicado (extra vs dependency-group) con contenido distinto.

### 3.5 Documentación (AST-9) — el mayor multiplicador de daño
- Desincronizada desde el 2026-09-21: `HANDOFF.md` congelado en `5fe9c1f` (16-sep) mientras entraban JEVAL, shadow-mode, bytia-tts y el fix del botón de audio.
- 22 parches documentales accionables (la mayoría de 1 línea) en la tabla D1-D22 de AST-9 §3, con fuente única de verdad propuesta: `pyproject.toml:3` (versión), conteo real de pytest (tests), `registry.py:43-50` (allowlist).
- Pendientes reales consolidados (P1-P5): MCP lifecycle (abierto, cuello de botella de v0.8.0), emisor `blocked` (abierto, sin flujo de aprobación), upstream herdr (externo), refactor TUI (abierto y creciendo), memoria semántica (solo extra declarado).

---

## 4. Correcciones al plan original de AST-4

1. **"Allowlist bash (31 binarios)"** (plan §2, hecho 2 de la planificación): falso — son **34** (`registry.py:43-50`). El dato venía de `ARCHITECTURE.md:254`, que también está mal. Detectado por AST-6 y AST-9 de forma independiente.
2. **"34 binarios" vs percepción de riesgo:** la planificación no dimensionó la gravedad — no es "posibles bypass del validador" (plan §3 AST-6): el validador es irrelevante porque **no hace falta ningún bypass** (T1).
3. El resto de los hechos de la planificación (MCP latente, edge-tts, console script, MagicMock, ROADMAP v0.7.8) quedó confirmado por las auditorías sin cambios.

**Lección para el proceso:** dos de los cinco enunciados llevaban un número falso copiado de la documentación. Ninguna auditoría futura debe tomar cifras de docs sin contarlas en código — regla que queda incorporada de facto por AST-9 D16.

---

## 5. Recomendación de ataque — 4 oleadas, ~1 semana de equipo

Criterio: primero restaurar la señal (sin ella no se valida nada), luego cerrar el riesgo vivo, luego el núcleo, y por último las decisiones de producto. Las oleadas 0-2 no requieren decisiones del Socio salvo la aceptación del recorte de la allowlist; la 3 es decisión de producto.

### Oleada 0 — "Verdad y verde" (~4-6 h, 3 personas) · *sin riesgo funcional*
| # | Acción | Dónde | Esfuerzo | Dueño |
|---|---|---|---|---|
| 0.1 | Hermetizar gate JEVAL: `monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")` en `_gate()` | `tests/test_jeval_guardrail.py:19-21` | 1 línea | Engineer |
| 0.2 | Parar la basura SQLite: `cfg.data_dir = tmp_path` en el fixture (la 2ª pasada de QA §8 demuestra que `chdir` solo *reubica* la basura — son SQLite reales de 36 KB) + `TypeError` si `db_path` no es `str\|Path` en `session.py:107-109` | `tests/test_jeval_guardrail.py:93-98` | 2-5 líneas | QA |
| 0.3 | Verificar estado real de Actions y dejar CI verde; smoke de extras en CI: instalar `dist/*.whl[mcp]` + `import bytia_kode.mcp` | `.github/workflows/ci.yml` | ~1 h | DevOps |
| 0.4 | Parche documental D1-D22 con fuente única de verdad | ver AST-9 §3 | ~2 h | Researcher |
| 0.5 | Honestidad de producto: bajar MCP de "Added" a "WIP" en `CHANGELOG.md:5-12` y/o try/except del import con stub | `mcp/__init__.py:15-16`, `CHANGELOG.md` | <1 h | DevOps |

*Por qué primera:* es la señal de calidad de todo el repo; hoy es falsa en ambas direcciones (roja sin secreto, verde ambiental). Todo lo demás se valida contra esta señal. **Gate de salida:** `pytest -q` → 184 passed en entorno limpio; CI verde; diff documental aplicado.

### Oleada 1 — "Perímetro real" (~1 día) · *cierra el riesgo vivo T1/T2/T4/T8*
| # | Acción | Esfuerzo (est. AST-6) |
|---|---|---|
| 1.1 | **T1**: recortar allowlist (`python`, `pip`, `uv`, `ssh`, `scp`, `wsl`, `curl`, `wget` fuera o tras confirmación humana); rechazar `-c`/`-m`/`alias`/`-exec` post-shlex; resolver binarios con `shutil.which()` bajo `/usr/*bin` | 1-2 h |
| 1.2 | **T2**: denylist de IPs privadas/loopback/link-local pre-conexión y en cada redirect; límite de bytes | 2-3 h |
| 1.3 | **T4**: denylist de writes del agente sobre `~/.bytia-kode/.env`, `mcp_servers.json`, `skills/**`; `override=False` en dotenv global | 1 h |
| 1.4 | **T8**: `check_secrets.py` en CI (15 min) + redactar argumentos en `agent.py:672` | 30 min |
| 1.5 | **T3**: referencia fuerte a tasks shadow (`guardrail.py:147`, set module-level) — coincide con AST-5 M2 | 30 min |

*Por qué segunda y no primera:* sin CI verde (oleada 0) no se puede validar el recorte de allowlist sin regresiones; con ella, este es el mayor delta de riesgo por hora del proyecto. **Gate de salida:** suite verde + repro T1 documentado cerrado (los 8 vectores de AST-6 dejan de funcionar).

### Oleada 2 — "Núcleo crítico" (~1 día) · *los 7 quick wins de AST-5, <20 líneas en total*
1. H1: mover `_cancel_event.clear()` fuera del `for` (`agent.py:759-760`) — 1 línea.
2. H2: eliminar el `clear()` final de `kill()` (`agent.py:1044`) — 1 línea.
3. H6: `process.kill()` + `await process.wait()` en el TimeoutError de BashTool (`registry.py:225-228`) — 3 líneas.
4. H4: id determinista `f"{source}_{source_ref}"` en `create_session` (`session.py:136`) — 2 líneas (desbloquea el resume de Telegram).
5. M4: `msg_count_before == 1` (`agent.py:885`) — 1 línea (auto-título de sesión).
6. M1: parseo de respuesta JEVAL dentro del try fail-open (`guardrail.py:119-122`) — 4 líneas.
7. H3-parcial: registrar `on_subprocess` en el bot de Telegram (`bot.py`, wiring) — horas, no líneas.
Después: H5 (compactación por pares, con tests) y M3 (tool error memory con expiración) como piezas de tamaño medio.

### Oleada 3 — "Decisiones de producto" (decide el Socio)
1. **MCP: cerrar o completar.** Cerrar (WIP, quitar extra, ~2 h) vs completar (`manager.py` + `execute()` + wiring + tests, 1-2 días, desbloquea el release v0.8.0 que lleva "EN PROGRESO" 4 meses). Mientras se decide, la oleada 0.5 ya desactiva el bug latente.
2. **INTERCOM-REFACTOR:** 4 decisiones abiertas que requieren al Socio (`docs/INTERCOM-REFACTOR.md:203-208`), ausentes de los pendientes de `HANDOFF.md`.
3. Aparcados deliberadamente (deuda real, sin efecto inmediato): refactor de widgets TUI (P4, 1281 L y creciendo — reevaluar tras oleada 2), memoria semántica FAISS (P5), upstream herdr (externo).

---

## 6. Qué pediría al Socio (3 decisiones, en orden)

1. **¿Aprueba el recorte de la allowlist (oleada 1.1)?** Es la única decisión que cambia la experiencia de uso (menos comodidad: `python`/`curl`/`ssh` dejan de estar a un mensaje de distancia). Todo lo demás de las oleadas 0-2 es ejecutable sin decisiones.
2. **¿MCP se cierra o se completa?** (oleada 3.1 — determina si v0.8.0 sale en días o en semanas).
3. **¿Priorizamos alguna de las 4 decisiones abiertas de INTERCOM-REFACTOR?** (bloquean un plan dormido).

---

## 7. Cierre de AST-4

- AST-5, AST-6, AST-7, AST-8, AST-9: **todas `done`** con informe completo en comentario final de su issue + fichero commiteado en `reports/` + work product.
- Este informe cierra el contrato del plan (§5): síntesis del estado real + recomendación de ataque. AST-4 → `done`.
- Higiene del workspace: se elimina el directorio basura `MagicMock/` (evidencia de C2; son SQLite reales de 36 KB — reproducible a demanda con el comando de `reports/QA-qa.md` §7.3).
- Pasadas de verificación posteriores al cierre (2ª de QA §8 en `QA-qa.md`, anexo DevOps `DEVOPS-devops-annex-de57bd59.md`): re-confirmaron C1-C3 sin contradicciones; la de QA refina el fix de la basura (0.2).
- **Nada de lo aquí recomendado se ha ejecutado sobre el código** (el encargo era solo lectura); cada oleada necesita su propia issue de implementación tras la decisión del Socio.
