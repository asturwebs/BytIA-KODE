# PLAN-escalation-orchestrator-B-KODE.md

> **Escalation Orchestrator — modo multi-agente con ledger para BytIA KODE**
> Estado: DRAFT v1 · 2026-10-25 · Autor: BytIA (análisis + diseño), a petición de Pedro · Audiencia: PapperClip (revisión e implementación)
> Inspiración: **GVS5H** — https://github.com/slee-persis/GVS5H (código MIT, paper/figuras CC-BY-4.0). NO es un port: es una adaptación al contexto KODE (coding de repos reales vs competitive programming, multi-provider vs same-model, router llama.cpp vs Ollama).
> Clon de referencia: `/tmp/GVS5H` en el VPS (efímero; re-clonar con `git clone --depth 1 https://github.com/slee-persis/GVS5H`). Las referencias `fichero:linea` corresponden a master (push 2026-09-23).

---

## 0. Scope / TL;DR

- Añadir a KODE un **modo de orquestación por escalamiento**, opt-in, para tareas duras: en lugar de un único loop agéntico, un equipo de **instancias frescas** del modelo coordina a través de un **ledger en filesystem** (plan, notas, solución actual, lista de tareas, registro).
- Dos motores, independientes y reutilizables:
  1. **Ladder**: cascada solver↔crítico de modelo pequeño→grande (barato primero, la respuesta sube como "hint a verificar").
  2. **Ledger multiagente**: primary (manager) + workers con protocolo de secciones estrictas y **verificación REAL** (KODE ejecuta pytest/build — ventaja estructural sobre GVS5H, que solo corre sample tests del benchmark).
- Trigger: comando `/escalate` (TUI y Telegram). Auto-trigger por estancamiento como fase posterior, **OFF por defecto**.
- Presupuestos duros (rondas, tareas, tokens, wall-clock) + kill-switch. **El path por defecto del agente queda intocado.**
- Es candidato a feature de v0.9.x — decisión final en ROADMAP tras F5 (evaluación).

## 1. Por qué GVS5H es una base legítima (y sus límites)

Verificado en el código, no solo en el README:
- `codebase/v2-current/escalation/run_bench.py` (579 líneas): driver de benchmark serio — checkpoint JSONL con fsync y lock, clasifica fallos de infra separados de fallos del modelo (`ok/infra/error/truncated/empty_stop`), paralelismo por ThreadPoolExecutor, integración con el runner oficial de LiveCodeBench.
- `multiagent.py` (496 líneas) y `orchestrator.py` (534 líneas): protocolo completo, no vaporware.
- Honestidad inusual: el abstract admite que "gains are not universal: some models are unchanged or worse", y que Opus 5 corrió en un scaffold anterior vía OpenRouter (footnote del README).
- Higiene de licencias ejemplar (MIT código / CC-BY-4.0 paper+runs / NOTICE.md por ruta).

Límites que condicionan el diseño:
- **n=100** problemas → error bars de ±3-4 pts en pass@1. El "supera a Fable 5" (93.0 vs 90.4) es ruido estadístico; la dirección es válida, el titular no es concluyente.
- **Coste**: 5+ pasadas, hasta 128k tokens y 2h de timeout por problema. Inaceptable en un asistente interactivo → de ahí los presupuestos duros de nuestra adaptación.
- **Repo dormido** desde 2026-09-23, 0 issues: es referencia de diseño, no dependencia. Cero código copiado sin revisar; licencia MIT lo permite con atribución (añadir a NOTICE si se copia código literal).
- **No universal**: la ganancia depende del modelo base. Whitelist por modelo y medición en F5.

## 2. Dissección técnica de GVS5H

### 2.1 Ladder de escalado — `orchestrator.py`

- `LADDER` por defecto: `qwen3.5:2b → qwen3.5:9b → qwen3.5:35b → qwen3.5:122b` (orchestrator.py:25, env `ESCALATION_LADDER`).
- `solve_layer()` (linea 474): loop **solver↔crítico** con `MAX_ROUNDS=2`. El crítico responde `APPROVED` en primera línea o `REJECTED` + lista numerada de problemas concretos y reparables. El solver revisa **en el mismo hilo de mensajes** (conserva su cadena de razonamiento).
- Entre capas: la respuesta de la capa inferior sube como `prior_answer` con prompt "Treat it as a hint only: verify it, fix any mistakes, and produce YOUR OWN best solution" — evita anclaje.
- `escalate()` (linea 524): recorre la ladder pequeña→grande enhebrando respuestas hacia arriba.

### 2.2 Ledger multiagente — `multiagent.py` (el corazón)

