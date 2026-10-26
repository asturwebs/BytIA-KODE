# HANDOFF — BytIA-KODE (B-KODE)

> Memoria transferible del repo. Leer ANTES de asumir contexto. Actualizar al cerrar sesión significativa.
> Última actualización: 2026-10-25 (S40 — plan escalation-orchestrator revisado y commiteado en `9850bc9`; aiohttp 3.14.5 + certifi 2026.10.23, 9 alertas resueltas por versión; **503/503 tests**). Antes: 2026-10-03 (v0.8.6 — parcheo de seguridad: 17 alertas Dependabot cerradas + suelos en extras. Antes: v0.8.5 — anexo DEVOPS §5: la versión nunca se inventa. Antes: v0.8.4 — AST-33: gate CI de verdad ejecutable del README + fix `--bot` y `TELEGRAM_API_BASE` de AST-32; antes: v0.8.3 — AST-30: política de workspace de AST-26 y blindaje content-plane de AST-27, **publicada en PyPI** 2026-09-28 desde main `2521890`; v0.8.2 — AST-25: blindaje de cancelación de AST-24; v0.8.1 — AST-23: README profesional + estreno del flujo OIDC + `--version` + `.vendor-version` real)
>
> Cambios del **2026-09-21** incorporados: guardarraíl **JEVAL** (`cf66bec`, modos `off`/`shadow`/`enforce`, default `off`), modo **shadow** fire-and-forget (`ab6554b`), TTS local vía **`bytia-tts` + piper** — sustituye al TTS en la nube de la era WSL (`4b12ca7`), y botón de audio que vuelve a "Escuchar" al terminar (`768d3ff`). Sesiones anteriores a esta oleada: ver `docs/devlog/` y `reports/`.

## Qué es

Agente CLI propio (Python 3.11+ / Textual): agente + skills + terminal.
"Efectividad > Coste. Zero Hype. Truth > Comfort."

## Estado