**Workspace** (ficheros físicos, no contexto): `plan.md`, `notes.md`, `solution.py` (código) o `answer.md` (math), `tasks.json`, y un registro de eventos. Cada instancia fresca lee el estado de ahí; el prompt de cada llamada es corto.

Protocolo por roles:
- `_primary_plan` (linea 170): el PRIMARY produce `### PLAN` (3-6 frases de estrategia) + `### TASKS` (3-6 bullets concretos) → escribe `plan.md` + `tasks.json`.
- `_ideation_worker` (linea 194): el PRIMER worker **no resuelve**: identifica la dificultad central y propone varios enfoques genuinamente DISTINTOS (algoritmos/estructuras/reducciones), en prose, sin código (`### NOTES` + `### NEXT`). Append a `notes.md`.
- `_worker` (linea 290): ejecuta UNA tarea. Salida estricta:
  - `### CODE` — programa COMPLETO autocontenido (reemplaza `solution.py`); si la tarea es cambiar de enfoque, solución FRESCA, no parche del atascado.
  - `### NOTES` — **reescritura COMPLETA** de las notas: reemplaza el fichero, pliega hallazgos nuevos, BORRA lo superado; ~800 palabras; sin headings (el parser corta por ahí).
  - `### NEXT` — siguientes pasos. `### STATUS` — solved|continue.
  - Modo `finalize=True`: "produce the DEFINITIVE final solution now".
- `_run_samples` (linea 368): **ejecuta** la solución contra sample tests; el veredicto viaja al manager como ground truth.
- `_primary_manage` (linea 218): el manager posee la lista de tareas. Entrada: solución actual + notes + tareas + último resultado del worker + propuestas. Salida estricta: `### STATUS` (done|continue), `### NEXT` (UNA tarea exacta), `### TASKS` (lista curada: fusiona duplicados, marca done, pliega propuestas). Reglas anti-thrash explícitas en el system prompt: veredicto de tests = ground truth; fallo → `continue` obligatorio; sin progreso real → CAMBIAR de enfoque, no pulir el atascado. Invariantes en código: no `done` sin respuesta; `continue` sin NEXT → primera tarea pendiente; sin respuesta y sin NEXT → tarea por defecto.
- `_summarize_cutoff` (linea 274): si un worker corta por límite de tokens, una llamada fresca resume el intento parcial (3-5 frases: enfoque, qué estableció, qué falta) para que otro continúe.
- Bucle principal `multiagent_solve` (linea 412): plan → ideation → [worker → samples → manage]* hasta done o presupuesto. `single_solve` (linea 479) = baseline.

### 2.3 Robustez de infraestructura (patrón reutilizable)

`openai_chat` (orchestrator.py:87): timeout duro por hilo, 429 con Retry-After respetado, error de contexto → reduce `max_tokens` automáticamente y reintenta, 4xx no reintentables abortan, respuesta vacía/clampeada → reencamina a otro provider (lista `ignore`), y un flag `infra_exhausted` que **distingue fallo de infra de fallo del modelo** en la contabilidad. Esta separación es oro para KODE (su `ProviderManager` ya registra éxito/fallo por provider — extender con esta semántica).

### 2.4 Anti-objetivos — lo que NO copiar

1. **Same-model only**: GVS5H no mezcla modelos. KODE SÍ puede (manager en primary/deepseek, workers en local) — extensión directa de su `ProviderManager`.
2. **Verificación solo con sample tests del benchmark**: en KODE la verificación real es ejecutar pytest/build del repo objetivo.
3. **Coste sin techo** (128k tokens / 2h por problema): presupuestos duros obligatorios aquí.
4. **Ejecutar workers con bash crudo**: en KODE los workers pasan por el tool registry (jail + whitelist), no por shell sin sandbox.

## 3. Estado actual de KODE relevante (v0.8.6 — HEAD 555660b, 500 tests green, verificado 2026-10-25)

Lo que ya existe y se reutiliza (verificar contra `docs/ARCHITECTURE.md`):
- `src/bytia_kode/agent.py` — clase `Agent`: loop con `_parse_text_tool_calls`, gestión de contexto (`_manage_context`, `_summarize_messages` — precedente directo del patrón cutoff-summary), cancelación (`interrupt()`, `kill()`, `_track_subprocess`) — el kill-switch del orquestador reutiliza esto.
- `src/bytia_kode/providers/manager.py` — `ProviderManager`: slots `primary/fallback/deepseek/local/unsloth`, `pin()`, `auto_detect_model()`, `get_healthy()`, `report_success/report_failure`, `get_status()`. El orquestador pide instancias AQUÍ, no crea clientes propios.
- `src/bytia_kode/providers/circuit.py` — `CircuitBreaker` (3 fallos / 60s): si el local abre el circuito, el orquestador aborta con estado `infra`.
- `src/bytia_kode/tools/registry.py` — jail de workspace (`set_trusted_paths`, `set_workspace_root`, whitelist de binarios, `_check_agent_write_allowed`). El ledger y el worktree del orquestador se registran aquí.
- `src/bytia_kode/providers/client.py` — cliente OpenAI-compatible async (httpx): los workers hablan con el router llama.cpp :8080/v1 igual que hoy (GVS5H usa /api/chat de Ollama — esa parte NO se porta).
- Convenciones: `docs/devlog/` por sesión, doc de plan `docs/PLAN-<tema>-B-KODE.md` (este fichero sigue esa convención), tests pytest, instalación/dev según `docs/DEVELOPMENT.md`.

Lo que NO existe aún: orquestación multi-instancia, ledger persistente, verificación formal de tests como señal de parada, trigger de escalamiento.

## 4. Diseño propuesto

### 4.1 Principios

1. Opt-in explícito. Default path intocado; `KODE_ESCALATION_ENABLED=false` por defecto.
2. El ledger vive bajo el jail del registry (`set_trusted_paths`).
3. Orquestación **heterogénea**: manager = `local` por defecto; workers = `local` (:8080). Cloud solo opt-in explícito y **prohibido en repos de cliente** (C2). Configurable por claves de entorno.
4. Verificación real (pytest/build en un worktree desechable) como ground truth del manager.
5. Presupuestos duros + kill-switch + estados `infra` vs `model_fail`.
6. Instancias frescas por rol (contexto corto + ledger) — sin context bloat; el resumen de corte reutiliza el patrón de `_summarize_messages`.

### 4.2 Módulos nuevos

```
src/bytia_kode/orchestrator/
├── __init__.py
├── ledger.py      # read/write/append atómicos del workspace, record.jsonl
├── specs.py       # specs de dominio (CODE_REPO hoy; extensible)
├── runner.py      # multiagent_solve: plan→ideation→[worker→verify→manage]*
├── prompts.py     # system prompts por rol (plantillas de secciones)
└── verify.py      # pytest/build en worktree, veredicto estructurado
```
Fase 1 puede ser un único `escalation.py`; el paquete es la forma final. Integración mínima en `agent.py` (comando) y `config.py` (claves). TUI/Telegram: comando `/escalate <tarea>`.

### 4.3 Workspace del ledger (y seguridad git)

```
~/.bytia-kode/workspaces/<session_id>/<task_slug>/
├── plan.md · notes.md · tasks.json · record.jsonl
├── scratch/        # worktree git OBLIGATORIO para elegibilidad; cp -r = modo degradado sin verify (R3)
└── patch.diff      # artefacto final: git diff del scratch, aplicable a demanda
```
- Los workers editan SOLO `scratch/` (registrado en trusted paths). El repo real del usuario **nunca** se toca durante la orquestación; `patch.diff` se propone al usuario al final (aplicar/revisar/descartar).
- Teardown obligatorio del worktree (`git worktree remove` + `prune`, también en el camino de error) y declaración de la traza en el `.git` del usuario (R4).
- `record.jsonl`: una línea por llamada (rol, provider, tokens, duración, verdict, status infra|model) — misma semántica de contabilidad que GVS5H.

### 4.4 Flujo (pseudocódigo del runner)

```
tarea = entrada del usuario (texto + repo objetivo)
ws = crear workspace; escribir problem.md
plan   = primary_plan(manager)                    # ### PLAN / ### TASKS
notes  += ideation(worker local, sin código)      # enfoques distintos
for round in 1..MAX_ROUNDS:
    task = elegir_siguiente(tasks)                # del manager o primera pending
    out  = worker(local, task, notes, scratch)    # edita scratch con tools -> ### NOTES/### NEXT/### STATUS
    tamper = detectar_toque_tests(scratch)        # ANTES de restaurar (R2/C7)
    ledger.aplicar(out)                           # notes rewrite + tasks (+ invalid si tamper)
    restaurar_tests(scratch)                      # checkout + git clean -fd acotado + assert status limpio
    verdict = verify.py(scratch)                  # pytest -x / build  (REAL)
    checkpoint(scratch)                           # git add -A + commit (R6)
    status,next,tasks = primary_manage(manager, verdict, ...)   # done|continue
    if status == done or presupuesto agotado: break
artefacto = git -C scratch add -A && git -C scratch diff <base> > patch.diff   # R6
reporte = resumen(record.jsonl) → usuario (aplicar / descartar)
```
Corte limpio en cualquier punto: todo el estado ya está en el ledger; una sesión futura puede retomar (resolviendo el problema de las 50 iteraciones del loop actual).