- **Versión**: `0.8.6` (bump 2026-10-03, parcheo de dependencias: pyjwt 2.15.1, urllib3 2.8.0, sentence-transformers 5.6.1 en `uv.lock` + suelos de seguridad en los extras `mcp`/`memory`; cierra las 17 alertas Dependabot y el PR #7. Ninguna era dependencia del paquete base). Publicadas en PyPI: 0.8.1 (2026-09-27, primer OIDC), 0.8.2, 0.8.3 (2026-09-28), 0.8.4 (2026-09-29), 0.8.5 (2026-10-03). MCP sigue WIP/stub, no feature
- **Rewrite de historia (2026-10-03, post-v0.8.6)**: 151 trailers `Co-Authored-By` no canónicos (Claude Code/Opus/Paperclip y BytIA con emails no canónicos) + 4 trailers `Paperclip-Issue` normalizados a `BytIA <bytia@bytia.es>` / eliminados con `git filter-repo` (2 pasadas: la primera se saltó los `Co-authored-by:` en minúscula). ⚠️ **Todos los SHAs pre-rewrite quedaron huérfanos** — los citados en CHANGELOG/ROADMAP/HANDOFF escritos antes de esta fecha (`7ee7b88`, `91fb426`, `64ce5c9`, `38f2053`, `2521890`…) ya no resuelven en el repo: son referencias de época. Lo mismo aplica a las estampas `_commit.txt` de los wheels 0.8.1–0.8.6 publicados. Backup completo pre-rewrite: `~/Backups/bytia-kode-pre-rewrite-20261003.bundle` (`--all`, 2 MB). Tags v0.5.3–v0.8.6 reescritos y force-pusheados; ruleset `protect-main` desactivado/reactivado alrededor del force-push. Desglose causal de las citas de `reports/` (solo 7 son huérfanas-por-rewrite; 12 son hashes del workspace de Paperclip que nunca fueron commits de main) y tabla de traducción old→new verificada por patch-id: `reports/CTO-addendum-rewrite-20261003.md` (AST-34).
- **Gotcha del clon compartido** (2026-10-03): en checkouts compartidos entre terminales/agentes, verificar `git branch --show-current` (y `git rev-parse HEAD`) ANTES de cualquier `git am`/push — operar sobre la rama equivocada costó un `git am` fallido y un push no-op entre terminales durante el ciclo AST-34.
- **Gate de citas SHA en `reports/` (2026-10-04, AST-35)**: `scripts/check_report_citations.py` + `tests/test_check_report_citations.py` + paso en `ci.yml`/`release.yml` — **2 criterios**: toda cita con forma de SHA (fail cerrado: hex 7..40, incl. decimales) debe **resolver** (`git cat-file`) o estar **anotada** (sufijo `@ws`/`@bundle`/`@nocommit` o entrada en `DECLARED_CITATIONS` con clase/causa). `checkout` con `fetch-depth: 0` (la historia completa es precondición del gate). Entregado por el rol DevOps desde el workspace de Paperclip (rama `paperclip/review-2026-09-25`, rango `7d29844..9fb57bd`), integrado en main con resolución de conflicto contra el bump de actions (`checkout@v7` + `fetch-depth: 0`), trailer del primer commit normalizado a `BytIA <bytia@bytia.es>` al aplicar. CI verde sobre `5e19f12`. El gate es **número-cero**: jamás titular numérico por regex — inventario por clase/causa (regla de método de AST-34).
- **Tests**: **503/503 ✅** (observado 2026-10-25, 50,1 s: 500 previos + 3 del escáner de secretos). Histórico: 491/491 (recuento **observado** el 2026-10-04 con el gate de citas integrado: +9 tests sobre los 482 del 3-oct. Antes decía 482, observado el 2026-10-03: `python -m pytest -q` → 482 passed en 50 s. Esta línea venía diciendo 466, ya por detrás de los 477 que declaraba el ROADMAP en v0.8.4 — es exactamente la deriva que señaló el anexo DEVOPS §11; aquí queda con el número real y su fecha). Histórico: (`PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q`, verificado sin `TYPESAFE_API_KEY` en el entorno; AST-22 añadió `test_canonical_install` + `test_release_workflow`, AST-23 añadió `test_version_flag` + `test_vendor_version`, AST-24 añadió `test_cancellation_armor` + `test_tui_interruption` — +17: blindaje de cancelación y primeros tests de TUI; AST-26 +49 (`test_workspace_policy`: política de workspace), AST-27 +40 (blindaje content-plane) — 466). La suite fue **hermetizada en la oleada O0** (issue hermana **O0-A / AST-11**, commit `38f2053`): el gate JEVAL ya no exige `TYPESAFE_API_KEY` y desapareció la basura `MagicMock/` en el árbol (antes del fix: 180/184). Las oleadas **O1** (T1 allowlist, T2 SSRF, T4 trusted paths, T8 redacción; commits `a2cb332`+`a4f9da1`+`f6143f9`) y **O2** (7 quick wins de núcleo; commit `2341a78`) añadieron 59+18 tests de regresión sobre los 184 herméticos. Post-merge, la **ronda F** de endurecimiento de la capa 2 del BashTool añadió 53 más: tests propios del escáner de secretos (`fa9ce29`+`e98fb5b`), F1 flags de programa inline (`670b056`, AST-18) y F2 programa posicional de awk/gawk (`ddfc27d`, AST-19). El **build id** (`61604aa`, AST-20) añadió 17 tests de estampa/`version_label` sobre los 314.
- **Hotfix 2026-09-16** (`3a1b9ee`): failover vivo — pin solo en F3 (guard `_provider_sync`), router pineable de nuevo (`list_pinnable()`; F3→primary pina el router). 2 bugs HIGH hallados por OpenCodeReview revisando `ae97b37`. Detalle: `docs/devlog/2026-09-16.md`
- **Auto-sanado verificado (16-sep, auditoría)**: sin pin, cada chat camina desde la cabeza (`get_healthy`) y el half-open del breaker reintenta el Studio a los 60 s — se recupera solo, sin F3 ni reinicio (`test_self_heal_returns_to_chain_head_after_recovery`). Residual real: el reintento half-open puede costar un arranque en frío del Studio; el failover en-chat continúa y el mensaje no se pierde.
- **Selección directa de providers (2026-09-16)**: **F1 = modo AUTO** (pin(None), reversible desde cualquier pin) · F4 Studio · F5 Ollama · F6 Z.ai · F7 DeepSeek · F8 Router (pin manual, aviso de circuito) · F3 cicla. Resuelve el "slot Auto" pendiente del re-review ocr.
- **CI**: `.github/workflows/ci.yml` — validación (metadata + tests + wheel + twine). Push a main NO deploya.
- **Release**: `.github/workflows/release.yml` (AST-22) — push de tag `v*` → gates + `uv build` → `pypa/gh-action-pypi-publish` por **OIDC/Trusted Publishers** en el environment `pypi` (required reviewer = PROD GATE del Socio) → **GitHub Release automática** con notas extraídas del CHANGELOG (job `github-release`, AST-23). Cero secretos en el repo. **Fail-closed**: hasta que el Socio registre el Trusted Publisher en PyPI (owner `asturwebs`, repo `BytIA-KODE`, workflow `release.yml`, environment `pypi`), el job publish falla en el intercambio OIDC — eso es por diseño. El proceso completo, paso a paso: `RELEASING.md` (AST-23).
- **Instalación canónica (AST-22)**: `pip install bytia-kode` / `uv tool install bytia-kode` (PyPI). `install.sh` hace bootstrap de uv → instala desde PyPI → configura `~/.bytia-kode/.env`. El clone es SOLO desarrollo.
- **Lanzador**: `~/.local/bin/bytia-kode` — en **esta máquina** sigue siendo el **wrapper bash de la era clone** (143 B, 15-sep): `exec ~/Projects/BytIA-KODE/.venv/bin/bytia-kode`, y ese venv tiene el paquete en **editable** (`direct_url.json` → `"editable": true`), así que `--version` sale con SHA git (`0.8.4+91fb426`) en vez de versión pelada. Es el camino de **desarrollo**, no el canónico: en una instalación de PyPI el lanzador es el console script real (entry `bytia_kode.__main__:main`, AST-22: despacha `--bot`; AST-23: `--version` imprime `versión (+ build id)` y sale 0). Verificado 2026-10-03 — hasta hoy esta doc afirmaba que el wrapper "ya no existe", inexacto para esta máquina. Las skills vendor se re-siembran solas cuando cambia la versión instalada (`importlib.metadata`, AST-23 — antes el sello decía "unknown" en installs de PyPI y el reseed nunca disparaba).
- **Cerebro**: `~/.bytia-kode/` (config, sesiones SQLite, temas, `mcp_servers.json`)

## Sesión 2026-10-25 (S40) — plan de escalation

- **Plan**: `docs/PLAN-escalation-orchestrator-B-KODE.md` (commit `9850bc9`) — orquestación por escalamiento inspirada en GVS5H, adaptada a KODE. Incluye **Anexo C** (revisión adversarial: C1 integridad de tests, C2 privacidad manager cloud, C3 worker agéntico, C4 baseline+checkpoints, C5 F0/F5, C6 conformidad de protocolo), **C7** (orden detección→restore→verify→checkpoint, `WORKER_MAX_ITER=12`) y **C8** (tareas test-targeted no elegibles).
- **Decisiones cerradas**: worker agéntico con tools (opción B, `### CODE` fuera); manager `local` por defecto, cloud solo opt-in; F5 pareado (McNemar/bootstrap) con coste ≤3×; verificación real con tests restaurados desde el SHA base.
- **Seguridad (mismo día)**: `e6843cc` aiohttp 3.14.5 + certifi 2026.10.23 (9 alertas Dependabot resueltas por versión, pendiente re-escaneo de GitHub) + `.github/dependabot.yml`; `3e4a169` el escáner de secretos ya no marca nombres `KODE_*` de configuración (con control negativo en tests).
- **F0 completado (2026-10-25)**: 2 pasadas × 3 tareas = 30 llamadas, **30/30 conformidad** (Wilson 95% inferior **88,6%** → hacen falta **≥35** para certificar ≥90%), peor ciclo **9,72 min**, peor **19.494 tokens**, 6/6 ejecuciones 5/5 tests → **Go provisional**. **79,8% del output son `<think>`** (coste real). VRAM 21,7/24,5 GB (workers secuenciales). Informe: `~/Projects/lab/gvs5h-spike/REPORT.md`. Anexo D: R1-R9 del CTO incorporadas y cuerpo sincronizado. **Gate F1: (a) números F0 ✅, (b) R1-R9 ✅** — abierto a decisión del Socio.
- **Pendiente**: re-escaneo Dependabot · Paperclip **AST-39** (`in_review`, CTO) · decisión F1.

### F1 — escalation core (mergeado en main)

- Rama **`f1-escalation-core`** mergeada en `main` con **`--no-ff`** → merge commit **`4f7990f`** (2026-10-25), **594/594 tests**, CI verde. Tag de retorno **`pre-f1-merge`** en `6937990`.
- Módulos: `src/bytia_kode/orchestrator/{protocol,ledger,specs,prompts,runner}.py` + `EscalationConfig` en `config.py`.
- Revisiones: revisor independiente (1 Critical + 10 Important, corregidos), **Engineer** (`AST-40`: 4 Important + 8 Minor, corregidos) y **CTO APROBADO** (`AST-41`, `f9adb32`, 594/594 en venv virgen, 2026-10-25). **Mergeado en main (`4f7990f`, CI verde)**.
- **NO hay comando `/escalate`** (es F2) y el CLI de la máquina corre el venv editable de `main` → F1 no cambia el runtime actual.
- Secuencia: Engineer → fixes → CTO → tag + merge **hechos**. Siguiente: **F2** (verify real, worktree, Agent async, TUI/Telegram, jail, `patch.diff`) con los requisitos **M1-M4** del CTO (Anexo D). Sin release en PyPI hasta F2.

### F2 — integración real (rama `f2-integration`)

- Rama **`f2-integration`** (worktree `~/Projects/lab/kode-f2`), base `5ea530d`. HEAD **`dde5947`**, **647/647 tests verificados sobre el commit**. **NO en main.**
- T6 scratch git-worktree (R3/R4/R6/R2, fixes H1-H7 + H1 de AST-43) · T7 `verify.py` (baseline, timeout, exit 2/3/4/5 = no-ok) · T8 worker agéntico + **jail save/restore (R5)** · T9 providers + circuit → infra · T10 `/escalate` en TUI y Telegram · T11 `patch.diff` · T12 M1-M4 del CTO · T13 e2e.
- **E2E real ✅ FINAL**: repo con bug (`add` restaba) → **`done` en 1 ronda**, 5.870 tokens, 163,6 s, **patch limpio** (solo `src/calc.py`). Cierre por ground truth (tests verdes + worker solved) tras detectar 4 rondas `budget` con el patch ya correcto.
- Revisiones del Engineer (AST-43): 2 rondas, NO APROBADO → **H1-H4 + R2-1 + R2-M1 cerrados** (`f4fc6a8`, `dde5947`). Pendiente su re-revisión del HEAD.
- **Pendiente final: merge a main = decisión del Socio** (tag `pre-f2-merge` + merge `--no-ff` + CI, igual que F1). Sin release hasta F2 cerrado.

## Arquitectura en 30 segundos

```
src/bytia_kode/
├── tui.py        # BytIAKODEApp (Textual). ActivityIndicator.set_status = choke point de estados
├── agent.py      # loop agéntico
├── providers/    # multi-provider + failover local-first + circuit breaker
├── mcp/          # cliente MCP (Adapter sobre Tool registry)
├── herdr.py      # puente herdr: auto-reporte al panel de agentes del multiplexor
├── session.py    # persistencia SQLite de sesiones
├── skills/       # loader de skills
└── telegram/     # bot (--bot)
```

## Integración herdr (2026-09-15, commit bc24e04)

Si corre en un pane de herdr (`HERDR_PANE_ID`), el TUI se auto-reporta al panel
de agentes del multiplexor (label `bytia-kode`, estados working/idle/blocked).
También ancla el id de sesión activa (`--agent-session-id`, re-ancla en /load
y /new) — herdr 0.8.2 lo acepta pero aún no lo expone (forward-compatible).
Kill-switch: `BYTIA_KODE_HERDR=0`. Detalles y gotcha del parser CLI 0.8.2
(positional antes que opciones): docstring de `src/bytia_kode/herdr.py`.

## Decisiones vivas

- **Cadena auto v3 (2026-09-15 noche, `ae97b37`)**: `unsloth(Studio bandeja) →
  local(ollama) → fallback(z.ai) → deepseek`. El ROUTER (:8080) es **BAJO DEMANDA**:
  fuera del walk de failover — no se auto-despierta nunca; solo pin manual (F3) o
  último recurso si TODO caído. El sondeo lee su catálogo (GET /v1/models no carga
  modelo) para tener el preset listo en la demanda. Evolución: v2 (`27934dc`) puso
  primary primero; el Socio migró a Studio-en-bandeja (autostart + idle-unload 300s)
  y pidió que el router no cargue solo. `active_provider` inicial = 1º de la cadena.
- **Estados → herdr**: `ready→idle`, `thinking/tool/skill→working`. Aún no hay
  prompt de aprobación nativo → `blocked` soportado en el mapa pero sin emisor.
- **CLI de herdr, no socket**: interfaz pública estable > protocolo interno.
- venv con `uv`; tests con pytest; estilo: docstrings/comentarios en español.

## Pendiente (próxima sesión)

- MCP (v0.8.0) — **WIP / experimental, NO feature de la release** (decisión del Socio, 2026-09-27):
  la optional dep **`[mcp]` YA existe** en `pyproject.toml` (`mcp>=1.28.1,<2`),
  y con ella instalada `import bytia_kode.mcp` **cae al stub** en lugar de romper
  (fix de la issue hermana **O0-B / AST-12**, commit `5537803`, cerrada +
  smoke de extras `[mcp]` en CI). Quedan pendientes `mcp/manager.py` lifecycle,
  wiring bootstrap en agent+tui y `McpTool.execute()` (`TODO(human)`).
  La TUI no depende del paquete mcp.
- Dependabot: ✅ **36 vulns cerradas (2026-09-15)** y **9 cerradas por versión (2026-10-25: aiohttp 3.14.5, certifi 2026.10.23)** — verificar el re-escaneo de GitHub (la API aún marcaba `open` con rangos `<3.14.4` / `<2026.10.19`, ya satisfechos). Automatizado desde hoy con `.github/dependabot.yml`.
- **Registro de deuda de dependencias (AST-37, 2026-10-06)** — evaluación formal de
  los mayores abiertos, sin tocar deps; informe completo con fuentes en
  `reports/AST-37-majors-deps-20261006.md`. Recomendaciones: **twine 7.0.0 SUBIR**
  (6.2.0 rompe `twine check` contra Metadata 2.5 — verificado sobre la wheel 0.8.4;
  CI ya usa 7 vía `uvx`), **sentence-transformers 6.1.0 SUBIR** en el mismo re-lock
  (floors ya satisfechos por el lock: transformers 5.17/hub 1.8/torch 2.14; extra
  sin uso hoy — cap 5.x interino por línea sin smoke del extra `memory`),
  **faiss-cpu 1.15.1 SUBIR** (wheels cp310-abi3, sin knock-on),
  **llama-cpp-python 0.3.36 APLAZAR** (sdist-only, compila cada install; renombres
  C API del vendor ggml-org; re-evaluar al abrir la feature de inferencia embebida
  o 2027-01-06). `mcp<2` cap deliberado intacto (motivo en el bloque Dependabot de
  arriba). Ejecución, si procede: issue única de re-lock decidida por el Socio.
- Emisor de estado `blocked` cuando exista flujo de aprobación de tools
- Upstream herdr: que exponga/persista sesiones self-reported (hoy las traga)

## Telegram bot (2026-09-15, servicio activado por el Socio)

- **Servicio**: `bytia-kode-telegram.service` (systemd USER, enabled — arranca al
  boot vía Linger). Activo y polleando (`api.telegram.org` ESTABLISHED, 0 restarts).
- **Invocación correcta**: `.venv/bin/python -m bytia_kode --bot` — el binario del
  venv (`bytia-kode`) apunta a `tui:run_tui` e IGNORA argv (por eso `--help` lanza
  la TUI). Un solo poller: lanzar `--bot` a mano en otra máquina/proceso da 409.
- Token + allowed_users en `~/.bytia-kode/.env` (600). PATH del unit incluye shims
  mise + `~/.local/bin` (tools del agente).

## Gotchas

- **Bump de versión en el clon editable ⇒ `uv sync` obligatorio**: `--version` lee la versión del `dist-info` **instalado**, no del `pyproject.toml` del árbol. Si bumpeas y no re-sincronizas el venv, el gate de claims del README se pone rojo (`--version` imprime la vieja) y bloquea el commit. Pasó al preparar v0.8.5 (2026-10-03). En CI no ocurre porque reinstala el paquete en cada corrida. Si `uv sync` no basta, el síntoma es siempre el mismo: `ls .venv/lib/python3.*/site-packages/bytia_kode-*.dist-info`.
- `git pull` antes de trabajar: otras sesiones de Claude pueden commitear en paralelo (ha pasado).
- El parser del CLI `herdr` 0.8.2 exige `<PANE_ID>` antes que las `--opciones`.
- `scripts/check_secrets.py` escanea el árbol completo en CI: los nombres de config `KODE_*` con valor corto están exentos (`CONFIG_VAR_PATTERN`); un valor de alta entropía sigue marcándose aunque vaya tras un nombre `KODE_`.