### 4.5 Specs de dominio (`specs.py`)

- `CODE_REPO`: `solver_system` adaptado a repos (no stdin/stdout): "eres un ingeniero senior trabajando en un checkout en `scratch/`; usa las tools del registry; deja el árbol compilable y testeable" (worker agéntico: edita ficheros, no devuelve `### CODE` — C3/R1).
- `critic`: NO basado en APPROVED/REJECTED de un LLM como primera línea de defensa: `verify.py` ejecuta `pytest -x`/`build` y devuelve veredicto estructurado (pasos, fallos, salida recortada). El crítico LLM queda como segunda opinión opcional (reutilizando el protocolo APPROVED de GVS5H).

### 4.6 Config (config.py + `.env`)

```
KODE_ESCALATION_ENABLED=false        # kill-switch global
KODE_ESCALATION_MANAGER_PROVIDER=local   # default local; cloud solo opt-in (C2)
KODE_ESCALATION_WORKER_PROVIDER=local
KODE_ESCALATION_WORKER_MAX_ITER=12   # techo por worker agéntico (C7)
KODE_ESCALATION_MAX_ROUNDS=4         # rondas worker→verify→manage
KODE_ESCALATION_MAX_TASKS=8
KODE_ESCALATION_MAX_WALLCLOCK_MIN=20
KODE_ESCALATION_MAX_TOKENS=200000    # presupuesto agregado de la tarea
KODE_ESCALATION_AUTO_TRIGGER=false   # fase 3
KODE_ESCALATION_AUTO_AFTER_ITER=6    # iteraciones sin progreso → proponer escalar
```

### 4.7 UX

- TUI y Telegram: `/escalate <tarea>` → progreso por fases (plan → ideación → ronda N: worker T4 → tests OK → manage → …) con tokens/tiempo acumulados. Cancelación reutiliza `interrupt()`/`kill()` del Agent; el estado queda en el ledger.
- Al terminar: reporte + acción sobre `patch.diff` (aplicar/revisar/descartar).

### 4.8 Guardarraíles

- Workers SOLO con tools del registry (jail + whitelist); bash limitado a scratch/.
- CircuitBreaker del provider local: si abre, abortar con estado `infra` (no quemar tokens).
- Sin paralelismo de workers en la 4090 (VRAM compartida con Ollama/embeddings) — secuencia estricta.
- Presupuestos: al agotar cualquiera, corte limpio + reporte (nunca excepción desnuda al usuario).

## 5. Plan de implementación por fases

Cada fase: entrada en `docs/devlog/` según convención (Files Changed / Tests / Commits), commits atómicos convencionales, suite 500+ verde, reinstall según `docs/DEVELOPMENT.md`.

- **F0 — Spike (0.5-1d)**. Re-clonar GVS5H en el OMEN; correr `multiagent_solve` adaptando solo el cliente (Ollama → OpenAI-compatible :8080) sobre 2-3 tareas de juguete con Qwen3.8-27B (alias `qwen38-160k` en el router :8080). Criterio: un ciclo worker→tests→manage completo end-to-end y medición de tokens/tiempo. Go/No-go.
- **F1 — Núcleo ledger (2-3d)**. `ledger.py`, `specs.py`, `prompts.py`, `runner.py` con provider mock; tests unit del parser de secciones (incl. NOTES con headings prohibidos), invariants del manager, corte por presupuesto. Criterio: 100% del protocolo cubierto por tests sin GPU.
- **F2 — Integración KODE (2-3d)**. `verify.py` (pytest/build en scratch), `orchestrator` + `ProviderManager` heterogéneo + CircuitBreaker + trusted paths, comando `/escalate` TUI+Telegram, `patch.diff` con revisión. Criterio: una tarea real de repo resuelta y aplicada desde la TUI; 491+ tests verdes.
- **F3 — Auto-trigger opcional (1-2d)**. Detección de estancamiento (N iteraciones sin delta de tests/ficheros) → PROPUESTA al usuario (pregunta explícita, nunca silencioso). `KODE_ESCALATION_AUTO_TRIGGER=false` por defecto.
- **F4 — Observabilidad y UX fina (1-2d)**. `record.jsonl` → reporte final (tokens, tiempo, rondas, decisiones del manager), progreso en TUI/Telegram, cancelación/reanudación.
- **F5 — Evaluación y decisión (1-2d)**. Mini-bench propio: 10-20 tareas reales con tests (issues del propio KODE u otros repos), single-agent vs escalate, misma GPU/quant, mismos límites. Opcional: subconjunto LCB-hard si la GPU está libre. Go/No-go para promocionar el modo en ROADMAP (v0.9.x).

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| VRAM 4090 compartida (router :8080 + Ollama :11434) | Workers secuenciales; abortar si CircuitBreaker abre; documentar en el reporte |
| Latencia (minutos por tarea) | Presupuestos duros + progreso visible + cancelable/reanudable |
| Ganancia no universal por modelo | Opt-in; whitelist por modelo tras F5; medir siempre single vs escalate |
| Runaway loops | MAX_ROUNDS/MAX_TASKS/wallclock/tokens; kill-switch |
| Coste API del manager | Preferir local/cheap; presupuesto agregado; estado `infra` distinto de `model_fail` |
| Workers fuera del jail | Solo tools del registry; trusted paths a scratch/; bash restringido |
| Notas divergentes/context bloat | Protocolo de reescritura completa con cap (~800 palabras), como GVS5H |
| Integridad del repo del usuario | Todo en scratch/ (worktree); entrega vía patch.diff con revisión humana |

## 7. Métricas de éxito (F5)

- ≥ +15 pts de tasa de resolución en tareas duras sin regresión en tareas fáciles (fáciles no escalan por diseño).
- Coste (tokens) y tiempo por tarea documentados en `record.jsonl`; comparativa single vs escalate.
- 0 crashes de TUI; cancelación y reanudación funcionales.
- Decisión ROADMAP data-driven, no por entusiasmo.

## 8. Extensiones futuras

- Ladder como primer nivel (barato→caro) ANTES del multiagente.
- 2 workers en paralelo con segunda instancia de router (si VRAM lo permite).
- Integración con memoria (`herdr.py`) para reutilizar notes entre sesiones de la misma tarea.
- Reproducir el subset LCB-hard para comparar con los números públicos de GVS5H.

## 9. Referencias

- GVS5H: https://github.com/slee-persis/GVS5H · clon VPS: /tmp/GVS5H (re-clonar si no existe)
  - Ladder: `codebase/v2-current/escalation/orchestrator.py` (LADDER:25, solve_layer:474, escalate:524)
  - Ledger: `codebase/v2-current/escalation/multiagent.py` (_primary_plan:170, _ideation_worker:194, _primary_manage:218, _summarize_cutoff:274, _worker:290, _run_samples:368, multiagent_solve:412)
  - Infra: `orchestrator.py:87` (openai_chat), `run_bench.py` (checkpoint/clasificación)
- KODE: `/home/asturwebs/Projects/BytIA-KODE` — `agent.py` (`_manage_context`, `interrupt`), `providers/manager.py` (`ProviderManager`), `providers/circuit.py`, `tools/registry.py` (jail), `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`

## Anexo A — Mapping GVS5H → KODE

| GVS5H | KODE propuesto |
|---|---|
| ollama_chat / openai_chat | providers/client.py vía ProviderManager.get("local"/"primary") |
| LADDER (2b→122b) | (extensión futura) ladder antes del multiagente |
| solution.py / answer.md | scratch/ (worktree) + patch.diff |
| _run_samples (benchmark) | verify.py (pytest/build real) |
| primary mismo modelo | manager en provider primary/deepseek, workers en local (heterogéneo) |
| record/meta de openai_chat | record.jsonl con estados infra vs model_fail |
| checkpoint JSONL del bench | reanudación desde ledger (plan/notes/tasks/record) |

## Anexo B — Comandos útiles

```bash
# re-clonar referencia
git clone --depth 1 https://github.com/slee-persis/GVS5H /tmp/GVS5H
# spike F0 (OMEN): adaptar ollama_chat → OpenAI-compatible :8080 y correr 1 tarea
# (el runner de GVS5H es síncrono; para el spike basta urllib contra http://localhost:8080/v1/chat/completions)
```

---
## Anexo C — Revisión adversarial (BytIA · Claude Code, 2026-10-25)

> Revisión pedida por el Socio antes de entregar el plan a Paperclip. Método: verificación empírica, no lectura. Clon upstream de GVS5H comprobado línea a línea contra `slee-persis/GVS5H@707e212` (2026-09-23); estado de KODE verificado contra el código; suite ejecutada. **Este anexo prevalece sobre el cuerpo donde haya conflicto.**

### Verificado y correcto
- 12/12 referencias `fichero:línea` de §9 exactas: `LADDER:25`, `openai_chat:87`, `solve_layer:474`, `escalate:524`, `_primary_plan:170`, `_ideation_worker:194`, `_primary_manage:218`, `_summarize_cutoff:274`, `_worker:290`, `_run_samples:368`, `multiagent_solve:412`, `single_solve:479`. Tamaños 496/534/579 exactos. MIT + CC-BY-4.0 + NOTICE.md presentes. 0 issues.
- Estado de KODE: HEAD `555660b`, v0.8.6. Todos los símbolos citados existen con esos nombres (`manager.py:36-56`, `circuit.py:12`, `registry.py:58/74/331`, `agent.py:493/555/601/1106/1135`).
- Suite actual: **500 passed en 49,35 s** (medido 2026-10-25). El "491" del cuerpo era un dato desfasado — corregido arriba.
- El README de GVS5H confirma que el modelo del titular es **Qwen3.8-27B** y que el caso local sube **66,8% → 92,4%** en LCB-100. El router del OMEN sirve exactamente ese modelo (`Qwen3.8-27B-UD-IQ4_XS.gguf`, alias `qwen38-160k`). F0 no es un experimento a ciegas: reproduce el caso medido por el paper (el quant puede variar los números).

### C1 — BLOQUEANTE: el worker puede falsear la verificación tocando los tests
En GVS5H los sample tests viven FUERA del workspace del worker (los inyecta el harness). En KODE, `verify.py` correría los tests del repo DENTRO del scratch que el worker controla con tools de escritura → el worker puede editar `tests/`, `conftest.py`, `pytest.ini` o `[tool.pytest]` y producir un verde falso. La "ventaja estructural" de §0 se evapora.
**Mitigación obligatoria (F2):** antes de cada `verify`, restaurar desde el SHA base los ficheros de test y config de test:
`git -C scratch checkout <SHA-base> -- tests conftest.py pytest.ini tox.ini pyproject.toml setup.cfg`
Y marcar la ronda como `invalid` (registrada en `record.jsonl`) si el diff del worker toca esas rutas.

### C2 — BLOQUEANTE de privacidad: manager cloud por defecto
`KODE_ESCALATION_MANAGER_PROVIDER=primary` y `PROVIDER_*` es un endpoint cloud con API key. El manager recibe plan, notas, solución y fragmentos del repo. Con repos de clientes eso es código propietario saliendo a un tercero por defecto, sin aviso. Contradice el valor 3 del Kernel y la regla local-first.
**Decisión cerrada:** default `local`. El modo cloud exige (a) opt-in explícito, (b) aviso visible de que el contenido del repo se envía al proveedor, (c) bloqueo en workspaces marcados como cliente. **Decisión del Socio (2026-10-25): NO.** El modo cloud queda prohibido en repos de cliente; solo `local`/`unsloth`.

### C3 — BLOQUEANTE de diseño: worker textual vs. worker agéntico
§2.2/§4.4 portan el protocolo de GVS5H (`### CODE` = programa completo autocontenido); §4.8 dice que los workers usan tools del registry sobre scratch. En repos reales no existe "el programa completo". Sin decidirlo, F1 no se puede escribir.
**Decisión cerrada — opción B (agéntica):** el worker edita `scratch/` con las tools del registry y devuelve solo `### NOTES / ### NEXT / ### STATUS`. `### CODE` desaparece del protocolo; el artefacto es el árbol de trabajo + `patch.diff`. Consecuencias: (i) `patch.diff` se calcula contra el SHA base (`git -C scratch diff <base>`, incluye commits y working tree); (ii) el parser se reduce a tres secciones; (iii) el worker es una instancia `Agent` de KODE, no una llamada de chat suelta.

### C4 — BLOQUEANTE: baseline de tests y atomicidad del scratch
(a) `pytest -x` como ground truth exige baseline: si la suite del repo ya estaba roja o no hay suite, el manager verá fallo perpetuo. **Mitigación:** capturar al inicio la lista de tests que ya fallan y comparar contra ella; si no hay suite ni build detectable, la tarea NO es elegible para escalar. Añadir `KODE_ESCALATION_VERIFY_CMD` con timeout y subset (tests del área tocada, no la suite entera cada ronda).
(b) "Corte limpio en cualquier punto" es falso a nivel de scratch: un kill a mitad de edición multi-fichero deja el árbol incoherente (GVS5H no lo sufre: reescribe `solution.py` atómicamente). **Mitigación:** `git -C scratch commit -m "checkpoint ronda N"` tras cada ronda verificada + SHA base y último checkpoint en el ledger. Reanudar = `git reset --hard <checkpoint>`.

### C5 — F5 mal diseñada estadísticamente; F0 sin criterio
- F0 se llama Go/No-go pero su criterio es "que funcione un ciclo" (smoke test). **Añadir:** conformidad de protocolo ≥90% sobre ≥30 llamadas, ciclo completo <15 min, tokens/tarea <30k (calibrar en el propio F0).
- F5: n=10-20 con objetivo +15 pts contradice §1 (efecto observado +2.6 ±3-4). Con medias brutas es indetectable. **Mitigación:** diseño PAREADO (misma tarea/repo/GPU/semilla en single y escalate), análisis McNemar o bootstrap de diferencias, y umbral doble: (i) efecto distinguible de 0, (ii) coste ≤ factor 3 en tokens y tiempo. Sustituir el +15 por ese criterio. Pre-registrar las tareas antes de correr.

### C6 — Heterogeneidad = riesgo de parser, no solo de rendimiento
El protocolo de secciones funciona en GVS5H porque manager y workers son el MISMO modelo. Un 27B local por llama.cpp romperá el formato con más frecuencia. **Mitigación:** medir tasa de conformidad por modelo en F0, parser tolerante con fallback y lista blanca de modelos elegibles (si no supera el umbral, no se usa).

### Erratas corregidas en el cuerpo
- "Qwen3.5-27B" (×2) → Qwen3.8-27B (alias `qwen38-160k` en el router :8080). El modelo que nombraba no existe en esta máquina.
- "491 tests green" / "suite 491+ verde" → 500 (verificado 2026-10-25: 500 passed, 49,35 s).
- `docs/devlog/2026-10-25.md`: "Suite intacta: 491 passed" era una afirmación no ejecutada en esa sesión (solo documentación) → anotada con la medición real.

### C7 — Refinamientos operativos de C1 y C3 (BytIA · OpenClaw, 2026-10-25)

- **Orden de operaciones en C1** (sin este orden, la mitigación se autoanula): (1) `git -C scratch diff` contra el checkpoint/base ANTES de restaurar nada → si el diff toca rutas de test/config de tests, marcar la ronda `invalid` y registrarla en `record.jsonl`; (2) restaurar tests/config desde el SHA base; (3) `verify.py`; (4) checkpoint commit del estado ya saneado. Detectar el toque de tests DESPUÉS de restaurar pierde la evidencia.
- **Techo por worker (consecuencia de la opción B de C3):** un worker agéntico es una instancia `Agent` completa, no una llamada suelta — su bucle puede quemar la economía entera de la tarea en una sola ronda. Añadir `KODE_ESCALATION_WORKER_MAX_ITER` (propuesto: 12, muy por debajo del techo del loop normal) y contabilizar sus tokens dentro del presupuesto agregado de §4.6.

### C8 — Limitación declarada: tareas cuyo objetivo son los tests (BytIA · OpenClaw, 2026-10-25)

- La regla de C1 («diff que toca tests → invalid») excluye de `/escalate` las tareas cuyo objetivo legítimo ES modificar tests (refactor de suite, subida de cobertura, migración de framework). Limitación aceptada y declarada — mejor aquí que descubrirla en producción.
- Mitigación barata en F2: el runner detecta pronto la no-elegibilidad — si el PLAN del manager o la tarea `NEXT` apuntan a modificar `tests/`, abortar con estado `ineligible: test-targeted` antes de gastar la primera ronda.
- Escape hatch futuro (fuera de F1): `KODE_ESCALATION_ALLOW_TEST_EDITS=true` + whitelist explícita de rutas; con ella el diff de tests se permite, pero los ficheros siguen snapshot-ándose para reversión limpia.

## Anexo D — Correcciones del CTO (R1-R9) y cierre del gate F1

> Revisión del CTO de Paperclip (documento `4ce1bcdf`, aceptado por el Socio 2026-10-25). Veredicto: **APROBADO CONDICIONADO** — C1-C8 correctas en sustancia; F1 cerrado hasta (a) números de F0 y (b) R1-R9 al doc. Este anexo incorpora R1-R9 y registra los números de F0; **prevalece sobre el Anexo C donde haya conflicto**.

### R1 — Cuerpo sincronizado con la opción B
§4.1.3 (manager `local` por defecto), §4.4 (sin `### CODE`; el worker edita scratch con tools y devuelve `### NOTES/### NEXT/### STATUS`) y §4.5 (spec en términos de tools + patch) corregidos en este mismo commit.

### R2 — C1: el restore debe dejar «status limpio»
`git checkout <base> -- <rutas>` **no elimina tests NUEVOS**. Invariant obligatorio:
1. Detectar el toque (diff contra checkpoint/base) y registrar `invalid`.
2. `git checkout <SHA-base> -- <rutas>` + `git clean -fd -- <rutas>`.
3. Assert `git status --porcelain -- <rutas>` vacío.
4. Enumeración de rutas de test desde el índice git con **un predicado único** compartido por detección y restore (raíz y `src/tests/`, conftests anidados).
5. `pyproject.toml` se restaura solo en sus secciones de test (`[tool.pytest…]`); revertir el fichero entero se declara como collateral de dep-bumps.

### R3 — Elegibilidad = scratch git-worktree
`cp -r` produce un scratch sin git: desactiva C1 (restore), C4b (checkpoints) y `patch.diff`. `cp -r` queda como modo degradado **sin verify**. Sin worktree no hay `/escalate`.

### R4 — Teardown y traza en el `.git` del usuario
`git worktree add` escribe metadatos en el `.git` del repo del usuario. Obligatorio `git worktree remove` + `git worktree prune` en el cierre (incluido el camino de error) y declararlo en el reporte.

### R5 — Jail del worker: save/restore alrededor de cada worker
El jail del registry es estado global de módulo (`registry.py:58-100`: `_TRUSTED_PATHS` aditivo sin reversión; `_WORKSPACE_ROOT`/`_workspace_mode` single-slot). Un worker `Agent` anidado pisaría la jail de la sesión del usuario. Los workers son secuenciales ⇒ **save/restore explícito** de las tres variables alrededor de cada worker (race-free). Jail del worker = root `scratch/` + modo `confined` + trusted ∅ (no heredar `~/.bytia-kode`, trusted por defecto y con las SQLite de sesión).

### R6 — `git add -A` antes de checkpoint y de `patch.diff`
`git diff <base>` no incluye ficheros nuevos sin `git add`. Sin esto, verify ve el fichero nuevo pero el entregable lo pierde. Regla: `git add -A` → checkpoint → `git diff <base>`.

### R7 — Semántica de ronda inválida
Una ronda `invalid` conserva el árbol ya saneado (tests restaurados) y se registra en `record.jsonl`; **cuenta contra `MAX_ROUNDS`**. Techo propio: 2 consecutivas ⇒ abort con estado `protocol: test-tamper`. Calibrar `MAX_ROUNDS`, `MAX_WALLCLOCK_MIN` y `WORKER_MAX_ITER` juntos con los minutos/iteración de F0.

### R8 — C2 con enforcement real
Marcador de workspace de cliente (agent-write-denied, como T4) + **error duro** si `MANAGER_PROVIDER ∉ {local, unsloth}` en un repo marcado como cliente. No un aviso.

### R9 — F0: qué prueba y qué no
F0 mide el protocolo **textual de 4 secciones de GVS5H** (con `### CODE`), no el agéntico de 3 secciones de F1. Es un **proxy del modelo** (router/latencia/tokens/conformidad textual), **no transferible** como conformidad del worker de F2. **Re-baseline de conformidad en F2** (1 tarea real) antes de F5. n≥30 llamadas asegurado (contar sobre la marcha; añadir tarea si quedan <30) y el informe debe desglosar por tipo de sección qué rompe.

### Números de F0 (cierre de la condición (a))

Run del 2026-10-25 sobre `qwen38-160k` (Qwen3.8-27B IQ4_XS, ctx 163840), 3 tareas de juguete, protocolo textual de GVS5H:

| Tarea | Tests | Llamadas | Tokens | Minutos | Protocolo |
|---|---|---|---|---|---|
| fizzbuzz | 5/5 | 5 | 9.337 | 3,30 | 5/5 |
| two_sum | 5/5 | 5 | 12.496 | 5,35 | 5/5 |
| csv_to_dicts | 5/5 | 5 | 16.505 | 8,20 | 5/5 |

Criterios C5: conformidad **100%** (≥90% ✅) · peor ciclo **8,20 min** (<15 ✅) · peor tokens **16.505** (<30k ✅). VRAM con el modelo cargado: **21,7/24,5 GB** → workers secuenciales confirmados.
**Go en los tres criterios**, con la salvedad de R9 (proxy del modelo, no del protocolo final).

### Gate F1 — estado
- (a) Números de F0 contra C5: **✅** (tabla arriba).
- (b) R1-R9 incorporados al doc: **✅** (este anexo + cuerpo sincronizado).
F1 queda **abierto** a decisión del Socio.

---

*Fin del plan. Dudas de diseño → preguntar a Pedro/BytIA antes de improvisar sobre GVS5H: lo que está en este doc ya fue filtrado por sus límites (ver §1 y §2.4).*
